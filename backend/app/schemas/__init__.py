"""
Pydantic schemas for the BI Agent application.
"""

from app.schemas.common import (
    ErrorResponse,
    SuccessResponse,
    PaginatedResponse,
    PaginationMeta,
)
from app.schemas.auth import (
    LoginRequest,
    SignupRequest,
    TokenResponse,
    RefreshTokenRequest,
)
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.organization import (
    OrgCreate,
    OrgResponse,
    OrgUpdate,
    MemberResponse,
    InviteMemberRequest,
    UpdateMemberRoleRequest,
)
from app.schemas.data_source import (
    DataSourceCreate,
    DataSourceResponse,
    DataSourceTestResult,
    PostgresConnectionConfig,
)
from app.schemas.dataset import (
    DatasetResponse,
    DatasetSchema,
    DatasetUpdate,
    ColumnInfoSchema,
)
from app.schemas.conversation import (
    ConversationCreate,
    ConversationResponse,
    MessageCreate,
    MessageResponse,
    AnalysisRequest,
)
from app.schemas.query import QueryExecutionResponse
from app.schemas.chart import ChartSpec, ChartType
from app.schemas.report import (
    ReportCreate,
    ReportUpdate,
    ReportResponse,
    ReportVersionResponse,
    SavedAnalysisCreate,
    SavedAnalysisResponse,
)
from app.schemas.anomaly import (
    AnomalyScanRequest,
    AnomalyResponse,
    AnomalyStatusUpdate,
)
from app.schemas.scheduled_job import (
    ScheduledJobCreate,
    ScheduledJobUpdate,
    ScheduledJobResponse,
    JobRunResponse,
)
from app.schemas.audit import AuditEventResponse, NotificationResponse

__all__ = [
    "ErrorResponse",
    "SuccessResponse",
    "PaginatedResponse",
    "PaginationMeta",
    "LoginRequest",
    "SignupRequest",
    "TokenResponse",
    "RefreshTokenRequest",
    "UserResponse",
    "UserUpdate",
    "OrgCreate",
    "OrgResponse",
    "OrgUpdate",
    "MemberResponse",
    "InviteMemberRequest",
    "UpdateMemberRoleRequest",
    "DataSourceCreate",
    "DataSourceResponse",
    "DataSourceTestResult",
    "PostgresConnectionConfig",
    "DatasetResponse",
    "DatasetSchema",
    "DatasetUpdate",
    "ColumnInfoSchema",
    "ConversationCreate",
    "ConversationResponse",
    "MessageCreate",
    "MessageResponse",
    "AnalysisRequest",
    "QueryExecutionResponse",
    "ChartSpec",
    "ChartType",
    "ReportCreate",
    "ReportUpdate",
    "ReportResponse",
    "ReportVersionResponse",
    "SavedAnalysisCreate",
    "SavedAnalysisResponse",
    "AnomalyScanRequest",
    "AnomalyResponse",
    "AnomalyStatusUpdate",
    "ScheduledJobCreate",
    "ScheduledJobUpdate",
    "ScheduledJobResponse",
    "JobRunResponse",
    "AuditEventResponse",
    "NotificationResponse",
]
