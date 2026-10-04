# Book2Skill

Book2Skill converts books and knowledge sources into structured, validated, AI-ready skill packages.

## Project status

This repository is in the foundation phase of the build described in the master plan. The current implementation focuses on a working core pipeline:

- document ingestion
- title extraction
- knowledge extraction
- validation
- SKILL.md compilation
- CLI execution

## Quick start

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
python -m book2skill --input samples\sample-book.md --output output
```

## Core behavior

The compiler reads a supported document, extracts structured knowledge, validates it, and writes a skill package containing:

- title
- concepts
- principles
- methods
- raw excerpt
- markdown export

## Tests

```bash
pytest -q
```

## Accounts and Premium Billing

New accounts receive seven days of free compiler access. Only one free trial is granted per network IP during the configured 12-month cooldown, so creating another email account from the same address does not restart the trial. The service stores a keyed one-way IP fingerprint, not the raw IP address. Accounts, password hashes, sessions, IP trial claims, and usage are stored in SQLite. Premium accounts receive unlimited compilations.

## Free Hosting on Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/vortexpwn09-netizen/book2skill)

This project includes a `render.yaml` Blueprint for a free Render web service. Click the button above (or create a new Blueprint in Render and select this repository). Render will provide an `onrender.com` address; set `PUBLIC_BASE_URL` to that address in the service environment before enabling Stripe checkout. Set a stable `BOOK2SKILL_IP_HASH_SECRET` and use `FORWARDED_ALLOW_IPS=*` only behind Render's proxy so the trial limit sees the visitor IP.

Render's free service has an ephemeral filesystem and may sleep when idle. This setup is suitable for a demo, but the local SQLite database can reset when the service restarts or redeploys, losing accounts and trial records. Use persistent database storage before selling subscriptions or relying on user accounts. A custom domain also needs a domain you own.

To enable paid subscriptions, create a recurring Price in Stripe, copy `.env.example` to `.env`, and configure `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`, `PREMIUM_PRICE_LABEL`, and `PUBLIC_BASE_URL`. Register `POST /api/billing/webhook` in Stripe for `checkout.session.completed`, `customer.subscription.updated`, and `customer.subscription.deleted`. Set a stable, random `BOOK2SKILL_IP_HASH_SECRET` in production and keep it unchanged so existing trial claims remain valid. When running behind a reverse proxy, set `FORWARDED_ALLOW_IPS` to the trusted proxy address(es); do not trust arbitrary forwarded headers. Set `BOOK2SKILL_COOKIE_SECURE=true` when the public site uses HTTPS. Docker Compose persists the database in its named volume.

