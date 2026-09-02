# Bridge — services map and operations guide

How the Bridge feasibility engine's pieces fit together, what each one costs,
how to run it locally, and what deploying it to AWS will involve. Companion to
`bridge-plan-v3.md` (the design) — this file describes what was actually built
and the operational decisions around it. Keep it updated when the wiring
changes; `.gitignore` carries an explicit exception so this file IS tracked
while `*.md` in general is not.

Last verified against the code: 2026-08-20. Library seeded over 18 topics for
$0.38; both scouts live; three datasets featured per step for step0 and step1.

---

## 1. The services and how they interact

```mermaid
flowchart TB
    subgraph browser [Browser SPA]
        BR["/training/:modelId/bridge (Bridge.tsx)\n/training/:modelId/bridge/:topicSlug (BridgeVerdict.tsx)\nreached from the model's learn rail"]
    end

    subgraph web [web process — uvicorn (FastAPI)]
        API["routers/bridge.py\nGET /bridge/specs · /library · /verdicts · /runs\nPOST /bridge/runs"]
    end

    subgraph pg [PostgreSQL + pgvector]
        JOBS[(bridge_jobs\nthe queue)]
        VERD[(bridge_verdicts\ncache + library)]
        POOL[(bridge_candidate_pools)]
        CARDS[(bridge_dataset_cards\nVector 1024)]
        PLANS[(bridge_query_plans)]
        CACHE[(bridge_llm_cache)]
    end

    subgraph worker [worker process — python -m backend.worker]
        TRAIN[training claim loop]
        EMAIL[email-drain thread]
        DRAIN["bridge-drain thread\nservices/bridge_drain.py"]
        PIPE["pipeline.py\nplan → scout → gates → replan ≤2 → probe → verdict → critic"]
    end

    subgraph ext [External APIs]
        ANTH[Anthropic API\nSonnet 5 planner\nHaiku 4.5 judge + summary]
        VOY[Voyage AI\nvoyage-4-lite embeddings]
        HF[HuggingFace Hub search\n+ datasets-server inspection\nno auth]
        KAG[Kaggle SDK search\nneeds KAGGLE_USERNAME/KEY]
        LF[Langfuse Cloud\noptional tracing]
        PUB[Curated public APIs\napi_registry.json, live-probed]
    end

    BR -- "2s poll while active" --> API
    API -- "insert job / read rows" --> JOBS
    API -- "library + verdict reads" --> VERD
    DRAIN -- "FOR UPDATE SKIP LOCKED" --> JOBS
    DRAIN --> PIPE
    PIPE --> ANTH & VOY & HF & KAG & PUB
    PIPE -. "when keys set" .-> LF
    PIPE --> VERD & POOL & CARDS & PLANS & CACHE
```

Everything durable lives in Postgres; the worker holds nothing in memory a
crash could lose. The API never calls an external service — it only inserts and
reads rows, so the web image ships none of the ML/LLM dependencies (verified:
importing `backend.main` pulls in no sklearn/anthropic/voyageai).

## 2. What each call costs (measured 2026-08-20)

| Call site | Model | Role | Typical per verdict |
|---|---|---|---|
| `query_planner` | claude-sonnet-5 | 6–10 search queries; replans see the rejection breakdown | 1–3 calls, ~$0.003 each |
| `relevance_judge` | claude-haiku-4-5 | binary topic relevance per candidate | up to 40 calls, ~$0.0006 each |
| `verdict_summary` | claude-haiku-4-5 | the artefact's ONE generated sentence | 1 call, ~$0.0007 |
| `embedding` | voyage-4-lite | card index + recall queries | ~500 tokens, ~$0.00001 |

Measured live verdicts: **$0.013** with HuggingFace alone, **$0.028–0.048** once
the Kaggle scout is active (it roughly doubles the candidate pool, and judging is
per candidate). `BRIDGE_MAX_JUDGED_CANDIDATES` (default 40) is the lever that
bounds it. Pricing table lives in `backend/services/bridge/llm.py`, dated.

**Prompt caching does nothing at the judge site, and that is expected.** The
static instruction block there is ~100 tokens, far below the ~1024-token minimum
cacheable prefix, so every judge call bills its full input. The candidate card
text dominates that cost anyway, so the effective control is judging fewer
candidates, not caching the instructions.

**Spend guardrails, all enforced in code:**

- $0.15 hard per-verdict ceiling (`BRIDGE_VERDICT_SPEND_CEILING_USD`), checked
  *before* each paid call is dispatched — a wide topic aborts mid-run with an
  honest error, never a surprise bill.
- $1.00/day global cap (`BRIDGE_DAILY_SPEND_CAP_USD`), summed over ALL users'
  and seed jobs' `cost_usd`; POST /bridge/runs returns 429 past it.
- `RATE_LIMIT_BRIDGE` = 3 runs/hour/IP, plus one active run per user enforced
  by a partial unique index (409 on the second).
- `bridge_llm_cache`: byte-identical requests are free. This is what makes
  repeated local runs ~$0 and bounds the queue's at-least-once duplicate spend.
- Slug normalisation: "Wine  Quality!" and "wine quality" share one verdict.
- Library/cache hits short-circuit in the router — no job row, no spend.

## 3. Decisions of record

| Decision | Choice and why |
|---|---|
| Probe/training contention | One worker process, bridge runs on its own daemon thread beside the email drain. Probes are capped (≤5000 rows, sklearn) and training runs in a subprocess, so no GIL contention. A dedicated probe worker would cost a second Fargate task for a personal project — revisit only if probe latency measurably hurts training runs. |
| At-least-once duplicate spend | Accepted. Bounded three ways: verdict-exists short-circuit on re-claim, `bridge_llm_cache` making replayed calls free, and the per-verdict ceiling capping the worst case. |
| Verdict = static artefact | Not a tracked project (v2 Q1). Cheapest and honest; revisit if retention ever matters. |
| Promotion | Always manual review via the CLI (v2 Q2). There is no admin role in the app; `python -m backend.services.bridge.cli promote <slug> <step>` is the whole workflow. |
| Bridge never feeds the trainer | Verdicts point off-platform by design — the roadmap's thesis is you build it yourself in C++. Revisit consciously (it changes the driver contract and storage story) if that ever flips. |
| Presentation is computed at serve time | `services/bridge/plain.py` turns records (licence slugs, difficulty tiers, probe outcomes) into the sentences a student reads, and the router serves them beside the artefact. Improving a phrase improves every verdict already on disk, with no re-run and no spend. The one exception is the LLM summary, which is generated prose and needs `cli resummarise` after a prompt change. |
| Probe outcomes carry a `code` | One outcome can mean two things: a step0 FAIL is either "nothing here is learnable" or "this needs a hidden layer". `decide()` returns an optional code and `ProbeSpec.plain_outcomes` keys wording on it, so the page never tells a student the wrong one. |
| Seeding runs synchronously, not via the Batch API | Conscious deviation from bridge-plan-v3.md §14.7. Stage-wise batching across topics would mean a second orchestrator to save ~50% of ≈$1 (30 cells), and pool-sharing across the three tabular steps already removes two thirds of the search cost. Revisit at 10× library size. |
| A fourth verdict value | `not_at_this_step` joins the design's three, for the §19 case where real data exists but the probe shows it doesn't demonstrate what the chosen step needs. Folding that into the other values would be dishonest. |
| No ANN index on the card embeddings | Exact scan is correct and fast at this corpus size; add HNSW in a migration when it isn't. |
| A record is never shown as a sentence | `plain.fit_line` returns prose this repo wrote, for every shape of record — including one it has no wording for, via an explicit fallback. It previously fell through to the probe's own `reason`, which put a raw numpy message ("Input X contains infinity...") on a dataset page. Technical reasons now live only in the "How I checked this" disclosure. The one text that passes through untouched is `BridgeSpec.no_probe_reason`, because that is curated prose and §4 requires it be printed. |
| Probes drop non-finite rows, not just NaN | `np.isnan` is False for ±inf, so a single infinity survived the row filter and then failed every seed inside sklearn, costing the page its fit line entirely. Sensor exports carry infinities routinely. `prepare_xy` filters on `np.isfinite`. |
| A stuck queue is derived, not tracked | `stalled` is computed on every read from the age of the queue's **head** — not from a job's own age, and not from `queue_position`. Second in line has position 1 and was created seconds ago, so both of those call it healthy while nothing is draining. A worker-liveness table would let `POST /bridge/runs` refuse honestly instead of queueing into a void (the `train.py` TRAINING_ENABLED principle), but that is persistent schema and a migration to catch "I forgot to restart the worker", which the runbook now covers. Build it if this ever recurs in the deployed App Runner + Fargate split, where it fails differently. |
| `LANGCHAIN_API_KEY` in backend/.env | Is actually a **Tavily** key (`tvly-` prefix), unused by anything. The API-feasibility path uses the curated `api_registry.json` + plain httpx per §7's scope guard. |

## 4. Environment variables and keys

All bridge keys are `Optional` in `Settings` so the web container boots without
them; `check_bridge_registry()` refuses to boot only if `BRIDGE_ENABLED=true`
while a required key is missing.

**Status below is this dev machine's `backend/.env`, not a claim about prod.** For
the AWS deployment's secrets/rollout, see §7.

| Variable | Needed for | Status (local dev only) |
|---|---|---|
| `ANTHROPIC_API_KEY` | planner / judge / summary | ✅ in backend/.env |
| `VOYAGER_API_KEY` | Voyage embeddings (passed explicitly; the SDK's own `VOYAGE_API_KEY` lookup never runs) | ✅ in backend/.env |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_HOST` | tracing (free account at cloud.langfuse.com) | ✅ in backend/.env; **required** everywhere `BRIDGE_ENABLED=true`, including prod (`HOST` excluded — it has a real code default) |
| `KAGGLE_USERNAME` / `KAGGLE_KEY` | the Kaggle scout (kaggle.com/settings → API) | ✅ in backend/.env, scout live; **required** everywhere `BRIDGE_ENABLED=true`, including prod |
| `BRIDGE_ENABLED` | the live path (router + drain) | default **false**, set true in backend/.env locally; CLI works regardless |
| `RATE_LIMIT_BRIDGE`, `BRIDGE_VERDICT_SPEND_CEILING_USD`, `BRIDGE_DAILY_SPEND_CAP_USD`, `BRIDGE_RUN_TIMEOUT_SECONDS`, `BRIDGE_JOB_*`, `BRIDGE_SCOUT_CONCURRENCY`, `BRIDGE_MAX_JUDGED_CANDIDATES` | tuning | sensible defaults in `core/config.py` |

## 4b. Where a student meets this

The finder lives in each model's learn rail ("Find a dataset →", above "Start
training →"), so it is scoped to the step being learned. That page shows three
hand-picked datasets for that step and a search box; every other checked topic
stays in the cache and surfaces the moment its name is typed, which is what
keeps the page short as the library grows. Promoting more datasets is therefore
a deliberate act of curation, not a way to grow a list.

Currently featured (probe PASS, permissive licence, least cleaning, varied
subjects):

| Step | Featured topics |
|---|---|
| step0 single neuron | mushroom edibility, titanic survival, breast cancer diagnosis |
| step1 MLP | heart disease, air quality, student exam performance |

Promote with `cli promote <slug> <step>`, pull one back with `cli demote`.

## 5. Local runbook

One-time setup (already done on this machine):

```bash
brew install pgvector                      # builds against postgresql@18
psql -d ncplusplus_dev  -c 'CREATE EXTENSION vector'   # pgvector is NOT a
psql -d ncplusplus_test -c 'CREATE EXTENSION vector'   # trusted extension —
                                                       # needs a superuser once
.venv/bin/pip install -r backend/requirements-worker.lock.txt
.venv/bin/alembic -c backend/alembic.ini upgrade head
```

Run a verdict from the CLI (no worker or web needed):

```bash
.venv/bin/python -m backend.services.bridge.cli run --topic "wine quality" --model step1
.venv/bin/python -m backend.services.bridge.cli list-drafts
.venv/bin/python -m backend.services.bridge.cli promote wine-quality step1
```

Seed the library (18 topics × steps 0/1 took ~14 min and $0.38, hard-capped by
`--max-spend`). Re-run the sentence generation after any prompt change with
`cli resummarise` (~$0.03 for the whole library):

```bash
.venv/bin/python -m backend.services.bridge.cli seed \
    --topics backend/services/bridge/seed_topics.json --steps step0,step1,step3
```

Full local stack (the live path through the UI):

```bash
# backend/.env: BRIDGE_ENABLED=true
.venv/bin/uvicorn backend.main:app --reload --port 8000   # terminal 1
.venv/bin/python -m backend.worker                        # terminal 2
cd frontend && npm run dev                                # terminal 3
# → http://localhost:5173 → a model → Learn → "Find a dataset →" in the rail
```

> **Restart the worker after any backend change. It does not auto-reload.**
> uvicorn has `--reload` and the worker has no equivalent, so a long-lived
> worker silently keeps running whatever code it imported at startup. This has
> already cost one debugging session: a worker started before `bridge_drain`
> existed had no drain thread at all, so submitted runs sat `queued` forever
> while the API happily accepted them and the UI polled every 2 seconds. The
> tell is a run whose `started_at` is NULL long after `created_at`, and the
> confirmation is `bridge drain started` missing from the worker's log.
>
> The API now reports `stalled: true` on any queued job once the head of the
> queue goes unclaimed past `BRIDGE_JOB_QUEUE_STALE_SECONDS` (300s), and the
> finder says so instead of "starting up" and offers "Stop waiting", which
> cancels the job and frees the one-active-run slot. That makes the failure
> visible; it does not make it stop happening. Restart the worker.

Tests: `.venv/bin/pytest` (the bridge suite is `backend/tests/unit/test_bridge_*`
+ `backend/tests/test_bridge_endpoints.py`; the probe self-tests double as the
§3 CI gate). Probe fixtures regenerate via
`python -m backend.services.bridge.probes.fixtures.generate`.

## 5b. Dependency hygiene

`requirements-worker.txt` declares every package the bridge imports directly,
including `httpx`, `tenacity` and `kagglesdk`, which each also arrive
transitively today (via langfuse, voyageai and kagglehub). A direct import
resting on someone else's dependency breaks the day that package drops it. The
lockfiles are unchanged by those declarations because the resolved set already
pinned them, and **Docker installs from the lock, never the .txt**.

Do not regenerate the lockfiles casually: a fresh resolve today pulls unrelated
major bumps (anthropic 1.0, fastapi 0.141, httpx2). The pins are what the live
verification ran against.

## 6. Data lifecycle

- **Live run**: POST /bridge/runs → `bridge_jobs` row → bridge-drain thread
  claims it → pipeline writes a `bridge_verdicts` DRAFT row → the requester can
  view it; it enters the public library only after `promote`.
- **Seed run**: same pipeline, `source='seed'`, no user; spend is ledgered the
  same so the daily cap sees it.
- **Pools** are keyed `(topic_slug, modality)` and shared across steps — adding
  step3 to a topic that ran step1 reuses the whole search.
- **Dataset rot**: `last_verified` is stamped on verdicts and pools; gates
  re-inspect live on every fresh assessment. A background revalidation sweep is
  future work (bridge-plan-v3.md §19).

## 7. AWS deployment appendix (when the time comes)

The bridge rides the existing two-image topology (`DEPLOYMENT_GUIDE.md`): the
single-container web service on App Runner, the worker on Fargate. Additions:

1. **Secrets, in BOTH places** — this is the step that bites (§12): add all six of
   `ANTHROPIC_API_KEY`, `VOYAGER_API_KEY`, `KAGGLE_USERNAME`, `KAGGLE_KEY`,
   `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` to Secrets Manager — required, not
   optional, in this project — then reference them in **both**
   `apprunner-web.json` → `RuntimeEnvironmentSecrets` **and** the Fargate
   `worker-taskdef.json` → `secrets`, **and** add their ARNs to both IAM
   `read-secrets` role policies (an explicit ARN allowlist, not a wildcard — a
   secret missing from it fails at container start with `AccessDenied`, not at
   `create-secret` time). `Settings()` tolerates their absence at import (fields
   are Optional), but `check_bridge_registry()` refuses to boot **either**
   service with `BRIDGE_ENABLED=true` and any of the six missing — by design.
2. **RDS pgvector** — once, as the RDS master user:
   `CREATE EXTENSION vector;` on the app database. pgvector is on RDS's
   supported-extension list; the migration's `IF NOT EXISTS` then no-ops.
   Without this the `a3c9e51f7d24` migration aborts with a clear message.
3. **Worker egress** — the worker (public-IP Fargate task per the deployment
   guide; NAT optional) must reach: `api.anthropic.com`, `api.voyageai.com`,
   `huggingface.co` + `datasets-server.huggingface.co`, `www.kaggle.com`,
   `cloud.langfuse.com`, and the `api_registry.json` hosts. No inbound anything.
4. **Rollout order** — deploy with `BRIDGE_ENABLED=false` everywhere; run the
   migration (web entrypoint does); flip `BRIDGE_ENABLED=true` on **worker
   first**, then web. The router 503s POSTs until its own flag is on, so no
   zombie jobs either way.
5. **Seeding from local, not cloud** — the seed CLI runs against the prod
   `DATABASE_URL` from your machine (it's a one-off, auditable, and avoids
   giving the cloud worker a long-lived batch workload).
6. **nginx** — `/bridge` is already in the API-prefix regex in
   `docker/nginx.conf.template` (and the vite dev proxy); no further routing
   work. Remember `add_header` does not merge — don't add headers in that
   location block.
7. **Cost posture in prod** — the same three guardrails apply unchanged; the
   daily cap is global, so a traffic spike degrades to 429s, not spend. If the
   site ever gets real traffic, revisit `RATE_LIMIT_STORAGE_URI` (Redis) so
   limits hold across instances — already documented in `core/config.py`.

## 8. Evaluation status (bridge-plan-v3.md §15)

- **Positive fixtures**: in CI (`test_bridge_probes.py`) — each step's template
  passes its own probe.
- **Step discrimination**: in CI — step0's blobs fail step1's reading and vice
  versa; the live wine-quality run demonstrated the honest UNCONFIRMED case
  (gap +0.014 inside a 0.035 band, both steps offered).
- **Negative fixtures / live fixture hand-check / collection-time check**:
  to run as the library seeds; record results here.
