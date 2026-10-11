# jev-lab

Demo companion for the Jev article. One command from clone to working app.

**What Jev is, in two sentences:** Jev is TypeSafe's System One decision model — text state in, typed answers out. You send `state` + typed `questions` (Choice/Score/Noul) to `POST /v1/systemone` and get structured answers with probabilities your code can branch on.

## Quickstart (3 commands)

```bash
git clone <this-repo> && cd jev-lab
make setup
make run
```

Opens the Playground on a pre-filled example. No key needed (demo mode).

Live mode:

```bash
cp .env.example .env   # add TYPESAFE_API_KEY
make run-live
```

Windows (no `make`): `uv run streamlit run streamlit_app.py`.

Normal flow once you have a key: `make record-rec && make test`.

Public demo deploys: set `JEV_PUBLIC_DEMO=1` — the app never loads the key at all, so a misconfigured deployment can't spend.

## Demo vs live mode

* **Demo:** recorded scenarios only, served from `recordings/` (real Jev responses with `recorded_at` + resolved model). Editors shown disabled; free typing disabled ("add a key"). Cache-miss = friendly error, never a fake answer.
* **Live:** fully editable, hits the real API through the $1 guardrail. `make record-rec` refreshes recordings (`RECORD_ARGS="--force"` to re-record).
* Only `recordings/ILLUSTRATIVE_shape_example.json` is hand-made and labeled `_origin: illustrative` — never presented as Jev output.

## Tab tour

Sidebar radio in suggested order (Playground → Fan-out → Gates → Chat, ~8 min, free order, ✓ checklist + closing card). Beginner view is default (expert shows raw JSON); all wording lives in `ui/help_text.yaml`.

1. **Playground** — string vs JSON state, request anatomy, cURL/Python snippets.
2. **Support Desk Chat** — left chat, right 5-step "What just happened" panel (build state → 1 call → answers → rules checklist → named template). Beginner/expert toggle, what-if threshold sliders (re-decide, no call), token-growth meter, budget pill, reset. Replies are canned templates; Jev only judges. Priority handoffs go to a human queue. Demo only — in a real emergency, contact local emergency services.
3. **Parallel fan-out** — 1 batched vs 8 sequential vs 8 parallel (cap 4); warm-up excluded, interleaved, ≥5 runs median+range, retries flagged, token/cost panel ("state resent 8×"), recording stamp.
4. **Confidence gates** — 30 inbox tickets re-sorted live by sliders (Choice/Score confidence pair + Noul P(yes) pair, proxy reference-only). Mechanics demo at frozen defaults, not an accuracy figure.

Calibration is **not in v1** (see "How we score Score" for the deferred definitions; `metrics.py` kept for later).

## Presets (chosen from N candidates — see `recordings/manifest.json`)

Playground keeps 5 presets for teaching value; rejects stay in the manifest with full state/questions/result. The injection preset demonstrates a safety Noul; one example is not a robustness evaluation. Scripted 3-turn chats replay exactly (deterministic templates); history window is fixed at 6 in demo (a different window = a different state with no recording).

## Thresholds (frozen before recording)

`override P≥0.75` refuse · `safety P≥0.50` urgent handoff (lower: misses cost more) · `asks_human P≥0.60` handoff · intent conf `<0.50` clarify · urgency/frustration `≥2.5` priority. Sliders show sensitivity; post-record changes get a changelog line here. Recorded intent confidences are bimodal (19/30 at 1.0, tail 0.29–0.70, 4 below 0.50 → clarify) — the 0.50 default works but the distribution is clustered, not spread. First-record agreement: 20/30 at defaults (mismatches mostly safety-threshold sensitivity); thresholds deliberately not retuned.

## How we score Score

Choice/Noul have right/wrong; Score is ordinal + fractional (deferred to post-v1 calibration):

* **Primary: P(true level)** — probability on the labeled level.
* **MAE** — `|score − true_level|` in levels.
* **Within-one rate** — fraction with `|score − true| < 1.0`.

## Data (v1 stand-in)

`data/inbox.jsonl` (30 hand-labeled, labels written before any Jev run, never adjusted after seeing output) replaces the deferred 150-ticket split. Gates wording: "agreement with my labels on 30 examples at defaults." See `data/LABEL_NOTES.md`.

## Budget ($1.00 hard cap)

* One choke point: every live call goes through `client.decide()` → `budget.reserve()` → call → `settle(actual)`. Over cap = `BudgetExceeded`, exit 1. Retries preflight each attempt (SDK internal retries disabled via `RetryPolicy(max_retries=0)`); timeouts count at estimate (possibly billed).
* Estimates over-count by design (350-token overhead + max-observed chars ratio + 10%); spend counted from actual `usage.input_tokens`. Per-request ceiling 64k tok regardless of budget.
* Ledger `.jevlab_usage.json` is local + gitignored. Corrupt/unreadable ledger **blocks** live calls (fail closed, never auto-resets). `make budget-status` shows spend; `python scripts/budget.py --reset-confirm` archives with timestamp (history kept).
* Replay/demo/what-if never touch the ledger. Guardrail is project-local only — check `console.typesafe.ai` for server-side spend limits/alerts, reconcile ledger vs console after larger runs, and rotate the key if it ever appears outside `.env`.

## Honest caveats

* 30 hand-labeled examples show mechanics, not accuracy. Thresholds are starting defaults, not recommendations.
* Limits/prices in `jevlab/limits.yaml` (per-field sources) — beta, `make doctor` warns when >30d stale.
* Recorded latencies depend on network/account/limits — rerun live for timing claims; re-record before publishing (`RECORD_ARGS="--force --where <net>"`).
* All recorded state is synthetic; recordings never contain keys (contract test scans).
* Don't deploy live mode publicly — anyone chatting spends your balance. Public builds: `JEV_PUBLIC_DEMO=1` (demo-only).
