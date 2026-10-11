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

Normal flow once you have a key: `make record && make test`.

## Demo vs live mode

* **Demo:** preset scenarios only, served from `recordings/` (real Jev responses with `recorded_at` + resolved model). Editors are shown disabled so screenshots match live UI. Cache-miss = friendly error, never a fake answer.
* **Live:** fully editable, hits the real API. `make record` refreshes `recordings/` (`RECORD_ARGS="--force"` to re-record; cost is negligible at $0.042/M in-tok).
* Only `recordings/ILLUSTRATIVE_shape_example.json` is hand-made and is labeled `_origin: illustrative` — never presented as Jev output. Calibration requires real recordings.

## Presets (chosen from N candidates — see `recordings/manifest.json`)

4 presets (+1 paired variant) kept for teaching value from ~12 recorded candidates; rejects stay in the manifest with full state/questions/result. The injection preset demonstrates a safety Noul; one example is not a robustness evaluation.

## How we score Score

Choice/Noul have right/wrong; Score is ordinal + fractional. We report three, defined in `jevlab/metrics.py`:

* **Primary: P(true level)** — probability on the labeled level (calibration quantity).
* **MAE** — `|score − true_level|` in levels.
* **Within-one rate** — fraction with `|score − true| < 1.0` (tolerant secondary).

## Tune/test split

`data/` (100 tune / 50 test): thresholds tuned on tune-only, final numbers on test-only. If ever tuned on the reporting set, we say so plainly. See `data/LABEL_NOTES.md` for honest change counts.

## Budget ($1.00 hard cap)

* One choke point: every live call goes through `client.decide()` → `budget.reserve()` → call → `settle(actual)`. Over cap = `BudgetExceeded`, exit 1. Retries preflight each attempt (SDK internal retries disabled via `RetryPolicy(max_retries=0)`); timeouts count at estimate (possibly billed).
* Estimates over-count by design (300-token overhead + max-observed chars ratio + 10%); spend counted from actual `usage.input_tokens`. Per-request ceiling 64k tok regardless of budget.
* Ledger `.jevlab_usage.json` is local + gitignored. Corrupt/unreadable ledger **blocks** live calls (fail closed, never auto-resets). `make budget-status` shows spend; `python scripts/budget.py --reset-confirm` archives with timestamp (history kept).
* Replay/demo never touches the ledger. This guardrail is project-local only — check `console.typesafe.ai` for server-side spend limits/alerts, reconcile ledger vs console after first record, and rotate the key if it ever appears outside `.env`.

## Tabs (v1)

1. **Playground** — string vs JSON state, request anatomy.
2. **Parallel fan-out** — batched vs sequential vs parallel-client (v2: warm-up excluded, interleaved, ≥5 runs median+range, retry counts logged, token/cost prominent, where/when recorded).
3. **Confidence gates** — Choice/Score on confidence, Noul on P(yes) directly (own sliders; proxy shown underneath).
4. **Calibration lab** — top-prob vs accuracy AND confidence vs accuracy separately; Noul P(yes) separate; 5 bins + Wilson CIs (activates after `make record`).

## Honest caveats

* Small synthetic dataset (~150 tickets planned), not a rigorous benchmark.
* LLM-drafted tickets + generator labels can bias calibration; labels written before any Jev run, ambiguous ones hand-checked (see `data/LABEL_NOTES.md`).
* Limits/prices in `jevlab/limits.yaml` (as of 2026-10-11, per-field sources) — beta, `make doctor` warns when >30d stale.
* Noul gates on P(yes) directly; `|2p-1|` shown for reference only, never pooled.
* Recorded latencies depend on network/account/limits — rerun live for timing claims; re-record before publishing.
* All recorded state is synthetic; recordings never contain keys (contract test scans).
