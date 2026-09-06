# Project Context — `pranav-2399/hpa` (AI-Driven Kubernetes Horizontal Pod Autoscaler)

_Generated from a live clone of the repo on 2026-09-06. This reflects what is **actually implemented in code**, not the original plan document._

## 1. High-Level Summary

The repo builds an AI-driven Kubernetes autoscaler: a Prometheus-monitored Flask "workload" app is scaled up/down by a Python `autoscaler` agent that calls an LLM (Groq/Llama) to reason about scaling decisions, exposes its state via a Flask REST `server`, and visualizes it in a React `frontend` dashboard. There's also a `k8s/` folder with manifests for deploying the workload with a native Kubernetes HPA in parallel.

Four components exist side-by-side and are only partially wired together:
1. `app/` — the monitored workload (e-commerce-style Flask API)
2. `autoscaler/` — the AI decision engine (fully built, in-memory persistence)
3. `server/` — REST API bridging autoscaler ↔ frontend (built as a single file, simpler than planned)
4. `frontend/` — React + Vite dashboard (built, polls the server every 5s)

Plus `k8s/` (manifests) and root-level `Dockerfile` / `requirements.txt` / `run.py` / `app.py` / `prometheus.yml`.

---

## 2. Component-by-Component Status

### 2.1 `app/` — Monitored Workload Application
A **Flask e-commerce-style API**, standing in as the "real" workload that gets load-tested and autoscaled — not literally described in the original plan, which just said "Workload Application."
- Structure: `app/__init__.py` (factory `create_app`), `app/config.py`, `app/extensions.py` (SQLAlchemy `db`), `app/models.py`, `app/utils.py`
- Routes (blueprints), each under `/api/...`: `health`, `auth`, `users`, `products`, `categories`, `orders`, `cart`, `reviews`, `search`, `analytics`, `notifications`, `admin`
- Instruments itself with `prometheus_flask_exporter` (best-effort; wrapped in try/except so missing package doesn't break startup)
- Persistence: SQLAlchemy, defaults to SQLite in the Dockerfile (`sqlite:////data/app.db`), overridable via `DATABASE_URL`
- Entry point: `run.py` → `app.create_app()`; `app.py` at root is a thin backward-compatible shim importing from `run.py`
- Packaged via the root `Dockerfile` (multi-stage build, non-root user, Gunicorn w/ 4 sync workers)

### 2.2 `autoscaler/` — AI Decision Engine (fully implemented)
This is the most complete part of the repo. Structure:

- **`config.py`** — `AutoscalerConfig` dataclass loading everything from env/`.env`: cluster/K8s settings, Prometheus URL, `DATABASE_URL`, Groq/LLM settings (`GROQ_API_KEY`, model `openai/gpt-oss-20b` by default — **note: the plan doc said Llama 3.3, but the actual default model configured in code is `openai/gpt-oss-20b`**), scaling thresholds (CPU 75%, memory 80%, min/max replicas 1–10), and cost-per-pod-hour.
- **`models/`** — plain dataclasses, no ORM: `Cluster`/`Pod` (cluster.py), `MetricSnapshot` (metrics.py), `TrafficPrediction` (prediction.py), `ResourceAnalysis`/`CostAnalysis` (analysis.py), `ScalingRecommendation`/`ScalingAction` + action constants (recommendation.py), `DecisionLog` (decision_log.py). Each model has small domain methods (e.g. `calculateAverageLoad()`, `detectOverUtilization()`, `isTrafficIncreaseExpected()`).
- **`services/`**:
  - `PrometheusService` — queries PromQL (`/api/v1/query`), fails soft (returns `[]`/logs warning) if Prometheus is unreachable
  - `KubernetesService` — wraps the official `kubernetes` Python SDK; loads either in-cluster or local kubeconfig; reads pod/deployment state and can scale
  - `PredictionService` — very simple linear-trend forecaster over recent RPS history (mean + slope), **not** a real ML model
  - `ResourceAnalysisService` — classifies CPU/Memory as OVER/UNDER/NORMAL vs configured thresholds, computes recommended replicas using the standard `ceil(current * (currentUtil/targetUtil))` HPA formula
  - `CostAnalysisService` — trivial `pods × cost-per-hour` arithmetic, compares current vs recommended
  - `LLMService` — builds a structured prompt from the four summaries above and calls the Groq-compatible chat completions endpoint
- **`repositories/`** — repository pattern with a `DatabaseService` + `BaseRepository` base class. **Important:** `DatabaseService.connect()` attempts a real `psycopg2` connection to Postgres, but on *any* failure (or if not "postgresql" in the URL) it silently falls back to Python-process in-memory dicts — and even `executeQuery()` is essentially unused by the repos. All six repositories (`Metric`, `Prediction`, `ResourceAnalysis`/`CostAnalysis`, `ScalingAction`, `DecisionLog`) currently **read/write to an in-memory `_store` dict, not Postgres**, regardless of whether `DATABASE_URL` is set. So all history is lost on process restart.
- **`agent/decision_coordinator.py`** — the core orchestrator (`DecisionCoordinator`), ~270 lines. Its control loop (`runSingleControlLoopIteration`, invoked by `autoscaler/main.py` or the server's `/api/agent/trigger`):
  1. `analyzeSystemState()` — pulls CPU/Mem/RPS/latency from Prometheus + current replica count from K8s → builds & saves a `MetricSnapshot`
  2. `collectAnalysisResults()` — runs prediction, resource analysis, and cost analysis services, saving each
  3. `generateDecision()` — builds an LLM prompt from all of the above and gets back a scaling decision + reasoning + confidence, saved as a `DecisionLog`
  4. (further in the file, not fully re-inspected) validates the decision against min/max replicas and stabilization window, then executes the scale via `KubernetesService` and logs a `ScalingAction`
- **`main.py`** — `build_autoscaler_agent()` factory wiring all services/repos/coordinator together from `config`; CLI entry point supports `--once` (single iteration, prints summary) or continuous polling loop (`--interval`, default 30s)

### 2.3 `server/` — REST API Bridge
Implemented as a **single file** (`server/app.py`), not the `routes/` sub-package structure the original plan proposed (`metrics_api.py`, `agent_api.py`, `cluster_api.py`, `analytics_api.py`). Current endpoints actually built:

| Endpoint | Method | Status vs plan |
|---|---|---|
| `/api/cluster/status` | GET | ✅ built — returns snapshot + K8s state + per-pod utilization |
| `/api/metrics/history` | GET | ✅ built — returns recent `MetricSnapshot`s (in-memory only, see above) |
| `/api/agent/decisions` | GET | ✅ built — recent `DecisionLog`s |
| `/api/actions/history` | GET | ✅ built — recent `ScalingAction`s, replaces planned `/api/agent/recommendations` naming |
| `/api/agent/trigger` | POST | ⚠️ not in original plan — manually fires one control-loop iteration (used by the frontend's "trigger" button) |
| `/api/analytics/summary` or `/api/analytics/predictions` / `/api/analytics/costs` | GET | ❌ **not built yet** — no analytics/predictions/cost endpoint exists in `server/app.py` despite being in the plan and despite a `CostPredictionWidget` being planned for the frontend |

The server instantiates one shared `DecisionCoordinator` at startup (`build_autoscaler_agent()`) and reuses it across requests — so the manual `/api/agent/trigger` endpoint and the standalone `autoscaler/main.py` polling loop would run **two independent coordinator instances** with two independent in-memory stores if both are run at once (no shared state between them apart from Prometheus/K8s ground truth).

CORS is enabled (`flask-cors`) for the frontend. Runs on port 5001 (separate from the workload app's port 5000).

### 2.4 `frontend/` — React Dashboard
Vite + React 18 app (not TypeScript). Structure differs slightly from the plan's proposed component names:

| Plan component | Actual file | Status |
|---|---|---|
| `Header.jsx` | ✅ same name | built — shows status, has the manual "trigger loop" button, last-updated time |
| `MetricCards.jsx` | ✅ same name | built — KPI cards from cluster status |
| `RealtimeCharts.jsx` | → `MetricsChart.jsx` | built under a different filename, uses `recharts` |
| `AgentReasoningFeed.jsx` | ✅ same name | built |
| `ReplicaTimeline.jsx` | → `ScalingTimeline.jsx` | built under a different filename |
| (pod grid, implied by "Pod Replica Visualizer" feature) | `PodVisualizer.jsx` | built (not explicitly named in the plan's file list, but matches feature #3) |
| `CostPredictionWidget.jsx` | — | ❌ **not built** — no cost/forecast widget exists yet, consistent with the missing `/api/analytics/*` backend endpoint |

- `App.jsx` polls all four working endpoints every 5 seconds via `setInterval` and renders the grid layout described in the plan (metric cards → chart → 2-column [reasoning feed, pod visualizer] → scaling timeline)
- `services/api.js` — plain `fetch`-based client (not Axios, despite the plan mentioning "Axios/Fetch client"), hardcoded to `http://localhost:5001/api` (not environment-configurable yet)
- Dependencies: `react`, `react-dom`, `recharts`, `lucide-react`; dev: `vite`, `@vitejs/plugin-react`
- No dark/glassmorphism CSS confirmed in detail (`index.css` exists but wasn't inspected line-by-line)

### 2.5 `k8s/` — Kubernetes Manifests
- `deployment.yaml`, `service.yaml` — for the workload app (`app/`)
- `hpa.yaml` — a **native Kubernetes `HorizontalPodAutoscaler` (autoscaling/v2)** for `hpa-flask`, min 2 / max 10 replicas, CPU 50% + memory 70% targets, custom scale-up/down behavior (fast scale-up, conservative scale-down). This runs **independently of and in addition to** the custom AI `autoscaler/` agent — i.e., the repo currently has two autoscaling mechanisms that could fight each other if both are pointed at the same deployment (worth flagging to the user).

### 2.6 Root-level files
- `Dockerfile` — builds only the `app/` workload image (multi-stage, non-root, Gunicorn); does **not** yet containerize `autoscaler/`, `server/`, or `frontend/`
- `requirements.txt` — Flask, Flask-SQLAlchemy, flask-cors, prometheus-flask-exporter, Werkzeug, gunicorn, requests, kubernetes SDK, psycopg2-binary, pydantic
- `prometheus.yml` — scrape config (per the plan)
- `run.py` — entry point for the workload app; `app.py` — backward-compat shim

---

## 3. Gaps / Divergences From the Original Plan (things to know before building further)

1. **No real database persistence yet.** `DATABASE_URL`/Postgres is configured but `BaseRepository` silently falls back to in-memory dicts on any connection issue — right now it *always* falls back because `executeQuery` is never actually used to persist entities. All metrics/decisions/actions vanish on restart.
2. **Analytics/cost endpoints are missing** on the backend (`/api/analytics/summary`, predictions, costs) and correspondingly the frontend's cost/forecast widget was never built.
3. **Two independent autoscalers exist**: the native K8s `HorizontalPodAutoscaler` (`k8s/hpa.yaml`) and the custom AI `DecisionCoordinator` loop. If both are deployed against the same target, they can conflict.
4. **LLM model mismatch**: plan says Llama 3.3 via Groq; code defaults to `openai/gpt-oss-20b` (still via the Groq-compatible endpoint) — easy to override via `LLM_MODEL_NAME` env var, but worth confirming which model you actually want.
5. **Prediction model is a naive linear trend**, not any kind of trained/ML model — fine for a demo, but worth knowing if "prediction" claims need to be accurate.
6. **Server structure simplified**: one `server/app.py` file instead of the planned `server/routes/*.py` split — functionally fine at this size, but will need refactoring if more endpoints are added.
7. **No `.env` file checked into the repo** (expected/good for secrets), so `GROQ_API_KEY`, `DATABASE_URL`, etc. must be supplied by whoever runs it.
8. **Containerization is partial** — only the workload app has a Dockerfile; `autoscaler/`, `server/`, and `frontend/` have no Dockerfiles/compose setup yet, so running the full stack today means running each piece manually.

---

## 4. Decisions Made (resolving the open questions above)

1. **Scope**: all four gaps get closed — persistence, analytics/cost endpoints, dual-autoscaler conflict, and containerization.
2. **Deployment target**: an actual Kubernetes cluster via **minikube** (not Docker Compose).
3. **Native K8s HPA vs AI autoscaler**: kept **both**, made **switchable from the frontend** — the user can toggle live between the built-in K8s `HorizontalPodAutoscaler` and the custom AI agent from the dashboard UI.
4. **LLM model**: switch to **Llama 3.3** (`llama-3.3-70b-versatile`) via Groq, resolving the `config.py` vs `LLMService` default mismatch in favor of Llama 3.3 everywhere.

---

## 5. Implementation Plan — Closing All Gaps (Minikube target)

Sequenced so each phase is independently testable before the next builds on it, since they touch shared code (coordinator, server, k8s manifests).

**Order of execution:** Persistence → LLM switch → Autoscaler mode toggle (the big one) → Analytics/cost endpoints → Containerization → Dual-HPA resolution (folded into the toggle work) → Final integration test on minikube.

### Phase 0 — Preconditions (verify before touching code)

1. Confirm `minikube` is running with the metrics-server addon enabled (`minikube addons enable metrics-server`) — required for both the native K8s HPA and for `KubernetesService`/Prometheus CPU/memory queries to return real numbers.
2. Confirm Prometheus is deployed inside/reachable from the minikube cluster (or at least reachable from wherever `autoscaler/main.py` and `server/app.py` run), and that `prometheus.yml`'s scrape target matches the actual Service DNS name of `app/` inside the cluster (not `localhost:5000`, which only works if autoscaler runs outside the cluster with port-forwarding).
3. Confirm a real Postgres instance is reachable (either as a minikube-deployed pod/Service, or external) so Phase 1 has something to connect to.
4. Get a Groq API key with Llama 3.3 access enabled (needed for Phase 2).

### Phase 1 — Fix Real Postgres Persistence

**Problem:** `BaseRepository` reads/writes an in-memory `_store` dict; `DatabaseService.executeQuery()` is never actually called by any repository.

1. Design a minimal schema (6 tables): `metric_snapshots`, `traffic_predictions`, `resource_analyses`, `cost_analyses`, `scaling_actions`, `decision_logs` — one row per dataclass field, plus a `cluster_id` and timestamp column on each (mirrors existing dataclasses in `autoscaler/models/`).
2. Add a lightweight migration mechanism: either raw SQL DDL run once at `DatabaseService.connect()` time (`CREATE TABLE IF NOT EXISTS ...`), or introduce Alembic if proper migrations are wanted going forward. For this project's size, raw DDL is proportionate.
3. Rewrite `BaseRepository.save()`, `findById()`, `findAll()`, `findByCluster()`, `findByTimeRange()`, `delete()` in each of the 6 concrete repository classes to issue real SQL via `self.db_service.executeQuery(...)` instead of touching `self._store`. Each dataclass needs a `to_row()`/`from_row()` (or reuse the existing `to_dict()` methods already on some models) for serialization.
4. Remove the silent in-memory fallback in `DatabaseService.connect()` — or at minimum, log it loudly / expose it in `/api/cluster/status` as a `"persistence": "degraded"` flag, so a broken Postgres connection is visible instead of silently swallowed.
5. Handle JSON columns: `DecisionLog.inputSummary` is a `Dict[str, Any]` — store as `JSONB` in Postgres.
6. Update `Step 1.1` of the original setup guide unchanged (it already provisions `hpa_user`/`hpa_db`) — just make sure `DATABASE_URL` is actually passed into whichever pod/process runs the autoscaler on minikube (via a K8s `Secret`/`ConfigMap`, not just a local `.env`).
7. **Test:** run `autoscaler/main.py --once` twice in separate processes; confirm the second run's `getRecentSnapshots()` includes data from the first run (proves it survived a process restart, i.e., is no longer in-memory-only).

### Phase 2 — Switch LLM to Llama 3.3 via Groq

1. In `autoscaler/config.py`, change the default: `LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "llama-3.3-70b-versatile")` (this is already the value `LLMService`'s own constructor default uses — just make `config.py`'s default consistent with it, since currently `config.py` defaults to `openai/gpt-oss-20b` while `LLMService.__init__` defaults to `llama-3.3-70b-versatile` — they disagree today).
2. Verify `LLMService.buildPrompt()`'s output format matches what Llama 3.3 responds well to (Llama 3.3 via Groq's OpenAI-compatible endpoint should work unchanged, but re-check any response-parsing assumptions in `LLMService` for JSON-mode/tool-call quirks specific to the old model).
3. Update the `GROQ_API_KEY` setup step (already in the original guide) — no change needed there, just confirm the key has Llama 3.3 access.
4. **Test:** run `--once` and inspect the printed `Recommendation` — confirm `DecisionLog.reasoning` reads like coherent Llama output and `modelUsed`/logged model name reflects `llama-3.3-70b-versatile`.

### Phase 3 — Switchable Autoscaler Mode (Native K8s HPA ⟷ AI Autoscaler), controlled from the frontend

This is the largest phase. Goal: a toggle in the dashboard lets the user pick which mechanism is actively scaling `hpa-flask`, with no conflict between the two.

**3.1 — Mutual exclusion mechanism**
1. The native K8s HPA and the AI autoscaler must never both be actively adjusting replicas at once. Since `k8s/hpa.yaml` is a real K8s object that acts continuously once applied, "switching modes" means **applying or deleting the `HorizontalPodAutoscaler` object itself**, not just pausing a loop.
2. Introduce a `KubernetesService` method `enableNativeHPA()` / `disableNativeHPA()` that uses the K8s Python SDK's `AutoscalingV2Api` to create/delete the `HorizontalPodAutoscaler` resource for `hpa-flask` in-cluster (reading the manifest content from `k8s/hpa.yaml`, templated so it can be created programmatically rather than only via `kubectl apply`).
3. Introduce a shared **mode state** — a simple row/key in Postgres (or a K8s `ConfigMap`, given you're already in-cluster) storing `autoscaler_mode: "NATIVE_HPA" | "AI_AGENT"`. Postgres is preferable since Phase 1 already gives a persistence layer.
4. `DecisionCoordinator.runSingleControlLoopIteration()` must check this mode at the top of each iteration and **no-op** (skip analysis/decision/execution, just log "AI autoscaler is in standby") if mode is `NATIVE_HPA`. This means the continuous polling loop (`autoscaler/main.py`) keeps running always, but only *acts* when in `AI_AGENT` mode — this way there's no race between "loop running" and "loop should be running."

**3.2 — Backend endpoints (`server/app.py`)**
1. `GET /api/autoscaler/mode` — returns current mode (`NATIVE_HPA` / `AI_AGENT`) plus whether the native HPA object currently exists in-cluster (sanity check for drift).
2. `POST /api/autoscaler/mode` — body `{"mode": "NATIVE_HPA" | "AI_AGENT"}`. On switch to `NATIVE_HPA`: call `enableNativeHPA()`, persist mode. On switch to `AI_AGENT`: call `disableNativeHPA()` (delete the K8s HPA object so it stops interfering), persist mode. Return the new state.
3. Guard against invalid transitions (e.g., no-op if already in the requested mode) and surface K8s API errors (e.g., RBAC permission issues — minikube's default service account may need a `ClusterRole`/`RoleBinding` granting `autoscaling` API group access if the server/autoscaler runs in-cluster).
4. Extend `/api/cluster/status` response to include the current `autoscalerMode` so the frontend header can reflect it without a second round-trip.

**3.3 — Frontend changes**
1. Add a mode toggle (e.g., a segmented control or switch) in `Header.jsx`, next to the existing "trigger loop" button.
2. Extend `services/api.js` with `fetchAutoscalerMode()` and `setAutoscalerMode(mode)`.
3. When mode is `NATIVE_HPA`, the "trigger loop" button and `AgentReasoningFeed` should visually indicate "AI agent is in standby" (grey out / show a banner) rather than pretending decisions are being made.
4. Add a confirmation step in the UI before switching modes (this changes live cluster behavior — a stray click shouldn't silently swap autoscalers).
5. Poll `/api/autoscaler/mode` on the same 5s interval as the rest of the dashboard so mode changes made elsewhere (e.g., via `kubectl` directly) are reflected.

**3.4 — RBAC for minikube**
1. Since `KubernetesService` needs to create/delete `HorizontalPodAutoscaler` objects (not just read pod status as it does today), if `server/` or `autoscaler/` runs in-cluster it needs a `ServiceAccount` with a `Role`/`ClusterRole` granting `get/list/watch/create/delete` on `horizontalpodautoscalers` in the `autoscaling` API group, plus existing permissions for `deployments/scale`, `pods`, etc. Add this as a new manifest, e.g. `k8s/rbac.yaml`.
2. If instead `server/`/`autoscaler/` run outside the cluster (local process using `~/.kube/config` against minikube), this is simpler — just make sure the local kubeconfig user has these permissions (default minikube admin context does).

**Test:** From the dashboard, switch to `AI_AGENT` mode → confirm `kubectl get hpa` shows no `hpa-flask` HPA object, and the AI loop starts producing `DecisionLog`s and executing scale actions. Switch back to `NATIVE_HPA` → confirm the HPA object reappears via `kubectl get hpa`, and the AI loop's next iteration logs standby with no scaling action.

### Phase 4 — Analytics & Cost Endpoints + Frontend Widget

1. Add `GET /api/analytics/summary` to `server/app.py`, aggregating:
   - Latest `TrafficPrediction` (via `predictionRepo.getLatestPrediction()`)
   - Latest `CostAnalysis` (via `costRepo.getLatestAnalysis()` — note: check if this method exists on `CostAnalysisRepository`, since only `ResourceAnalysisRepository` was confirmed to have `getLatestAnalysis()` — add it if missing, mirroring the resource repo's pattern)
   - A simple cost-over-time series (current vs projected, per recent snapshot) for the frontend chart
2. Decide whether to keep it as one combined `/api/analytics/summary` endpoint (simpler, matches what's already partially planned) or split into `/api/analytics/predictions` and `/api/analytics/costs` as the original plan proposed — recommend keeping it combined since the frontend widget needs both together anyway.
3. Build `frontend/src/components/CostPredictionWidget.jsx`: forecast graph (traffic prediction vs actual) + a cost comparison (current hourly cost vs projected cost if the AI recommendation were applied), using `recharts` to match `MetricsChart.jsx`'s existing style.
4. Wire it into `App.jsx`'s grid layout and `services/api.js`.
5. **Test:** confirm the widget updates on the same 5s polling cycle and reflects the Phase 1 persisted history (not just the current process's memory).

### Phase 5 — Containerize `autoscaler/`, `server/`, and `frontend/`

Currently only `app/` has a Dockerfile.

1. **`autoscaler/Dockerfile`** — Python image, installs `requirements.txt`, runs `python -m autoscaler.main --interval 30`. Needs the K8s SDK to reach the in-cluster API (use in-cluster config + a mounted ServiceAccount token when deployed as a Pod — set `IN_CLUSTER=true`).
2. **`server/Dockerfile`** — Python image, runs via Gunicorn (`gunicorn -w 2 -b 0.0.0.0:5001 server.app:create_server_app()`) or similar factory-pattern invocation.
3. **`frontend/Dockerfile`** — multi-stage: `npm run build` → serve static assets via nginx (or similar), with the API base URL made configurable at build/runtime (currently hardcoded to `http://localhost:5001/api` in `services/api.js` — this must become an environment-driven value, e.g. injected via a runtime `env.js` or Vite `.env` build arg, since inside minikube the frontend won't reach the server at `localhost`).
4. Add corresponding `k8s/` manifests: `autoscaler-deployment.yaml`, `server-deployment.yaml` + `server-service.yaml`, `frontend-deployment.yaml` + `frontend-service.yaml` (and an `Ingress` or `NodePort`/`minikube service` exposure so the dashboard can be reached from a browser outside the cluster).
5. Build images directly into minikube's Docker daemon (`eval $(minikube docker-env)` then `docker build ...`) or push to a registry minikube can pull from, to avoid `ImagePullBackOff`.
6. **Test:** `kubectl apply -f k8s/` deploys the full stack; `minikube service frontend-service` opens the dashboard in a browser, and it's able to reach the server, which reaches Postgres/Prometheus/K8s API — full closed loop.

### Phase 6 — Full Integration Test on Minikube

1. Deploy everything (`app/`, `autoscaler/`, `server/`, `frontend/`, Postgres, Prometheus, RBAC) via `kubectl apply -f k8s/`.
2. Generate load against `app/` (e.g., a simple `hey`/`ab`/`k6` script) to trigger real CPU/RPS changes.
3. Confirm in `NATIVE_HPA` mode: `kubectl get hpa hpa-flask -w` shows replica changes reacting to load, dashboard reflects it read-only.
4. Switch to `AI_AGENT` mode via the dashboard toggle: confirm native HPA object is removed, AI loop starts making decisions with Llama 3.3, `DecisionLog`/`ScalingAction` rows appear in Postgres and survive a pod restart, and replicas actually change via `KubernetesService`'s scale call.
5. Confirm the cost/prediction widget updates meaningfully as load changes.
6. Switch back to `NATIVE_HPA`, confirm clean handoff with no double-scaling or orphaned HPA objects.

