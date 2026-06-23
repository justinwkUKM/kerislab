from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import uuid4


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def now_utc() -> datetime:
    return datetime.now(UTC)


def session_expires_at() -> datetime:
    return now_utc() + timedelta(days=30)


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


class ScanJobType(StrEnum):
    PASSIVE_SCAN = "passive_scan"
    AUTONOMOUS_START = "autonomous_start"
    APPROVAL_REQUEST = "approval_request"
    COMPLETE_SCAN = "complete_scan"
    FAIL_SCAN = "fail_scan"


class ScanJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BrowserExecutionStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class BillingProvider(StrEnum):
    MANUAL = "manual"
    STRIPE = "stripe"


class CheckoutSessionStatus(StrEnum):
    CREATED = "created"
    PAID = "paid"
    CANCELLED = "cancelled"


class InvoiceStatus(StrEnum):
    OPEN = "open"
    PAID = "paid"
    VOID = "void"


class PaymentStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class AuditAction(StrEnum):
    LOGIN = "login"
    OAUTH_STATE_CREATED = "oauth_state_created"
    OAUTH_STATE_CONSUMED = "oauth_state_consumed"
    WORKSPACE_CREATED = "workspace_created"
    WORKSPACE_SSO_UPDATED = "workspace_sso_updated"
    WORKSPACE_MEMBER_AUTO_JOINED = "workspace_member_auto_joined"
    PROJECT_CREATED = "project_created"
    TARGET_CREATED = "target_created"
    MODEL_PROFILE_CREATED = "model_profile_created"
    MODEL_PROFILE_TESTED = "model_profile_tested"
    SCAN_CREATED = "scan_created"
    SCAN_EXECUTED = "scan_executed"
    SCAN_PAUSED = "scan_paused"
    SCAN_RESUMED = "scan_resumed"
    SCAN_INSTRUCTIONS_UPDATED = "scan_instructions_updated"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_RESOLVED = "approval_resolved"
    REPORT_GENERATED = "report_generated"
    CREDITS_GRANTED = "credits_granted"
    BILLING_CHECKOUT_CREATED = "billing_checkout_created"
    BILLING_CHECKOUT_CONFIRMED = "billing_checkout_confirmed"
    SETTINGS_UPDATED = "settings_updated"


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
class UserSession:
    user_id: str
    token: str
    auth_provider: AuthProvider
    user_agent: str | None = None
    ip_address: str | None = None
    id: str = field(default_factory=lambda: new_id("ses"))
    created_at: datetime = field(default_factory=now_utc)
    expires_at: datetime = field(default_factory=session_expires_at)
    revoked_at: datetime | None = None
    last_seen_at: datetime | None = None


@dataclass
class OAuthState:
    provider: AuthProvider
    state: str
    nonce: str
    redirect_uri: str
    consumed_at: datetime | None = None
    id: str = field(default_factory=lambda: new_id("oas"))
    created_at: datetime = field(default_factory=now_utc)


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
class BillingCustomer:
    workspace_id: str
    provider: BillingProvider
    provider_customer_id: str
    billing_email: str
    id: str = field(default_factory=lambda: new_id("bilcus"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class BillingCheckoutSession:
    workspace_id: str
    provider: BillingProvider
    credit_amount: int
    unit_amount_cents: int
    currency: str = "USD"
    status: CheckoutSessionStatus = CheckoutSessionStatus.CREATED
    provider_session_id: str | None = None
    checkout_url: str | None = None
    id: str = field(default_factory=lambda: new_id("bilchk"))
    created_at: datetime = field(default_factory=now_utc)
    completed_at: datetime | None = None


@dataclass
class BillingInvoice:
    workspace_id: str
    checkout_session_id: str
    provider: BillingProvider
    amount_cents: int
    currency: str
    status: InvoiceStatus = InvoiceStatus.OPEN
    provider_invoice_id: str | None = None
    id: str = field(default_factory=lambda: new_id("bilinv"))
    created_at: datetime = field(default_factory=now_utc)
    paid_at: datetime | None = None


@dataclass
class BillingPayment:
    workspace_id: str
    invoice_id: str
    provider: BillingProvider
    amount_cents: int
    currency: str
    status: PaymentStatus
    provider_payment_id: str | None = None
    id: str = field(default_factory=lambda: new_id("bilpay"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class BillingWebhookEvent:
    provider: BillingProvider
    provider_event_id: str
    event_type: str
    payload: dict[str, Any]
    processed: bool = False
    error: str = ""
    id: str = field(default_factory=lambda: new_id("bilwh"))
    received_at: datetime = field(default_factory=now_utc)
    processed_at: datetime | None = None


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
class BrowserExecution:
    scan_id: str
    browser_plan_id: str
    engine: str
    status: BrowserExecutionStatus = BrowserExecutionStatus.RUNNING
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    id: str = field(default_factory=lambda: new_id("bex"))
    started_at: datetime = field(default_factory=now_utc)
    completed_at: datetime | None = None


@dataclass
class EvidenceArtifact:
    scan_id: str
    artifact_type: str
    uri: str
    summary: str
    content_type: str
    content: str = ""
    browser_execution_id: str | None = None
    finding_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("evd"))
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


@dataclass
class ScanJob:
    scan_id: str
    job_type: ScanJobType
    status: ScanJobStatus = ScanJobStatus.QUEUED
    payload: dict[str, Any] = field(default_factory=dict)
    attempts: int = 0
    id: str = field(default_factory=lambda: new_id("job"))
    created_at: datetime = field(default_factory=now_utc)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str = ""


@dataclass
class AuditLog:
    action: AuditAction | str
    actor_user_id: str | None
    workspace_id: str | None = None
    project_id: str | None = None
    target_id: str | None = None
    scan_id: str | None = None
    approval_id: str | None = None
    report_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: new_id("aud"))
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class WorkerHeartbeat:
    name: str
    queue_name: str
    status: str = "running"
    processed_jobs: int = 0
    error: str = ""
    id: str = field(default_factory=lambda: new_id("wrk"))
    started_at: datetime = field(default_factory=now_utc)
    last_seen_at: datetime = field(default_factory=now_utc)
