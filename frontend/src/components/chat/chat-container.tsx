"use client";

import React, { useState, useEffect, useRef } from "react";
import { Send, Bot, User, Loader2, Sparkles, Database } from "lucide-react";
import { ApiClient } from "../../lib/api";
import { Dataset, Message } from "../../lib/types";
import { Button } from "../ui/button";
import { ChartRenderer } from "../charts/chart-renderer";
import { QueryDetail } from "./query-detail";

export function ChatContainer({
  conversationId,
  onConversationCreated,
}: {
  conversationId?: string;
  onConversationCreated?: (id: string) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ApiClient.getDatasets().then((ds) => {
      setDatasets(ds);
      if (ds.length > 0) setSelectedDatasetId(ds[0].id);
    });
  }, []);

  useEffect(() => {
    if (conversationId) {
      ApiClient.getConversation(conversationId).then((res) => {
        setMessages(res.messages || []);
      });
    } else {
      setMessages([
        {
          id: "welcome",
          role: "assistant",
          content:
            "Hello! I am your AI Business Intelligence Agent. Ask me questions about your revenue, customer trends, product performance, or transactions. All answers are computed from verified SQL queries without hallucinations.",
          created_at: new Date().toISOString(),
        },
      ]);
    }
  }, [conversationId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;

    const userText = input.trim();
    setInput("");

    // Add user message to UI immediately
    const tempUserMsg: Message = {
      id: Math.random().toString(),
      role: "user",
      content: userText,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setIsLoading(true);

    try {
      const res = await ApiClient.askQuestion(
        userText,
        selectedDatasetId ? [selectedDatasetId] : undefined,
        conversationId
      );

      if (!conversationId && onConversationCreated) {
        onConversationCreated(res.conversation_id);
      }

      const assistantMsg: Message = {
        id: res.message_id,
        role: "assistant",
        content: res.answer,
        metadata: {
          queries: res.queries,
          chart: res.chart,
          sources: res.sources,
        },
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: Message = {
        id: Math.random().toString(),
        role: "assistant",
        content: `Error executing analysis: ${err.message}`,
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-10rem)] bg-white rounded-xl border border-gray-200 shadow-sm overflow-hidden">
      {/* Context Bar */}
      <div className="px-6 py-3 bg-gray-50 border-b border-gray-200 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2 text-gray-700">
          <Database className="w-4 h-4 text-indigo-600" />
          <span className="font-medium">Active Dataset Context:</span>
          <select
            value={selectedDatasetId}
            onChange={(e) => setSelectedDatasetId(e.target.value)}
            className="bg-white border border-gray-300 rounded px-2 py-1 text-xs focus:ring-1 focus:ring-indigo-500"
          >
            <option value="">All Permitted Datasets</option>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.row_count || 0} rows)
              </option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-1.5 text-indigo-600 font-medium">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Zero-Hallucination SQL Guard Active</span>
        </div>
      </div>

      {/* Message List */}
      <div className="flex-1 overflow-y-auto p-6 space-y-6">
        {messages.map((m) => {
          const isUser = m.role === "user";
          return (
            <div
              key={m.id}
              className={`flex gap-3 max-w-3xl ${isUser ? "ml-auto flex-row-reverse" : "mr-auto"}`}
            >
              <div
                className={`w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-xs font-bold ${
                  isUser
                    ? "bg-indigo-600 text-white"
                    : "bg-gray-900 text-white shadow-sm"
                }`}
              >
                {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
              </div>

              <div className="space-y-2 max-w-2xl">
                <div
                  className={`p-4 rounded-xl text-sm leading-relaxed ${
                    isUser
                      ? "bg-indigo-600 text-white"
                      : "bg-gray-100 text-gray-900 border border-gray-200/60"
                  }`}
                >
                  <p className="whitespace-pre-wrap">{m.content}</p>
                </div>

                {/* Inline chart rendering if present */}
                {m.metadata?.chart && <ChartRenderer spec={m.metadata.chart} />}

                {/* SQL execution details panel */}
                {m.metadata?.queries &&
                  m.metadata.queries.map((q) => <QueryDetail key={q.id} query={q} />)}
              </div>
            </div>
          );
        })}

        {isLoading && (
          <div className="flex gap-3 max-w-md mr-auto items-center">
            <div className="w-8 h-8 rounded-full bg-gray-900 text-white flex items-center justify-center">
              <Bot className="w-4 h-4" />
            </div>
            <div className="flex items-center gap-2 p-3 bg-gray-50 border rounded-xl text-xs text-gray-500">
              <Loader2 className="w-4 h-4 animate-spin text-indigo-600" />
              <span>Inspecting schema, validating SQL, and querying data...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Box */}
      <form onSubmit={handleSend} className="p-4 border-t border-gray-200 bg-white flex gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question (e.g. 'What were total sales this month compared to last month?')"
          disabled={isLoading}
          className="flex-1 px-4 py-2.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm"
        />
        <Button type="submit" disabled={isLoading || !input.trim()} className="gap-2">
          <span>Send</span>
          <Send className="w-4 h-4" />
        </Button>
      </form>
    </div>
  );
}
