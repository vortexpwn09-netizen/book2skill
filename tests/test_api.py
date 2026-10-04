import pytest
from fastapi.testclient import TestClient

from book2skill.api import app, create_app


client = TestClient(app)


@pytest.fixture
def api_client(tmp_path):
    return TestClient(create_app(db_path=tmp_path / "accounts.db"))


@pytest.fixture
def authenticated_client(api_client):
    response = api_client.post(
        "/api/auth/register",
        json={"email": "reader@example.com", "password": "secure-pass-123"},
    )
    assert response.status_code == 201
    return api_client


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_compile_requires_login(api_client):
    response = api_client.post("/compile", json={"text": "A short source."})
    assert response.status_code == 401


def test_signup_session_compiles_and_logout_revokes_access(authenticated_client):
    payload = {
        "title": "Focus System",
        "text": "AI agents use context and memory. Principle: keep it simple. Method: plan, then execute.",
    }
    response = authenticated_client.get("/api/auth/me")
    assert response.status_code == 200
    assert response.json()["user"]["plan"] == "trial"
    assert response.json()["user"]["trial_days_remaining"] == 7

    response = authenticated_client.post("/compile", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Focus System"
    assert "concepts" in data
    assert "principles" in data
    assert "methods" in data
    assert "# Skill: Focus System" in data["skill_markdown"]
    assert data["monthly_usage"] == 1

    assert authenticated_client.post("/api/auth/logout").status_code == 200
    assert authenticated_client.post("/compile", json=payload).status_code == 401


def test_signup_creates_persistent_account_session(api_client):
    registration = api_client.post(
        "/api/auth/register", json={"email": "returning@example.com", "password": "secure-pass-123"}
    )
    assert registration.status_code == 201
    assert "httponly" in registration.headers["set-cookie"].lower()
    assert api_client.get("/api/auth/me").json()["user"]["email"] == "returning@example.com"
    api_client.post("/api/auth/logout")

    response = api_client.post(
        "/api/auth/login",
        json={"email": "RETURNING@example.com", "password": "secure-pass-123"},
    )
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "returning@example.com"


def test_pdf_upload_returns_downloadable_skill(monkeypatch, authenticated_client):
    monkeypatch.setattr("book2skill.api.extract_pdf_text", lambda content: "Principle: keep knowledge clear.")
    response = authenticated_client.post(
        "/compile/pdf",
        files={"file": ("focus.pdf", b"%PDF-1.4 example", "application/pdf")},
        data={"title": "Focus Guide"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "SKILL.md"
    assert data["package"]["title"] == "Focus Guide"
    assert "# Skill: Focus Guide" in data["skill_markdown"]


def test_pdf_upload_rejects_non_pdf(authenticated_client):
    response = authenticated_client.post(
        "/compile/pdf",
        files={"file": ("notes.txt", b"plain text", "text/plain")},
    )

    assert response.status_code == 415


def test_free_trial_expires_after_seven_days(authenticated_client):
    payload = {"text": "Principle: protect focused work."}
    assert authenticated_client.post("/compile", json=payload).status_code == 200

    user_id = authenticated_client.get("/api/auth/me").json()["user"]["id"]
    store = authenticated_client.app.state.auth_store
    with store._connect() as connection:
        connection.execute(
            "UPDATE users SET free_trial_expires_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00+00:00", user_id),
        )

    assert authenticated_client.get("/api/auth/me").json()["user"]["plan"] == "expired"
    response = authenticated_client.post("/compile", json=payload)
    assert response.status_code == 402
    assert "trial has expired" in response.json()["detail"]


def test_second_email_from_same_ip_does_not_get_another_trial(authenticated_client):
    second_client = TestClient(authenticated_client.app)
    response = second_client.post(
        "/api/auth/register", json={"email": "alternate@example.com", "password": "secure-pass-789"}
    )
    assert response.status_code == 201
    assert response.json()["user"]["plan"] == "expired"
    assert second_client.post("/compile", json={"text": "Principle: protect focus."}).status_code == 402


def test_premium_checkout_requires_stripe_configuration(authenticated_client, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)

    response = authenticated_client.post("/api/billing/checkout")
    assert response.status_code == 503


def test_stripe_webhook_activates_premium(authenticated_client, monkeypatch):
    import stripe

    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    user_id = authenticated_client.get("/api/auth/me").json()["user"]["id"]
    event = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"user_id": user_id},
                "subscription": "sub_test",
                "customer": "cus_test",
            }
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda *args: event)

    response = authenticated_client.post(
        "/api/billing/webhook",
        content=b"{}",
        headers={"stripe-signature": "test-signature"},
    )
    assert response.status_code == 200
    assert authenticated_client.get("/api/auth/me").json()["user"]["plan"] == "premium"


def test_jobs_and_projects_are_private_to_their_account(authenticated_client):
    project = authenticated_client.post("/projects", json={"name": "Private notes"}).json()
    job = authenticated_client.post(
        "/processing/jobs",
        json={"title": "Private job", "text": "Principle: keep data private."},
    ).json()

    second_client = TestClient(authenticated_client.app)
    second_client.post(
        "/api/auth/register",
        json={"email": "other-reader@example.com", "password": "secure-pass-456"},
    )
    assert second_client.get(f"/projects/{project['id']}").status_code == 404
    assert second_client.get(f"/processing/jobs/{job['job_id']}").status_code == 404


def test_logged_out_home_redirects_to_login(api_client):
    response = api_client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/login"

    response = api_client.get("/login")
    assert response.status_code == 200
    assert "login-background.mp4" in response.text
    assert "Create account" in response.text


def test_authenticated_user_sees_tool_homepage(authenticated_client):
    response = authenticated_client.get("/")
    assert response.status_code == 200
    assert "TURN BOOKS" in response.text
    assert authenticated_client.get("/login", follow_redirects=False).headers["location"] == "/"


def test_signup_creates_account_without_email_verification(api_client):
    response = api_client.post(
        "/api/auth/register",
        json={"email": "verify-first@example.com", "password": "secure-pass-987"},
    )
    assert response.status_code == 201
    assert api_client.get("/api/auth/me").json()["user"]["email"] == "verify-first@example.com"
