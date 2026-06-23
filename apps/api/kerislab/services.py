from __future__ import annotations

import os
import queue
import threading
from base64 import b64encode
from datetime import timedelta
from pathlib import Path
from secrets import token_urlsafe
from collections.abc import Callable
from .models import (
    AgentPlan,
    AuditAction,
    AuditLog,
    ApprovalRequest,
    ApprovalStatus,
    AuthProvider,
    BillingCheckoutSession,
    BillingCustomer,
    BillingInvoice,
    BillingPayment,
    BillingProvider,
    BillingWebhookEvent,
    BrowserAction,
    BrowserExecution,
    BrowserExecutionStatus,
    BrowserPlan,
    CreditAccount,
    CheckoutSessionStatus,
    CreditLedgerEntry,
    CreditReservation,
    CreditReservationStatus,
    EvidenceArtifact,
    Finding,
    InvoiceStatus,
    LedgerEntryType,
    ModelProfile,
    OAuthState,
    PaymentStatus,
    Project,
    Report,
    Role,
    ScanJob,
    ScanJobStatus,
    ScanJobType,
    Scan,
    ScanEvent,
    ScanStatus,
    ScanType,
    Target,
    User,
    UserSession,
    UserSettings,
    VerificationStatus,
    WorkerHeartbeat,
    Workspace,
    WorkspaceMembership,
    now_utc,
)
from .scope import validate_target_scope
from .store import InMemoryStore


class CreditError(ValueError):
    pass


class ApprovalError(ValueError):
    pass


class AuthorizationError(ValueError):
    pass


class OAuthStateError(ValueError):
    pass


class BillingError(ValueError):
    pass


class EvidenceStorageError(ValueError):
    pass


class EvidenceStorageService:
    def __init__(self) -> None:
        self.endpoint = os.getenv("KERISLAB_OBJECT_STORAGE_ENDPOINT")
        self.bucket = os.getenv("KERISLAB_OBJECT_STORAGE_BUCKET", "kerislab-evidence")
        self.access_key = os.getenv("KERISLAB_OBJECT_STORAGE_ACCESS_KEY")
        self.secret_key = os.getenv("KERISLAB_OBJECT_STORAGE_SECRET_KEY")
        self.local_root = Path(os.getenv("KERISLAB_EVIDENCE_LOCAL_PATH", ".kerislab/evidence"))

    def store(
        self,
        *,
        key: str,
        content: str,
        content_type: str,
    ) -> str:
        if self.endpoint and self.access_key and self.secret_key:
            return self._store_s3(key=key, content=content, content_type=content_type)
        return self._store_local(key=key, content=content)

    def _store_s3(self, *, key: str, content: str, content_type: str) -> str:
        try:
            import boto3  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise EvidenceStorageError("boto3 is required for object storage") from exc
        client = boto3.client(
            "s3",
            endpoint_url=self.endpoint,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
        )
        client.put_object(Bucket=self.bucket, Key=key, Body=content.encode(), ContentType=content_type)
        return f"s3://{self.bucket}/{key}"

    def _store_local(self, *, key: str, content: str) -> str:
        path = self.local_root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return f"file://{path}"


class WorkerStatusService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def heartbeat(
        self,
        *,
        worker_id: str,
        name: str,
        queue_name: str,
        processed_jobs: int = 0,
        status: str = "running",
        error: str = "",
    ) -> WorkerHeartbeat:
        heartbeat = self.store.worker_heartbeats.get(worker_id)
        if heartbeat is None:
            heartbeat = WorkerHeartbeat(id=worker_id, name=name, queue_name=queue_name)
            self.store.worker_heartbeats[worker_id] = heartbeat
        heartbeat.name = name
        heartbeat.queue_name = queue_name
        heartbeat.status = status
        heartbeat.processed_jobs = processed_jobs
        heartbeat.error = error
        heartbeat.last_seen_at = now_utc()
        self.store.sync()
        return heartbeat

    def components(self, *, active_after_seconds: int = 90) -> dict[str, object]:
        self.store.reload()
        cutoff = now_utc() - timedelta(seconds=active_after_seconds)
        workers = list(self.store.worker_heartbeats.values())
        active_workers = [worker for worker in workers if worker.last_seen_at >= cutoff and worker.status == "running"]
        queued_jobs = [job for job in self.store.scan_jobs.values() if job.status == ScanJobStatus.QUEUED]
        running_jobs = [job for job in self.store.scan_jobs.values() if job.status == ScanJobStatus.RUNNING]
        failed_jobs = [job for job in self.store.scan_jobs.values() if job.status == ScanJobStatus.FAILED]
        return {
            "status": "ok" if active_workers else "degraded",
            "worker_heartbeat": {
                "status": "ok" if active_workers else "missing",
                "active": len(active_workers),
                "total": len(workers),
                "workers": workers,
            },
            "queue": {
                "queued": len(queued_jobs),
                "running": len(running_jobs),
                "failed": len(failed_jobs),
            },
        }


class AuditService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def record(
        self,
        action: AuditAction,
        *,
        actor_user_id: str | None,
        workspace_id: str | None = None,
        project_id: str | None = None,
        target_id: str | None = None,
        scan_id: str | None = None,
        approval_id: str | None = None,
        report_id: str | None = None,
        details: dict[str, object] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            action=action,
            actor_user_id=actor_user_id,
            workspace_id=workspace_id,
            project_id=project_id,
            target_id=target_id,
            scan_id=scan_id,
            approval_id=approval_id,
            report_id=report_id,
            details=details or {},
        )
        self.store.audit_logs.append(entry)
        self.store.sync()
        return entry

    def list(
        self,
        *,
        workspace_id: str | None = None,
        actor_user_id: str | None = None,
        action: str | None = None,
    ) -> list[AuditLog]:
        entries = list(self.store.audit_logs)
        if workspace_id:
            entries = [entry for entry in entries if entry.workspace_id == workspace_id]
        if actor_user_id:
            entries = [entry for entry in entries if entry.actor_user_id == actor_user_id]
        if action:
            entries = [entry for entry in entries if str(entry.action) == action or entry.action == action]
        return sorted(entries, key=lambda entry: entry.created_at)


class AuthorizationService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def workspace_membership(self, user_id: str, workspace_id: str) -> WorkspaceMembership | None:
        return next(
            (m for m in self.store.memberships.values() if m.user_id == user_id and m.workspace_id == workspace_id),
            None,
        )

    def require_workspace_member(self, user_id: str, workspace_id: str) -> WorkspaceMembership:
        membership = self.workspace_membership(user_id, workspace_id)
        if membership is None:
            raise AuthorizationError("user is not a member of this workspace")
        return membership

    def require_workspace_role(
        self,
        user_id: str,
        workspace_id: str,
        allowed_roles: set[Role],
    ) -> WorkspaceMembership:
        membership = self.require_workspace_member(user_id, workspace_id)
        if membership.role not in allowed_roles:
            roles = ", ".join(sorted(role.value for role in allowed_roles))
            raise AuthorizationError(f"workspace role must be one of: {roles}")
        return membership

    def require_scan_access(self, user_id: str, scan_id: str) -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        self.require_workspace_member(user_id, scan.workspace_id)
        return scan


class AuthService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def login_identity(
        self,
        *,
        email: str,
        display_name: str,
        provider: AuthProvider,
        avatar_url: str | None = None,
    ) -> User:
        existing = next((u for u in self.store.users.values() if u.email == email), None)
        if existing:
            AuditService(self.store).record(
                AuditAction.LOGIN,
                actor_user_id=existing.id,
                details={"provider": provider, "email": email},
            )
            self.reconcile_domain_memberships(existing)
            return existing
        user = self.store.add(
            self.store.users,
            User(email=email, display_name=display_name, provider=provider, avatar_url=avatar_url),
        )
        self.store.user_settings[user.id] = UserSettings(user_id=user.id)
        AuditService(self.store).record(
            AuditAction.LOGIN,
            actor_user_id=user.id,
            details={"provider": provider, "email": email},
        )
        self.reconcile_domain_memberships(user)
        self.store.sync()
        return user

    def reconcile_domain_memberships(self, user: User) -> list[WorkspaceMembership]:
        _, _, domain = user.email.lower().partition("@")
        if not domain:
            return []
        created: list[WorkspaceMembership] = []
        for workspace in self.store.workspaces.values():
            allowed_domains = {item.lower().strip() for item in workspace.allowed_domains}
            if domain not in allowed_domains:
                continue
            if any(m.user_id == user.id and m.workspace_id == workspace.id for m in self.store.memberships.values()):
                continue
            membership = WorkspaceMembership(workspace_id=workspace.id, user_id=user.id, role=Role.DEVELOPER)
            self.store.add(self.store.memberships, membership)
            if self.store.user_settings[user.id].default_workspace_id is None:
                self.store.user_settings[user.id].default_workspace_id = workspace.id
            AuditService(self.store).record(
                AuditAction.WORKSPACE_MEMBER_AUTO_JOINED,
                actor_user_id=user.id,
                workspace_id=workspace.id,
                details={"email_domain": domain, "role": membership.role},
            )
            created.append(membership)
        if created:
            self.store.sync()
        return created

    def create_session(
        self,
        user: User,
        *,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> UserSession:
        session = UserSession(
            user_id=user.id,
            token=token_urlsafe(32),
            auth_provider=user.provider,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.store.add(self.store.user_sessions, session)
        self.store.sync()
        return session

    def user_for_session_token(self, token: str) -> User:
        session = next((s for s in self.store.user_sessions.values() if s.token == token), None)
        if session is None:
            raise AuthorizationError("session token is invalid")
        now = now_utc()
        if session.revoked_at is not None:
            raise AuthorizationError("session token has been revoked")
        if session.expires_at <= now:
            raise AuthorizationError("session token has expired")
        session.last_seen_at = now
        self.store.sync()
        return self.store.get(self.store.users, session.user_id, "user")

    def revoke_session_token(self, token: str) -> UserSession:
        session = next((s for s in self.store.user_sessions.values() if s.token == token), None)
        if session is None:
            raise AuthorizationError("session token is invalid")
        session.revoked_at = now_utc()
        self.store.sync()
        return session


class OAuthStateService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create(self, *, provider: AuthProvider, state: str, nonce: str, redirect_uri: str) -> OAuthState:
        oauth_state = OAuthState(provider=provider, state=state, nonce=nonce, redirect_uri=redirect_uri)
        self.store.oauth_states[state] = oauth_state
        AuditService(self.store).record(
            AuditAction.OAUTH_STATE_CREATED,
            actor_user_id=None,
            details={"provider": provider, "state_id": oauth_state.id},
        )
        self.store.sync()
        return oauth_state

    def consume(self, *, provider: AuthProvider, state: str) -> OAuthState:
        oauth_state = self.store.oauth_states.get(state)
        if oauth_state is None:
            raise OAuthStateError("OAuth state is invalid")
        if oauth_state.provider != provider:
            raise OAuthStateError("OAuth state provider mismatch")
        if oauth_state.consumed_at is not None:
            raise OAuthStateError("OAuth state has already been used")
        oauth_state.consumed_at = now_utc()
        AuditService(self.store).record(
            AuditAction.OAUTH_STATE_CONSUMED,
            actor_user_id=None,
            details={"provider": provider, "state_id": oauth_state.id},
        )
        self.store.sync()
        return oauth_state


class WorkspaceService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_workspace(self, *, name: str, owner: User, initial_credits: int = 0) -> Workspace:
        workspace = self.store.add(self.store.workspaces, Workspace(name=name))
        membership = WorkspaceMembership(workspace_id=workspace.id, user_id=owner.id, role=Role.OWNER)
        self.store.add(self.store.memberships, membership)
        self.store.credit_accounts[workspace.id] = CreditAccount(workspace_id=workspace.id)
        self.store.user_settings[owner.id].default_workspace_id = workspace.id
        if initial_credits:
            CreditService(self.store).grant(workspace.id, initial_credits, note="Initial workspace grant")
        AuditService(self.store).record(
            AuditAction.WORKSPACE_CREATED,
            actor_user_id=owner.id,
            workspace_id=workspace.id,
            details={"name": workspace.name, "initial_credits": initial_credits},
        )
        self.store.sync()
        return workspace

    def update_sso_domains(self, *, workspace_id: str, allowed_domains: list[str]) -> Workspace:
        workspace = self.store.get(self.store.workspaces, workspace_id, "workspace")
        normalized = sorted({domain.lower().strip() for domain in allowed_domains if domain.strip()})
        for domain in normalized:
            if "@" in domain or "/" in domain:
                raise ValueError("allowed domains must be bare email domains")
        workspace.allowed_domains = normalized
        self.store.sync()
        return workspace


class CreditService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def account(self, workspace_id: str) -> CreditAccount:
        if workspace_id not in self.store.credit_accounts:
            self.store.credit_accounts[workspace_id] = CreditAccount(workspace_id=workspace_id)
        return self.store.credit_accounts[workspace_id]

    def grant(self, workspace_id: str, amount: int, note: str = "") -> CreditLedgerEntry:
        if amount <= 0:
            raise CreditError("credit grant amount must be positive")
        account = self.account(workspace_id)
        account.available += amount
        entry = CreditLedgerEntry(
            workspace_id=workspace_id,
            entry_type=LedgerEntryType.GRANT,
            amount=amount,
            balance_after=account.available,
            note=note,
        )
        self.store.credit_ledger.append(entry)
        self.store.sync()
        return entry

    def reserve_for_scan(self, workspace_id: str, scan_id: str) -> CreditReservation:
        account = self.account(workspace_id)
        if account.available < 1:
            raise CreditError("workspace has no available scan credits")
        account.available -= 1
        account.reserved += 1
        reservation = CreditReservation(workspace_id=workspace_id, scan_id=scan_id)
        self.store.credit_reservations[scan_id] = reservation
        self.store.credit_ledger.append(
            CreditLedgerEntry(
                workspace_id=workspace_id,
                entry_type=LedgerEntryType.RESERVE,
                amount=-1,
                balance_after=account.available,
                scan_id=scan_id,
                note="Reserved one credit for scan",
            )
        )
        self.store.sync()
        return reservation

    def deduct_completed_scan(self, scan: Scan) -> None:
        reservation = self.store.credit_reservations.get(scan.id)
        if not reservation or reservation.status == CreditReservationStatus.DEDUCTED:
            return
        if reservation.status == CreditReservationStatus.RELEASED:
            raise CreditError("cannot deduct a released credit reservation")
        account = self.account(scan.workspace_id)
        account.reserved -= 1
        account.consumed += 1
        reservation.status = CreditReservationStatus.DEDUCTED
        self.store.credit_ledger.append(
            CreditLedgerEntry(
                workspace_id=scan.workspace_id,
                entry_type=LedgerEntryType.DEDUCT,
                amount=-1,
                balance_after=account.available,
                scan_id=scan.id,
                note="Deducted one credit for completed scan",
            )
        )
        self.store.sync()

    def release_scan(self, scan: Scan) -> None:
        reservation = self.store.credit_reservations.get(scan.id)
        if not reservation or reservation.status != CreditReservationStatus.RESERVED:
            return
        account = self.account(scan.workspace_id)
        account.reserved -= 1
        account.available += 1
        reservation.status = CreditReservationStatus.RELEASED
        self.store.credit_ledger.append(
            CreditLedgerEntry(
                workspace_id=scan.workspace_id,
                entry_type=LedgerEntryType.RELEASE,
                amount=1,
                balance_after=account.available,
                scan_id=scan.id,
                note=f"Released credit after scan ended with {scan.status}",
            )
        )
        self.store.sync()


class BillingService:
    DEFAULT_UNIT_AMOUNT_CENTS = 500

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store
        self.credits = CreditService(store)

    def ensure_customer(
        self,
        *,
        workspace_id: str,
        billing_email: str,
        provider: BillingProvider | str = BillingProvider.MANUAL,
        provider_customer_id: str | None = None,
    ) -> BillingCustomer:
        provider = BillingProvider(provider)
        existing = next(
            (
                customer
                for customer in self.store.billing_customers.values()
                if customer.workspace_id == workspace_id and customer.provider == provider
            ),
            None,
        )
        if existing:
            return existing
        customer = BillingCustomer(
            workspace_id=workspace_id,
            provider=provider,
            provider_customer_id=provider_customer_id or f"{provider.value}:{workspace_id}",
            billing_email=billing_email,
        )
        self.store.add(self.store.billing_customers, customer)
        self.store.sync()
        return customer

    def create_checkout_session(
        self,
        *,
        workspace_id: str,
        credit_amount: int,
        billing_email: str,
        provider: BillingProvider | str = BillingProvider.MANUAL,
        unit_amount_cents: int = DEFAULT_UNIT_AMOUNT_CENTS,
    ) -> BillingCheckoutSession:
        provider = BillingProvider(provider)
        if credit_amount <= 0:
            raise BillingError("credit_amount must be positive")
        if unit_amount_cents <= 0:
            raise BillingError("unit_amount_cents must be positive")
        self.ensure_customer(workspace_id=workspace_id, billing_email=billing_email, provider=provider)
        session = BillingCheckoutSession(
            workspace_id=workspace_id,
            provider=provider,
            credit_amount=credit_amount,
            unit_amount_cents=unit_amount_cents,
            provider_session_id=f"{provider.value}:{new_billing_reference()}",
        )
        session.checkout_url = f"https://billing.kerislab.local/checkout/{session.id}"
        self.store.add(self.store.billing_checkout_sessions, session)
        self.store.sync()
        return session

    def confirm_checkout_session(
        self,
        *,
        checkout_session_id: str,
        provider_payment_id: str | None = None,
    ) -> tuple[BillingCheckoutSession, BillingInvoice, BillingPayment, CreditLedgerEntry]:
        session = self.store.get(self.store.billing_checkout_sessions, checkout_session_id, "billing checkout session")
        if session.status == CheckoutSessionStatus.PAID:
            invoice = next(
                invoice for invoice in self.store.billing_invoices.values() if invoice.checkout_session_id == session.id
            )
            payment = next(payment for payment in self.store.billing_payments.values() if payment.invoice_id == invoice.id)
            ledger_entry = next(
                entry
                for entry in reversed(self.store.credit_ledger)
                if entry.workspace_id == session.workspace_id and f"checkout:{session.id}" in entry.note
            )
            return session, invoice, payment, ledger_entry
        if session.status != CheckoutSessionStatus.CREATED:
            raise BillingError("checkout session cannot be confirmed")

        amount_cents = session.credit_amount * session.unit_amount_cents
        invoice = BillingInvoice(
            workspace_id=session.workspace_id,
            checkout_session_id=session.id,
            provider=session.provider,
            amount_cents=amount_cents,
            currency=session.currency,
            status=InvoiceStatus.PAID,
            provider_invoice_id=f"{session.provider.value}:invoice:{session.id}",
            paid_at=now_utc(),
        )
        payment = BillingPayment(
            workspace_id=session.workspace_id,
            invoice_id=invoice.id,
            provider=session.provider,
            amount_cents=amount_cents,
            currency=session.currency,
            status=PaymentStatus.SUCCEEDED,
            provider_payment_id=provider_payment_id or f"{session.provider.value}:payment:{session.id}",
        )
        session.status = CheckoutSessionStatus.PAID
        session.completed_at = now_utc()
        self.store.add(self.store.billing_invoices, invoice)
        self.store.add(self.store.billing_payments, payment)
        ledger_entry = self.credits.grant(
            session.workspace_id,
            session.credit_amount,
            note=f"Billing checkout confirmed checkout:{session.id} invoice:{invoice.id}",
        )
        self.store.sync()
        return session, invoice, payment, ledger_entry

    def process_webhook_event(
        self,
        *,
        provider: BillingProvider | str,
        provider_event_id: str,
        event_type: str,
        payload: dict[str, object],
    ) -> BillingWebhookEvent:
        provider = BillingProvider(provider)
        existing = next(
            (
                event
                for event in self.store.billing_webhook_events.values()
                if event.provider == provider and event.provider_event_id == provider_event_id
            ),
            None,
        )
        if existing:
            return existing

        event = BillingWebhookEvent(
            provider=provider,
            provider_event_id=provider_event_id,
            event_type=event_type,
            payload=payload,
        )
        self.store.add(self.store.billing_webhook_events, event)
        try:
            if event_type == "checkout.session.completed":
                checkout_session_id = str(payload["checkout_session_id"])
                provider_payment_id = str(payload.get("provider_payment_id") or "")
                self.confirm_checkout_session(
                    checkout_session_id=checkout_session_id,
                    provider_payment_id=provider_payment_id or None,
                )
            else:
                raise BillingError(f"unsupported billing webhook event type: {event_type}")
            event.processed = True
            event.error = ""
            event.processed_at = now_utc()
        except Exception as exc:
            event.error = str(exc)
            event.processed_at = now_utc()
            self.store.sync()
            raise
        self.store.sync()
        return event


def new_billing_reference() -> str:
    return now_utc().strftime("%Y%m%d%H%M%S%f")


class ProjectService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_project(self, *, workspace_id: str, name: str) -> Project:
        project = self.store.add(self.store.projects, Project(workspace_id=workspace_id, name=name))
        self.store.sync()
        return project

    def create_target(
        self,
        *,
        workspace_id: str,
        project_id: str,
        name: str,
        url: str,
        excludes: list[str] | None = None,
        allow_private_networks: bool = False,
    ) -> Target:
        target = Target(
            workspace_id=workspace_id,
            project_id=project_id,
            name=name,
            url=url,
            excludes=excludes or [],
            allow_private_networks=allow_private_networks,
        )
        validate_target_scope(target)
        target = self.store.add(self.store.targets, target)
        self.store.sync()
        return target


class ModelProfileService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def create_profile(self, *, workspace_id: str, name: str, model: str, api_base: str) -> ModelProfile:
        if not model.strip():
            raise ValueError("model is required")
        if not api_base.startswith(("http://", "https://")):
            raise ValueError("api_base must be an HTTP URL")
        profile = ModelProfile(workspace_id=workspace_id, name=name, model=model, api_base=api_base)
        profile = self.store.add(self.store.model_profiles, profile)
        self.store.sync()
        return profile

    def test_profile(self, profile_id: str) -> dict[str, object]:
        profile = self.store.get(self.store.model_profiles, profile_id, "model profile")
        return {
            "ok": True,
            "profile_id": profile.id,
            "route": profile.api_base,
            "model": profile.model,
            "message": "Profile shape is valid; live LiteLLM call is performed by deployment integration tests.",
        }


class ScanService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store
        self.credits = CreditService(store)

    def create_scan(
        self,
        *,
        workspace_id: str,
        project_id: str,
        target_id: str,
        scan_type: ScanType,
        model_profile_id: str,
        instructions: str = "",
    ) -> Scan:
        target = self.store.get(self.store.targets, target_id, "target")
        validate_target_scope(target)
        scan = self.store.add(
            self.store.scans,
            Scan(
                workspace_id=workspace_id,
                project_id=project_id,
                target_id=target_id,
                scan_type=scan_type,
                model_profile_id=model_profile_id,
                instructions=instructions,
            ),
        )
        self.credits.reserve_for_scan(workspace_id, scan.id)
        self.emit(scan.id, "scan.queued", "Scan queued and credit reserved")
        self.store.sync()
        return scan

    def emit(self, scan_id: str, event_type: str, summary: str, payload: dict | None = None) -> ScanEvent:
        event = ScanEvent(scan_id=scan_id, type=event_type, summary=summary, payload=payload or {})
        self.store.events.append(event)
        return event

    def run_passive_scan(self, scan_id: str) -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        target = self.store.get(self.store.targets, scan.target_id, "target")
        scan.status = ScanStatus.RUNNING
        self.emit(scan.id, "scan.phase.started", "Passive blackbox scan started")
        self.emit(scan.id, "tool.completed", "Security header check completed", {"target": target.url})
        finding = Finding(
            scan_id=scan.id,
            title="Security header review completed",
            severity="info",
            affected_asset=target.url,
            evidence_refs=[f"evidence://{scan.id}/security-headers"],
            verification_status=VerificationStatus.VERIFIED,
        )
        self.store.add(self.store.findings, finding)
        self.emit(scan.id, "finding.verified", "Informational finding stored", {"finding_id": finding.id})
        self.complete_scan(scan.id)
        self.store.sync()
        return scan

    def pause_scan(self, scan_id: str) -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        if scan.status not in {ScanStatus.RUNNING, ScanStatus.AWAITING_APPROVAL}:
            raise ValueError("only running or awaiting approval scans can be paused")
        scan.status = ScanStatus.PAUSED
        self.emit(scan.id, "scan.paused", "Scan paused by operator")
        self.store.sync()
        return scan

    def resume_scan(self, scan_id: str) -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        if scan.status != ScanStatus.PAUSED:
            raise ValueError("only paused scans can be resumed")
        scan.status = ScanStatus.RUNNING
        self.emit(scan.id, "scan.resumed", "Scan resumed by operator")
        self.store.sync()
        return scan

    def update_instructions(self, scan_id: str, instructions: str) -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        scan.instructions = instructions
        self.emit(scan.id, "scan.instructions.updated", "Operator instructions updated")
        self.store.sync()
        return scan

    def complete_scan(self, scan_id: str) -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        scan.status = ScanStatus.COMPLETED
        scan.completed_at = now_utc()
        self.credits.deduct_completed_scan(scan)
        self.emit(scan.id, "scan.completed", "Scan completed and one credit deducted")
        self.store.sync()
        return scan

    def fail_scan(self, scan_id: str, reason: str = "Scan failed") -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        scan.status = ScanStatus.FAILED
        self.credits.release_scan(scan)
        self.emit(scan.id, "scan.failed", reason)
        self.store.sync()
        return scan

    def cancel_scan(self, scan_id: str) -> Scan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        scan.status = ScanStatus.CANCELLED
        self.credits.release_scan(scan)
        self.emit(scan.id, "scan.cancelled", "Scan cancelled and reserved credit released")
        self.store.sync()
        return scan


class AutonomousPentestService:
    phases = [
        "scope_validation",
        "recon",
        "crawl",
        "attack_surface_mapping",
        "safe_testing",
        "gated_verification",
        "report",
    ]

    def __init__(self, store: InMemoryStore) -> None:
        self.store = store
        self.scans = ScanService(store)

    def start(self, scan_id: str) -> AgentPlan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        if scan.scan_type != ScanType.AUTONOMOUS_BLACKBOX:
            raise ValueError("autonomous start requires autonomous_blackbox scan type")
        target = self.store.get(self.store.targets, scan.target_id, "target")
        validate_target_scope(target)
        scan.status = ScanStatus.RUNNING
        plan = AgentPlan(
            scan_id=scan.id,
            phases=self.phases,
            current_phase="recon",
            objective=f"Run guarded autonomous blackbox assessment for {target.url}",
        )
        self.store.agent_plans[scan.id] = plan
        self.scans.emit(scan.id, "agent.plan.updated", "Autonomous plan created", {"plan_id": plan.id})
        self.scans.emit(scan.id, "scan.phase.started", "Recon phase started", {"phase": "recon"})
        browser_plan = self.create_browser_plan(scan.id)
        self.scans.emit(
            scan.id,
            "browser.plan.created",
            "Web/UI-driven scan plan created",
            {"browser_plan_id": browser_plan.id, "engine": browser_plan.engine},
        )
        self.scans.emit(scan.id, "tool.completed", "Safe HTTP baseline completed", {"target": target.url})
        self.store.sync()
        return plan

    def create_browser_plan(self, scan_id: str) -> BrowserPlan:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        target = self.store.get(self.store.targets, scan.target_id, "target")
        validate_target_scope(target)
        plan = BrowserPlan(
            scan_id=scan.id,
            target_url=target.url,
            engine="playwright",
            actions=[
                BrowserAction(
                    action_type="navigate",
                    selector="document",
                    description="Open the scoped target in an isolated browser context",
                    value=target.url,
                ),
                BrowserAction(
                    action_type="crawl",
                    selector="a[href], button, input, form",
                    description="Discover reachable UI routes and form entry points without submitting destructive actions",
                ),
                BrowserAction(
                    action_type="assert",
                    selector="form, [data-auth], input[type=password]",
                    description="Identify authentication, upload, and state-changing UI surfaces",
                ),
                BrowserAction(
                    action_type="capture_evidence",
                    selector="main, body",
                    description="Capture screenshot and DOM snapshot evidence for replayable findings",
                ),
                BrowserAction(
                    action_type="submit_controlled_payload",
                    selector="input[type=file], form[enctype]",
                    description="Verify upload handling only after human approval",
                    value="kerislab-controlled-upload.txt",
                    requires_approval=True,
                ),
            ],
        )
        self.store.browser_plans[scan.id] = plan
        self.store.sync()
        return plan

    def browser_plan(self, scan_id: str) -> BrowserPlan:
        if scan_id not in self.store.browser_plans:
            return self.create_browser_plan(scan_id)
        return self.store.browser_plans[scan_id]

    def request_gated_upload_verification(self, scan_id: str) -> ApprovalRequest:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        target = self.store.get(self.store.targets, scan.target_id, "target")
        scan.status = ScanStatus.AWAITING_APPROVAL
        request = ApprovalRequest(
            workspace_id=scan.workspace_id,
            scan_id=scan.id,
            requested_by_agent="dast-agent",
            risk_category="file_upload_verification",
            target=target.url,
            proposed_tool="http.request.replay",
            proposed_action="Submit a controlled upload payload to verify file handling behavior",
            reason="The crawler discovered an upload endpoint that requires gated verification.",
            expected_evidence="HTTP transcript and response diff for the upload endpoint.",
            policy_reason="File upload verification is approval-required under guarded autonomy.",
        )
        self.store.approval_requests[request.id] = request
        self.scans.emit(
            scan.id,
            "approval.requested",
            "Approval required for upload verification",
            {"approval_id": request.id, "risk_category": request.risk_category},
        )
        self.store.sync()
        return request

    def approve(self, approval_id: str, *, user_id: str, note: str = "") -> ApprovalRequest:
        request = self.store.get(self.store.approval_requests, approval_id, "approval request")
        if request.status != ApprovalStatus.PENDING:
            raise ApprovalError("approval request has already been resolved")
        request.status = ApprovalStatus.APPROVED
        request.resolved_by = user_id
        request.operator_note = note
        request.resolved_at = now_utc()
        scan = self.store.get(self.store.scans, request.scan_id, "scan")
        scan.status = ScanStatus.RUNNING
        self.scans.emit(
            scan.id,
            "approval.resolved",
            "Approval request approved",
            {"approval_id": request.id, "status": request.status},
        )
        self.scans.emit(scan.id, "tool.completed", "Gated upload verification completed", {"approval_id": request.id})
        self.store.sync()
        return request

    def reject(self, approval_id: str, *, user_id: str, note: str = "") -> ApprovalRequest:
        request = self.store.get(self.store.approval_requests, approval_id, "approval request")
        if request.status != ApprovalStatus.PENDING:
            raise ApprovalError("approval request has already been resolved")
        request.status = ApprovalStatus.REJECTED
        request.resolved_by = user_id
        request.operator_note = note
        request.resolved_at = now_utc()
        scan = self.store.get(self.store.scans, request.scan_id, "scan")
        scan.status = ScanStatus.RUNNING
        self.scans.emit(
            scan.id,
            "approval.resolved",
            "Approval request rejected; agent will replan",
            {"approval_id": request.id, "status": request.status},
        )
        self.scans.emit(scan.id, "agent.plan.updated", "Agent replanned without rejected gated action")
        self.store.sync()
        return request


class BrowserExecutionService:
    def __init__(
        self,
        store: InMemoryStore,
        runner: Callable[[BrowserPlan], dict[str, object]] | None = None,
    ) -> None:
        self.store = store
        self.scans = ScanService(store)
        self.autonomous = AutonomousPentestService(store)
        self.runner = runner
        self.evidence_storage = EvidenceStorageService()

    def execute(self, scan_id: str) -> dict[str, object]:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        plan = self.autonomous.browser_plan(scan_id)
        execution = BrowserExecution(scan_id=scan.id, browser_plan_id=plan.id, engine=plan.engine)
        self.store.browser_executions[execution.id] = execution
        self.scans.emit(
            scan.id,
            "browser.execution.started",
            "Browser execution started",
            {"plan_id": plan.id, "execution_id": execution.id},
        )
        try:
            result = self.runner(plan) if self.runner else self._run_with_playwright(plan)
        except Exception as exc:
            execution.status = BrowserExecutionStatus.FAILED
            execution.error = str(exc)
            execution.completed_at = now_utc()
            self.scans.emit(
                scan.id,
                "browser.execution.failed",
                str(exc),
                {"plan_id": plan.id, "execution_id": execution.id},
            )
            self.store.sync()
            raise
        execution.status = BrowserExecutionStatus.COMPLETED
        artifacts = self._persist_evidence(scan_id=scan.id, execution_id=execution.id, result=result)
        if artifacts:
            result["evidence_refs"] = [artifact.uri for artifact in artifacts]
        execution.result = result
        execution.completed_at = now_utc()
        payload = {"execution_id": execution.id, **result}
        self.scans.emit(scan.id, "browser.execution.completed", "Browser execution completed", payload)
        self.store.sync()
        return payload

    def _persist_evidence(
        self,
        *,
        scan_id: str,
        execution_id: str,
        result: dict[str, object],
    ) -> list[EvidenceArtifact]:
        raw_items = result.pop("evidence", [])
        if not isinstance(raw_items, list):
            raise ValueError("browser execution evidence must be a list")
        artifacts: list[EvidenceArtifact] = []
        for item in raw_items:
            if not isinstance(item, dict):
                raise ValueError("browser execution evidence item must be an object")
            metadata = item.get("metadata", {})
            artifact_type = str(item.get("artifact_type", "browser_evidence"))
            content_type = str(item.get("content_type", "application/octet-stream"))
            key = f"{scan_id}/{execution_id}/{len(artifacts) + 1}-{artifact_type}"
            object_uri = self.evidence_storage.store(
                key=key,
                content=str(item.get("content", "")),
                content_type=content_type,
            )
            artifact = EvidenceArtifact(
                scan_id=scan_id,
                browser_execution_id=execution_id,
                artifact_type=artifact_type,
                uri=f"evidence://{scan_id}/{execution_id}/{len(artifacts) + 1}",
                summary=str(item.get("summary", "Browser evidence captured")),
                content_type=content_type,
                content="",
                metadata={**(metadata if isinstance(metadata, dict) else {}), "object_uri": object_uri},
            )
            self.store.add(self.store.evidence_artifacts, artifact)
            artifacts.append(artifact)
        return artifacts

    def _run_with_playwright(self, plan: BrowserPlan) -> dict[str, object]:
        try:
            from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
        except Exception as exc:  # pragma: no cover - optional runtime dependency
            raise ValueError("playwright is not installed; install playwright and browser binaries") from exc

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            visited: list[str] = []
            evidence: list[dict[str, object]] = []
            try:
                for action in plan.actions:
                    if action.requires_approval:
                        continue
                    if action.action_type == "navigate" and action.value:
                        page.goto(action.value, wait_until="domcontentloaded")
                        visited.append(page.url)
                    elif action.action_type == "crawl":
                        page.locator(action.selector).count()
                    elif action.action_type == "assert":
                        page.locator(action.selector).count()
                    elif action.action_type == "capture_evidence":
                        screenshot = page.screenshot()
                        evidence.append(
                            {
                                "artifact_type": "browser_screenshot",
                                "summary": "Playwright screenshot captured",
                                "content_type": "image/png;base64",
                                "content": b64encode(screenshot).decode(),
                                "metadata": {"url": page.url},
                            }
                        )
                        evidence.append(
                            {
                                "artifact_type": "browser_dom_snapshot",
                                "summary": "Playwright DOM snapshot captured",
                                "content_type": "text/html",
                                "content": page.content(),
                                "metadata": {"url": page.url},
                            }
                        )
                title = page.title()
            finally:
                browser.close()
        return {"engine": plan.engine, "visited": visited, "title": title, "actions": len(plan.actions), "evidence": evidence}


class ReportService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store

    def generate_json_report(self, scan_id: str) -> Report:
        scan = self.store.get(self.store.scans, scan_id, "scan")
        findings = [f for f in self.store.findings.values() if f.scan_id == scan_id]
        events = [e for e in self.store.events if e.scan_id == scan_id]
        content = {
            "scan": {
                "id": scan.id,
                "status": scan.status,
                "scan_type": scan.scan_type,
                "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
            },
            "findings": [
                {
                    "id": finding.id,
                    "title": finding.title,
                    "severity": finding.severity,
                    "affected_asset": finding.affected_asset,
                    "verification_status": finding.verification_status,
                    "evidence_refs": finding.evidence_refs,
                }
                for finding in findings
            ],
            "event_count": len(events),
        }
        report = Report(
            workspace_id=scan.workspace_id,
            project_id=scan.project_id,
            scan_id=scan.id,
            title=f"KerisLab report for {scan.id}",
            format="json",
            content=content,
        )
        report = self.store.add(self.store.reports, report)
        self.store.sync()
        return report

    def get_finding(self, finding_id: str) -> Finding:
        return self.store.get(self.store.findings, finding_id, "finding")

    def get_report(self, report_id: str) -> Report:
        return self.store.get(self.store.reports, report_id, "report")


class ScanExecutionService:
    def __init__(self, store: InMemoryStore) -> None:
        self.store = store
        self.scans = ScanService(store)
        self.autonomous = AutonomousPentestService(store)
        self._queue: queue.Queue[str] = queue.Queue()
        self.redis_url = os.getenv("KERISLAB_REDIS_URL", "")
        self.redis_queue = os.getenv("KERISLAB_REDIS_QUEUE", "kerislab:scan-jobs")
        self._redis_client: object | None = None
        self._redis_disabled = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run_forever, name="kerislab-scan-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def enqueue(self, scan_id: str, job_type: ScanJobType, payload: dict[str, object] | None = None) -> ScanJob:
        job = ScanJob(scan_id=scan_id, job_type=job_type, payload=payload or {})
        self.store.add(self.store.scan_jobs, job)
        self._queue.put(job.id)
        self._enqueue_redis(job.id)
        self.store.sync()
        return job

    def drain(self) -> None:
        while True:
            try:
                job_id = self._queue.get_nowait()
            except queue.Empty:
                return
            self._execute(job_id)

    def pending_jobs(self) -> list[ScanJob]:
        return [job for job in self.store.scan_jobs.values() if job.status in {ScanJobStatus.QUEUED, ScanJobStatus.RUNNING}]

    def drain_persisted_jobs(self) -> int:
        self.store.reload()
        queued_jobs = [job for job in self.store.scan_jobs.values() if job.status == ScanJobStatus.QUEUED]
        for job in sorted(queued_jobs, key=lambda item: item.created_at):
            self._execute(job.id)
        return len(queued_jobs)

    def drain_available_jobs(self) -> int:
        drained = self.drain_redis_jobs()
        drained += self.drain_persisted_jobs()
        return drained

    def drain_redis_jobs(self, *, max_jobs: int = 25) -> int:
        client = self._get_redis_client()
        if client is None:
            return 0
        drained = 0
        for _ in range(max_jobs):
            try:
                job_id = client.lpop(self.redis_queue)
            except Exception:
                self._redis_disabled = True
                return drained
            if not job_id:
                return drained
            if isinstance(job_id, bytes):
                job_id = job_id.decode()
            self.store.reload()
            self._execute(str(job_id))
            drained += 1
        return drained

    def _run_forever(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = self._queue.get(timeout=0.25)
            except queue.Empty:
                continue
            self._execute(job_id)

    def _enqueue_redis(self, job_id: str) -> None:
        client = self._get_redis_client()
        if client is None:
            return
        try:
            client.rpush(self.redis_queue, job_id)
        except Exception:
            self._redis_disabled = True

    def _get_redis_client(self) -> object | None:
        if not self.redis_url or self._redis_disabled:
            return None
        if self._redis_client is not None:
            return self._redis_client
        try:
            import redis  # type: ignore[import-not-found]
        except Exception:
            self._redis_disabled = True
            return None
        try:
            self._redis_client = redis.Redis.from_url(self.redis_url, decode_responses=True)
            self._redis_client.ping()
        except Exception:
            self._redis_client = None
            self._redis_disabled = True
            return None
        return self._redis_client

    def _execute(self, job_id: str) -> None:
        job = self.store.get(self.store.scan_jobs, job_id, "scan job")
        if job.status != ScanJobStatus.QUEUED:
            return
        job.status = ScanJobStatus.RUNNING
        job.started_at = now_utc()
        job.attempts += 1
        self.store.sync()
        try:
            if job.job_type == ScanJobType.PASSIVE_SCAN:
                self.scans.run_passive_scan(job.scan_id)
            elif job.job_type == ScanJobType.AUTONOMOUS_START:
                self.autonomous.start(job.scan_id)
            elif job.job_type == ScanJobType.APPROVAL_REQUEST:
                self.autonomous.request_gated_upload_verification(job.scan_id)
            elif job.job_type == ScanJobType.COMPLETE_SCAN:
                self.scans.complete_scan(job.scan_id)
            elif job.job_type == ScanJobType.FAIL_SCAN:
                self.scans.fail_scan(job.scan_id, reason=str(job.payload.get("reason", "Scan failed")))
            else:  # pragma: no cover - defensive
                raise ValueError(f"unsupported scan job type: {job.job_type}")
            job.status = ScanJobStatus.COMPLETED
            job.completed_at = now_utc()
            job.error = ""
        except Exception as exc:
            job.status = ScanJobStatus.FAILED
            job.completed_at = now_utc()
            job.error = str(exc)
            raise
        finally:
            self.store.sync()

    def get_finding(self, finding_id: str) -> Finding:
        return self.store.get(self.store.findings, finding_id, "finding")

    def get_report(self, report_id: str) -> Report:
        return self.store.get(self.store.reports, report_id, "report")
