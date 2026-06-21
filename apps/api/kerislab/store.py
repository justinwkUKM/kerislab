from __future__ import annotations

from dataclasses import asdict
from threading import RLock
from typing import TypeVar

from .models import (
    BrowserPlan,
    CreditAccount,
    CreditLedgerEntry,
    CreditReservation,
    Finding,
    AgentPlan,
    ApprovalRequest,
    ModelProfile,
    Project,
    Report,
    Scan,
    ScanEvent,
    Target,
    User,
    UserSettings,
    Workspace,
    WorkspaceMembership,
)

T = TypeVar("T")


class NotFoundError(ValueError):
    pass


class InMemoryStore:
    """Small repository used by the MVP and unit tests.

    The service layer is written against this repository shape so it can later
    be replaced by SQLAlchemy/PostgreSQL without changing API behavior.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self.users: dict[str, User] = {}
        self.user_settings: dict[str, UserSettings] = {}
        self.workspaces: dict[str, Workspace] = {}
        self.memberships: dict[str, WorkspaceMembership] = {}
        self.credit_accounts: dict[str, CreditAccount] = {}
        self.credit_ledger: list[CreditLedgerEntry] = []
        self.credit_reservations: dict[str, CreditReservation] = {}
        self.projects: dict[str, Project] = {}
        self.model_profiles: dict[str, ModelProfile] = {}
        self.targets: dict[str, Target] = {}
        self.scans: dict[str, Scan] = {}
        self.events: list[ScanEvent] = []
        self.agent_plans: dict[str, AgentPlan] = {}
        self.browser_plans: dict[str, BrowserPlan] = {}
        self.approval_requests: dict[str, ApprovalRequest] = {}
        self.findings: dict[str, Finding] = {}
        self.reports: dict[str, Report] = {}

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
