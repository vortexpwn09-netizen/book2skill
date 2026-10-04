from __future__ import annotations

import os
import hashlib
import hmac
import ipaddress
import re
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .core.compiler import build_skill_package, render_skill_markdown
from .core.ingestion import extract_pdf_text
from .auth import hash_password, verify_password
from .jobs import create_processing_job, get_job, process_job
from .projects import ProjectStore, add_document, create_project, get_project
from .storage import SQLiteStore

load_dotenv()


class CompileRequest(BaseModel):
    title: str | None = Field(default=None, description="Document title")
    text: str = Field(..., min_length=1, description="Document content to compile")
    max_items: int = Field(default=10, ge=1, le=50, description="Maximum items per category")


class JobCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, description="Document title")
    text: str = Field(..., min_length=1, description="Document content")


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, description="Project name")


class ProjectDocumentRequest(BaseModel):
    filename: str = Field(..., min_length=1, description="Document filename")
    content: str = Field(..., min_length=1, description="Document content")


class AuthRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=128)


MAX_PDF_BYTES = 25 * 1024 * 1024
SESSION_COOKIE = "book2skill_session"
SESSION_TTL_DAYS = 14


def create_app(db_path: str | Path | None = None) -> FastAPI:
    app = FastAPI(
        title="Book2Skill",
        version="0.1.0",
        description="Production-oriented knowledge compiler and public web app",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    origins = os.getenv("CORS_ORIGINS", "*").split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in origins if origin.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    project_store = ProjectStore()
    project_owners: dict[str, str] = {}
    job_owners: dict[str, str] = {}
    auth_store = SQLiteStore(db_path or os.getenv("BOOK2SKILL_DB_PATH", "book2skill.db"))
    free_trial_days = max(1, int(os.getenv("BOOK2SKILL_FREE_TRIAL_DAYS", "7")))
    ip_trial_cooldown_days = max(
        free_trial_days,
        int(os.getenv("BOOK2SKILL_IP_TRIAL_COOLDOWN_DAYS", "365")),
    )
    ip_hash_secret = os.getenv("BOOK2SKILL_IP_HASH_SECRET") or auth_store.get_or_create_setting(
        "ip_trial_hmac_secret", secrets.token_hex(32)
    )
    app.state.auth_store = auth_store
    WEB_ROOT = Path(__file__).resolve().parents[1] / "apps" / "web"
    app.mount("/static", StaticFiles(directory=str(WEB_ROOT / "static")), name="static")

    def now_utc() -> datetime:
        return datetime.now(timezone.utc)

    def iso_utc(value: datetime) -> str:
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")

    def session_token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def ip_fingerprint(request: Request) -> str:
        address = request.client.host if request.client else "unknown"
        try:
            normalized_address = ipaddress.ip_address(address).compressed
        except ValueError:
            normalized_address = address.strip().lower() or "unknown"
        return hmac.new(
            ip_hash_secret.encode("utf-8"),
            normalized_address.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def set_session_cookie(response: Response, user_id: str) -> None:
        token = secrets.token_urlsafe(32)
        now = now_utc()
        max_age = SESSION_TTL_DAYS * 24 * 60 * 60
        auth_store.create_session(
            session_token_hash(token),
            user_id,
            iso_utc(now + timedelta(days=SESSION_TTL_DAYS)),
            iso_utc(now),
        )
        secure_setting = os.getenv("BOOK2SKILL_COOKIE_SECURE")
        secure = (
            secure_setting.lower() in {"1", "true", "yes"}
            if secure_setting is not None
            else os.getenv("BOOK2SKILL_ENV", "development").lower() == "production"
        )
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=max_age,
            httponly=True,
            secure=secure,
            samesite="lax",
            path="/",
        )

    def session_user(request: Request) -> dict[str, Any] | None:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return None
        return auth_store.get_user_by_session(session_token_hash(token), iso_utc(now_utc()))

    def require_user(request: Request) -> dict[str, Any]:
        user = session_user(request)
        if user is None:
            raise HTTPException(status_code=401, detail="Sign in to use Book2Skill.")
        return user

    def public_user(user: dict[str, Any]) -> dict[str, Any]:
        usage = auth_store.monthly_compile_count(user["id"], month_start())
        premium = user["subscription_status"] in {"active", "trialing"}
        trial_expiry = user.get("free_trial_expires_at")
        trial_expiry_datetime = datetime.fromisoformat(trial_expiry) if trial_expiry else None
        if trial_expiry_datetime and trial_expiry_datetime.tzinfo is None:
            trial_expiry_datetime = trial_expiry_datetime.replace(tzinfo=timezone.utc)
        trial_active = bool(trial_expiry_datetime and trial_expiry_datetime > now_utc())
        trial_days_remaining = (
            max(0, (trial_expiry_datetime - now_utc() + timedelta(days=1) - timedelta(seconds=1)).days)
            if trial_active and trial_expiry_datetime
            else 0
        )
        return {
            "id": user["id"],
            "email": user["email"],
            "plan": "premium" if premium else "trial" if trial_active else "expired",
            "subscription_status": user["subscription_status"],
            "monthly_usage": usage,
            "trial_expires_at": trial_expiry,
            "trial_days_remaining": trial_days_remaining,
            "premium_price_label": os.getenv("PREMIUM_PRICE_LABEL", "Premium subscription"),
        }

    def month_start() -> str:
        now = now_utc()
        return iso_utc(now.replace(day=1, hour=0, minute=0, second=0, microsecond=0))

    def enforce_compile_quota(user: dict[str, Any]) -> None:
        if user["subscription_status"] in {"active", "trialing"}:
            return
        expiry = user.get("free_trial_expires_at")
        expiry_datetime = datetime.fromisoformat(expiry) if expiry else None
        if expiry_datetime and expiry_datetime.tzinfo is None:
            expiry_datetime = expiry_datetime.replace(tzinfo=timezone.utc)
        if expiry_datetime is None or expiry_datetime <= now_utc():
            raise HTTPException(
                status_code=402,
                detail=f"Your {free_trial_days}-day free trial has expired or was already claimed from this network. Upgrade to Premium to keep using the compiler.",
            )

    def record_compile(user_id: str) -> int:
        auth_store.record_compile(user_id, iso_utc(now_utc()))
        return auth_store.monthly_compile_count(user_id, month_start())

    def normalized_email(email: str) -> str:
        value = email.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise HTTPException(status_code=422, detail="Enter a valid email address.")
        return value

    @app.get("/", response_class=HTMLResponse, response_model=None)
    def home(request: Request) -> HTMLResponse | RedirectResponse:
        if session_user(request) is None:
            return RedirectResponse(url="/login", status_code=302)
        index_html = (WEB_ROOT / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(content=index_html)

    @app.get("/login", response_class=HTMLResponse, response_model=None)
    def login_page(request: Request) -> HTMLResponse | RedirectResponse:
        if session_user(request) is not None:
            return RedirectResponse(url="/", status_code=302)
        login_html = (WEB_ROOT / "login.html").read_text(encoding="utf-8")
        return HTMLResponse(content=login_html)

    @app.get("/health")
    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/auth/register", status_code=201)
    def register(payload: AuthRequest, request: Request, response: Response) -> dict[str, Any]:
        if len(payload.password) < 10:
            raise HTTPException(status_code=422, detail="Password must be at least 10 characters.")
        email = normalized_email(payload.email)
        now = now_utc()
        try:
            user = auth_store.create_account(
                email,
                hash_password(payload.password),
                ip_fingerprint(request),
                iso_utc(now),
                iso_utc(now + timedelta(days=free_trial_days)),
                iso_utc(now + timedelta(days=ip_trial_cooldown_days)),
            )
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="An account with this email already exists.") from exc
        set_session_cookie(response, user["id"])
        return {"user": public_user(user)}

    @app.post("/api/auth/login")
    def login(payload: AuthRequest, response: Response) -> dict[str, Any]:
        email = normalized_email(payload.email)
        user = auth_store.get_user_by_email(email)
        if user is None or not verify_password(payload.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Email or password is incorrect.")
        set_session_cookie(response, user["id"])
        return {"user": public_user(user)}

    @app.post("/api/auth/logout")
    def logout(request: Request, response: Response) -> dict[str, bool]:
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            auth_store.delete_session(session_token_hash(token))
        response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, samesite="lax")
        return {"ok": True}

    @app.get("/api/auth/me")
    def who_am_i(request: Request) -> dict[str, Any]:
        token = request.cookies.get(SESSION_COOKIE)
        user = auth_store.get_user_by_session(session_token_hash(token), iso_utc(now_utc())) if token else None
        return {
            "user": public_user(user) if user else None,
            "free_trial_days": free_trial_days,
            "ip_trial_cooldown_days": ip_trial_cooldown_days,
            "premium_price_label": os.getenv("PREMIUM_PRICE_LABEL", "Premium subscription"),
        }

    @app.get("/api/billing/plans")
    def billing_plans() -> dict[str, Any]:
        return {
            "free_trial_days": free_trial_days,
            "ip_trial_cooldown_days": ip_trial_cooldown_days,
            "premium_price_label": os.getenv("PREMIUM_PRICE_LABEL", "Premium subscription"),
            "checkout_configured": bool(os.getenv("STRIPE_SECRET_KEY") and os.getenv("STRIPE_PRICE_ID")),
        }

    @app.post("/api/billing/checkout")
    def create_checkout(user: dict[str, Any] = Depends(require_user)) -> dict[str, str]:
        secret_key = os.getenv("STRIPE_SECRET_KEY")
        price_id = os.getenv("STRIPE_PRICE_ID")
        if not secret_key or not price_id:
            raise HTTPException(status_code=503, detail="Premium checkout is not configured yet.")
        if user["subscription_status"] in {"active", "trialing"}:
            raise HTTPException(status_code=409, detail="Your account already has Premium.")
        import stripe

        stripe.api_key = secret_key
        base_url = (
            os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8000"
        ).rstrip("/")
        checkout_args: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": f"{base_url}/?checkout=success",
            "cancel_url": f"{base_url}/#pricing",
            "metadata": {"user_id": user["id"]},
            "subscription_data": {"metadata": {"user_id": user["id"]}},
        }
        if user.get("stripe_customer_id"):
            checkout_args["customer"] = user["stripe_customer_id"]
        else:
            checkout_args["customer_email"] = user["email"]
        try:
            checkout = stripe.checkout.Session.create(**checkout_args)
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Could not start Premium checkout.") from exc
        return {"checkout_url": checkout.url}

    @app.post("/api/billing/portal")
    def create_billing_portal(user: dict[str, Any] = Depends(require_user)) -> dict[str, str]:
        secret_key = os.getenv("STRIPE_SECRET_KEY")
        if not secret_key or not user.get("stripe_customer_id"):
            raise HTTPException(status_code=503, detail="Subscription management is not available yet.")
        import stripe

        stripe.api_key = secret_key
        base_url = (
            os.getenv("PUBLIC_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL") or "http://localhost:8000"
        ).rstrip("/")
        try:
            portal = stripe.billing_portal.Session.create(
                customer=user["stripe_customer_id"],
                return_url=f"{base_url}/#pricing",
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail="Could not open subscription management.") from exc
        return {"portal_url": portal.url}

    @app.post("/api/billing/webhook")
    async def stripe_webhook(request: Request) -> dict[str, bool]:
        webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
        if not webhook_secret:
            raise HTTPException(status_code=503, detail="Billing webhook is not configured.")
        import stripe

        try:
            event = stripe.Webhook.construct_event(
                await request.body(),
                request.headers.get("stripe-signature", ""),
                webhook_secret,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Invalid billing webhook signature.") from exc

        event_type = event["type"]
        billing_object = event["data"]["object"]
        if event_type == "checkout.session.completed":
            user_id = billing_object.get("metadata", {}).get("user_id")
            if user_id and billing_object.get("subscription"):
                auth_store.set_billing_status(user_id, "active", billing_object.get("customer"))
        elif event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
            user = auth_store.get_user_by_stripe_customer(billing_object.get("customer", ""))
            if user:
                status = billing_object.get("status", "canceled")
                auth_store.set_billing_status(
                    user["id"],
                    status if status in {"active", "trialing"} else "free",
                )
        return {"ok": True}

    @app.post("/compile")
    @app.post("/api/compile")
    def compile_document(
        payload: CompileRequest,
        user: dict[str, Any] = Depends(require_user),
    ) -> dict[str, Any]:
        enforce_compile_quota(user)
        package = build_skill_package(
            title=payload.title or "Untitled Knowledge Source",
            text=payload.text,
            max_items=payload.max_items,
        )
        package["monthly_usage"] = record_compile(user["id"])
        package["trial_days_remaining"] = public_user(user)["trial_days_remaining"]
        package["skill_markdown"] = render_skill_markdown(package)
        return package

    @app.post("/compile/pdf")
    async def compile_pdf(
        file: UploadFile = File(...),
        title: str | None = Form(default=None),
        user: dict[str, Any] = Depends(require_user),
    ) -> dict[str, Any]:
        enforce_compile_quota(user)
        filename = Path(file.filename or "").name
        if not filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=415, detail="Please upload a PDF file.")

        content = await file.read(MAX_PDF_BYTES + 1)
        if len(content) > MAX_PDF_BYTES:
            raise HTTPException(status_code=413, detail="PDF must be 25 MB or smaller.")
        if b"%PDF-" not in content[:1024]:
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid PDF.")

        try:
            text = extract_pdf_text(content)
        except Exception as exc:
            raise HTTPException(status_code=400, detail="Could not read this PDF file.") from exc
        if not text.strip():
            raise HTTPException(
                status_code=422,
                detail="No selectable text found. This may be a scanned PDF; OCR is not supported yet.",
            )

        resolved_title = (title or Path(filename).stem).strip() or "Untitled Knowledge Source"
        package = build_skill_package(title=resolved_title, text=text)
        monthly_usage = record_compile(user["id"])
        return {
            "filename": "SKILL.md",
            "package": package,
            "monthly_usage": monthly_usage,
            "trial_days_remaining": public_user(user)["trial_days_remaining"],
            "skill_markdown": render_skill_markdown(package),
        }

    @app.post("/processing/jobs")
    def create_job(
        payload: JobCreateRequest,
        user: dict[str, Any] = Depends(require_user),
    ) -> dict[str, Any]:
        enforce_compile_quota(user)
        job = create_processing_job(payload.title, payload.text)
        job_owners[job.job_id] = user["id"]
        package = process_job(job)
        record_compile(user["id"])
        return {
            "job_id": job.job_id,
            "status": job.status,
            "title": job.title,
            "package": package,
        }

    @app.get("/processing/jobs/{job_id}")
    def get_job_status(job_id: str, user: dict[str, Any] = Depends(require_user)) -> dict[str, Any]:
        if job_owners.get(job_id) != user["id"]:
            raise HTTPException(status_code=404, detail="Job not found")
        job = get_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Job not found")

        return {
            "job_id": job.job_id,
            "status": job.status,
            "title": job.title,
            "created_at": job.created_at.isoformat(),
            "updated_at": job.updated_at.isoformat(),
            "error": job.error,
            "package": job.package,
        }

    @app.post("/projects")
    def create_project_endpoint(
        payload: ProjectCreateRequest,
        user: dict[str, Any] = Depends(require_user),
    ) -> dict[str, Any]:
        project = create_project(project_store, payload.name)
        project_owners[project["id"]] = user["id"]
        return project

    @app.get("/projects/{project_id}")
    def get_project_endpoint(
        project_id: str,
        user: dict[str, Any] = Depends(require_user),
    ) -> dict[str, Any]:
        if project_owners.get(project_id) != user["id"]:
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            return get_project(project_store, project_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/projects/{project_id}/documents")
    def add_document_endpoint(
        project_id: str,
        payload: ProjectDocumentRequest,
        user: dict[str, Any] = Depends(require_user),
    ) -> dict[str, Any]:
        if project_owners.get(project_id) != user["id"]:
            raise HTTPException(status_code=404, detail="Project not found")
        try:
            return add_document(project_store, project_id, payload.filename, payload.content)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return app


app = create_app()
