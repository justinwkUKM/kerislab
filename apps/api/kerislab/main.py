from __future__ import annotations

import hmac
import json
import os
from hashlib import sha256
from secrets import token_urlsafe
from dataclasses import asdict, is_dataclass
from typing import Any

try:
    from fastapi import Depends, FastAPI, Header, HTTPException
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field
except ImportError as exc:  # pragma: no cover - exercised only without runtime deps
    raise RuntimeError(
        "FastAPI runtime dependencies are missing. Install with `pip install -e .` "
        "or use the domain services directly in tests."
    ) from exc

from .auth import OAuthConfigurationError, OAuthService
from .models import AuthProvider, Role, ScanType
from .services import (
    AuthService,
    AuditService,
    ApprovalError,
    AutonomousPentestService,
    AuthorizationError,
    AuthorizationService,
    BillingError,
    BillingService,
    BrowserExecutionService,
    CreditError,
    CreditService,
    ModelProfileService,
    OAuthStateError,
    OAuthStateService,
    ProjectService,
    ReportService,
    ScanService,
    ScanExecutionService,
    WorkerStatusService,
    WorkspaceService,
)
from .scope import ScopeError
from .store import InMemoryStore, NotFoundError, create_store
from .models import AuditAction, ScanJobType

app = FastAPI(title="KerisLab API", version="0.1.0")
store = create_store()


def get_execution_engine() -> ScanExecutionService:
    engine = getattr(app.state, "execution_engine", None)
    if engine is None or engine.store is not store:
        engine = ScanExecutionService(store)
        app.state.execution_engine = engine
    return engine


@app.on_event("startup")
def startup_execution_engine() -> None:
    engine = get_execution_engine()
    if os.getenv("KERISLAB_BACKGROUND_WORKER", "").lower() in {"1", "true", "yes"}:
        engine.start()


@app.on_event("shutdown")
def shutdown_execution_engine() -> None:
    engine = getattr(app.state, "execution_engine", None)
    if engine is not None:
        engine.stop()


class LoginRequest(BaseModel):
    email: str
    display_name: str
    provider: AuthProvider = AuthProvider.GOOGLE
    avatar_url: str | None = None


class WorkspaceCreate(BaseModel):
    name: str
    initial_credits: int = Field(default=0, ge=0)


class WorkspaceSsoUpdate(BaseModel):
    allowed_domains: list[str] = Field(default_factory=list)


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


class BillingCheckoutCreate(BaseModel):
    credit_amount: int = Field(gt=0)
    billing_email: str
    unit_amount_cents: int = Field(default=500, gt=0)
    provider: str = "manual"


class BillingWebhookPayload(BaseModel):
    provider: str = "stripe"
    provider_event_id: str
    event_type: str
    data: dict[str, object]


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
    if isinstance(value, dict):
        return {key: serialize(item) for key, item in value.items()}
    return value


def current_user_id(
    authorization: str | None = Header(default=None),
    x_kerislab_user: str | None = Header(default=None),
) -> str:
    if authorization:
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise HTTPException(status_code=401, detail="Invalid Authorization header")
        try:
            return AuthService(store).user_for_session_token(token).id
        except Exception as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    if not x_kerislab_user:
        raise HTTPException(status_code=401, detail="Missing bearer token or X-KerisLab-User header")
    if x_kerislab_user not in store.users:
        raise HTTPException(status_code=401, detail="Unknown user")
    return x_kerislab_user


def handle_error(exc: Exception) -> None:
    if isinstance(exc, (NotFoundError,)):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, AuthorizationError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, (OAuthConfigurationError, OAuthStateError)):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, (ApprovalError, BillingError, CreditError, ScopeError, ValueError)):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    raise exc


def require_workspace_access(user_id: str, workspace_id: str) -> None:
    try:
        AuthorizationService(store).require_workspace_member(user_id, workspace_id)
    except Exception as exc:
        handle_error(exc)


def require_workspace_role(user_id: str, workspace_id: str, allowed_roles: set[Role]) -> None:
    try:
        AuthorizationService(store).require_workspace_role(user_id, workspace_id, allowed_roles)
    except Exception as exc:
        handle_error(exc)


WORKSPACE_ADMIN_ROLES = {Role.OWNER, Role.ADMIN}
WORKSPACE_SECURITY_ROLES = {Role.OWNER, Role.ADMIN, Role.SECURITY_LEAD}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "kerislab-api"}


@app.get("/api/health/components")
def health_components() -> dict[str, object]:
    return serialize(WorkerStatusService(store).components())


@app.get("/api/auth/providers")
def auth_providers() -> dict[str, object]:
    return {
        "providers": [
            {"id": "google", "label": "Continue with Google", "enabled": True},
            {"id": "sso", "label": "Continue with SSO", "enabled": True},
        ]
    }


@app.get("/api/auth/google/login")
def google_login() -> dict[str, str]:
    try:
        service = OAuthService()
        config = service.google_config()
        state = token_urlsafe(24)
        nonce = token_urlsafe(24)
        OAuthStateService(store).create(
            provider=config.provider,
            state=state,
            nonce=nonce,
            redirect_uri=config.redirect_uri,
        )
        url = service.authorization_url(config, state=state, nonce=nonce)
    except Exception as exc:
        handle_error(exc)
    return {"authorization_url": url}


@app.get("/api/auth/sso/login")
def sso_login() -> dict[str, str]:
    try:
        service = OAuthService()
        config = service.sso_config()
        state = token_urlsafe(24)
        nonce = token_urlsafe(24)
        OAuthStateService(store).create(
            provider=config.provider,
            state=state,
            nonce=nonce,
            redirect_uri=config.redirect_uri,
        )
        url = service.authorization_url(config, state=state, nonce=nonce)
    except Exception as exc:
        handle_error(exc)
    return {"authorization_url": url}


def oidc_callback_response(*, provider: AuthProvider, code: str, state: str) -> dict[str, object]:
    service = OAuthService()
    try:
        config = service.google_config() if provider == AuthProvider.GOOGLE else service.sso_config()
        oauth_state = OAuthStateService(store).consume(provider=provider, state=state)
        token_response = service.exchange_code(config, code=code)
        profile = service.resolve_profile(config, token_response, expected_nonce=oauth_state.nonce)
        user = AuthService(store).login_identity(
            email=str(profile["email"]),
            display_name=str(profile["display_name"]),
            provider=provider,
            avatar_url=profile["avatar_url"],
        )
        session = AuthService(store).create_session(user)
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"{exc.args[0]} is required") from exc
    except Exception as exc:
        handle_error(exc)
    return {
        "user": serialize(user),
        "access_token": session.token,
        "token_type": "bearer",
        "session": serialize(session),
        "session_header": {"X-KerisLab-User": user.id},
    }


def provider_for_oauth_state(state: str) -> AuthProvider:
    oauth_state = store.oauth_states.get(state)
    if oauth_state is None:
        raise HTTPException(status_code=400, detail="OAuth state is invalid")
    return oauth_state.provider


@app.get("/api/auth/oidc/callback")
def oidc_callback_get(code: str, state: str, provider: str | None = None) -> dict[str, object]:
    resolved_provider = AuthProvider(provider) if provider else provider_for_oauth_state(state)
    return oidc_callback_response(provider=resolved_provider, code=code, state=state)


@app.post("/api/auth/oidc/callback")
def oidc_callback(payload: dict[str, str]) -> dict[str, object]:
    try:
        provider = AuthProvider(payload["provider"]) if payload.get("provider") else provider_for_oauth_state(payload["state"])
        return oidc_callback_response(provider=provider, code=payload["code"], state=payload["state"])
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=f"{exc.args[0]} is required") from exc


@app.post("/api/auth/dev-login")
def dev_login(payload: LoginRequest) -> dict[str, object]:
    user = AuthService(store).login_identity(
        email=payload.email,
        display_name=payload.display_name,
        provider=payload.provider,
        avatar_url=payload.avatar_url,
    )
    session = AuthService(store).create_session(user)
    return {
        "user": serialize(user),
        "access_token": session.token,
        "token_type": "bearer",
        "session": serialize(session),
        "session_header": {"X-KerisLab-User": user.id},
    }


@app.post("/api/auth/logout")
def logout(authorization: str | None = Header(default=None)) -> dict[str, object]:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization header")
    try:
        session = AuthService(store).revoke_session_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return {"session": serialize(session)}


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
    AuditService(store).record(AuditAction.SETTINGS_UPDATED, actor_user_id=user_id, workspace_id=settings.default_workspace_id)
    store.sync()
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


@app.get("/api/workspaces")
def list_workspaces(user_id: str = Depends(current_user_id)) -> dict[str, object]:
    workspace_ids = {m.workspace_id for m in store.memberships.values() if m.user_id == user_id}
    return {"workspaces": serialize([w for w in store.workspaces.values() if w.id in workspace_ids])}


@app.get("/api/workspaces/{workspace_id}")
def get_workspace(workspace_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    require_workspace_access(_, workspace_id)
    workspace = store.get(store.workspaces, workspace_id, "workspace")
    memberships = [m for m in store.memberships.values() if m.workspace_id == workspace_id]
    return {
        "workspace": serialize(workspace),
        "memberships": serialize(memberships),
        "credits": serialize(CreditService(store).account(workspace_id)),
    }


@app.patch("/api/workspaces/{workspace_id}/sso")
def update_workspace_sso(
    workspace_id: str,
    payload: WorkspaceSsoUpdate,
    user_id: str = Depends(current_user_id),
) -> dict[str, object]:
    require_workspace_role(user_id, workspace_id, WORKSPACE_ADMIN_ROLES)
    try:
        workspace = WorkspaceService(store).update_sso_domains(
            workspace_id=workspace_id,
            allowed_domains=payload.allowed_domains,
        )
        AuditService(store).record(
            AuditAction.WORKSPACE_SSO_UPDATED,
            actor_user_id=user_id,
            workspace_id=workspace_id,
            details={"allowed_domains": workspace.allowed_domains},
        )
    except Exception as exc:
        handle_error(exc)
    return {"workspace": serialize(workspace)}


@app.get("/api/workspaces/{workspace_id}/credits")
def get_credits(workspace_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    require_workspace_access(_, workspace_id)
    return {"credits": serialize(CreditService(store).account(workspace_id))}


@app.post("/api/workspaces/{workspace_id}/credits/grant")
def grant_credits(workspace_id: str, payload: CreditGrant, _: str = Depends(current_user_id)) -> dict[str, object]:
    require_workspace_role(_, workspace_id, WORKSPACE_ADMIN_ROLES)
    try:
        entry = CreditService(store).grant(workspace_id, payload.amount, payload.note)
        AuditService(store).record(
            AuditAction.CREDITS_GRANTED,
            actor_user_id=_,
            workspace_id=workspace_id,
            details={"amount": payload.amount, "note": payload.note},
        )
    except Exception as exc:
        handle_error(exc)
    return {"entry": serialize(entry), "credits": serialize(store.credit_accounts[workspace_id])}


@app.get("/api/workspaces/{workspace_id}/credit-ledger")
def credit_ledger(workspace_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    require_workspace_access(_, workspace_id)
    entries = [e for e in store.credit_ledger if e.workspace_id == workspace_id]
    return {"entries": serialize(entries)}


@app.post("/api/workspaces/{workspace_id}/billing/checkout-sessions")
def create_billing_checkout(
    workspace_id: str,
    payload: BillingCheckoutCreate,
    user_id: str = Depends(current_user_id),
) -> dict[str, object]:
    require_workspace_role(user_id, workspace_id, WORKSPACE_ADMIN_ROLES)
    try:
        session = BillingService(store).create_checkout_session(
            workspace_id=workspace_id,
            credit_amount=payload.credit_amount,
            billing_email=payload.billing_email,
            provider=payload.provider,
            unit_amount_cents=payload.unit_amount_cents,
        )
        AuditService(store).record(
            AuditAction.BILLING_CHECKOUT_CREATED,
            actor_user_id=user_id,
            workspace_id=workspace_id,
            details={"checkout_session_id": session.id, "credit_amount": session.credit_amount},
        )
    except Exception as exc:
        handle_error(exc)
    return {"checkout_session": serialize(session)}


@app.post("/api/billing/checkout-sessions/{checkout_session_id}/confirm")
def confirm_billing_checkout(
    checkout_session_id: str,
    payload: dict[str, str],
    user_id: str = Depends(current_user_id),
) -> dict[str, object]:
    session = store.get(store.billing_checkout_sessions, checkout_session_id, "billing checkout session")
    require_workspace_role(user_id, session.workspace_id, WORKSPACE_ADMIN_ROLES)
    try:
        session, invoice, payment, ledger_entry = BillingService(store).confirm_checkout_session(
            checkout_session_id=checkout_session_id,
            provider_payment_id=payload.get("provider_payment_id"),
        )
        AuditService(store).record(
            AuditAction.BILLING_CHECKOUT_CONFIRMED,
            actor_user_id=user_id,
            workspace_id=session.workspace_id,
            details={
                "checkout_session_id": session.id,
                "invoice_id": invoice.id,
                "payment_id": payment.id,
                "credit_ledger_entry_id": ledger_entry.id,
            },
        )
    except Exception as exc:
        handle_error(exc)
    return {
        "checkout_session": serialize(session),
        "invoice": serialize(invoice),
        "payment": serialize(payment),
        "ledger_entry": serialize(ledger_entry),
        "credits": serialize(store.credit_accounts[session.workspace_id]),
    }


@app.post("/api/billing/webhooks")
def billing_webhook(
    payload: BillingWebhookPayload,
    x_kerislab_signature: str | None = Header(default=None),
) -> dict[str, object]:
    secret = os.getenv("KERISLAB_BILLING_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=400, detail="KERISLAB_BILLING_WEBHOOK_SECRET is required")
    body = payload.model_dump()
    signed_body = json.dumps(body, separators=(",", ":"), sort_keys=True).encode()
    expected = hmac.new(secret.encode(), signed_body, sha256).hexdigest()
    if not x_kerislab_signature or not hmac.compare_digest(x_kerislab_signature, expected):
        raise HTTPException(status_code=401, detail="Invalid billing webhook signature")
    try:
        event = BillingService(store).process_webhook_event(
            provider=payload.provider,
            provider_event_id=payload.provider_event_id,
            event_type=payload.event_type,
            payload=payload.data,
        )
        if event.processed:
            workspace_id = str(payload.data.get("workspace_id") or "")
            AuditService(store).record(
                AuditAction.BILLING_CHECKOUT_CONFIRMED,
                actor_user_id=None,
                workspace_id=workspace_id or None,
                details={"provider_event_id": payload.provider_event_id, "event_type": payload.event_type},
            )
    except Exception as exc:
        handle_error(exc)
    return {"event": serialize(event)}


@app.get("/api/projects")
def list_projects(workspace_id: str | None = None, _: str = Depends(current_user_id)) -> dict[str, object]:
    projects = list(store.projects.values())
    if workspace_id:
        require_workspace_access(_, workspace_id)
        projects = [project for project in projects if project.workspace_id == workspace_id]
    else:
        workspace_ids = {m.workspace_id for m in store.memberships.values() if m.user_id == _}
        projects = [project for project in projects if project.workspace_id in workspace_ids]
    return {"projects": serialize(projects)}


@app.get("/api/projects/{project_id}/targets")
def list_project_targets(project_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    project = store.get(store.projects, project_id, "project")
    require_workspace_access(_, project.workspace_id)
    targets = [target for target in store.targets.values() if target.project_id == project_id]
    return {"targets": serialize(targets)}


@app.post("/api/settings/llm/profiles")
def create_model_profile(payload: ModelProfileCreate, _: str = Depends(current_user_id)) -> dict[str, object]:
    require_workspace_role(_, payload.workspace_id, WORKSPACE_SECURITY_ROLES)
    try:
        profile = ModelProfileService(store).create_profile(**payload.model_dump())
        AuditService(store).record(
            AuditAction.MODEL_PROFILE_CREATED,
            actor_user_id=_,
            workspace_id=payload.workspace_id,
            details={"profile_id": profile.id, "model": profile.model},
        )
    except Exception as exc:
        handle_error(exc)
    return {"profile": serialize(profile)}


@app.post("/api/settings/llm/profiles/{profile_id}/test")
def test_model_profile(profile_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        profile = store.get(store.model_profiles, profile_id, "model profile")
        require_workspace_role(_, profile.workspace_id, WORKSPACE_SECURITY_ROLES)
        result = ModelProfileService(store).test_profile(profile_id)
        AuditService(store).record(
            AuditAction.MODEL_PROFILE_TESTED,
            actor_user_id=_,
            workspace_id=profile.workspace_id,
            details={"profile_id": profile_id},
        )
    except Exception as exc:
        handle_error(exc)
    return result


@app.post("/api/projects")
def create_project(payload: ProjectCreate, _: str = Depends(current_user_id)) -> dict[str, object]:
    require_workspace_access(_, payload.workspace_id)
    project = ProjectService(store).create_project(workspace_id=payload.workspace_id, name=payload.name)
    AuditService(store).record(
        AuditAction.PROJECT_CREATED,
        actor_user_id=_,
        workspace_id=payload.workspace_id,
        project_id=project.id,
        details={"name": project.name},
    )
    return {"project": serialize(project)}


@app.post("/api/targets")
def create_target(payload: TargetCreate, _: str = Depends(current_user_id)) -> dict[str, object]:
    require_workspace_access(_, payload.workspace_id)
    try:
        target = ProjectService(store).create_target(**payload.model_dump())
        AuditService(store).record(
            AuditAction.TARGET_CREATED,
            actor_user_id=_,
            workspace_id=payload.workspace_id,
            project_id=payload.project_id,
            target_id=target.id,
            details={"name": target.name, "url": target.url},
        )
    except Exception as exc:
        handle_error(exc)
    return {"target": serialize(target)}


@app.post("/api/scans")
def create_scan(payload: ScanCreate, _: str = Depends(current_user_id)) -> dict[str, object]:
    require_workspace_access(_, payload.workspace_id)
    try:
        scan = ScanService(store).create_scan(**payload.model_dump())
        AuditService(store).record(
            AuditAction.SCAN_CREATED,
            actor_user_id=_,
            workspace_id=payload.workspace_id,
            project_id=payload.project_id,
            target_id=payload.target_id,
            scan_id=scan.id,
            details={"scan_type": payload.scan_type},
        )
        job_type = ScanJobType.PASSIVE_SCAN if payload.scan_type == ScanType.PASSIVE_BLACKBOX else None
        if job_type is not None:
            get_execution_engine().enqueue(scan.id, job_type)
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan), "credits": serialize(store.credit_accounts[payload.workspace_id])}


@app.get("/api/scans/{scan_id}")
def get_scan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    scan = AuthorizationService(store).require_scan_access(_, scan_id)
    return {"scan": serialize(scan)}


@app.get("/api/execution/jobs")
def execution_jobs(_: str = Depends(current_user_id)) -> dict[str, object]:
    engine = get_execution_engine()
    workspace_ids = {m.workspace_id for m in store.memberships.values() if m.user_id == _}
    jobs = [j for j in store.scan_jobs.values() if store.scans[j.scan_id].workspace_id in workspace_ids]
    pending = [j for j in engine.pending_jobs() if store.scans[j.scan_id].workspace_id in workspace_ids]
    return {"jobs": serialize(jobs), "pending": serialize(pending)}


@app.get("/api/audit-logs")
def audit_logs(
    workspace_id: str | None = None,
    actor_user_id: str | None = None,
    action: str | None = None,
    _: str = Depends(current_user_id),
) -> dict[str, object]:
    if workspace_id:
        require_workspace_access(_, workspace_id)
        entries = AuditService(store).list(workspace_id=workspace_id, actor_user_id=actor_user_id, action=action)
    else:
        workspace_ids = {m.workspace_id for m in store.memberships.values() if m.user_id == _}
        entries = [
            entry
            for entry in AuditService(store).list(actor_user_id=actor_user_id, action=action)
            if entry.workspace_id is None or entry.workspace_id in workspace_ids
        ]
    return {"entries": serialize(entries)}


@app.post("/api/execution/drain")
def drain_execution_jobs(_: str = Depends(current_user_id)) -> dict[str, object]:
    engine = get_execution_engine()
    engine.drain()
    workspace_ids = {m.workspace_id for m in store.memberships.values() if m.user_id == _}
    jobs = [j for j in store.scan_jobs.values() if store.scans[j.scan_id].workspace_id in workspace_ids]
    return {"jobs": serialize(jobs)}


@app.post("/api/scans/{scan_id}/run-passive")
def run_passive(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
    try:
        scan = ScanService(store).run_passive_scan(scan_id)
        AuditService(store).record(AuditAction.SCAN_EXECUTED, actor_user_id=_, workspace_id=scan.workspace_id, scan_id=scan.id)
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan)}


@app.post("/api/scans/{scan_id}/pause")
def pause_scan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
    try:
        scan = ScanService(store).pause_scan(scan_id)
        AuditService(store).record(AuditAction.SCAN_PAUSED, actor_user_id=_, workspace_id=scan.workspace_id, scan_id=scan.id)
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan)}


@app.post("/api/scans/{scan_id}/resume")
def resume_scan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
    try:
        scan = ScanService(store).resume_scan(scan_id)
        AuditService(store).record(AuditAction.SCAN_RESUMED, actor_user_id=_, workspace_id=scan.workspace_id, scan_id=scan.id)
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan)}


@app.post("/api/scans/{scan_id}/instructions")
def update_scan_instructions(scan_id: str, payload: dict[str, str], _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
    try:
        scan = ScanService(store).update_instructions(scan_id, payload.get("instructions", ""))
        AuditService(store).record(
            AuditAction.SCAN_INSTRUCTIONS_UPDATED,
            actor_user_id=_,
            workspace_id=scan.workspace_id,
            scan_id=scan.id,
        )
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan)}


@app.post("/api/scans/{scan_id}/complete")
def complete_scan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
    try:
        scan = ScanService(store).complete_scan(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan), "credits": serialize(store.credit_accounts[scan.workspace_id])}


@app.post("/api/scans/{scan_id}/fail")
def fail_scan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
    try:
        scan = ScanService(store).fail_scan(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan), "credits": serialize(store.credit_accounts[scan.workspace_id])}


@app.post("/api/scans/{scan_id}/cancel")
def cancel_scan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
    try:
        scan = ScanService(store).cancel_scan(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"scan": serialize(scan), "credits": serialize(store.credit_accounts[scan.workspace_id])}


@app.post("/api/scans/{scan_id}/start-autonomous")
def start_autonomous(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
    try:
        plan = AutonomousPentestService(store).start(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"plan": serialize(plan), "scan": serialize(store.scans[scan_id])}


@app.get("/api/scans/{scan_id}/browser-plan")
def browser_plan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
    try:
        plan = AutonomousPentestService(store).browser_plan(scan_id)
    except Exception as exc:
        handle_error(exc)
    return {"browser_plan": serialize(plan)}


@app.post("/api/scans/{scan_id}/browser-plan/execute")
def execute_browser_plan(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    scan = AuthorizationService(store).require_scan_access(_, scan_id)
    try:
        result = BrowserExecutionService(store).execute(scan_id)
        AuditService(store).record(
            AuditAction.SCAN_EXECUTED,
            actor_user_id=_,
            workspace_id=scan.workspace_id,
            scan_id=scan.id,
            details={"engine": result.get("engine"), "mode": "browser"},
        )
    except Exception as exc:
        handle_error(exc)
    return {"result": serialize(result)}


@app.get("/api/scans/{scan_id}/evidence")
def scan_evidence(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
    evidence = [artifact for artifact in store.evidence_artifacts.values() if artifact.scan_id == scan_id]
    return {"evidence": serialize(evidence)}


@app.post("/api/scans/{scan_id}/approvals/request-upload-verification")
def request_upload_verification(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    scan = AuthorizationService(store).require_scan_access(_, scan_id)
    try:
        request = AutonomousPentestService(store).request_gated_upload_verification(scan_id)
        AuditService(store).record(
            AuditAction.APPROVAL_REQUESTED,
            actor_user_id=_,
            workspace_id=scan.workspace_id,
            scan_id=scan_id,
            approval_id=request.id,
        )
    except Exception as exc:
        handle_error(exc)
    return {"approval": serialize(request), "scan": serialize(store.scans[scan_id])}


@app.get("/api/scans/{scan_id}/approvals")
def scan_approvals(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
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
        AuditService(store).record(
            AuditAction.APPROVAL_RESOLVED,
            actor_user_id=user_id,
            workspace_id=request.workspace_id,
            scan_id=request.scan_id,
            approval_id=request.id,
            details={"status": request.status},
        )
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
        AuditService(store).record(
            AuditAction.APPROVAL_RESOLVED,
            actor_user_id=user_id,
            workspace_id=request.workspace_id,
            scan_id=request.scan_id,
            approval_id=request.id,
            details={"status": request.status},
        )
    except Exception as exc:
        handle_error(exc)
    return {"approval": serialize(request)}


@app.get("/api/scans/{scan_id}/events")
def scan_events(scan_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    AuthorizationService(store).require_scan_access(_, scan_id)
    return {"events": serialize([e for e in store.events if e.scan_id == scan_id])}


@app.get("/api/findings")
def findings(scan_id: str | None = None, _: str = Depends(current_user_id)) -> dict[str, object]:
    values = list(store.findings.values())
    if scan_id:
        AuthorizationService(store).require_scan_access(_, scan_id)
        values = [f for f in values if f.scan_id == scan_id]
    else:
        workspace_ids = {m.workspace_id for m in store.memberships.values() if m.user_id == _}
        scan_ids = {s.id for s in store.scans.values() if s.workspace_id in workspace_ids}
        values = [f for f in values if f.scan_id in scan_ids]
    return {"findings": serialize(values)}


@app.get("/api/findings/{finding_id}")
def finding_detail(finding_id: str, _: str = Depends(current_user_id)) -> dict[str, object]:
    finding = ReportService(store).get_finding(finding_id)
    AuthorizationService(store).require_scan_access(_, finding.scan_id)
    return {"finding": serialize(finding)}


@app.post("/api/reports")
def create_report(payload: dict[str, str], _: str = Depends(current_user_id)) -> dict[str, object]:
    try:
        scan = AuthorizationService(store).require_scan_access(_, payload["scan_id"])
        report = ReportService(store).generate_json_report(payload["scan_id"])
        AuditService(store).record(
            AuditAction.REPORT_GENERATED,
            actor_user_id=_,
            workspace_id=scan.workspace_id,
            project_id=scan.project_id,
            scan_id=scan.id,
            report_id=report.id,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail="scan_id is required") from exc
    except Exception as exc:
        handle_error(exc)
    return {"report": serialize(report)}


@app.get("/api/reports/{report_id}/download")
def download_report(report_id: str, _: str = Depends(current_user_id)):
    report = ReportService(store).get_report(report_id)
    AuthorizationService(store).require_scan_access(_, report.scan_id)
    return JSONResponse(content=serialize(report.content))
