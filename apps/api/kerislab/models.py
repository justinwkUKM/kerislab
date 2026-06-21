from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def now_utc() -> datetime:
    return datetime.now(UTC)


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    SECURITY_LEAD = "security_lead"
    PENTESTER = "pentester"
    DEVELOPER = "developer"
    AUDITOR = "auditor"


class AuthProvider(StrEnum):
    GOOGLE = "google"
    SSO = "sso"
    DEVELOPMENT = "development"


class ScanType(StrEnum):
    PASSIVE_BLACKBOX = "passive_blackbox"
    ACTIVE_BLACKBOX = "active_blackbox"
    AUTONOMOUS_BLACKBOX = "autonomous_blackbox"
    WHITEBOX = "whitebox"
    HYBRID = "hybrid"


class ScanStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    BLOCKED = "blocked"


class CreditReservationStatus(StrEnum):
    RESERVED = "reserved"
    DEDUCTED = "deducted"
    RELEASED = "released"


class LedgerEntryType(StrEnum):
    GRANT = "grant"
    RESERVE = "reserve"
    DEDUCT = "deduct"
    RELEASE = "release"
    ADJUSTMENT = "adjustment"
    REFUND = "refund"


class FindingStatus(StrEnum):
    NEW = "new"
    TRIAGED = "triaged"
    VERIFIED = "verified"
    FALSE_POSITIVE = "false_positive"
    ACCEPTED_RISK = "accepted_risk"
    FIXED = "fixed"
    RETEST_REQUIRED = "retest_required"


class VerificationStatus(StrEnum):
    UNVERIFIED = "unverified"
    SUSPECTED = "suspected"
    VERIFIED = "verified"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    AUTO_DENIED = "auto_denied"


@dataclass
class ModelProfile:
    workspace_id: str
    name: str
    model: str
    api_base: str
    timeout_seconds: int = 60
    id: str = field(default_factory=lambda: new_id("llm"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class User:
    email: str
    display_name: str
    provider: AuthProvider
    avatar_url: str | None = None
    id: str = field(default_factory=lambda: new_id("usr"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class UserSettings:
    user_id: str
    default_workspace_id: str | None = None
    theme: str = "light"
    timezone: str = "UTC"
    notifications_enabled: bool = True


@dataclass
class Workspace:
    name: str
    allowed_domains: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: new_id("wks"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class WorkspaceMembership:
    workspace_id: str
    user_id: str
    role: Role
    id: str = field(default_factory=lambda: new_id("mem"))


@dataclass
class CreditAccount:
    workspace_id: str
    available: int = 0
    reserved: int = 0
    consumed: int = 0


@dataclass
class CreditLedgerEntry:
    workspace_id: str
    entry_type: LedgerEntryType
    amount: int
    balance_after: int
    scan_id: str | None = None
    note: str = ""
    id: str = field(default_factory=lambda: new_id("led"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class CreditReservation:
    workspace_id: str
    scan_id: str
    status: CreditReservationStatus = CreditReservationStatus.RESERVED
    id: str = field(default_factory=lambda: new_id("crr"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class Project:
    workspace_id: str
    name: str
    id: str = field(default_factory=lambda: new_id("prj"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class Target:
    workspace_id: str
    project_id: str
    name: str
    url: str
    includes: list[str] = field(default_factory=list)
    excludes: list[str] = field(default_factory=list)
    allow_private_networks: bool = False
    id: str = field(default_factory=lambda: new_id("tgt"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class Scan:
    workspace_id: str
    project_id: str
    target_id: str
    scan_type: ScanType
    model_profile_id: str
    status: ScanStatus = ScanStatus.QUEUED
    autonomy_level: str = "guarded"
    instructions: str = ""
    id: str = field(default_factory=lambda: new_id("scn"))
    created_at: datetime = field(default_factory=now_utc)
    completed_at: datetime | None = None


@dataclass
class ScanEvent:
    scan_id: str
    type: str
    summary: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("evt"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class AgentPlan:
    scan_id: str
    phases: list[str]
    current_phase: str
    objective: str
    id: str = field(default_factory=lambda: new_id("pln"))
    created_at: datetime = field(default_factory=now_utc)
    updated_at: datetime = field(default_factory=now_utc)


@dataclass
class BrowserAction:
    action_type: str
    selector: str
    description: str
    value: str | None = None
    requires_approval: bool = False
    id: str = field(default_factory=lambda: new_id("act"))


@dataclass
class BrowserPlan:
    scan_id: str
    target_url: str
    engine: str
    actions: list[BrowserAction]
    id: str = field(default_factory=lambda: new_id("brw"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class ApprovalRequest:
    workspace_id: str
    scan_id: str
    requested_by_agent: str
    risk_category: str
    target: str
    proposed_tool: str
    proposed_action: str
    reason: str
    expected_evidence: str
    policy_reason: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    resolved_by: str | None = None
    operator_note: str = ""
    id: str = field(default_factory=lambda: new_id("apr"))
    requested_at: datetime = field(default_factory=now_utc)
    resolved_at: datetime | None = None


@dataclass
class Finding:
    scan_id: str
    title: str
    severity: str
    affected_asset: str
    evidence_refs: list[str]
    status: FindingStatus = FindingStatus.NEW
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    id: str = field(default_factory=lambda: new_id("fnd"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class Report:
    workspace_id: str
    project_id: str
    scan_id: str
    title: str
    format: str
    content: dict[str, Any]
    id: str = field(default_factory=lambda: new_id("rpt"))
    created_at: datetime = field(default_factory=now_utc)
