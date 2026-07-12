# LUNIQ Health API (Production)

A rebuilt version of the LUNIQ Health POC with a real **agent + tool-calling** architecture,
**persistent memory**, and the operational basics needed to run reliably for a group of
~100 users: auth, rate limiting, logging, error handling, and a Docker setup.

## What changed from the POC, and why

| Area | POC | Production version | Why |
|---|---|---|---|
| Vitals validation | Hard `ge=`/`le=` limits on every field — out-of-range input got a 422 error, AI never saw it | No hard limits at the schema level. A **deterministic rule engine** (`app/tools/vitals_rules.py`) decides Normal/Warning/Critical from clinical thresholds | The API should never silently reject a real (if unusual) reading — it should look at it and respond appropriately. But the *safety decision* shouldn't be left to an LLM's mood; the rule engine is fixed and auditable, and the LLM is **not allowed to downgrade** its status (see `vitals_agent.py`). |
| Medicine dosing | LLM stated doses from its own training memory | Still the LLM, using its own knowledge, answering the user's actual message directly | No hardcoded reference table. The model reads what the user actually asked and responds to that, with instructions to say so plainly (and suggest a pharmacist) if it isn't confident about a dose, rather than inventing one. |
| Emergency detection | Left entirely to the LLM's judgement | A `check_emergency_symptoms` **tool** with a red-flag keyword list runs before the model advises anything | A keyword check can't be "reasoned around" the way a language model sometimes can be — it's a hard backstop. |
| Memory | In-process RAM (`deque`) — wiped on every restart/redeploy | SQLite-backed (`app/db/memory_store.py`), same "last 5 turns per user" behavior, but durable. The `.db` file is created automatically the moment the app starts (see `init_db()` in `app/main.py`'s lifespan handler) | A restart shouldn't erase every user's conversation context, and the database shouldn't need a manual setup step. |
| Auth | None | Optional `X-API-Key` header, enforced via `app/core/security.py` | An open API serving health guidance to 100 people needs at least a shared secret. |
| Abuse protection | None | Per-user rate limiting (`app/core/rate_limit.py`), default 10 req/min | Protects your OpenAI spend and keeps one user from starving others. |
| Observability | Plain print/HTTPException | Structured logs with request IDs, a `/health` endpoint, global exception handler | You need to be able to see what happened when something breaks, and a load balancer needs something to poll. |
| Deployment | `uvicorn --reload` | `Dockerfile` + `docker-compose.yml` running Gunicorn with multiple Uvicorn workers | A single dev server process isn't resilient enough for real traffic. |

## Project structure

```
luniq_prod/
├── app/
│   ├── main.py                 # FastAPI app, middleware, logging, startup
│   ├── config.py                # All settings, loaded from .env
│   ├── logging_config.py
│   ├── models/
│   │   ├── vitals.py             # VitalsInput / AssessmentResponse (no hard bounds)
│   │   └── chat.py               # ChatInput / ChatResponse / HistoryResponse
│   ├── db/
│   │   ├── database.py           # SQLite connection + schema
│   │   └── memory_store.py       # Persistent last-N-turn conversation memory
│   ├── tools/                    # Functions the agent can call
│   │   ├── emergency_check.py    # Red-flag symptom keyword screen
│   │   └── vitals_rules.py       # Deterministic Normal/Warning/Critical engine
│   ├── agents/
│   │   ├── chat_agent.py         # Tool-calling loop for the /chat endpoint - answers from the model's own knowledge
│   │   └── vitals_agent.py       # Rule engine + LLM narrative for /assess
│   ├── core/
│   │   ├── security.py           # X-API-Key auth dependency
│   │   └── rate_limit.py         # Per-user request throttling
│   ├── routers/
│   │   ├── chat.py               # POST /chat, GET/DELETE /chat/history/{mobile}
│   │   └── assess.py             # POST /assess
│   └── main.py                   # also creates luniq_memory.db automatically on startup
├── tests/
│   └── test_basic.py             # Rule engine, tools, memory, endpoint tests
├── requirements.txt
├── .env.example
├── Dockerfile
├── docker-compose.yml
└── .gitignore
```

## How the agents work

**`/chat` (chat_agent.py):** the model reads the user's actual message and answers it directly using
its own knowledge - no hardcoded lookup table. It has one tool available, `check_emergency_symptoms`,
which runs a red-flag keyword check before any symptom-related advice; if it detects a possible
emergency, the model is instructed to lead with telling the user to seek immediate care. The response
includes `tools_used` so you can see whether that check fired for a given message. The system prompt
still requires the model to say "I'm not confident about this dose, check the label or a pharmacist"
rather than invent a number it isn't sure of.

**`/assess` (vitals_agent.py):** the deterministic rule engine decides the status first. The
LLM is only asked to explain it in plain language — the code has a hard safety net that refuses
to accept a downgraded status even if the model's JSON output tries to soften it.

## Setup (local)

```bash
cd luniq_prod
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # edit .env: add OPENAI_API_KEY and a real API_KEY
uvicorn app.main:app --reload
```

Docs: http://127.0.0.1:8000/docs

## Setup (Docker — recommended for actually running this for a group of users)

```bash
cp .env.example .env             # edit .env with real values
docker compose up --build -d
```

This runs Gunicorn with 4 Uvicorn workers behind port 8000, and persists the SQLite database
in a named Docker volume so conversation memory survives container restarts. Tune the worker
count in the `Dockerfile` CMD to roughly `2 x CPU cores + 1`.

## Calling the API

Every request needs an `X-API-Key` header matching your `.env` `API_KEY` (unless you leave
`API_KEY` blank, which disables auth — fine for local dev only).

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "username": "John Doe",
    "mobile_number": "9876543210",
    "age": 30,
    "query": "Can I take Dolo 650 for fever?"
  }'
```

```bash
curl -X POST http://localhost:8000/assess \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "username": "John Doe",
    "mobile_number": "9876543210",
    "age": 30,
    "heart_rate": 72,
    "sys_bp": 120,
    "dia_bp": 80,
    "oxygen": 98,
    "temperature": 37.1,
    "ecg": "Normal"
  }'
```

Other endpoints:
- `GET /health` — liveness check for load balancers/uptime monitors
- `GET /chat/history/{mobile_number}` — view a user's stored conversation
- `DELETE /chat/history/{mobile_number}` — clear a user's conversation

## Scaling past ~100 users

This setup (SQLite + in-memory-per-process rate limiting, single instance, Gunicorn workers)
comfortably handles a group of ~100 users on one server. If you outgrow that:

- **Multiple servers / horizontal scaling:** swap SQLite for Postgres, and the rate limiter
  for Redis — both `memory_store.py` and `rate_limit.py` were written with a narrow function
  signature specifically so this swap doesn't touch any router or agent code.
- **Cost control:** consider a shared cache for `lookup_otc_medicine` results, and truncate
  chat history further if OpenAI token costs grow.
- **Secrets:** in Docker/cloud deployments, use a secrets manager instead of a plain `.env`
  file for `OPENAI_API_KEY` and `API_KEY`.

## Running tests

```bash
pip install -r requirements.txt
pytest tests/ -v
```

## Safety notes (please read before real users touch this)

This is still a **proof-of-concept health information tool**, not a medical device or a
substitute for professional care:
- The rule-engine thresholds in `vitals_rules.py` are general-population defaults, not
  clinician-defined ranges for a specific person (athletes, chronic conditions, medications,
  etc. all shift what's "normal").
- Medicine dosing guidance comes from the LLM's own knowledge, not a pharmacy-grade drug
  database - the model is instructed to say so plainly (and point to a pharmacist/doctor)
  whenever it isn't confident, but always keep the "confirm with a pharmacist/doctor" language
  visible in your app UI as an extra layer of safety.
- Before any real deployment to real users, have a clinician review the thresholds and the
  chatbot's medicine-related answers.
