from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

try:
    from fastapi import Depends, FastAPI, Header, HTTPException
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - exercised only without runtime deps
    raise RuntimeError(
        "FastAPI runtime dependencies are missing. Install with `pip install -e .` "
        "or use the domain services directly in tests."
    ) from exc

from .models import AuthProvider, ScanType
from .services import (
    AuthService,
    ApprovalError,
    AutonomousPentestService,
    CreditError,
    CreditService,
    ModelProfileService,
    ProjectService,
    ReportService,
    ScanService,
    WorkspaceService,
)
from .scope import ScopeError
from .store import InMemoryStore, NotFoundError

app = FastAPI(title="KerisLab API", version="0.1.0")
store = InMemoryStore()


class LoginRequest(BaseModel):
    email: str
    display_name: str
    provider: AuthProvider = AuthProvider.GOOGLE
    avatar_url: str | None = None


class WorkspaceCreate(BaseModel):
    name: str
    initial_credits: int = Field(default=0, ge=0)


class ProjectCreate(BaseModel):
    workspace_id: str
    name: str


class TargetCreate(BaseModel):
    workspace_id: str
    project_id: str
    name: str
    url: str
    excludes: list[str] = Field(default_factory=list)
    allow_private_networks: bool = False


class CreditGrant(BaseModel):
    amount: int = Field(gt=0)
    note: str = ""


class ModelProfileCreate(BaseModel):
    workspace_id: str
    name: str
    model: str
    api_base: str


class ScanCreate(BaseModel):
    workspace_id: str
    project_id: str
    target_id: str
    scan_type: ScanType = ScanType.PASSIVE_BLACKBOX
    model_profile_id: str = "default"
    instructions: str = ""


class ApprovalDecision(BaseModel):
    note: str = ""


def serialize(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, list):
        return [serialize(item) for item in value]
    return value


def current_user_id(x_kerislab_user: str | None = Header(default=None)) -> str:
    if not x_kerislab_user:
        raise HTTPException(status_code=401, detail="Missing X-KerisLab-User header")
    if x_kerislab_user not in store.users:
        raise HTTPException(status_code=401, detail="Unknown user")
    return x_kerislab_user


def handle_error(exc: Exception) -> None:
    if isinstance(exc, (NotFoundError,)):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, (ApprovalError, CreditError, ScopeError, ValueError)):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "kerislab-api"}


@app.get("/api/auth/providers")
def auth_providers() -> dict[str, object]:
    return {
        "providers": [
            {"id": "google", "label": "Continue with Google", "enabled": True},
            {"id": "sso", "label": "Continue with SSO", "enabled": True},
        ]
    }


@app.post("/api/auth/dev-login")
def dev_login(payload: LoginRequest) -> dict[str, object]:
    user = AuthService(store).login_identity(
        email=payload.email,
        display_name=payload.display_name,
        provider=payload.provider,
        avatar_url=payload.avatar_url,
    )
    return {"user": serialize(user), "session_header": {"X-KerisLab-User": user.id}}


@app.get("/api/auth/me")
def auth_me(user_id: str = Depends(current_user_id)) -> dict[str, object]:
    user = store.users[user_id]
    settings = store.user_settings[user_id]
    memberships = [m for m in store.memberships.values() if m.user_id == user_id]
    return {
        "user": serialize(user),
        "settings": serialize(settings),
        "memberships": serialize(memberships),
    }


@app.patch("/api/users/me")
def update_me(payload: dict[str, object], user_id: str = Depends(current_user_id)) -> dict[str, object]:
    settings = store.user_settings[user_id]
    if "theme" in payload:
        settings.theme = str(payload["theme"])
    if "timezone" in payload:
        settings.timezone = str(payload["timezone"])
    if "notifications_enabled" in payload:
        settings.notifications_enabled = bool(payload["notifications_enabled"])
    return {"settings": serialize(settings)}


@app.post("/api/workspaces")
def create_workspace(payload: WorkspaceCreate, user_id: str = Depends(current_user_id)) -> dict[str, object]:
    owner = store.users[user_id]
    workspace = WorkspaceService(store).create_workspace(
        name=payload.name,
        owner=owner,
        initial_credits=payload.initial_credits,
    )
    return {"workspace": serialize(workspace), "credits": serialize(store.credit_accounts[workspace.id])}


@app.get("/api/workspaces/{workspace_id}/credits")
def get_credits(workspace_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    return {"credits": serialize(CreditService(store).account(workspace_id))}


@app.post("/api/workspaces/{workspace_id}/credits/grant")
def grant_credits(workspace_id: str, payload: CreditGrant, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        entry = CreditService(store).grant(workspace_id, payload.amount, payload.note)
    except Exception as exc:
        handle_error(exc)
    return {"entry": serialize(entry), "credits": serialize(store.credit_accounts[workspace_id])}


@app.get("/api/workspaces/{workspace_id}/credit-ledger")
def credit_ledger(workspace_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    entries = [e for e in store.credit_ledger if e.workspace_id == workspace_id]
    return {"entries": serialize(entries)}


@app.post("/api/settings/llm/profiles")
def create_model_profile(payload: ModelProfileCreate, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        profile = ModelProfileService(store).create_profile(**payload.model_dump())
    except Exception as exc:
        handle_error(exc)
    return {"profile": serialize(profile)}


@app.post("/api/settings/llm/profiles/{profile_id}/test")
def test_model_profile(profile_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        result = ModelProfileService(store).test_profile(profile_id)
    except Exception as exc:
        handle_error(exc)
    return result


@app.post("/api/projects")
def create_project(payload: ProjectCreate, _: str = Depends(current_user_id)) -> dict[str, object]:
    project = ProjectService(store).create_project(workspace_id=payload.workspace_id, name=payload.name)
    return {"project": serialize(project)}


@app.post("/api/targets")
def create_target(payload: TargetCreate, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        target = ProjectService(store).create_target(**payload.model_dump())
    except Exception as exc:
        handle_error(exc)
    return {"target": serialize(target)}


@app.post("/api/scans")
def create_scan(payload: ScanCreate, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        scan = ScanService(store).create_scan(**payload.model_dump())
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan), "credits": serialize(store.credit_accounts[payload.workspace_id])}


@app.post("/api/scans/{scan_id}/run-passive")
def run_passive(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        scan = ScanService(store).run_passive_scan(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan)}


@app.post("/api/scans/{scan_id}/complete")
def complete_scan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        scan = ScanService(store).complete_scan(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan), "credits": serialize(store.credit_accounts[scan.workspace_id])}


@app.post("/api/scans/{scan_id}/fail")
def fail_scan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        scan = ScanService(store).fail_scan(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan), "credits": serialize(store.credit_accounts[scan.workspace_id])}


@app.post("/api/scans/{scan_id}/cancel")
def cancel_scan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        scan = ScanService(store).cancel_scan(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan), "credits": serialize(store.credit_accounts[scan.workspace_id])}


@app.post("/api/scans/{scan_id}/start-autonomous")
def start_autonomous(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        plan = AutonomousPentestService(store).start(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"plan": serialize(plan), "scan": serialize(store.scans[scan_id])}


@app.get("/api/scans/{scan_id}/browser-plan")
def browser_plan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        plan = AutonomousPentestService(store).browser_plan(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"browser_plan": serialize(plan)}


@app.post("/api/scans/{scan_id}/approvals/request-upload-verification")
def request_upload_verification(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        request = AutonomousPentestService(store).request_gated_upload_verification(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"approval": serialize(request), "scan": serialize(store.scans[scan_id])}


@app.get("/api/scans/{scan_id}/approvals")
def scan_approvals(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    approvals = [a for a in store.approval_requests.values() if a.scan_id == scan_id]
    return {"approvals": serialize(approvals)}


@app.post("/api/approvals/{approval_id}/approve")
def approve_request(
    approval_id: str,
    payload: ApprovalDecision,
    user_id: str = Depends(current_user_id),
) -> dict[str, object]:
    try:
        request = AutonomousPentestService(store).approve(approval_id, user_id=user_id, note=payload.note)
    except Exception as exc:
        handle_error(exc)
    return {"approval": serialize(request)}


@app.post("/api/approvals/{approval_id}/reject")
def reject_request(
    approval_id: str,
    payload: ApprovalDecision,
    user_id: str = Depends(current_user_id),
) -> dict[str, object]:
    try:
        request = AutonomousPentestService(store).reject(approval_id, user_id=user_id, note=payload.note)
    except Exception as exc:
        handle_error(exc)
    return {"approval": serialize(request)}


@app.get("/api/scans/{scan_id}/events")
def scan_events(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    return {"events": serialize([e for e in store.events if e.scan_id == scan_id])}


@app.get("/api/findings")
def findings(scan_id: str | None = None, _: str = Depends(current_user_id)) -> dict[str, object]:
    values = list(store.findings.values())
    if scan_id:
        values = [f for f in values if f.scan_id == scan_id]
    return {"findings": serialize(values)}


@app.post("/api/reports")
def create_report(payload: dict[str, str], _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        report = ReportService(store).generate_json_report(payload["scan_id"])
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="scan_id is required") from exc
    except Exception as exc:
        handle_error(exc)
    return {"report": serialize(report)}
