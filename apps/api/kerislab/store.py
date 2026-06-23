from __future__ import annotations

import json
from dataclasses import asdict
from dataclasses import fields as dataclass_fields
from dataclasses import is_dataclass
from datetime import datetime
from enum import Enum
import os
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Any, TypeVar, get_args, get_origin, get_type_hints

from .models import (
    BrowserPlan,
    BrowserExecution,
    BillingCheckoutSession,
    BillingCustomer,
    BillingInvoice,
    BillingPayment,
    BillingWebhookEvent,
    AuditLog,
    CreditAccount,
    CreditLedgerEntry,
    CreditReservation,
    EvidenceArtifact,
    Finding,
    AgentPlan,
    OAuthState,
    ApprovalRequest,
    ModelProfile,
    Project,
    Report,
    ScanJob,
    Scan,
    ScanEvent,
    Target,
    User,
    UserSession,
    UserSettings,
    WorkerHeartbeat,
    Workspace,
    WorkspaceMembership,
)

T = TypeVar("T")

COLLECTION_SPECS = {
    "users": (User, "dict"),
    "user_settings": (UserSettings, "dict"),
    "user_sessions": (UserSession, "dict"),
    "oauth_states": (OAuthState, "dict"),
    "workspaces": (Workspace, "dict"),
    "memberships": (WorkspaceMembership, "dict"),
    "credit_accounts": (CreditAccount, "dict"),
    "credit_ledger": (CreditLedgerEntry, "list"),
    "credit_reservations": (CreditReservation, "dict"),
    "billing_customers": (BillingCustomer, "dict"),
    "billing_checkout_sessions": (BillingCheckoutSession, "dict"),
    "billing_invoices": (BillingInvoice, "dict"),
    "billing_payments": (BillingPayment, "dict"),
    "billing_webhook_events": (BillingWebhookEvent, "dict"),
    "projects": (Project, "dict"),
    "model_profiles": (ModelProfile, "dict"),
    "targets": (Target, "dict"),
    "scans": (Scan, "dict"),
    "events": (ScanEvent, "list"),
    "agent_plans": (AgentPlan, "dict"),
    "browser_plans": (BrowserPlan, "dict"),
    "browser_executions": (BrowserExecution, "dict"),
    "evidence_artifacts": (EvidenceArtifact, "dict"),
    "approval_requests": (ApprovalRequest, "dict"),
    "findings": (Finding, "dict"),
    "reports": (Report, "dict"),
    "scan_jobs": (ScanJob, "dict"),
    "audit_logs": (AuditLog, "list"),
    "worker_heartbeats": (WorkerHeartbeat, "dict"),
}


def _encode_value(value: Any) -> Any:
    if is_dataclass(value):
        return {field.name: _encode_value(getattr(value, field.name)) for field in dataclass_fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_encode_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _encode_value(item) for key, item in value.items()}
    return value


def _decode_value(value: Any, annotation: Any) -> Any:
    if value is None:
        return None
    origin = get_origin(annotation)
    args = get_args(annotation)
    if origin is list and args:
        return [_decode_value(item, args[0]) for item in value]
    if origin is dict and len(args) == 2:
        return {key: _decode_value(item, args[1]) for key, item in value.items()}
    if origin is tuple and args:
        return tuple(_decode_value(item, args[min(index, len(args) - 1)]) for index, item in enumerate(value))
    if origin is not None and type(None) in args:
        inner = next(arg for arg in args if arg is not type(None))
        return _decode_value(value, inner)
    if origin is not None and str(origin) == "types.UnionType" and type(None) in args:
        inner = next(arg for arg in args if arg is not type(None))
        return _decode_value(value, inner)
    if isinstance(annotation, type):
        if issubclass(annotation, Enum):
            return annotation(value)
        if issubclass(annotation, datetime):
            return datetime.fromisoformat(value)
        if is_dataclass(annotation):
            return _hydrate_dataclass(annotation, value)
    return value


def _hydrate_dataclass(cls: type[T], payload: dict[str, Any]) -> T:
    type_hints = get_type_hints(cls)
    kwargs: dict[str, Any] = {}
    for field in dataclass_fields(cls):
        field_value = payload[field.name]
        annotation = type_hints.get(field.name, field.type)
        kwargs[field.name] = _decode_value(field_value, annotation)
    return cls(**kwargs)


class StoreBase:
    def reload(self) -> None:
        return None

    def sync(self) -> None:
        return None


class NotFoundError(ValueError):
    pass


class InMemoryStore(StoreBase):
    """Small repository used by the MVP and unit tests.

    The service layer is written against this repository shape so it can later
    be replaced by SQLAlchemy/PostgreSQL without changing API behavior.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self.users: dict[str, User] = {}
        self.user_settings: dict[str, UserSettings] = {}
        self.user_sessions: dict[str, UserSession] = {}
        self.oauth_states: dict[str, OAuthState] = {}
        self.workspaces: dict[str, Workspace] = {}
        self.memberships: dict[str, WorkspaceMembership] = {}
        self.credit_accounts: dict[str, CreditAccount] = {}
        self.credit_ledger: list[CreditLedgerEntry] = []
        self.credit_reservations: dict[str, CreditReservation] = {}
        self.billing_customers: dict[str, BillingCustomer] = {}
        self.billing_checkout_sessions: dict[str, BillingCheckoutSession] = {}
        self.billing_invoices: dict[str, BillingInvoice] = {}
        self.billing_payments: dict[str, BillingPayment] = {}
        self.billing_webhook_events: dict[str, BillingWebhookEvent] = {}
        self.projects: dict[str, Project] = {}
        self.model_profiles: dict[str, ModelProfile] = {}
        self.targets: dict[str, Target] = {}
        self.scans: dict[str, Scan] = {}
        self.events: list[ScanEvent] = []
        self.agent_plans: dict[str, AgentPlan] = {}
        self.browser_plans: dict[str, BrowserPlan] = {}
        self.browser_executions: dict[str, BrowserExecution] = {}
        self.evidence_artifacts: dict[str, EvidenceArtifact] = {}
        self.approval_requests: dict[str, ApprovalRequest] = {}
        self.findings: dict[str, Finding] = {}
        self.reports: dict[str, Report] = {}
        self.scan_jobs: dict[str, ScanJob] = {}
        self.audit_logs: list[AuditLog] = []
        self.worker_heartbeats: dict[str, WorkerHeartbeat] = {}

    def add(self, collection: dict[str, T], entity: T) -> T:
        with self._lock:
            collection[getattr(entity, "id")] = entity
            return entity

    def get(self, collection: dict[str, T], entity_id: str, label: str) -> T:
        with self._lock:
            try:
                return collection[entity_id]
            except KeyError as exc:
                raise NotFoundError(f"{label} not found: {entity_id}") from exc

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "users": [asdict(v) for v in self.users.values()],
                "workspaces": [asdict(v) for v in self.workspaces.values()],
                "projects": [asdict(v) for v in self.projects.values()],
                "targets": [asdict(v) for v in self.targets.values()],
                "scans": [asdict(v) for v in self.scans.values()],
                "agent_plans": [asdict(v) for v in self.agent_plans.values()],
                "browser_plans": [asdict(v) for v in self.browser_plans.values()],
                "approval_requests": [asdict(v) for v in self.approval_requests.values()],
                "findings": [asdict(v) for v in self.findings.values()],
                "reports": [asdict(v) for v in self.reports.values()],
            }


class SQLiteStore(InMemoryStore):
    """SQLite-backed store for local persistence."""

    def __init__(self, database_path: str | Path) -> None:
        super().__init__()
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.database_path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS store_entities ("
                "collection TEXT NOT NULL,"
                "entity_id TEXT NOT NULL,"
                "payload TEXT NOT NULL,"
                "PRIMARY KEY(collection, entity_id)"
                ")"
            )
        self._load_or_initialize()

    def _clear(self) -> None:
        for collection_name in COLLECTION_SPECS:
            getattr(self, collection_name).clear()

    def _load_or_initialize(self) -> None:
        self._clear()
        rows = self._connection.execute(
            "SELECT collection, entity_id, payload FROM store_entities ORDER BY collection, entity_id"
        ).fetchall()
        for row in rows:
            collection = row["collection"]
            entity_id = row["entity_id"]
            payload = json.loads(row["payload"])
            model_cls, kind = COLLECTION_SPECS[collection]
            entity = _hydrate_dataclass(model_cls, payload)
            if kind == "list":
                getattr(self, collection).append(entity)
            else:
                getattr(self, collection)[entity_id] = entity
        self.credit_ledger.sort(key=lambda entry: entry.created_at)
        self.events.sort(key=lambda event: event.created_at)

    def reload(self) -> None:
        self._load_or_initialize()

    def sync(self) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM store_entities")
            for collection_name, (model_cls, kind) in COLLECTION_SPECS.items():
                collection = getattr(self, collection_name)
                if kind == "list":
                    iterable = ((getattr(entity, "id"), entity) for entity in collection)
                else:
                    iterable = collection.items()
                for entity_id, entity in iterable:
                    payload = json.dumps(_encode_value(entity))
                    self._connection.execute(
                        "INSERT INTO store_entities (collection, entity_id, payload) VALUES (?, ?, ?)",
                        (collection_name, entity_id, payload),
                    )


class PostgresStore(InMemoryStore):
    """PostgreSQL-backed store with the same table layout as SQLiteStore."""

    def __init__(self, database_url: str) -> None:
        super().__init__()
        try:
            import psycopg  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("psycopg is not installed") from exc
        self._psycopg = psycopg
        self.database_url = database_url
        self._connection = self._psycopg.connect(database_url)
        with self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS store_entities ("
                "collection TEXT NOT NULL,"
                "entity_id TEXT NOT NULL,"
                "payload TEXT NOT NULL,"
                "PRIMARY KEY(collection, entity_id)"
                ")"
            )
        self._load_or_initialize()

    def _load_or_initialize(self) -> None:
        for collection_name in COLLECTION_SPECS:
            getattr(self, collection_name).clear()
        rows = self._connection.execute(
            "SELECT collection, entity_id, payload FROM store_entities ORDER BY collection, entity_id"
        ).fetchall()
        for row in rows:
            collection = row[0]
            entity_id = row[1]
            payload = json.loads(row[2])
            model_cls, kind = COLLECTION_SPECS[collection]
            entity = _hydrate_dataclass(model_cls, payload)
            if kind == "list":
                getattr(self, collection).append(entity)
            else:
                getattr(self, collection)[entity_id] = entity
        self.credit_ledger.sort(key=lambda entry: entry.created_at)
        self.events.sort(key=lambda event: event.created_at)

    def reload(self) -> None:
        self._load_or_initialize()

    def sync(self) -> None:
        with self._connection:
            self._connection.execute("DELETE FROM store_entities")
            for collection_name, (model_cls, kind) in COLLECTION_SPECS.items():
                collection = getattr(self, collection_name)
                if kind == "list":
                    iterable = ((getattr(entity, "id"), entity) for entity in collection)
                else:
                    iterable = collection.items()
                for entity_id, entity in iterable:
                    payload = json.dumps(_encode_value(entity))
                    self._connection.execute(
                        "INSERT INTO store_entities (collection, entity_id, payload) VALUES (%s, %s, %s)",
                        (collection_name, entity_id, payload),
                    )


def create_store(
    *,
    database_url: str | None = None,
    sqlite_path: str | Path | None = None,
) -> StoreBase:
    database_url = database_url or os.getenv("KERISLAB_DATABASE_URL")
    if database_url:
        try:
            from .migrations import apply_postgres_migrations

            apply_postgres_migrations(database_url)
            return PostgresStore(database_url)
        except Exception:
            pass

    path = Path(sqlite_path or os.getenv("KERISLAB_SQLITE_PATH") or ".kerislab/kerislab.db")
    try:
        from .migrations import apply_sqlite_migrations

        apply_sqlite_migrations(path)
        return SQLiteStore(path)
    except Exception:
        return InMemoryStore()
