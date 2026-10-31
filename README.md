# Dukan Dost

Voice-first AI munshi for Paytm kiranas: speak an udhaar entry, snap a distributor bill, see the Diwali cash gap,
send WhatsApp reminders with a pay link, and get a loan offer only for what's left.

## Run it

```bash
make install      # uv sync + npm install
cp .env.example .env   # optional — defaults run fully offline (fake AI, in-memory Mongo)
make dev          # API http://localhost:8000 (docs at /docs) · app http://localhost:5173
```
Login: `+919999900001` / OTP `123456`.

With MongoDB Atlas (`MONGO_URI=mongodb+srv://…`), run `make seed` once before the first start and again whenever
you want to reset to the exact demo state. With `MONGO_URI=memory` the API seeds itself on every start. `make test` runs the API tests (the §17 demo numbers) and the web typecheck.

## Architecture

- `apps/api` — FastAPI. `services/forecast.py` is the deterministic engine (every rupee from code);
  `agents/cash_advisor.py` is the LangGraph graph (load → compute → plan → explain → persist);
  `ai/` holds Sarvam STT, Claude (Anthropic API or Bedrock) with structured outputs, and deterministic fakes;
  `adapters/paytm_mock.py` issues pay links and HMAC-signed webhooks; `db.py` scopes every query by merchant.
- `apps/web` — React + Vite PWA, eight screens from the build map.

## Demo script

1. Home: today ₹12,480 (cash "aapne bataya"), udhaar ₹8,550, no alert.
2. Mic: "Sharma ji 450 udhaar, doodh aur atta" → confirm → udhaar ₹9,000.
3. Scan the Balaji bill → ₹18,400 due 5 Nov, sums match → save.
4. Forecast: ₹45,000 needed, ₹30,000 available, ₹15,000 short → collect ₹9,000 + loan ₹6,000.
5. Udhaar → plan reminders → WhatsApp to Sharma ji → open the pay link → Pay ₹1,250 → udhaar ₹7,750.

## Known limits

Mock Paytm (own pay page), rule-based forecast, fixed demo login,
balance updates are single-document `$inc` rather than multi-document transactions.
