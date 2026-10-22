# MedXChAIn 2.0 — Complete Enhancement & New-Feature Plan

**Companion to `TECHNICAL_AUDIT.md`.** The audit said *what is broken*; this document says *what to build, in what order, and exactly how*.

---

## 0. How to read this

Three reading paths:

| You have… | Read | Outcome |
| :--- | :--- | :--- |
| **1–2 days** | §1 (quick wins) + §17 (first 10 PRs) | Project stops lying and becomes defensible in a demo |
| **2–4 weeks** | Tracks A, C, E (core loop) | System actually trains, actually talks to the chain, dashboard shows real data |
| **One semester / 12 weeks** | Everything | Publication-grade research prototype + credible product |

Effort is in **person-days (pd)** for a competent developer who knows the codebase. Priority: **P0** = correctness/safety, **P1** = closes the loop, **P2** = product credibility, **P3** = research/stretch.

---

## 1. The 12 quick wins (start today, ~8 pd total)

These are cheap, high-signal, and unblock everything else.

| # | Change | File | pd | Closes |
| :-- | :--- | :--- | --: | :--- |
| 1 | Delete fabricated metrics from `fl_state`; return `null` + `"source": "unavailable"` when a dependency is down | `server.py:38` | 0.5 | C-02 |
| 2 | Add `require(bytes(cid).length > 0)` + `fileHash != 0` + `_requiredSubmissions > 0` | `ModelUpdateTracker.sol` | 0.5 | C-05, H-03 |
| 3 | Replace substring diagnosis with **HTTP 501 "model not wired"** until Track G lands | `server.py:89-114` | 0.5 | C-04 |
| 4 | Remove PII columns from the committed CSVs (keep `symptoms,label,Disease_name` only) | `FL/Train&TestCSVs/*` | 1 | C-03 |
| 5 | Delete the duplicated `LocalTraining/Train&TestCSVs/` tree (67 MB → 33 MB) | — | 0.2 | M-04 |
| 6 | Remove `FL/__pycache__/` and add `fl_server` note | — | 0.1 | M-04 |
| 7 | Fix `upload_to_ipfs` to multipart + verify CID, **never invent a CID** | `run_federated_pipeline.py:47-55` | 1 | H-02 |
| 8 | Seed everything (`random`, `numpy`, `torch`), log the seed in the round manifest | pipeline + notebooks | 0.5 | M-05 |
| 9 | Add `LICENSE` (MIT) and a `DATA_PROVENANCE.md` | root | 0.2 | M-03 |
| 10 | Add "Research prototype — not for clinical use" banner to the diagnosis view | `index.html` | 0.3 | §3.7 |
| 11 | Fix `.gitignore` (un-ignore the docs it currently hides), stop tracking `deployment_info.json` | `Blockchain/.gitignore` | 0.2 | M-04 |
| 12 | Add GitHub Actions: `ruff`, `pytest`, `hardhat test`, `slither` | `.github/workflows/ci.yml` | 1.5 | M-03 |

Everything below builds on these.

---

## 2. North-star architecture

### Today

```
CSV ──read 500 rows──► discard ──► randn training ──► .pt ──► [fake CID]
                                                                 │
dashboard ◄── hardcoded dict ── (nothing) ── chain (never called) ┘
```

### Target

```
┌──────────────────────── HOSPITAL EDGE (per site) ────────────────────────┐
│  FHIR/EHR export ──► local feature store ──► trainer (LoRA + DP-SGD)     │
│                                              │                            │
│                       encrypted adapter ─────┘                            │
│                              │                                            │
│                     AES-GCM seal + IPFS add (private swarm)               │
│                              │  CID + SHA-256 + ε spent                   │
└──────────────────────────────┼────────────────────────────────────────────┘
                               ▼
┌─────────────────────── ORCHESTRATION PLANE (FastAPI) ─────────────────────┐
│  Round state machine ──► quorum check ──► aggregation worker (SecAgg)     │
│         │                                        │                        │
│         │  Postgres (rounds, submissions,        │                        │
│         │  ε-ledger, audits)                     ▼                        │
│         │                              global adapter ──► IPFS            │
│         ▼                                        │                        │
│  Event indexer (The Graph / own worker) ◄──── L2 / Anvil                  │
└───────────────────────────────────────────────┬───────────────────────────┘
                                                │
              ┌─────────────────────────────────┴────────────────────┐
              ▼                                                       ▼
   ┌──────────────────┐                                   ┌────────────────────┐
   │ AUDITOR / GOV    │                                   │ CLINICIAN CONSOLE  │
   │ round replay,    │                                   │ diagnosis + evidence│
   │ ε ledger, export │                                   │ pack, overrides     │
   └──────────────────┘                                   └────────────────────┘
```

Key architectural shifts:

1. **One source of truth = Postgres.** JSON files (`deployment_info.json`, `fl_state`) become *outputs*, never state.
2. **Chain = audit anchor, not database.** One Merkle root per round + settlement events, not per-tensor writes.
3. **IPFS = transport of ciphertext.** Nothing readable is ever pushed.
4. **Dashboard = a client.** Zero literals; every number traceable to a query, with `provenance` metadata.
5. **Adapters, not full models.** LoRA makes communication, encryption and DP *practically* feasible (0.3 MB vs 440 MB).

---

## 3. Target repository layout

```
medxchain/
├── pyproject.toml                     # single source of deps, ruff/mypy/pytest config
├── Makefile                           # make dev | test | lint | up | seed | round
├── docker-compose.yml                 # anvil + 4 kubo + cluster + pg + redis + api + worker + ui + obs
├── .env.example
├── LICENSE
├── README.md                          # rewritten, claim-verified
├── docs/
│   ├── architecture.md  threat-model.md  privacy.md  compliance.md  runbook.md  adr/
├── src/medxchain/
│   ├── config.py                      # pydantic-settings
│   ├── logging.py                     # structlog, JSON, trace ids
│   ├── db/           models.py  session.py  migrations/
│   ├── chain/        client.py  abi/  events.py  indexer.py
│   ├── storage/      ipfs.py  crypto.py  verify.py
│   ├── fl/           model.py  lora.py  data.py  trainer.py  aggregator.py  dp.py  secagg.py  metrics.py
│   ├── rounds/       state.py  service.py  workers.py  manifest.py
│   ├── api/          app.py  deps.py  routes/{status,hospitals,rounds,diagnose,audit,admin}.py
│   ├── clinical/     infer.py  calibrate.py  conformal.py  explain.py  icd10.py  guardrails.py
│   └── cli.py                         # medxchain rounds start|seal|finalize, doctor check
├── contracts/                         # Foundry (replaces Hardhat)
│   ├── FederatedRound.sol
│   ├── test/FederatedRound.t.sol      # fuzz + invariant tests
│   └── script/Deploy.s.sol
├── tests/                             # pytest: unit, property, integration, e2e
├── web/                               # Vite + vanilla/React, no fabricated data
└── notebooks/                         # moved out of the runtime path, outputs cleared
```

Why: one package namespace kills the `sys.path` hacks, makes imports testable, and lets `pip install -e .` replace "somehow run this from the repo root".

---

## 4. Phase plan at a glance

| Phase | Weeks | Tracks | Exit criteria |
| :--- | :--- | :--- | :--- |
| **0 — Honesty** | 1 | §1 quick wins | No fabricated number anywhere; CI green; PII gone from Git |
| **1 — Loop closes** | 2–4 | A (core), C (v2 contract), E (service+DB) | One command runs a round end-to-end; every dashboard number comes from Postgres |
| **2 — Privacy** | 5–6 | B (DP-SGD, SecAgg, encrypted blobs) | ε reported per round; ciphertext-only IPFS; MIA AUC measured |
| **3 — Clinical** | 7–8 | G (calibration, conformal, abstention, ICD-10, explain) | Diagnosis output clinically sane + explains itself + refuses when unsure |
| **4 — Product** | 9–10 | F (dashboard 2.0), H (features), J (compliance pack) | Auditor can replay any round; ε ledger visible per site; signed audit PDF exported |
| **5 — Rigor** | 11–12 | L (benchmarks), K (ops), I (security) | FedAvg/FedProx/SCAFFOLD table on non-IID splits; threat model signed off |

Parallelizable by two people: **Dev 1 = A + G + L**, **Dev 2 = C + E + F**; B and I touch both.

---

## 5. Track A — Make the federated learning real

### A1. Data layer (2 pd) — closes C-01, M-08

Problems to fix: pipeline reads 500 rows and ignores them; IID splits; 7.2 % test leakage; PII columns; long-tail classes.

Do this:

```python
# src/medxchain/fl/data.py
REQUIRED = {"symptoms", "label"}
FORBIDDEN = {"Patient_First_Name", "Patient_Last_Name", "Patient_Email",
             "Patient_Phone_Number", "Patient_Date_Of_Birth", "Patient_Insurance_Provider",
             "Patient_Emergency_ContactEmail", "Patient_Emergency_Contact_PhoneNumber"}

def load_site(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, usecols=["symptoms", "label"], dtype={"symptoms": "string", "label": "int32"})
    assert REQUIRED <= set(df.columns), f"missing columns in {path}"
    assert not (FORBIDDEN & set(df.columns)), "PII columns must be stripped before packaging"
    df = df.dropna(subset=["symptoms"]).drop_duplicates(subset=["symptoms", "label"])
    return df

def split_site(df, seed=42, test_size=0.2):
    return train_test_split(df, test_size=test_size, random_state=seed, stratify=None)  # stratify fails on singletons
```

Then add:
- **Non-IID partitioner** (the single most important scientific upgrade):

```python
def dirichlet_partition(df, n_sites=3, alpha=0.3, seed=42):
    """Label-skew partition. alpha→0 = each site owns few classes (pathological)."""
    rng = np.random.default_rng(seed)
    parts = [[] for _ in range(n_sites)]
    for label, grp in df.groupby("label"):
        p = rng.dirichlet([alpha] * n_sites)
        idx = rng.permutation(len(grp))
        cuts = (np.cumsum(p) * len(grp)).astype(int)[:-1]
        for site, chunk in enumerate(np.split(idx, cuts)):
            parts[site].append(grp.iloc[chunk])
    return [pd.concat(p).sample(frac=1, random_state=seed) for p in parts]
```

- **Dedup across splits** (kills the 7.2 % leak): hash `symptoms`, drop test rows whose hash exists in any train split.
- **Class-imbalance handling:** report macro-F1; merge the 68 singleton classes into an `other` bucket *or* exclude them from top-1 and report separately. Do not silently keep a 793-way problem where 68 classes have one example.
- **Dataset card** (`docs/dataset.md`): provenance, licence, row counts, label histogram, known biases, PII statement.

**Acceptance:** `medxchain data validate` fails the build if PII columns or cross-split duplicates exist; a stored `data_stats.json` lists per-site row counts and label coverage.

### A2. Model & checkpoint contract (2 pd) — closes H-06

Today the notebook model (`encoder.*`, `classifier.0.*`, `classifier.3.*`) and pipeline model (`feature_extractor.*`, `classifier.*`) are load-incompatible. Define **one** artefact format:

```python
# src/medxchain/fl/model.py
@dataclass
class Checkpoint:
    format: str = "medxchain-ckpt/1"
    base_model: str = "ncbi/MedCPT-Query-Encoder"
    num_labels: int = 793
    tunable: str = "lora"            # "lora" | "head" | "full"
    seed: int = 0
    round: int = 0
    site_id: str = ""
    state_dict: dict[str, Tensor] = field(default_factory=dict)
    metrics: dict[str, float] = field(default_factory=dict)

    def save(self, path: Path) -> str:      # returns sha256 hex
        torch.save(asdict(self), path)
        return sha256_file(path)
```

Rules: every artefact carries `format`, `base_model`, `num_labels`, `tunable`, `seed`, `site_id`, `round`, `metrics`. `load_checkpoint()` **rejects** mismatched `base_model`/`num_labels`/`tunable` with a clear error. That single guard would have prevented the entire notebook/pipeline divergence.

**Add LoRA** (this is the highest-leverage ML change in the whole plan):

```python
from peft import LoraConfig, get_peft_model

def build_model(cfg) -> nn.Module:
    encoder = AutoModel.from_pretrained(cfg.base_model)
    if cfg.tunable == "lora":
        encoder = get_peft_model(encoder, LoraConfig(
            r=8, lora_alpha=16, lora_dropout=0.05,
            target_modules=["query", "value"], bias="none",
            task_type="FEATURE_EXTRACTION"))
    return MedCPTClassifier(encoder, cfg.num_labels, freeze_encoder=(cfg.tunable != "full"))

def trainable_state(model) -> dict[str, Tensor]:
    return {k: v.detach().clone() for k, v in model.state_dict().items() if is_trainable(model, k)}
```

Numbers: full MedCPT encoder ≈ 110 M params ≈ **440 MB** fp32 per hospital per round (1.3 GB/round for 3 sites). LoRA r=8 on q,v of 12 layers ≈ **295 k params ≈ 1.2 MB fp32 / 0.3 MB int8** — a **~370×** reduction. Everything downstream (IPFS latency, encryption cost, DP noise scale, HE feasibility, gas, dashboard transfer) gets 2–3 orders of magnitude easier. Do this before anything else in Track A.

**Acceptance:** `tests/test_checkpoint.py` round-trips, rejects mismatched format, and asserts `param_count(lora) / param_count(full) < 0.01`.

### A3. Real local training (3 pd) — closes C-01, M-05, M-09

Replace the `randn` loop with an actual loop, using the *same* function in the pipeline and in the hospital SDK:

```python
# src/medxchain/fl/trainer.py
def local_train(model, loader, *, epochs, lr, device, dp=None, global_state=None, mu=0.0, seed=0) -> tuple[nn.Module, dict]:
    set_seed(seed)
    model.to(device).train()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    if dp:                                        # Track B
        model, opt, loader, dp_ctx = dp.wrap(model, opt, loader, epochs)
    crit = nn.CrossEntropyLoss()
    for ep in range(epochs):
        for batch in loader:
            ids, mask, y = (t.to(device) for t in (batch["input_ids"], batch["attention_mask"], batch["label"]))
            logits = model(ids, mask)
            loss = crit(logits, y)
            if mu and global_state is not None:    # FedProx proximal term
                loss = loss + (mu / 2) * sum(((p - global_state[k].to(device)) ** 2).sum()
                                             for k, p in trainable_named(model))
            opt.zero_grad(set_to_none=True); loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
            opt.step()
        sched.step()
        log.info("local_epoch", epoch=ep, loss=float(loss))
    metrics = evaluate_local(model, loader, device)   # A5
    metrics["epsilon"] = dp_ctx.epsilon if dp else 0.0
    metrics["num_samples"] = len(loader.dataset)
    return model, metrics
```

Hard requirements:
- `num_samples` is recorded and used for weighted aggregation (fixes the README/implementation mismatch).
- Every hyper-parameter comes from config, not a literal inside the function.
- The function returns metrics; it never prints and pretends.
- Exceptions propagate with context (site id, round, stage) — remove the `try/except: use fake CID` pattern.

**Acceptance:** with a fixed seed, two runs produce byte-identical checkpoints (test); `metrics.json` exists per site per round; the pipeline fails loudly if a site cannot train.

### A4. Aggregation service (3 pd) — closes M-01 (weighting), H-08

```python
# src/medxchain/fl/aggregator.py
def fedavg(updates: list[Checkpoint], *, weights: list[float] | None = None) -> dict:
    assert len(updates) > 0
    w = np.array(weights if weights is not None else [u.metrics["num_samples"] for u in updates], dtype=np.float64)
    assert w.sum() > 0
    w = w / w.sum()
    keys = set(updates[0].state_dict)
    assert all(set(u.state_dict) == keys for u in updates), "incompatible updates"
    return {k: sum(torch.as_tensor(u.state_dict[k]).float() * w[i] for i, u in enumerate(updates)).to(updates[0].state_dict[k].dtype)
            for k in keys}
```

Add, behind flags (each is ~0.5 pd and gives you an ablation table for Track L):
- **`weighting: uniform | samples | quality`** — quality uses `n_k / loss_k` clamped, documented as a heuristic.
- **`fedprox`** — `mu` penalty in the client (above).
- **`scaffold`** — control variates (2–3 pd, only if you want a stronger paper).
- **Robust aggregation** — `trimmed_mean`, `coordinate_median`, `krum`. Required for any Byzantine claim:

```python
def trimmed_mean(updates, trim=0.2):
    stacked = torch.stack([flatten(u.state_dict) for u in updates])
    k = max(0, int(len(updates) * trim))
    values = stacked.sort(dim=0).values
    return unflatten(values[k:len(updates)-k].mean(0))
```

- **Straggler policy** — `ceil(2K/3)` quorum with timeout, record which sites missed the round (`missing: [3]`) so the audit trail is honest about partial participation.

**Acceptance:** property test — `fedavg` is invariant to update order, weights sum to 1, and `fedavg([u,u,u]) == u`; a 3-site round with one dropout still finalises and records `missing`.

### A5. Evaluation harness (2 pd) — closes C-02, M-08

Stop reporting one number. Produce per round:

```json
{
  "round": 4, "model": "v4.0.4", "timestamp": "...", "n_train": 148839,
  "global": {"accuracy": 0.74, "macro_f1": 0.51, "top5_accuracy": 0.88,
             "ece": 0.071, "coverage@0.9": 0.905, "set_size@0.9": 3.4},
  "per_site": {"h1": {...}, "h2": {...}, "h3": {...}},
  "worst_site": "h3", "worst_class_f1": 0.0, "classes_with_support<5": 68,
  "baselines": {"local_only_h1": 0.812, "centralized": null},
  "delta_vs_previous": {"macro_f1": +0.02}
}
```

Compute: accuracy, **macro-F1** (the honest metric for 793 imbalanced classes), top-5, per-class recall, **ECE** (calibration), **conformal coverage/set size**, confusion-matrix hash for drift detection.

Also store the **81.23 % local vs 73.9 % global** comparison as a first-class baseline and display it. Federation currently *hurts* — hiding that is the biggest scientific credibility problem in the repo.

**Acceptance:** `/api/rounds/{id}/metrics` returns this object; the dashboard charts it; a regression beyond `−0.02` macro-F1 fails CI on the golden dataset.

### A6. Round manifest (1 pd) — new

Every round writes an immutable bundle:

```
artifacts/rounds/0004/
├── manifest.json      # inputs: site ids, seeds, hyper-params, code git sha, container digests
├── metrics.json
├── submissions.json   # site → {cid, sha256, num_samples, epsilon, tx_hash}
├── global.json        # cid, sha256, tx_hash, merkle_root
└── env.lock           # pip freeze + npm ls
```

`manifest.json` must include `git_sha`, `image_digest`, and `seed` so a third party can reproduce. This is what turns "demo" into "research artefact".

---

## 6. Track B — Privacy engineering (the title finally becomes true)

Today: no DP, no secure aggregation, no encryption, no access control. Three claims in the README are simply false.

### B1. DP-SGD (3 pd) — closes M-06

```python
# src/medxchain/fl/dp.py
from opacus import PrivacyEngine

@dataclass
class DPContext:
    epsilon: float; delta: float; max_grad_norm: float

def wrap(model, opt, loader, epochs, *, target_eps, delta, clip):
    engine = PrivacyEngine(secure_mode=False)
    model, opt, loader = engine.make_private_with_epsilon(
        module=model, optimizer=opt, data_loader=loader, epochs=epochs,
        target_epsilon=target_eps, target_delta=delta,
        max_grad_norm=clip, grad_sample_mode="ghost")  # ghost = fast clipping
    return model, opt, loader, DPContext(target_eps, delta, clip)
```

Practical notes that will save you a week:
- **DP over LoRA adapters only** (A2) is the only way this runs in reasonable time — ghost clipping over 110 M params on CPU is hopeless.
- Batch size must be ≥ ~1 000 for meaningful ε at 5 epochs. Report the **ε actually spent**, per site, per round, in the manifest.
- `grad_sample_mode="ghost"` requires a recent Opacus; pin it.
- **Never** write "HIPAA compliant" because of DP. Say "ε = 7.8 (δ = 1e-5) under DP-SGD, which bounds membership-inference advantage" — a checkable statement.

**Acceptance:** `metrics.json` contains `epsilon`, `delta`, `noise_multiplier`; a test asserts ε grows monotonically across rounds; the ε ledger (feature F2) reads from here.

### B2. Secure aggregation (4 pd)

Server must never see an individual adapter. Simplest correct design: **pairwise additive masking** (SecAgg-lite).

```python
def mask_update(update: dict[str, Tensor], my_id, peer_ids, shared_secrets, round_id, shape) -> dict:
    """Each pair derives a deterministic PRG stream; masks cancel when summed."""
    masked = {k: v.clone() for k, v in update.items()}
    for peer in peer_ids:
        if peer == my_id: continue
        stream = prg(shared_secrets[peer], round_id, shape)   # SHAKE256 → int8 vector
        sign = +1 if my_id < peer else -1
        for k in masked: masked[k] += sign * stream[k]
    return masked
```

Server sums the masked tensors; pairwise masks cancel exactly (up to float drift — use int64 quantised fixed-point, which also gives you **quantisation for free**). Add dropout handling: a dropped client's mask must be cancelled by the surviving peers, otherwise the sum is wrong — implement the standard `recover` step, or restrict to synchronous rounds with a timeout and exclude non-responders *before* aggregation (much easier, acceptable for 3–5 sites).

Alternatives and when to prefer them:
| Option | When | Cost |
| :--- | :--- | :--- |
| Pairwise masking (above) | Default; 3–10 sites, synchronous | 4 pd, exact |
| TenSEAL CKKS HE | You need aggregation over encrypted values *and* want a paper | 8 pd; feasible **only** with LoRA-sized tensors |
| TEE (SGX/SEV) | You control the aggregator host | 5 pd + infra; trust assumption changes |
| Trusted aggregator + DP only | Demo, deadline | 0 pd, weakest guarantee — say so |

**Acceptance:** an integration test proves the server-visible tensor sum equals the plaintext sum within tolerance, and that no single masked update can be inverted.

### B3. Encrypt everything before IPFS (2 pd) — closes H-02/M-06

```python
# src/medxchain/storage/crypto.py
def seal(plaintext: bytes, key: bytes, aad: bytes = b"medxchain/v1") -> bytes:
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, plaintext, aad)

def open_(blob: bytes, key: bytes, aad: bytes = b"medxchain/v1") -> bytes:
    return AESGCM(key).decrypt(blob[:12], blob[12:], aad)
```

Key management options, in order of practicality:
1. **Per-round data key**, wrapped for each participant with X25519 (`cryptography` lib) — recipients unwrap, IPFS holds only ciphertext.
2. **External KMS / Vault** for the demo; document the trust boundary.
3. **Crypto-shredding for GDPR**: keep the *wrapping* key off-chain in your DB; deleting the key makes the on-chain hash useless → satisfies erasure without mutating the chain. **This is the cleanest answer to "right to erasure vs immutable ledger"** and belongs in `docs/compliance.md`.

Also: hash the *ciphertext*, publish `sha256(ciphertext)` on-chain, verify after download before decrypting. Store `key_id` (not the key) in the manifest.

**Acceptance:** IPFS content is high-entropy (test: `ent` on the blob), a wrong/absent key fails cleanly, and the audit log records `key_id` + `sha256`.

### B4. Attack evaluation (3 pd) — makes the privacy claim credible

Build `notebooks/attacks/` and report results — **positive or negative**, both are results:
- **Membership inference** (shadow-model, report AUC/TPR@FPR=1 %), DP on vs off.
- **Model inversion / DLG** on a single site's update, SecAgg on vs off.
- **Gradient leakage** baseline on the current pipeline (expected: trivially successful, which is a *great* before/after figure for the README).
- **Property inference** on adapter deltas.

**Acceptance:** `docs/privacy.md` contains a table: attack, setting, metric, before, after. This single table is worth more than ten marketing claims.

---

## 7. Track C — Blockchain v2 (`FederatedRound.sol`)

### Problems being fixed
C-05 (empty submissions accepted) · H-03 (`quorum = 0` deployable) · H-04 (owner = aggregator, zero-address aggregator, no revocation, immortal pause) · H-07 (silent overwrite, removed hospital still counted) · M-10 (docs describe an ABI that doesn't exist).

### Design decisions

| Decision | Choice | Why |
| :--- | :--- | :--- |
| Per-submission tx vs batch | **Events per submission + one Merkle root per round** | Keeps the audit trail, cuts gas ~3×, enables off-chain inclusion proofs |
| Access control | `AccessControl` roles, not `owner` | Aggregator ≠ governance ≠ pauser |
| Upgradeability | **UUPS proxy + 48 h timelock** (or immutable v1 for the demo) | Models evolve; immutability is *not* an excuse to ship a bug |
| Round finalisation | `seal` → **challenge window** → `finalize` | Gives hospitals a veto window; nothing is "final" the instant the aggregator says so |
| Stakes | Optional `stake`/`slash` | Needed only if you claim Byzantine resistance |
| Signature | EIP-712 optional `submitWithSig` | Hospital doesn't need gas; aggregator relays |

### Core contract (condensed but real)

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {Pausable} from "@openzeppelin/contracts/utils/Pausable.sol";
import {MerkleProof} from "@openzeppelin/contracts/utils/cryptography/MerkleProof.sol";

contract FederatedRound is AccessControl, Pausable {
    bytes32 public constant AGGREGATOR_ROLE = keccak256("AGGREGATOR_ROLE");
    bytes32 public constant HOSPITAL_ROLE   = keccak256("HOSPITAL_ROLE");
    bytes32 public constant PAUSER_ROLE     = keccak256("PAUSER_ROLE");

    uint32  public constant MAX_CID_LEN = 128;
    uint256 public immutable challengeWindow;   // seconds

    struct Update {
        bytes32 weightHash;    // sha256(ciphertext adapter)
        bytes32 keyCommitment; // keccak(keyId || salt) — never the key
        uint96  numSamples;
        uint32  lossBps;
        uint64  timestamp;
        bool    slashed;
    }

    enum Phase { None, Open, Sealed, Finalized, Disputed }

    uint256 public currentRound;
    uint256 public quorum;
    mapping(uint256 => Phase) public phase;
    mapping(uint256 => mapping(address => Update)) private _updates;
    mapping(uint256 => address[]) private _submitters;
    mapping(uint256 => bytes32) public merkleRoot;
    mapping(uint256 => uint96)  public totalSamples;
    mapping(uint256 => bytes32) public globalCidHash;
    mapping(uint256 => uint64)  public sealedAt;
    mapping(address => uint256) public stakeOf;
    mapping(address => uint32)  public reputation;

    error BadCid(); error EmptyHash(); error BadQuorum(); error NotOpen();
    error AlreadySubmitted(); error AlreadyRegistered(); error QuorumNotMet(); error NotSealed();
    error WindowOpen(); error WindowClosed(); error AlreadyFinalized();
    error ZeroAddress(); error NoStake();

    event HospitalRegistered(address indexed hospital, uint96 stake);
    event HospitalRevoked(address indexed hospital, string reason);
    event QuorumChanged(uint256 oldQuorum, uint256 newQuorum);
    event UpdateSubmitted(uint256 indexed round, address indexed hospital,
                          bytes32 weightHash, uint96 numSamples, uint32 lossBps);
    event RoundSealed(uint256 indexed round, bytes32 merkleRoot, uint96 totalSamples, uint32 count);
    event RoundDisputed(uint256 indexed round, address indexed hospital, string reason);
    event RoundFinalized(uint256 indexed round, bytes32 globalCidHash, string globalCid);
    event Slashed(address indexed hospital, uint256 amount, string reason);

    constructor(uint256 quorum_, uint256 challengeWindow_) {
        if (quorum_ == 0) revert BadQuorum();
        quorum = quorum_;
        challengeWindow = challengeWindow_;
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(AGGREGATOR_ROLE, msg.sender);
        _grantRole(PAUSER_ROLE, msg.sender);
        currentRound = 1;
        phase[1] = Phase.Open;
    }

    // ---- governance ----
    function registerHospital(address h, uint96 stake) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (h == address(0)) revert ZeroAddress();
        if (hasRole(HOSPITAL_ROLE, h)) revert AlreadyRegistered();
        stakeOf[h] = stake;
        _grantRole(HOSPITAL_ROLE, h);
        emit HospitalRegistered(h, stake);
    }

    function revokeHospital(address h, string calldata reason) external onlyRole(DEFAULT_ADMIN_ROLE) {
        _revokeRole(HOSPITAL_ROLE, h);          // AND remove from round accounting off-chain
        emit HospitalRevoked(h, reason);
    }

    function setQuorum(uint256 q) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (q == 0) revert BadQuorum();
        emit QuorumChanged(quorum, q);
        quorum = q;                              // note: effective next round, documented
    }

    address public aggregator;

    function setAggregator(address a) external onlyRole(DEFAULT_ADMIN_ROLE) {
        if (a == address(0)) revert ZeroAddress();
        address old = aggregator;
        if (old != address(0)) _revokeRole(AGGREGATOR_ROLE, old);
        aggregator = a;
        _grantRole(AGGREGATOR_ROLE, a);
        emit AggregatorChanged(old, a);
    }

    // ---- hospital ----
    function submitUpdate(
        uint256 round,
        string calldata cid,
        bytes32 weightHash,
        bytes32 keyCommitment,
        uint96 numSamples,
        uint32 lossBps
    ) external onlyRole(HOSPITAL_ROLE) whenNotPaused {
        if (phase[round] != Phase.Open) revert NotOpen();
        if (bytes(cid).length == 0 || bytes(cid).length > MAX_CID_LEN) revert BadCid();
        if (weightHash == bytes32(0)) revert EmptyHash();
        if (numSamples == 0) revert BadQuorum();
        if (_updates[round][msg.sender].timestamp != 0) revert AlreadySubmitted();

        _updates[round][msg.sender] = Update(weightHash, keyCommitment, numSamples, lossBps, uint64(block.timestamp), false);
        _submitters[round].push(msg.sender);
        totalSamples[round] += numSamples;
        reputation[msg.sender] += 1;
        emit UpdateSubmitted(round, msg.sender, weightHash, numSamples, lossBps);
    }

    // ---- aggregator ----
    function sealRound(uint256 round, bytes32 root, bytes32 cidHash)
        external onlyRole(AGGREGATOR_ROLE) whenNotPaused
    {
        if (phase[round] != Phase.Open) revert NotOpen();
        if (_submitters[round].length < quorum) revert QuorumNotMet();
        if (root == bytes32(0) || cidHash == bytes32(0)) revert EmptyHash();
        merkleRoot[round] = root;
        globalCidHash[round] = cidHash;
        sealedAt[round] = uint64(block.timestamp);
        phase[round] = Phase.Sealed;
        emit RoundSealed(round, root, totalSamples[round], uint32(_submitters[round].length));
    }

    function dispute(uint256 round, string calldata reason) external onlyRole(HOSPITAL_ROLE) {
        if (phase[round] != Phase.Sealed) revert NotSealed();
        if (block.timestamp > sealedAt[round] + challengeWindow) revert WindowClosed();
        phase[round] = Phase.Disputed;
        emit RoundDisputed(round, msg.sender, reason);
    }

    function finalizeRound(uint256 round, string calldata globalCid)
        external onlyRole(AGGREGATOR_ROLE)
    {
        if (phase[round] != Phase.Sealed) revert NotSealed();
        if (block.timestamp < sealedAt[round] + challengeWindow) revert WindowOpen();
        phase[round] = Phase.Finalized;          // never re-open, never overwrite
        emit RoundFinalized(round, globalCidHash[round], globalCid);
        currentRound = round + 1;
        phase[round + 1] = Phase.Open;
    }

    // ---- verification ----
    function verifyInclusion(uint256 round, bytes32 leaf, bytes32[] calldata proof) external view returns (bool) {
        return MerkleProof.verify(proof, merkleRoot[round], leaf);
    }

    function leafOf(uint256 round, address h) public view returns (bytes32) {
        Update memory u = _updates[round][h];
        return keccak256(abi.encode(round, h, u.weightHash, u.keyCommitment, u.numSamples, u.lossBps));
    }
}
```

> The `AggregatorChanged` event must also be declared with the other events (`event AggregatorChanged(address indexed oldAggregator, address indexed newAggregator);`). The audit probe P4 exists precisely because the current contract forgot the zero-check **and** the event.

### Tests you must add (Foundry)

| Test | Assertion |
| :--- | :--- |
| `test_RevertWhen_EmptyCid` | `submitUpdate("" , …)` reverts `BadCid` |
| `testFuzz_QuorumZero` | constructor always reverts for `q == 0` |
| `test_RevertWhen_DoubleSubmit` | second submission in same round reverts |
| `test_RevertWhen_SealBelowQuorum` | seal with `count < quorum` reverts |
| `test_RoundIsImmutable` | `finalizeRound` twice reverts; `merkleRoot` unchanged |
| `test_DisputeBlocksFinalize` | disputed round cannot be finalised |
| `test_RevokedHospitalCannotSubmit` | role revoked → reverts `Not hospital` |
| `test_ZeroAggregator` | `setAggregator(address(0))` reverts |
| `invariant_NoRoundAdvancesWithoutQuorum` | Foundry invariant across random call sequences |
| `test_GasSubmitUnder150k` | `assertLt(gasUsed, 150_000)` |

Plus `slither .` clean, `foundry coverage` ≥ 95 %.

**Acceptance:** all ten above pass; `docs/abi.md` is generated from artefacts (no hand-written ABI drift), and the README's Solidity snippets are extracted from the actual files (see §19 anti-patterns).

---

## 8. Track D — Storage v2

| Change | Detail | pd |
| :--- | :--- | --: |
| **Private swarm** | Generate `swarm.key`, mount identically into all 4 Kubo containers, `LIBP2P_FORCE_P2PSTREAM=true`; verifies isolation (no public DHT) | 1 |
| **IPFS Cluster** | Add `ipfs-cluster` with `replication_factor: 2-3`; pinning becomes a cluster operation, not a per-node `ipfs add` | 2 |
| **Correct client** | multipart `/api/v0/add?pin=true&cid-version=1&raw-leaves=true`; verify returned CID against local multihash; `raise` on mismatch | 1 |
| **CAR export** | `/api/v0/dag/export` per round → `artifacts/rounds/NNNN/bundle.car` for offline audit | 1 |
| **Encryption** | B3 before add; store `key_id` + `sha256(ciphertext)` | (B3) |
| **Retrieval with verification** | fetch → `sha256` → compare on-chain `weightHash` → decrypt → load; fail closed | 1 |
| **Retention** | pin TTL per round (e.g. keep 10 rounds); `ipfs pin rm` + garbage collect; documented | 0.5 |
| **Health** | `/api/v0/version`, `/api/v0/id`, cluster `/id`; **any non-200 or empty body = unhealthy** (the current emulator returns 200 + empty body for unknown routes — never trust that) | 0.5 |

---

## 9. Track E — Orchestration, API, and the database

### E1. FastAPI service (4 pd)

Replace `SimpleHTTPRequestHandler` with FastAPI + SQLAlchemy + Alembic. Why: you need validation, auth, async I/O, OpenAPI docs, and testability — all things the stdlib server makes painful.

```
POST   /auth/login                      → JWT (role claim)
GET    /api/status                      → real aggregate (see below)
GET    /api/hospitals                   → DB + chain
GET    /api/hospitals/{id}              → detail, contribution history
GET    /api/rounds                      → paginated
GET    /api/rounds/{id}                 → manifest + metrics + submissions
GET    /api/rounds/{id}/submissions/{site} → cid, sha256, tx, inclusion proof
POST   /api/rounds                       → start round (admin)
POST   /api/rounds/{id}/submit           → hospital upload (mTLS or JWT+hospital role)
POST   /api/rounds/{id}/seal            → aggregator
POST   /api/rounds/{id}/finalize        → aggregator
POST   /api/diagnose                     → real model, calibrated, with evidence
GET    /api/audit/events                 → indexed chain events
GET    /api/privacy/ledger               → ε per site per round
POST   /api/admin/hospitals/{id}/revoke  → governance
GET    /healthz /readyz /metrics         → probes + Prometheus
WS     /ws/rounds                        → live state push
```

`/api/status` must tell the truth about *provenance*:

```json
{
  "generated_at": "2026-10-22T09:31:04Z",
  "sources": {"chain": "ok", "ipfs": "degraded", "model": "ok", "db": "ok"},
  "round": {"id": 4, "phase": "finalized", "participants": 3, "required": 3,
            "started_at": "...", "finalized_at": "...", "tx_hash": "0x…", "merkle_root": "0x…"},
  "model": {"version": "v4.0.4", "cid": "bafy…", "sha256": "0x…", "params": 295424,
            "metrics": {"macro_f1": 0.51, "top5": 0.88, "ece": 0.071}},
  "privacy": {"dp": true, "epsilon_total": 7.8, "delta": 1e-05, "secagg": true},
  "hospitals": [{"id": "h1", "name": "…", "status": "online", "last_seen": "…", "epsilon": 2.4}]
}
```

If `ipfs: degraded`, the UI must render a banner. Never substitute stale numbers silently — that was finding M-01.

### E2. Round state machine (2 pd)

```python
# src/medxchain/rounds/state.py
class Phase(StrEnum):
    IDLE = "idle"; COLLECTING = "collecting"; QUORUM = "quorum_reached"
    SEALING = "sealing"; SEALED = "sealed"; AGGREGATING = "aggregating"
    PUBLISHING = "publishing"; FINALIZED = "finalized"; DISPUTED = "disputed"
    FAILED = "failed"; ABORTED = "aborted"

ALLOWED = {
    Phase.IDLE: {Phase.COLLECTING},
    Phase.COLLECTING: {Phase.QUORUM, Phase.ABORTED, Phase.FAILED},
    Phase.QUORUM: {Phase.SEALING, Phase.ABORTED},
    Phase.SEALING: {Phase.AGGREGATING, Phase.FAILED},
    Phase.AGGREGATING: {Phase.PUBLISHING, Phase.FAILED},
    Phase.PUBLISHING: {Phase.SEALED, Phase.FAILED},
    Phase.SEALED: {Phase.FINALIZED, Phase.DISPUTED},
    Phase.DISPUTED: {Phase.FAILED, Phase.SEALED},
    Phase.FINALIZED: {Phase.IDLE},
}

def transition(rnd, to: Phase) -> None:
    if to not in ALLOWED[rnd.phase]:
        raise IllegalTransition(f"{rnd.phase} -> {to}")
    rnd.phase = to            # persisted with SELECT ... FOR UPDATE
```

Persist with `SELECT ... FOR UPDATE` (optimistic locking), so two aggregator workers can't double-seal. Add an **idempotency key** on every POST and a `round_events` append-only table — the audit trail lives there, not only on-chain.

### E3. Worker + queue (2 pd)

Celery/RQ with Redis is enough. Jobs: `train_local` (edge, not server), `aggregate`, `publish_ipfs`, `anchor_chain`, `evaluate`, `index_events`. Requirements: retries with exponential backoff, dead-letter queue, per-round timeout, and a visible job status in the UI. Kill the current "synchronously do everything in one script with `try/except: fake it`" model.

### E4. Chain client + event indexer (2 pd)

```python
# src/medxchain/chain/client.py
class ChainClient:
    def __init__(self, rpc: str, address: str, abi_path: Path, key: str | None = None):
        self.w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 10}))
        self.contract = self.w3.eth.contract(address=Web3.to_checksum_address(address), abi=json.loads(abi_path.read_text()))
        self.account = self.w3.eth.account.from_key(key) if key else None

    def submit(self, round_id: int, cid: str, weight_hash: bytes, key_commitment: bytes, n: int, loss_bps: int) -> str:
        fn = self.contract.functions.submitUpdate(round_id, cid, weight_hash, key_commitment, n, loss_bps)
        tx = fn.build_transaction({"from": self.account.address, "nonce": self.w3.eth.get_transaction_count(self.account.address),
                                   "gas": 250_000, "gasPrice": self.w3.eth.gas_price})
        signed = self.account.sign_transaction(tx)
        return self.w3.eth.send_raw_transaction(signed.raw_transaction).hex()
```

Indexer: poll `UpdateSubmitted`/`RoundSealed`/`RoundFinalized` → upsert into `chain_events`; expose via `/api/audit/events`. For production, use The Graph or Ponder; for local, the poller is fine. Verify `deployment_info.json`'s address matches `contract.address` on start — 13 hard-coded addresses is 13 future bugs.

---

## 10. Track F — Dashboard 2.0

### F1. Data binding (3 pd) — closes M-01

Replace every literal with API-driven rendering:

| Element | Today | Target |
| :--- | :--- | :--- |
| Hospitals connected | literal `14` | `len(status.hospitals)` |
| Model updates | literal `1.2k` | `SELECT count(*) FROM submissions` |
| Global version | derived from round, but only badge | `status.model.version` + CID + sha |
| Accuracy chart | hard-coded coordinate array | `/api/rounds?fields=metrics` series |
| Participation bars | literal percentages | per-site `num_samples / total` |
| Ledger rows | 2023-10-24 + `0xdeadbeef…` | `/api/audit/events` |
| SHAP bars | hard-coded divs | attributions from `/api/diagnose` (Track G) |
| "124 hospitals / 1.2M gradients / 99.9 %" | literals | delete or compute |

Add: skeleton loaders, explicit empty states, and an **error banner with retry** when a source is degraded. Add `data-testid` attributes so Playwright can assert *no element ever shows a hard-coded number*.

### F2. Auth + RBAC (3 pd)

JWT with roles → view access:

| Role | Sees | Can do |
| :--- | :--- | :--- |
| `clinician` | diagnosis, anamnesis | request diagnosis, override, comment |
| `hospital_op` | own site only | upload update, rotate keys, view ε |
| `auditor` | everything read-only, replay, exports | verify inclusion proofs, export |
| `admin` | all | register/revoke hospitals, set quorum, pause |
| `public` | none (optional read-only transparency page) | — |

Implementation notes: `HttpOnly` cookie or `Authorization: Bearer`; short TTL + refresh; `Depends(require_roles("auditor"))`; every mutation writes an `audit_log` row with `actor, action, target, before, after, ip, trace_id`. Never ship the current "anyone can POST `/api/advance-round`" behaviour.

### F3. Accessibility & polish (2 pd)

Today: **0** `aria-*`, **0** `role=`, emoji-as-icons, no focus management, fonts from Google (breaks offline previews). Target WCAG 2.1 AA:
- semantic landmarks (`nav`, `main`, `aside`), `aria-current` on tabs, `role="tablist"/"tab"/"tabpanel"` with arrow-key handling;
- visible focus rings, `prefers-reduced-motion`, contrast ≥ 4.5:1;
- real SVG icons inline (no emoji), every icon `aria-hidden` with a text label;
- self-host Inter/JetBrains Mono (`woff2` in `web/public/fonts`);
- `axe-core` in CI on every view; Playwright keyboard-only smoke test.

### F4. Frontend build (2 pd)

Move to Vite + ES modules (or React if the team prefers). Why: you now have ~8 views, real auth, WebSocket, and shared components. Keep it framework-light if you want (`vite` + vanilla + small `lit`/`htm` templates), but get: hashing for cache-busting, tree-shaking, a single `npm run build`, and a CSP-friendly bundle. Replace hand-rolled canvas charts with `uPlot` (tiny, fast) or `Chart.js`; feed them API arrays.

---

## 11. Track G — Clinical AI that is safe to show a doctor

Current state: substring matching on disease names. It returned **"Open Wound Of The Chest 49 %"** for dyspnoea. This track is not optional if the demo is shown to anyone clinical.

### G1. Real inference service (2 pd)

```python
# src/medxchain/clinical/infer.py
class DiagnosisService:
    def __init__(self, ckpt_dir: Path, device="cpu"):
        self.ckpt = load_checkpoint(ckpt_dir / "global.pt")
        self.model = load_model_from_checkpoint(self.ckpt, device=device).eval()
        self.tok = AutoTokenizer.from_pretrained(self.ckpt.base_model)

    @torch.inference_mode()
    def predict(self, symptoms: str, top_k: int = 5) -> Prediction:
        enc = self.tok(symptoms, return_tensors="pt", truncation=True, max_length=128).to(self.device)
        logits = self.model(enc["input_ids"], enc["attention_mask"])
        probs = torch.softmax(self.temperature(logits), dim=-1)[0]
        return Prediction(probs=probs, top_k=top_k, model_version=self.ckpt.round, cid=self.ckpt_cid)
```

Guardrails (all cheap, all important):
- reject `< 3` symptoms or `< 10` chars with a 422 + guidance;
- **red-flag detection** ("chest pain", "suicidal", "stroke", "severe bleeding") → return an urgent-care advisory *before* any differential;
- cap `top_k` at 5, always show the model version, round, CID, and "decision support only";
- log the *redacted* query (strip anything that looks like a name/MRN) with a trace id;
- rate-limit per user/IP.

### G2. Calibration (1.5 pd)

```python
def fit_temperature(logits, labels):           # on a held-out calibration split
    T = nn.Parameter(torch.ones(1))
    opt = torch.optim.LBFGS([T], lr=0.1, max_iter=50)
    def closure():
        opt.zero_grad(); loss = F.cross_entropy(logits / T, labels); loss.backward(); return loss
    opt.step(closure); return float(T.detach())
```

Report **ECE** before/after. A model whose confidence is meaningless is worse than no confidence bar: the current UI paints 49 % on nonsense.

### G3. Conformal prediction + abstention (2 pd)

```python
# split-conformal, per class, on a calibration set
def conformal_threshold(scores_correct: np.ndarray, alpha=0.1) -> float:
    n = len(scores_correct)
    q = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(scores_correct, q))

def prediction_set(probs: torch.Tensor, thr: float, k_max: int = 5) -> list[tuple[int, float]]:
    idx = (probs >= thr).nonzero(as_tuple=True)[0].tolist()
    return sorted(((int(i), float(probs[i])) for i in idx), key=lambda t: -t[1])[:k_max]
```

Display: **"Prediction set (90 % coverage): 3 conditions"** instead of fake precision, and **abstain** (`"insufficient evidence — recommend workup X"`) when the set is empty or larger than `k_max`. This is the single most defensible clinical feature you can add in a semester, and it's easy to evaluate (coverage vs set size plot).

### G4. Explainability that is real (2 pd)

Replace the fake SHAP bars with token-level attribution that matches a text model:
- **Integrated gradients / attention rollout** over input tokens → highlight the symptoms that drove the prediction;
- or **LIME** (`lime` is already in `requirements.txt` and unused) on the text — slow but honest;
- **similar-case retrieval**: kNN over MedCPT embeddings of the training set, show 3 anonymised neighbours as evidence;
- if you insist on SHAP, use `shap.Explainer` on the classifier head and label it "feature attribution", not "consensus across hospitals".

Add an **evidence pack** export (feature F8): one PDF per diagnosis with model version, round, CID, tx hash, calibration, prediction set, top attributions, retrieved neighbours, and a disclaimer.

### G5. ICD-10 mapping (2 pd)

The 793 free-text labels need codes for any real integration. Build `data/icd10_map.csv` (label → ICD-10-CM → chapter), validate coverage (target ≥ 95 % of label mass), and display both. This also makes the ontology auditable and lets you group rare classes into chapters for macro metrics.

---

## 12. Track H — 18 new features

Grouped, each with *why / how / effort / priority / depends*. These are the things that turn the project from "course assignment" into "product with a story".

### Trust & audit

**F1. Round Replay (time-travel debugger)** · *P1 · 3 pd*
- **Why:** an auditor must be able to reconstruct any round without trusting you; it is also the best debugging tool you will ever build.
- **How:** `GET /api/rounds/{id}/replay` returns manifest + submissions + merkle proof + metrics + chain events; UI scrubs through phases with a timeline; `medxchain round replay 4 --verify` re-checks every hash/CID and prints PASS/FAIL per artefact.
- **Acceptance:** replay of round 4 on a fresh machine reproduces `metrics.json` within tolerance and re-verifies all CIDs.

**F2. Privacy (ε) ledger** · *P1 · 2 pd*
- **Why:** makes the privacy claim measurable and auditable; it is what a DPIA needs.
- **How:** table `epsilon_ledger(round, site, epsilon, delta, noise_mult, clip, accountant)`; per-site and cumulative budgets; UI gauge with a budget bar per hospital + CSV export; refuse to start a round that would exceed the configured budget.
- **Acceptance:** budget exhaustion blocks a round with a clear error; export matches the accountant's numbers.

**F3. Inclusion-proof verifier** · *P2 · 1.5 pd*
- **Why:** lets a hospital prove its update was counted — the actual point of the Merkle root.
- **How:** `/api/rounds/{id}/submissions/{site}/proof` → `{leaf, proof[], root}`; UI "Verify on-chain" button calls `verifyInclusion` via RPC and shows ✓/✗; public verify page (no auth) taking round+address.
- **Acceptance:** tampering with any leaf makes verification fail.

**F4. Immutable audit export** · *P2 · 1.5 pd*
- **Why:** regulators, journals, and your own future self need a portable artefact.
- **How:** `GET /api/audit/export?round=4&format=pdf|json|csv` → signed bundle (`sha256` + optional Ed25519 signature), including chain events, ε, metrics, disclaimers; `docs/compliance.md` explains how to verify offline.
- **Acceptance:** exported bundle re-verifies with `medxchain audit verify bundle.zip`.

### Privacy & governance

**F5. Consent & purpose registry** · *P2 · 3 pd*
- **Why:** GDPR/HIPAA need purpose limitation and demonstrable consent, not just "no raw data leaves".
- **How:** store `consent(patient_pseudonym_hmac, purpose, granted_at, revoked_at, policy_version)`; on-chain store only `keccak(policy_version)`; training refuses sites whose consent coverage for the purpose < threshold; dashboard shows coverage per purpose.
- **Acceptance:** revoking consent excludes the site from the next round and the manifest records why.

**F6. Crypto-shredding / right-to-erasure flow** · *P2 · 2 pd*
- **Why:** resolves the immutability-vs-GDPR-Art-17 tension without mutating the chain.
- **How:** per-round key in DB/KMS; `DELETE /api/privacy/keys/{key_id}` destroys the key → ciphertext becomes unreadable; on-chain hash remains but is no longer linkable; audit log records the erasure event and the affected rounds.
- **Acceptance:** after key destruction, `/rounds/{id}/artifact` returns `410 Gone` with an erasure reference; inclusion proof still verifies.

**F7. Hospital onboarding + key ceremony** · *P2 · 3 pd*
- **Why:** a real deployment's weakest link is how a new hospital joins.
- **How:** wizard: generate Ed25519 + X25519 keys → CSRs → admin approval → `registerHospital` tx → stake → mTLS cert issued → connectivity self-test (chain RPC, IPFS, API) → first dry-run round. Store key fingerprints; support rotation with overlap.
- **Acceptance:** a new site can join end-to-end in < 15 min without touching the codebase.

### Clinical

**F8. Evidence pack PDF per diagnosis** · *P1 · 2 pd*
- **Why:** clinicians don't trust a percentage; they trust a traceable artefact.
- **How:** WeasyPrint/ReportLab template: input (redacted), prediction set + coverage, calibration, top attributions, 3 similar cases, model version/round/CID/tx, disclaimer; QR code linking to the public verify page (F3).
- **Acceptance:** PDF contains the tx hash and re-verifies.

**F9. Human-in-the-loop review queue** · *P2 · 3 pd*
- **Why:** captures clinical feedback (the only ground truth you'll ever get) and creates an active-learning loop.
- **How:** `POST /api/diagnose/{id}/review {agree, corrected_label, note}`; queue view for clinicians; safe aggregation of corrections into a *separate* federated "feedback" round (never silently into the diagnostic model); track agreement rate and per-class disagreement.
- **Acceptance:** overrides are stored with actor + timestamp, appear in audit export, and never mutate past round artefacts.

**F10. Drift & data-quality monitor** · *P2 · 3 pd*
- **Why:** a federated model silently rots when one site's population shifts.
- **How:** per site per round: label-distribution JS divergence vs baseline, input-length and vocabulary drift, missing-field rate, PSI on numeric features; alert when above threshold; store the series for charts.
- **Acceptance:** injecting a synthetic 30 % label shift triggers an alert in the next round.

**F11. Champion / challenger** · *P3 · 3 pd*
- **Why:** lets you ship a new aggregation algorithm safely.
- **How:** two model versions scored on the same shadow set each round; promotion gate (`macro_f1 >= champion + 0.01` and `ece <= champion`), manual approval, rollback by round id.
- **Acceptance:** a deliberately worse challenger is never promoted.

### Operations

**F12. Federated cohort discovery** · *P3 · 4 pd*
- **Why:** the most compelling "why federated" demo — *"which sites have ≥ 20 cases of this rare condition?"* without exposing records.
- **How:** each site returns a noisy count per query label (Laplace/Gaussian, ε = 0.1); aggregator sums; UI shows counts with confidence intervals and suppresses cells < k (k-anonymity, e.g. 5).
- **Acceptance:** reconstructed counts within CI; no cell below k is ever displayed.

**F13. Simulation sandbox / digital twin** · *P2 · 4 pd*
- **Why:** "what if we add a 4th hospital / drop quorum to 2 / turn DP on?" — answers with numbers instead of opinions.
- **How:** run the aggregator against synthetic sites with configurable α (non-IID), dropout rate, and attack injectors; output a comparison table + charts; no chain writes.
- **Acceptance:** reproduces the FedAvg vs FedProx gap on a synthetic non-IID split.

**F14. Alert center + incident workflow** · *P2 · 2 pd*
- **Why:** an ops product needs to tell you when it's broken before a demo does.
- **How:** rules engine (round stuck > N min, host unreachable, ε budget > 80 %, hash mismatch, chain indexer lag, drift); dedupe/ack/silence; Slack/email webhook; each alert links to the affected round.
- **Acceptance:** killing a Kubo container raises `ipfs.unhealthy` within one scrape interval and clears on recovery.

### Platform

**F15. Python hospital SDK + CLI** · *P2 · 3 pd*
- **Why:** a hospital should not clone your repo to participate.
- **How:** `pip install medxchain-client`; `Client(rpc, ipfs, key).round(4).train(csv).submit()`; `medxchain doctor` runs preflight (chain, IPFS, cert, clock skew, disk); typed errors; offline dry-run mode.
- **Acceptance:** a 20-line script trains, encrypts, uploads, submits, and returns the tx hash.

**F16. Benchmark leaderboard** · *P2 · 2 pd*
- **Why:** turns "we built a system" into "we measured algorithms", which is what a paper needs.
- **How:** `bench/` runs FedAvg / FedProx / SCAFFOLD / trimmed-mean × IID / Dirichlet(0.5) / Dirichlet(0.1) × DP on/off; stores results; renders a sortable table with mean ± std over 3 seeds.
- **Acceptance:** one command produces the table in `results/leaderboard.md`.

**F17. Public transparency page** · *P3 · 1.5 pd*
- **Why:** the civic argument for this project — prove the network is healthy without exposing anything.
- **How:** unauthenticated read-only page: number of sites (opt-in), rounds completed, aggregate metrics, ε policy, incident history. **No** CIDs, no addresses, no PHI, no per-site numbers.
- **Acceptance:** security review confirms zero identifying data.

**F18. PWA + offline clinician mode** · *P3 · 2 pd*
- **Why:** hospitals have bad connectivity; the diagnosis view is the one that must work.
- **How:** service worker caches the shell + model; on-device inference via ONNX-exported head (LoRA-merged adapter is small: ~1 MB int8); queue diagnoses, sync when online; never cache other patients' data.
- **Acceptance:** airplane-mode diagnosis works and syncs idempotently.

---

## 13. Track I — Security engineering

Write `docs/threat-model.md` (STRIDE table) before writing code. Priority items:

| Area | Control | pd |
| :--- | :--- | --: |
| AuthN | JWT + refresh, short TTL, `jti` revocation list; hospital auth via **mTLS** | 2 |
| AuthZ | role checks on every route (deny-by-default dependency), object-level checks (a site only sees itself) | 1 |
| Transport | TLS everywhere (`mkcert` in dev, real certs in staging); HSTS | 1 |
| Input | Pydantic models, size caps (`max_body=1 MB`, uploads `50 MB`), regex on CIDs, reject unknown fields | 1 |
| Secrets | `.env` never committed; SOPS/Vault; **Anvil keys are dev-only** and must be refused if `env=prod` | 0.5 |
| Keys | Ed25519 signing, X25519 wrapping, rotation, fingerprints, HSM/KMS for prod | 2 |
| Supply chain | `pip-audit`, `npm audit --omit=dev`, `trivy fs`, SBOM (`syft`), Dependabot, pinned hashes | 1 |
| Contracts | `slither`, `foundry fmt`, invariant tests, timelock, multisig (Safe 2-of-3) as admin | 3 |
| Abuse | rate limiting (`slowapi`), request ids, per-IP quotas on `/diagnose` | 1 |
| Web | CSP (no inline), `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, CSRF token for cookie auth | 1 |
| Logging | structured, PII-redacted, `trace_id`, no secrets, 90-day retention policy | 1 |
| Backups | Postgres PITR, IPFS pin snapshots, restore drill documented | 1 |

Also: **rotate every key currently in the repo** (Anvil account #0 private key is public knowledge; `.env.example` has a stale deploy address). Treat the committed `deployment_info.json` as compromised-by-assumption.

---

## 14. Track J — Compliance & governance

You cannot say "HIPAA compliant" — you can say "designed against HIPAA Security Rule §164.312 controls; not yet audited". Build the evidence:

| Artefact | Contents | pd |
| :--- | :--- | --: |
| `docs/compliance/hipaa-mapping.md` | Each safeguard → implementation → test/evidence (access control, audit logs, integrity, transmission security) | 2 |
| `docs/compliance/gdpr-dpia.md` | Processing purposes, lawful basis, data minimisation, DPIA with DP + SecAgg + crypto-shredding, retention, sub-processors | 2 |
| `docs/compliance/kvkk.md` | Turkish law counterpart (the team context) | 1 |
| `docs/compliance/data-retention.md` | Round artefacts 10 rounds, logs 90 days, keys per policy, deletion procedure | 0.5 |
| `docs/compliance/samd-statement.md` | Explicit "research use only; not a medical device; no clinical claims" until validated | 0.5 |
| Consent + erasure | Features F5, F6 | (tracked) |
| Data processing register | Table of datasets, owners, locations, legal basis | 0.5 |

Governance (if you keep the "decentralized" framing): admin = **Safe multisig 2-of-3** (two institutions + one neutral), all role changes behind a 48 h timelock, and an ADR explaining why a single EOA was rejected. Otherwise, rename the project "federated learning with an on-chain audit log" — which is honest and still interesting.

---

## 15. Track K — MLOps, CI/CD, observability, deployment

### K1. CI (2 pd)

```yaml
# .github/workflows/ci.yml (jobs)
lint:      ruff check . && ruff format --check . && mypy src
py-test:   pytest -q --cov=medxchain --cov-fail-under=70
contracts: forge fmt --check && forge test -vvv && forge coverage --report summary
security:  slither contracts/ && pip-audit && npm audit --omit=dev
web:       npm ci && npm run lint && npm run build && npx playwright test
e2e:       docker compose up -d --wait && pytest -m e2e
```

Nightly: full e2e + benchmark smoke + dependency update PR. Pre-commit: `ruff`, `mypy`, `prettier`, `solhint`, `gitleaks`, `check-added-large-files` (would have caught the 67 MB CSVs).

### K2. Observability (2 pd)

- **Metrics** (Prometheus): `round_duration_seconds{phase}`, `submissions_received`, `quorum_wait_seconds`, `ipfs_upload_bytes`, `ipfs_latency_seconds`, `chain_tx_gas_used`, `chain_indexer_lag_blocks`, `epsilon_total{site}`, `model_macro_f1`, `diagnose_requests_total{outcome}`.
- **Traces** (OpenTelemetry): one trace per round, spans per hop (train → encrypt → ipfs → chain → aggregate → evaluate).
- **Logs**: JSON, `trace_id`/`round_id`/`site_id`, no PII.
- **Dashboards**: Grafana JSON committed in `ops/grafana/`; alerts (F14) wired to the same rules.
- **SLOs** in §16.

### K3. Deployment (2 pd)

Multi-stage Dockerfile (`python:3.12-slim`, non-root, healthcheck), full `docker-compose.yml` (anvil, 4 kubo, ipfs-cluster, postgres, redis, api, worker, web, prometheus, grafana, loki), `Makefile` targets (`make up`, `make seed`, `make round`, `make bench`), and a Helm chart for k8s. One command must bring up the whole system — the current README requires six terminals and manual address copying.

```yaml
# docker-compose.yml (excerpt)
services:
  anvil:   { image: ghcr.io/foundry-rs/foundry:latest, command: anvil --host 0.0.0.0 --chain-id 31337, ports: ["8545:8545"] }
  ipfs1:   { image: ipfs/kubo:latest, volumes: ["./ops/swarm.key:/data/ipfs/swarm.key", "ipfs1:/data/ipfs"], ports: ["5001:5001"] }
  cluster: { image: ipfs/ipfs-cluster:latest, depends_on: [ipfs1, ipfs2, ipfs3], ports: ["9094:9094"] }
  db:      { image: postgres:16, environment: { POSTGRES_DB: medxchain }, volumes: ["pg:/var/lib/postgresql/data"] }
  api:     { build: ., command: uvicorn medxchain.api.app:app --host 0.0.0.0 --port 8000, depends_on: [db, anvil] }
  worker:  { build: ., command: celery -A medxchain.rounds.workers worker -Q rounds }
  web:     { build: ./web, ports: ["3000:80"], environment: { API_URL: "http://api:8000" } }
```

---

## 16. Targets & SLOs

| Metric | Today | Target | How measured |
| :--- | :--- | :--- | :--- |
| Round wall-clock (3 sites, LoRA) | n/a | < 90 s local | `round_duration_seconds` |
| Submissions per round | 0 (fake) | 3/3 with proof | chain events |
| Upload size per site | 3.2 MB toy / 440 MB real | ≤ 2 MB (LoRA fp32) / 0.35 MB int8 | IPFS size |
| Gas per submission | ~200 k | ≤ 150 k | `forge snapshot` |
| Dashboard truthfulness | 2/12 panels live | 12/12 live, 0 literals | Playwright assertion |
| Test coverage | 0 % Python | ≥ 70 % Python, ≥ 95 % contracts | coverage reports |
| Macro-F1 (global) | 73.9 % acc (unknown F1) | ≥ 78 % acc, ≥ 0.55 macro-F1 | `metrics.json` |
| Calibration ECE | not measured | ≤ 0.08 | calibration report |
| Conformal coverage (α=0.1) | n/a | 0.88–0.92 | calibration report |
| ε per round | n/a | ≤ 2.0; total ≤ 8 | Opacus accountant |
| MIA AUC | presumably ~1.0 | ≤ 0.55 at ε ≤ 8 | attack notebook |
| API p95 latency | n/a | < 300 ms (non-ML routes) | Prometheus |
| Uptime (dev compose) | n/a | 99 % over a week | probes |

---

## 17. Finding → work-item coverage

Every audit finding must be closed by something in this plan:

| Finding | Closed by |
| :--- | :--- |
| C-01 no real training | A1, A3 |
| C-02 fabricated metrics | §1.1, A5, E1, F1 |
| C-03 PII in Git | §1.4, J (retention), history scrub |
| C-04 unsafe diagnosis | §1.3, §1.10, G1–G4 |
| C-05 empty submissions | C (contract v2) |
| H-01 chain never called | E4, A6 |
| H-02 broken IPFS + fake CIDs | §1.7, D |
| H-03 quorum 0 | C |
| H-04 admin centralization | C (roles, multisig, timelock) |
| H-05 unauthenticated API | E1, F2, I |
| H-06 incompatible checkpoints | A2 |
| H-07 silent overwrite | C (immutable finalize) |
| H-08 federation hurts accuracy | A2 (LoRA), A4 (FedProx), L (benchmarks) |
| M-01 mockup dashboard | F1 |
| M-02 contract sprawl | C, §1.11 |
| M-03 no CI/licence/tests | §1.9, §1.12, K1 |
| M-04 repo hygiene | §1.5, §1.6, §1.11, K1 |
| M-05 reproducibility | A3, A6, K3 |
| M-06 privacy claims | B1–B4, J |
| M-07 backend robustness | E1–E3 |
| M-08 data quality | A1, A5, G5 |
| M-09 silent failures | A3, E3, F14 |
| M-10 docs/ABI drift | C, §19 |
| L-* | F3, K1, I |

---

## 18. The first 10 pull requests (copy-paste backlog)

1. **PR-01 "honesty pass"** — remove fake metrics, stub `/diagnose` to 501, add disclaimers, add LICENSE, fix gitignores. *(1 pd)*
2. **PR-02 "contract safety"** — three `require`s + `setAggregator` zero-check + tests for each. *(1 pd)*
3. **PR-03 "repo slimming"** — dedupe CSVs, strip PII columns, drop `__pycache__`, move notebooks. *(1 pd)*
4. **PR-04 "packaging + CI"** — `pyproject.toml`, `src/medxchain`, ruff/mypy/pytest, GitHub Actions. *(2 pd)*
5. **PR-05 "real training"** — `data.py` + `trainer.py` + seeded deterministic test. *(3 pd)*
6. **PR-06 "checkpoint + LoRA"** — one artefact format, `peft` integration, param-count test. *(2 pd)*
7. **PR-07 "chain v2"** — `FederatedRound.sol` + Foundry fuzz/invariant suite + `web3.py` client + one real tx from the pipeline. *(4 pd)*
8. **PR-08 "IPFS correctness"** — multipart, CID verify, encryption, retrieval fail-closed. *(2 pd)*
9. **PR-09 "service + DB"** — FastAPI skeleton, Postgres schema, `/api/status` from real data, round state machine. *(4 pd)*
10. **PR-10 "dashboard truth"** — bind every panel to the API, add error states, Playwright literal-detection test. *(3 pd)*

After PR-10 the project is *honest and closed-loop*. Everything else is depth.

---

## 19. What NOT to build (yet)

- **Tokenomics / governance token.** Adds legal surface, zero scientific value; a multisig is enough.
- **On-chain model storage.** Prohibitively expensive, and you'd be publishing weights — the opposite of the privacy pitch.
- **Full zkML proofs of training.** Research-grade cost (minutes–hours per proof for tiny models). If you want ZK, start with a **norm-bound range proof** on the update (proves clipping, i.e. DP is honest) — that's tractable with Bulletproofs.
- **Kubernetes on day one.** Docker Compose until you have a second environment.
- **Microservices.** One API + one worker; split later if you ever need to.
- **A custom blockchain.** Anvil→Base/Sepolia is fine; the interesting work is the protocol, not consensus.
- **"HIPAA-compliant" wording.** Until an audit happens, say "designed against". Overclaiming is the repo's existing failure mode.
- **Frontend framework rewrite for its own sake.** A build step plus a chart library is enough.

---

## 20. Definition of done (per track)

A track ships only when **all** of these are true:

- [ ] Code lives under `src/medxchain` with types (`mypy --strict` on new modules)
- [ ] Unit + integration tests; coverage gate respected
- [ ] Failure paths tested (dependency down, hash mismatch, hash of empty, timeout)
- [ ] No literal appears in the UI that isn't in a test fixture
- [ ] Metrics/traces emitted; alert rule exists for the new failure mode
- [ ] `docs/` updated; README claim added **only** with a link to the artefact proving it
- [ ] Security review: inputs validated, authz checked, secrets externalised
- [ ] Migration + rollback documented (DB and contract)
- [ ] Manifest fields added so the round remains replayable

---

## 21. Risks & trade-offs

| Risk | Mitigation |
| :--- | :--- |
| LoRA-only training caps accuracy vs full fine-tuning | Report both; full-model mode behind a flag for offline runs |
| DP-SGD on CPU is slow | Ghost clipping + small adapter + small batch accumulation; GPU optional |
| SecAgg is complex and easy to get subtly wrong | Start with synchronous rounds + dropout exclusion; add recovery later; property-test the sum |
| Challenge window slows the demo | `challengeWindow = 60` in dev, `1 day` in prod; **document** the difference |
| More infra → more ways to fail during a demo | `make demo` runs a fully local, seeded, offline path; record a backup video |
| Scope explosion | The phase table is the contract: do not start Phase 3 before Phase 1 exits |
| Privacy claims outrun implementation | Every claim in README must cite `docs/privacy.md` numbers |

---

## 22. Appendix A — environment variables

```bash
MEDXCHAIN_ENV=dev
MEDXCHAIN_DEMO_MODE=true            # blocks fake data outside dev
MEDXCHAIN_CHAIN_RPC=http://127.0.0.1:8545
MEDXCHAIN_CHAIN_ID=31337
MEDXCHAIN_CONTRACT=0x…              # never hard-code; loaded from deployment_info.json by CLI
MEDXCHAIN_AGGREGATOR_KEY=0x…        # dev only; refuses to start when ENV=prod
MEDXCHAIN_IPFS_API=http://127.0.0.1:5001
MEDXCHAIN_IPFS_CLUSTER=http://127.0.0.1:9094
MEDXCHAIN_DB_URL=postgresql+psycopg://medxchain:medxchain@db:5432/medxchain
MEDXCHAIN_REDIS_URL=redis://redis:6379/0
MEDXCHAIN_JWT_SECRET=…
MEDXCHAIN_QUORUM=3
MEDXCHAIN_DP_ENABLED=true
MEDXCHAIN_DP_TARGET_EPSILON=8
MEDXCHAIN_DP_DELTA=1e-5
MEDXCHAIN_DP_MAX_GRAD_NORM=1.0
MEDXCHAIN_SECAGG_ENABLED=true
MEDXCHAIN_MODEL_BASE=ncbi/MedCPT-Query-Encoder
MEDXCHAIN_MODEL_TUNABLE=lora
MEDXCHAIN_CHALLENGE_WINDOW=60
MEDXCHAIN_LOG_LEVEL=info
```

## Appendix B — database schema (essentials)

```sql
CREATE TABLE hospitals (id UUID PRIMARY KEY, name TEXT NOT NULL, address TEXT UNIQUE NOT NULL,
                        public_key TEXT, status TEXT NOT NULL DEFAULT 'pending', created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE rounds (id BIGINT PRIMARY KEY, phase TEXT NOT NULL, quorum INT NOT NULL,
                     merkle_root BYTEA, global_cid TEXT, global_sha256 BYTEA, tx_hash TEXT,
                     started_at TIMESTAMPTZ, sealed_at TIMESTAMPTZ, finalized_at TIMESTAMPTZ);
CREATE TABLE submissions (round_id BIGINT REFERENCES rounds(id), hospital_id UUID REFERENCES hospitals(id),
                     cid TEXT NOT NULL, ciphertext_sha256 BYTEA NOT NULL, key_id TEXT NOT NULL,
                     num_samples INT NOT NULL CHECK (num_samples > 0), loss_bps INT,
                     epsilon REAL, delta REAL, tx_hash TEXT, created_at TIMESTAMPTZ DEFAULT now(),
                     PRIMARY KEY (round_id, hospital_id));
CREATE TABLE metrics (round_id BIGINT, scope TEXT, entity_id TEXT, name TEXT, value DOUBLE PRECISION,
                      PRIMARY KEY (round_id, scope, entity_id, name));
CREATE TABLE epsilon_ledger (round_id BIGINT, hospital_id UUID, epsilon REAL NOT NULL, delta REAL NOT NULL,
                      noise_mult REAL, clip REAL, accountant TEXT, created_at TIMESTAMPTZ DEFAULT now(),
                      PRIMARY KEY (round_id, hospital_id));
CREATE TABLE chain_events (id BIGSERIAL PRIMARY KEY, block_number BIGINT, tx_hash TEXT, log_index INT,
                      event TEXT, round_id BIGINT, payload JSONB, observed_at TIMESTAMPTZ DEFAULT now(),
                      UNIQUE (tx_hash, log_index));
CREATE TABLE audit_log (id BIGSERIAL PRIMARY KEY, actor TEXT, role TEXT, action TEXT, target TEXT,
                      before JSONB, after JSONB, ip INET, trace_id TEXT, created_at TIMESTAMPTZ DEFAULT now());
CREATE TABLE consent (id BIGSERIAL PRIMARY KEY, patient_hmac BYTEA, purpose TEXT, policy_version TEXT,
                      granted_at TIMESTAMPTZ, revoked_at TIMESTAMPTZ);
CREATE TABLE alerts (id BIGSERIAL PRIMARY KEY, rule TEXT, severity TEXT, payload JSONB, round_id BIGINT,
                      created_at TIMESTAMPTZ DEFAULT now(), acked_by TEXT, acked_at TIMESTAMPTZ);
```

## Appendix C — dependency additions

```toml
# pyproject.toml
dependencies = [
  "fastapi>=0.115", "uvicorn[standard]>=0.30", "pydantic>=2.8", "pydantic-settings>=2.4",
  "sqlalchemy>=2.0", "psycopg[binary]>=3.2", "alembic>=1.13", "redis>=5", "celery>=5.4",
  "web3>=7", "httpx>=0.27", "cryptography>=43",
  "torch>=2.3", "transformers>=4.44", "peft>=0.12", "opacus>=1.5",
  "scikit-learn>=1.5", "pandas>=2.2", "numpy>=1.26", "scipy>=1.13",
  "structlog>=24", "prometheus-client>=0.20", "opentelemetry-sdk>=1.26",
  "weasyprint>=62", "pyjwt>=2.9", "slowapi>=0.1.9",
]
dev = ["pytest", "pytest-cov", "pytest-asyncio", "hypothesis", "ruff", "mypy", "types-requests", "pip-audit"]
```

Contract tooling: `foundry` (forge/cast/anvil), `@openzeppelin/contracts@5`, `slither-analyzer`.

---

## 23. TL;DR

1. **Stop the lying first** (12 quick wins, 1 week) — fake accuracy, fake CIDs, fake transactions, unsafe diagnosis, PII in Git.
2. **Close the loop** (weeks 2–4) — real training on real rows, LoRA adapters, a hardened contract that *actually receives transactions*, Postgres as the source of truth, a dashboard bound to the API.
3. **Make the privacy real** (weeks 5–6) — DP-SGD with a published ε, secure aggregation, encrypted blobs, and an attack-evaluation table.
4. **Make the clinical AI defensible** (weeks 7–8) — calibration, conformal prediction sets, abstention, real explanations, ICD-10.
5. **Then add product features** (weeks 9–12) — round replay, ε ledger, inclusion proofs, evidence packs, onboarding, drift, champion/challenger, cohort discovery, benchmarks.
6. **Ship evidence, not adjectives** — every README claim links to a metrics file, a test, or a compliance artefact.
