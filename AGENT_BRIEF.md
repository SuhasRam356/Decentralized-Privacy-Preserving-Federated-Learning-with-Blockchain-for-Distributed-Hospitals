# Agent Briefing — MedXChAIn remediation

This briefing is addressed to the engineering agent (human or AI) that will implement the work. Parts I and II are the evidence and the plan; this is the contract for the engagement.

## 0.1 Mission

Take this repository from **"impressive demo shell around a non-functional core"** to **"verified prototype"**: one real federated round, every displayed number traceable to a source, and no claim in the documentation that the code does not support.

Success is measured, not asserted. When this engagement is done, all five statements below must be true and demonstrable in under five minutes:

1. `make round` executes **train → encrypt → IPFS → submit → aggregate → publish → evaluate** across three local sites and exits 0.
2. Every figure the dashboard renders can be reproduced with a single SQL query against Postgres.
3. `forge test` passes at ≥ 95 % coverage and `pytest` at ≥ 70 %, and CI is green on `main`.
4. The README contains no claim that is not backed by a link to a metrics file, a test or a compliance artefact.
5. The regression greps in `agent_backlog.yaml → regression_guards` return nothing.

## 0.2 Non-negotiable rules

| Rule | Why it exists | How it is checked |
| :--- | :--- | :--- |
| **R1 — Never fabricate a value.** No invented CID, hash, transaction, accuracy, timestamp or "system status". | The current codebase does exactly this (findings C-02, C-05, H-02) and it is the single reason the project cannot be trusted. | `grep -rn 'QmHospital\|Simulated\|deadbeef\|1\.2k\|89\.4'` must be empty |
| **R2 — Fail closed.** A missing dependency raises; it never degrades to a placeholder. | `try/except: use fake CID` is the pattern that created the problem. | Code review + a test per failure path |
| **R3 — Every number has provenance.** API responses carry `sources: {chain, ipfs, model, db}` and a `generated_at`. | Lets the UI show "degraded" instead of lying. | `tests/api/test_status.py` asserts provenance fields |
| **R4 — No compliance claims.** Write "designed against HIPAA §164.312"; never "HIPAA compliant". | An audit has not happened; overclaiming is the repo's existing failure mode. | `grep -rni 'hipaa compliant\|gdpr certified'` must be empty |
| **R5 — Tests travel with code.** A PR without a test for its new behaviour is incomplete. | There are currently zero Python tests. | CI coverage gate |
| **R6 — Preserve the user's data.** Do not delete or rewrite `FL/Train&TestCSVs/` or `LocalTraining/` without explicit approval; T-04/T-05 require a dry-run report first. | Irreversible; the data may be the only copy. | Stop condition, see §0.8 |
| **R7 — Small PRs.** ≤ 600 changed lines, one concern, conventional commit message. | Reviewability, and it makes each step independently revertible. | PR template checklist |
| **R8 — Pin dependencies.** No silent upgrades of `torch`, `transformers`, `opacus`, `web3`. | Reproducibility is a stated research goal. | Lock files committed |

## 0.3 Order of work and gates

Do the tasks in `agent_backlog.yaml` in ID order. The gates below are hard: do not start the next block before the previous one is green, because each block's tests are the safety net for the next.

| Gate | Tasks | Exit test | Why the gate exists |
| :--- | :--- | :--- | :--- |
| **G0 — Honesty** | T-01 … T-07 | `grep` guards empty, CI green | Every later PR would otherwise add features on top of fabricated output, making the lies harder to find |
| **G1 — Real training** | T-08 … T-10 | `tests/fl` green, determinism test passes | An aggregator over random models (today) cannot be evaluated, so nothing downstream can be validated |
| **G2 — Chain + service** | T-11 … T-14 | `make round` exits 0, dashboard shows only DB values | This is the first point at which the system is end-to-end real |
| **G3 — Clinical** | T-15 | `tests/clinical` green, no keyword matching left | Requires a real checkpoint (G1) and a real API (G2) |
| **G4 — Privacy** | T-16, T-17 | ε ledger populated, artefacts unreadable without keys | DP over a full 110 M-parameter model is not runnable; it depends on LoRA (T-09) |
| **G5 — Auditability** | T-18 | `round replay N --verify` passes | Needs real transactions and a real DB to replay |

## 0.4 Verification commands

Run these before every push. The environment notes matter: in a sandbox without outbound access to `binaries.soliditylang.org`, Hardhat cannot download `solc`.

```bash
# Python
pytest -q --cov=medxchain --cov-fail-under=70
ruff check . && ruff format --check . && mypy src

# Contracts — preferred
cd contracts && forge fmt --check && forge test -vvv && forge coverage --report summary

# Contracts — legacy Hardhat path (if forge is unavailable)
cd Blockchain && npx hardhat test --no-compile

# Contracts — compile when the compiler cannot be downloaded:
#   npm install --no-save solc@0.8.28
#   then compile contracts/ with the npm solc package (optimizer enabled, runs=200)
#   and emit Hardhat-format artefacts to Blockchain/artifacts/contracts/**.json
#   (this is exactly how the audit compiled them: 5 artefacts, 0 errors, 0 warnings)

# Regression guards
grep -rn 'QmHospital\|Simulated' --include=*.py .
grep -rn '0x5FbDB2315678afecb367f032d93F642f64180aa3' --include=*.py --include=*.js .
grep -rn 'e:/Fedacre\|/content/drive' --include=*.py .

# Behaviour
python -m medxchain.cli round run --sites 3 --verify-chain
python -m medxchain.cli round replay 1 --verify
```

## 0.5 Landmines found by execution — read these before debugging

These were discovered by running the code, not by reading it. Each will cost you hours if you hit it blind.

1. **The two halves of the ML system are incompatible.** The notebooks' model takes `(input_ids, attention_mask)` and its state dict has `encoder.*`, `classifier.0.*`, `classifier.3.*`. `run_federated_pipeline.py` takes a flat 768-vector and has `feature_extractor.*`, `classifier.*`. `load_state_dict` fails in both directions. Fix with the single checkpoint format in T-09 — do not try to "convert" ad hoc.
2. **Kubo rejects the current upload.** `requests.post(url, data=content)` sends raw bytes; `/api/v0/add` requires `multipart/form-data`. Against a real daemon this fails 100 % of the time — which is why nobody noticed the fake CIDs.
3. **The IPFS emulator lies convincingly.** `path.endswith("/add")` also matches `/api/v0/pin/add`, so a "pin" call stores an empty file and returns the CID of the empty string. Unknown routes (`/swarm/peers`) return HTTP 200 with an empty body. Any health check that only looks at the status code passes against a broken node.
4. **All four emulated "nodes" share one storage directory.** A file added on 5001 is readable from 5004 — impossible in a real cluster. Do not cite this as replication.
5. **Hardhat's compiler download is blocked in restricted networks** (`HH502`). Use the npm `solc` package as described in §0.4; this is an environment issue, not a repo defect.
6. **`deployment_info.json` is committed, gitignored, and stale.** `.env.example` advertises a different address than the committed deployment, and the README's second address matches neither. Pick one source of truth (the deploy output) and load it through config.
7. **`server.py` imports `torch` and never uses it.** It costs ~2 s of startup and a 2 GB dependency. Remove it; do not "fix" it by adding torch usage.
8. **`LocalTraining/` is a byte-identical duplicate** of `FL/Train&TestCSVs/` (verified by md5). Deleting the wrong copy loses nothing, but confirm before acting (R6).

## 0.6 Definition of done — per task

A task is done only when **all** boxes are true:

- [ ] Code under `src/medxchain/` (or the specified location) with type hints; `mypy` clean on new modules
- [ ] Unit test for the happy path **and** for each failure path introduced
- [ ] The specific `verify` command from `agent_backlog.yaml` passes
- [ ] No new `TODO`, no `except: pass`, no placeholder returned on error (R1/R2)
- [ ] Metrics/log line added for the new failure mode, with an alert rule (F14) if the service can be degraded
- [ ] `docs/` updated; any README change links to the artefact that proves it (R4)
- [ ] Migration + rollback noted for DB or contract changes
- [ ] Manifest fields recorded so the round remains replayable (T-18)

## 0.7 Reporting format — what to send back after each PR

Keep it short and verifiable; this is what a reviewer can check without reading the diff.

```text
TASK: T-09  Single checkpoint format + LoRA
STATUS: done | blocked | partial
CHANGED: src/medxchain/fl/model.py (+180/-12), tests/fl/test_checkpoint.py (new)
WHY: closes H-06 (incompatible checkpoints), enables H-08 fix via adapter-only averaging
EVIDENCE:
  pytest tests/fl/test_checkpoint.py -q        -> 7 passed
  ratio test (lora/full params)                -> 0.0027 (< 0.01 gate)
  grep -rn 'feature_extractor' src/            -> only model.py:31 (mapping helper)
BREAKING: checkpoint format v1; old .pt files cannot load (migration: re-train or convert via tools/convert_ckpt.py)
NEXT: T-10 (aggregator) — unblocked
OPEN QUESTION: none
```

## 0.8 Ask before doing (stop conditions)

Do not proceed silently on any of these; report and wait for approval:

- Deleting, rewriting or re-partitioning anything under `FL/Train&TestCSVs/` or `LocalTraining/` (R6)
- Rewriting git history (`filter-repo`, force-push) — required eventually for the PII scrub, but it is destructive and irreversible
- Adding a dependency that downloads weights or binaries at install time
- Changing the contract ABI after T-12 without regenerating `docs/abi.md`
- Enabling `MEDXCHAIN_DEMO_MODE=false` on anything that looks like production
- Any claim, diagram or README line that the implementation cannot demonstrate

## 0.9 Explicitly out of scope for this engagement

Tokenomics, on-chain model storage, zkML proofs, Kubernetes, microservice decomposition, a custom chain, and any framework rewrite for its own sake. See `ENHANCEMENT_ROADMAP.md` §19 for the reasoning — each of these adds cost and risk without moving the five success criteria in §0.1.

## 0.10 The one-sentence summary of the job

**Replace every plausible-looking fabrication with a smaller, uglier, verifiable truth — then build features only on top of what can be proven.**
