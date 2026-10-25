"""
AI Agent Orchestration Engine.
Coordinates planning, schema discovery, tool execution, SQL safety checks, query execution,
chart specification generation, and conversation state persistence.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
import structlog

from app.ai.prompts import SYSTEM_PROMPT
from app.ai.provider import LLMProvider
from app.ai.tools import get_agent_tools
from app.models.conversation import Conversation, Message, MessageRole
from app.models.dataset import Dataset
from app.models.query import QueryExecution
from app.schemas.chart import ChartSpec
from app.services.anomaly_service import AnomalyService
from app.services.audit_service import AuditService
from app.services.chart_service import ChartService
from app.services.query_executor import QueryExecutor
from app.services.sql_validator import SQLValidator

logger = structlog.get_logger(__name__)


class AIOrchestrator:
    @staticmethod
    async def analyze(
        db: AsyncSession,
        org_id: uuid.UUID,
        user_id: uuid.UUID,
        question: str,
        conversation_id: Optional[uuid.UUID] = None,
        dataset_ids: Optional[List[uuid.UUID]] = None,
    ) -> Dict[str, Any]:
        """
        Execute full orchestrated AI analysis cycle with tool calling, deterministic validation,
        and traceable audit history.
        """
        # 1. Fetch or create Conversation
        conversation = None
        if conversation_id:
            stmt = select(Conversation).where(
                Conversation.id == conversation_id, Conversation.org_id == org_id
            )
            res = await db.execute(stmt)
            conversation = res.scalar_one_or_none()

        if not conversation:
            conversation = Conversation(
                org_id=org_id,
                user_id=user_id,
                title=question[:80] + ("..." if len(question) > 80 else ""),
            )
            db.add(conversation)
            await db.flush()

        # 2. Save User Message
        user_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.USER,
            content=question,
            metadata_={},
        )
        db.add(user_msg)
        await db.flush()

        # 3. Retrieve permitted datasets
        dataset_query = select(Dataset).where(Dataset.org_id == org_id)
        if dataset_ids:
            dataset_query = dataset_query.where(Dataset.id.in_(dataset_ids))
        res = await db.execute(dataset_query)
        available_datasets = list(res.scalars().all())

        # Build schema context for system prompt
        schema_context = []
        for d in available_datasets:
            schema_context.append({
                "dataset_id": str(d.id),
                "name": d.name,
                "table_name": d.table_name,
                "row_count": d.row_count,
                "columns": d.schema_metadata.get("columns", []) if d.schema_metadata else [],
            })

        system_message = {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}\n\nAvailable Datasets:\n{json.dumps(schema_context, indent=2)}",
        }

        # Retrieve recent conversation messages (up to 6)
        stmt_msgs = (
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.asc())
            .limit(6)
        )
        history_msgs = (await db.execute(stmt_msgs)).scalars().all()

        messages_payload: List[Dict[str, Any]] = [system_message]
        for m in history_msgs:
            messages_payload.append({
                "role": m.role.value,
                "content": m.content,
            })

        provider = LLMProvider()
        tools = get_agent_tools()

        executed_queries: List[Dict[str, Any]] = []
        chart_spec: Optional[ChartSpec] = None
        assistant_content = ""

        # Tool execution loop (max 5 iterations for security and latency)
        for iteration in range(5):
            llm_response = await provider.chat_completion(
                messages=messages_payload,
                tools=tools,
            )

            if not llm_response.tool_calls:
                assistant_content = llm_response.content or "Analysis completed."
                break

            # Handle each tool call
            for tc in llm_response.tool_calls:
                func_name = tc.name
                args = tc.arguments
                result_str = ""

                if func_name == "list_available_datasets":
                    result_str = json.dumps([
                        {"id": str(d.id), "name": d.name, "table": d.table_name, "rows": d.row_count}
                        for d in available_datasets
                    ])

                elif func_name == "inspect_dataset_schema":
                    ds_id_str = args.get("dataset_id")
                    target = next((d for d in available_datasets if str(d.id) == ds_id_str), None)
                    if target:
                        result_str = json.dumps({
                            "dataset_id": str(target.id),
                            "table_name": target.table_name,
                            "columns": target.schema_metadata,
                            "sample_data": target.sample_data[:5] if target.sample_data else [],
                        })
                    else:
                        result_str = json.dumps({"error": "Dataset not found"})

                elif func_name == "validate_query":
                    sql = args.get("sql_query", "")
                    ds_id_str = args.get("dataset_id")
                    target = next((d for d in available_datasets if str(d.id) == ds_id_str), None)
                    dialect = "sqlite"  # default
                    allowed = {target.table_name.lower()} if target else set()
                    val = SQLValidator(allowed_tables=allowed, dialect=dialect).validate(sql)
                    result_str = json.dumps({
                        "is_valid": val.is_valid,
                        "errors": val.errors,
                        "tables_referenced": val.tables_referenced,
                    })

                elif func_name == "execute_read_only_query":
                    sql = args.get("sql_query", "")
                    ds_id_str = args.get("dataset_id")
                    try:
                        ds_id = uuid.UUID(ds_id_str)
                        exec_record, query_res = await QueryExecutor.execute_query(
                            db=db,
                            org_id=org_id,
                            user_id=user_id,
                            dataset_id=ds_id,
                            sql_query=sql,
                            message_id=user_msg.id,
                        )
                        if query_res and query_res.rows:
                            executed_queries.append({
                                "id": str(exec_record.id),
                                "sql": sql,
                                "row_count": query_res.row_count,
                                "duration_ms": query_res.execution_time_ms,
                            })
                            # Automatically recommend chart from actual query result
                            chart_spec = ChartService.recommend_chart(
                                data=query_res.rows,
                                columns=query_res.columns,
                                title_hint=question[:50],
                            )
                            result_str = json.dumps({
                                "columns": query_res.columns,
                                "row_count": query_res.row_count,
                                "data": query_res.rows[:50],
                                "execution_time_ms": query_res.execution_time_ms,
                            })
                        else:
                            result_str = json.dumps({
                                "error": exec_record.error_message or "Query returned 0 rows",
                                "validation_status": exec_record.validation_status.value,
                            })
                    except Exception as e:
                        result_str = json.dumps({"error": f"Execution failed: {str(e)}"})

                elif func_name == "run_anomaly_detection":
                    ds_id_str = args.get("dataset_id")
                    metric = args.get("metric_column")
                    try:
                        ds_id = uuid.UUID(ds_id_str)
                        anoms = await AnomalyService.run_detection(
                            db=db,
                            org_id=org_id,
                            dataset_id=ds_id,
                            metric_column=metric,
                            method=args.get("method", "z_score"),
                        )
                        result_str = json.dumps([
                            {"metric": a.metric_name, "value": a.metric_value, "severity": a.severity.value, "explanation": a.explanation}
                            for a in anoms
                        ])
                    except Exception as e:
                        result_str = json.dumps({"error": str(e)})

                else:
                    result_str = json.dumps({"error": f"Unknown tool: {func_name}"})

                # Append assistant tool call and tool result to messages payload
                messages_payload.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": tc.id, "type": "function", "function": {"name": func_name, "arguments": json.dumps(args)}}],
                })
                messages_payload.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": func_name,
                    "content": result_str,
                })

        # Save Assistant Message
        assistant_msg = Message(
            conversation_id=conversation.id,
            role=MessageRole.ASSISTANT,
            content=assistant_content or "Analysis completed based on the retrieved query data.",
            metadata_={
                "queries": executed_queries,
                "chart": chart_spec.model_dump() if chart_spec else None,
                "sources": [d.name for d in available_datasets],
            },
        )
        db.add(assistant_msg)
        await db.commit()
        await db.refresh(assistant_msg)

        return {
            "conversation_id": str(conversation.id),
            "message_id": str(assistant_msg.id),
            "answer": assistant_msg.content,
            "chart": chart_spec.model_dump() if chart_spec else None,
            "queries": executed_queries,
            "sources": [d.name for d in available_datasets],
        }
