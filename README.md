# NoorLink Automation

Automated eSIM purchase and delivery backend (FastAPI + Supabase + Stripe + Resend).

## Project layout

```
noorlink-automation/
├── app/
│   ├── api/          # FastAPI routes (main.py entrypoint)
│   ├── core/         # Settings / config
│   └── services/     # Fulfillment, email, travel assistant
├── supabase/         # SQL migrations + seed data
├── requirements.txt
└── .env              # local secrets (copy from .env.example)
```

All Python imports use the **`app`** package prefix (e.g. `from app.core.config import get_settings`).

## Local development

```bash
cd noorlink-automation
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Supabase, Stripe, Resend keys
```

### Start the API (port 8000)

From the **repository root**:

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

Or use the helper script:

```bash
chmod +x scripts/run.sh
./scripts/run.sh
```

### Health check

```bash
curl http://127.0.0.1:8000/health
```

## Deploy

Railway start command (see `railway.toml`):

```bash
uvicorn app.api.main:app --host 0.0.0.0 --port $PORT
```
