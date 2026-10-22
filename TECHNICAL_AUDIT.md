# MedXChAIn — Complete Technical Audit

*What is actually there, what it does when executed, and where the documentation diverges from the code.*

| Attribute | Detail |
| :--- | :--- |
| **Repository** | `SuhasRam356/Decentralized-Privacy-Preserving-Federated-Learning-with-Blockchain-for-Distributed-Hospitals` |
| **Commit audited** | `b0b8941` (single commit, 2026-10-22) |
| **Branch** | `arena/144b2365-decentralized-privacy-preservi` |
| **Audit date** | 2026-10-22 |
| **Scope** | every tracked file (66 files, ~137 MB working tree) |
| **Method** | full source read + static analysis + **live execution** of the Solidity contracts, the IPFS emulator, the FL pipeline components and the dashboard API (commands in Appendix A) |

---

## 0. Verdict at a glance

| Layer | Code maturity | Does it do what the README says? | Worst problem |
| :--- | :--- | :--- | :--- |
| **Federated learning** (`FL/`, `LocalTraining/`, `run_federated_pipeline.py`) | Prototype | ❌ No | "Training" runs on `torch.randn` tensors — no patient data is ever learned |
| **Smart contracts** (`Blockchain/contracts/`) | Prototype, compiles, 14 tests pass | ⚠️ Partly | Accepts empty CID/hash as a valid submission; fully centralized admin |
| **Blockchain integration** (Python side) | **Missing** | ❌ No | The pipeline **never sends a transaction**; `deployment_info.json` is only printed |
| **IPFS layer** (`ipfs-hospitals/`) | Working emulator | ⚠️ Partly | Not a real IPFS cluster (shared folder), and the client upload format is incompatible with Kubo |
| **Dashboard** (`UI-DashBoard/app/`) | Polished UI, hardcoded data | ❌ No | Reports synthetic numbers (89.4 % accuracy, 14 hospitals, 1.2 k updates) as if measured |
| **Clinical inference** (`/api/diagnose`) | **Demo stub** | ❌ No | Substring matching on disease *names*, not symptoms — produces medically wrong, confident output |
| **Privacy / compliance** | Claimed, absent | ❌ No | No DP, no secure aggregation, no encryption — and raw patient-like PII is committed to Git |
| **Engineering hygiene** | Fair | ⚠️ Partly | No CI, no LICENSE, no Python tests, 134 MB of duplicated CSVs, stale `.pyc` |

**Bottom line:** this is an **impressive-looking demonstration shell** around a **non-functional scientific core**. The UI, the contract layout, the CID math and the documentation are real work; the federated learning, the on-chain coordination, the IPFS integration and the clinical inference are **simulated, stubbed or disconnected**. Read as a *prototype/proof-of-concept with a presentation layer*, it is coherent. Read as the system the README describes (privacy-preserving clinical AI with an immutable on-chain audit trail), it is **not there yet**, and in several places it makes **claims that the code contradicts** (Section 7).

---

## 1. What the project actually is

A three-way proof of concept: three "hospital" notebooks train a MedCPT classifier, weights are averaged (FedAvg), CIDs are pushed to four IPFS daemons, and a Hardhat contract records round/slot metadata. A single-page dashboard visualises the network.

As implemented, the data path is:

```
 ┌──────────────────────────┐
 │ train_1.csv … train_3.csv│  186 000 rows, 31 columns, patient-like PII
 └─────────────┬────────────┘
               │  (read 500 rows … then ignored)
               ▼
 ┌──────────────────────────┐        torch.randn(32, 768)            ┌──────────────────┐
 │ run_federated_pipeline.py│ ──────────────────────────────────────► │ 5 Adam steps     │
 └─────────────┬────────────┘        (dummy features + labels)        │ random-init model│
               │                                                      └────────┬─────────┘
               │ .pt (3.2 MB, 800 537 params)
               ▼
 ┌──────────────────────────┐   POST raw bytes (Kubo needs multipart)  ┌──────────────────┐
 │ upload_to_ipfs()         │ ───────────────────────────────────────► │ ipfs_service.py  │
 └─────────────┬────────────┘            fails against real Kubo       │ 4 ports, 1 folder│
               │ on exception → "QmHospital1LocalModelWeightsSimulated"  └──────────────────┘
               ▼
 ┌──────────────────────────┐
 │ torch.stack(...).mean()  │  unweighted mean of 3 random models ≈ random model
 └─────────────┬────────────┘
               ▼
 ┌──────────────────────────┐        ┌───────────────────────────┐
 │ global_model_weights.pt  │        │ Blockchain  ←── NOT CALLED│  ← no web3/ethers/JSON-RPC
 └─────────────┬────────────┘        └───────────────────────────┘     anywhere in Python
               ▼
 ┌──────────────────────────┐        ┌───────────────────────────┐
 │ server.py (port 3000)    │ ◄──────│ hardcoded dict `fl_state` │
 └──────────────────────────┘        └───────────────────────────┘
```

Everything downstream of "IPFS" is disconnected from everything upstream. The chain never sees the pipeline; the dashboard never sees the chain, the files, or the model.

---

## 2. Inventory (measured)

| Metric | Value |
| :--- | :--- |
| Tracked files | 66 |
| Git commits | **1** (`feat: complete MedXChAIn overhaul…`) |
| Disk size (with `.git`) | 137 MB; unique CSV blobs 67 MB, stored **twice** (`FL/` + `LocalTraining/`, byte-identical) |
| Python | 573 LOC across 4 files (pipeline 200, server 141, IPFS 163, addToIPFS 69) |
| Solidity | 510 LOC across 4 contracts (ModelUpdateTracker 185, ModelRegistry2 193, ModelRegistry 100, Lock 32) |
| JavaScript | `app.js` 380 LOC + 5 Hardhat scripts (~292 LOC) |
| HTML / CSS | 908 / 2 350 LOC, 6 views, single page, no framework |
| Tests | 14 Hardhat tests (9 boilerplate `Lock.js`, 5 `ModelUpdateTracker`) — **0** for `ModelRegistry`/`ModelRegistry2`, **0** Python, **0** frontend |
| CI | none (`.github/` absent) |
| LICENSE | none, though README badge says MIT |
| Declared Python deps | 10; **7 never imported** by any shipped script (`transformers`, `accelerate`, `numpy`, `scikit-learn`, `joblib`, `lime`, `tqdm` — the first three appear only inside the Colab notebooks); `web3` — required to actually talk to the chain — **is not declared** |

---

## 3. Component deep dives

### 3.1 `run_federated_pipeline.py` — the "FL orchestrator"

What it does, in order:

1. Loads `FL/label_mapping.json` (793 classes) — genuine.
2. Reads `Blockchain/deployment_info.json` and **prints** the contract address (line 88-89). This is the *only* blockchain interaction in the entire Python codebase. There is no `web3`, no `eth_sendTransaction`, no `submitLocalModel` call, yet the script aborts with `FileNotFoundError` if the file is missing (line 69) — a hard dependency on a component it does not use.
3. For each "hospital": `pd.read_csv(..., nrows=500)` (line 98) → the DataFrame is **never used**. Training then runs 5 Adam steps on `torch.randn(32, 768)` and `torch.randint(...)` (lines 103-112). No seed is set, so every run produces different weights, and the "accuracy" is not computed at all.
4. Saves `state_dict` to `FL/LocalModels/hospital_N_weights.pt` and computes a real SHA-256 (correct implementation).
5. Uploads to `http://127.0.0.1:{5000+h}/api/v0/add` by POSTing **raw bytes** (`requests.post(url, data=content)`, line 52). Kubo's `/add` requires `multipart/form-data`. Against real Kubo this calls fails 100 % of the time.
6. On failure (i.e. always, with Docker), swallows the exception and invents a CID: `f"QmHospital{h_id}LocalModelWeightsSimulated"` (line 141). These strings are **not valid CIDv0** (37 chars, not a base58-encoded multihash) and are **content-independent**, so two different models get the same "CID". They are then displayed as if they were real.
7. FedAvg: `torch.stack(...).mean(dim=0)` (lines 149-151). **Uniform**, not sample-weighted, contradicting the README §4 formula; datasets are actually equal-sized so the result is mathematically the same — but the claim is still false.
8. Prints clinical differentials from `torch.randn(1, 768)` (line 181) — random logits presented as "confidence".
9. Final banner unconditionally prints `IPFS Decentralized CIDs Verified: Yes` and a **hard-coded** contract address (lines 194-196), regardless of what happened.

**Structural incompatibility:** the pipeline's `MedCPTClassifier` consumes a flat 768-d vector (keys: `feature_extractor.*`, `classifier.*`), while the notebooks' model consumes token IDs (keys: `encoder.*`, `classifier.0.*`, `classifier.3.*`). The two `state_dict`s **cannot be loaded into each other**. Any attempt to combine the "real training" notebooks with this pipeline breaks on `load_state_dict`.

### 3.2 Notebooks

| | `LocalTraining/LocalTrainingNotebook.ipynb` | `FL/GlobalModelTrainingNotebook.ipynb` |
| :--- | :--- | :--- |
| Domain | Real fine-tuning of `ncbi/MedCPT-Query-Encoder` on `symptoms` → 793 classes | Loading 3 checkpoints + averaging |
| Stored outputs | Test Accuracy **81.23 %** (cell 9) — but the 10-epoch training cell (8) has **no output**, so the run is incomplete/unverifiable | Global accuracy **73.84 % / 73.87 % / 73.97 %** per hospital test set |
| Problems | Colab `drive.mount` paths only; duplicates the model class in cells 5 and 6; always saves as `hospital_3_weights.pt` (hard-coded 3, so it *cannot* produce hospital 1/2 artefacts); no seeds; `execution_count` stripped | `NUM_LABELS = 797` (line 2164) contradicts the 793-class ontology (the variable is unused, so it is cosmetic but misleading); Turkish comments; no weighting, no aggregation diagnostics, no evaluation of the *local vs global* trade-off |

**The single most important number in the repo:** the only real measurements available show the federated global model at **≈ 73.9 %**, i.e. **7.3 points worse** than the single local model (**81.23 %**). Uniformly averaging full encoder weights of separately fine-tuned MedCPT models is expected to degrade accuracy; nothing in the codebase addresses this (no FedProx, no layer-selective aggregation, no learning-rate/round schedule). Meanwhile the dashboard and README advertise **89.4 %** — a figure that exists nowhere in the data.

### 3.3 Dataset

- 31 columns per row: `Patient_First_Name`, `Patient_Last_Name`, `Patient_Date_Of_Birth`, `Patient_Email`, `Patient_Phone_Number`, `Patient_Insurance_Provider`, `Billing Amount`, emergency-contact name/phone/email, treating doctor's name, **plus** `symptoms`, `Disease_name`, `label`.
- Rows: 49 613 / 49 614 / 49 613 train + 12 387 / 12 386 / 12 387 test = **62 000 per hospital, 186 000 total**. (README says the *train* files have 62 000 rows each; they actually hold ~49.6 k train + 12.4 k test.)
- Data look synthetic (Faker-style e-mails such as `misty.richards1@hotmail.com`, negative phone numbers, DOB stored as Excel serial `33239`) — but the repository still ships **patient-shaped PII**, duplicated in two directories, in plain text, forever in Git history.
- Label distribution is long-tailed: 737 of 793 classes appear in `train_1`; **68 classes have exactly one example**; the largest class has 350. A single top-1 accuracy figure over this distribution is close to meaningless — macro-F1 / top-5 / per-class recall are all absent.
- Partitions are **IID random splits** (row sets are disjoint: 0 overlap of `(name, DOB, symptoms, label)` tuples across hospitals), so the hardest part of federated learning — non-IID heterogeneity — is never exercised.
- **7.2 % of `test_1` rows have an exact duplicate `symptoms` string in `train_1`** (889 / 12 387), so reported test accuracy is mildly optimistic.
- Labels are duplicated in both `Disease_name` and numeric `label`; training on the full CSV would leak the target.

### 3.4 IPFS layer

Two independent implementations exist:

**`ipfs-hospitals/ipfs_service.py`** — a 163-line Kubo API emulator. Verified live:
- CIDv0 math is **correct**: `sha256(data)` → multihash `0x12 0x20 …` → base58. My independent call returned `QmYjyGJrNaqN9RuKUjW3QKtRZNNe2n2aiHTan9r3Lx1R2L`, matching the server exactly.
- **Not distributed:** all four ports (`5001-5004`) write to the *same* `storage/` folder, so "cat from node 5004 of a file added on 5001" succeeds — physically impossible in a real cluster. It simulates the API, not the network.
- **Routing by suffix:** `path.endswith("/add")` also matches `/api/v0/pin/add`; my probe of `pin/add` stored an **empty file** and returned `QmdfTbBqBPQ7VNxZEYEj14VmRuZBkqFbiwReogJgS1zR1n` (the CID of `""`). Unknown routes such as `swarm/peers` return **HTTP 200 with an empty body** — any "is IPFS healthy?" check passes.
- No `/pin`, `/cat` URI-decoding issues aside, no auth, no pinning semantics, no peer identity derived from keys (peer IDs are hard-coded per port), binds `127.0.0.1` only.

**`ipfs-hospitals/docker-compose.yml`** — correct-looking 4-node Kubo cluster (5001-5004, gateways 8081-8084). Combined with the broken multipart upload in the pipeline, the "real" path has never plausibly been exercised.

**`addToIPFS.py`** — `docker cp` + `docker exec ipfs add`; works only on Linux/macOS hosts with those container names, no error aggregation, prints raw `ipfs add` output (which includes the file path, not just the CID).

### 3.5 Smart contracts

All four contracts compile cleanly with `solc 0.8.28` (optimizer 200 runs, **no errors, no warnings**) and the existing test suite passes: **14/14 in 231 ms**. Measured gas:

| Function | Min | Max | Avg |
| :--- | ---: | ---: | ---: |
| `registerHospital` | 79 132 | 96 244 | 84 840 |
| `submitLocalModel` | 177 817 | 232 481 | ~200 000 |
| `publishGlobalModel` | 88 272 | 129 226 | ~102 000 |
| `ModelUpdateTracker` deployment | — | — | 1 022 944 |

README claims "≈ 120 000 gas per submission" — the real figure is **~1.7-1.9×** that.

**`ModelUpdateTracker.sol`** (the only contract the docs treat as production) — findings verified by executing probe tests:

| Probe | Result |
| :--- | :--- |
| Submit with **empty CID and zero hash** | **Succeeds**, counts toward quorum (`getRoundHospitals(1).length == 3`) — a hospital can satisfy the round with no artefact (`submitLocalModel` has no `require(bytes(cid).length > 0)`, unlike `ModelRegistry2`) |
| Publish global model with **empty CID** | **Succeeds** → round advances with an unusable pointer |
| `ModelUpdateTracker(0)` | **Deploys**; aggregator can `publishGlobalModel` with **0 submissions** and advance the round (`ModelRegistry2` does guard `requiredSubmissions > 0`; this one does not) |
| `setAggregator(address(0))` | **Accepted** → nobody can ever publish again; **no event**, no two-step handover |
| Change quorum later | **Impossible** — there is no `setRequiredSubmissions` (P3/P8 probes failed with "not a function") |
| Revoke a compromised hospital | **Impossible** — no `removeHospital`/`unregister`; 17 public functions, none can revoke |
| `pause()` | Owner can brick submissions indefinitely (no timelock, no multi-sig) |
| Round history | Per-round maps are keyed correctly, but a hospital's previous submission is only reachable via `getLocalModel(round, addr)`; there is no enumeration of submissions per round |

**`ModelRegistry2.sol`** — richer (hospital allowlist, aggregator role, quorum, submitter list) but:
- constructor **auto-whitelists the deployer as a hospital** (verified `isHospital(owner) == true`);
- `publishGlobalModel(round, …)` can be called **repeatedly for the same round** and **silently overwrites** the recorded global CID (verified: `QmGLOBAL-1` → `QmGLOBAL-2-SILENTLY-REPLACED`). That destroys the "immutable audit trail" property the project is built on;
- `removeHospital` does **not** remove the hospital from `roundSubmitters`, so quorum accounting is wrong after a revocation (verified: still 3 after removal);
- no events for `setAggregator`; no `fileHash != 0` checks.

**`ModelRegistry.sol`** — owner-only, single submission per round (duplicate reverts with `Round already exists`, verified), **no way to correct/update a round**, no enumeration. Dead code relative to the pipeline.

**`Lock.sol`** — Hardhat boilerplate, unrelated to the project, still compiled and tested.

**Centralization reality:** `owner == aggregator == deployer` at deployment (verified by `deploy.js` output and the contract). Every "decentralized" guarantee reduces to trusting one EOA that can rotate the aggregator, pause the network, and publish arbitrary CIDs. There is no multi-sig, no governance, no timelock, no dispute window.

### 3.6 Dashboard backend (`server.py`)

141 lines, stdlib `HTTPServer` (**single-threaded**, contrary to README "multi-threaded"), binds `127.0.0.1:3000` (line 136). Live transcripts (Appendix A.6) confirm:

- **`GET /api/status`** returns a **module-level literal** (`fl_state`, line 38): round 2, accuracy 89.4, 186 000 samples, three named hospitals with specific CIDs, `loss: 0.042`. None of it is read from the chain, IPFS or the model.
- **`POST /api/diagnose`** does **token substring matching against disease names**, not symptoms: for every word >2 chars in the query it checks `word in disease_lower` and scores matches, then fabricates a confidence with `(score / total) * 94 + 2` (line 106). Real output:
  - input `"shortness of breath, chest tightness, wheezing, cough"` → **`Open Wound Of The Chest` 49.0 %**, **`Whooping Cough` 49.0 %**.
  - input `"heart failure"` → Heart Failure 33.3 %, Congenital Heart Defect 17.7 %, Heart Attack 17.7 % …
  - input `not json` (empty) → **a canned list**: Acute Bronchospasm 76.4 %, URI 18.2 %, Allergic Rhinitis 5.4 %.
- **`POST /api/advance-round`** increments a counter and adds **+1.8 % accuracy per click**, capped at 98.5. Unauthenticated. 22 curls moved the "system" from round 2 to round 24 at 98.5 % with zero training.
- No authentication, no CSRF/origin check, no CORS policy, no request-size limit (`Content-Length` is trusted), bare `except:` on JSON parsing, global mutable state mutated without a lock, no logging, no graceful shutdown, `import torch` and `import torch.nn` are **never used** (≈2 s startup + a 2 GB dependency for nothing).
- Path traversal is **blocked** (404 on `/../../etc/passwd`) — the one thing `SimpleHTTPRequestHandler` gives you for free.

### 3.7 Dashboard frontend

Design craft is genuinely good: light medical theme, 6 views, canvas charts, responsive layout, `styles.css` 2 350 lines. But it is a **static mockup wired to two DOM fields**:
- `updateBadges()` (app.js:40-57) updates only the version badge and one CID string. The hospital table, ledger, chart curves, participation bars, "14 hospitals", "1.2k updates", "124 hospitals", "1.2M gradients", "99.9 % Integrity" are **hard-coded in `index.html`**.
- The "Blockchain Transaction Ledger" shows fabricated transactions dated **2023-10-24** with placeholder hashes (`0xdeadbeef12345678990…`, `0xabcdef1234567890ab…`) and hospital names that do not exist in the API (`Mary_Center_01`, `Cleveland_C.Hospital_04`).
- "SHAP Value Consensus" is seven `div`s with hard-coded heights — no SHAP anywhere in the repo.
- Chart data are literal coordinate arrays (`points = [{x:0.05,y:0.15}, …]`).
- Failure mode: if `/api/status` is down, the UI silently keeps showing the fake numbers — the most dangerous possible behaviour for a clinical dashboard.
- Accessibility: **0** `aria-*` / `role=` attributes, emoji-as-icons, no `alt` text (no `<img>`), one external Google Fonts dependency (breaks offline/in sandboxed previews).
- XSS surface is small (disease names come from the local mapping via `innerHTML`), but `renderDiagnosis` interpolates server strings without escaping — one bad label edit becomes script execution.

### 3.8 Scripts & docs

- `deploy.js` deploys `ModelUpdateTracker(3)` and writes `deployment_info.json` — it does **not** register hospitals (README §10 Step 3 says it does).
- `add_hospitals.js` hard-codes `0x5FbDB…` (the `ModelUpdateTracker` address) but calls `getContractAt("ModelRegistry2", …)` → wrong ABI for that address.
- `interact.js` is the only end-to-end on-chain demo; it submits placeholder CIDs like `cid-Hospital1-r1` and `0x1111…` hashes.
- `test_ipfs_connection.js` has **unreachable code** (the retrieval block sits after a `return` in the fallback branch); `ipfs-http-client@60` is deprecated in favour of Helia.
- `deployment_info.json` is **committed** even though `Blockchain/.gitignore` ignores it; `.env.example` advertises `0xe7f1725E…` which matches **neither** the committed deployment nor the second Hardhat deploy address used in the docs. 13 places hard-code `0x5FbDB2315678afecb367f032d93F642f64180aa3`.
- `Blockchain/.gitignore` also ignores `IMPROVEMENTS_EXPLAINED.md`, `STEP_BY_STEP_GUIDE.md`, `IPFS_BLOCKCHAIN_INTEGRATION_GUIDE.md`, `requirements.txt` — yet all four are tracked. The ignore file was copied from another project.
- `FL/__pycache__/fl_server.cpython-310.pyc` is committed and references a module (`fl_server.py`, functions `load_vocab`, `train_client`, `fedavg`) that **no longer exists**.
- README is 902 lines of high-quality prose — roughly 30 % of it describes code that is not in the repository (Section 7).

---

## 4. Runtime verification (what was actually executed)

| Check | Command | Result |
| :--- | :--- | :--- |
| Python syntax | `python3 -m compileall` | ✅ clean |
| Solidity compile | `solc 0.8.28` (optimizer 200) | ✅ 5 artifacts, **0 errors, 0 warnings** |
| Contract tests | `npx hardhat test --no-compile` | ✅ **14 passing (231 ms)** |
| Security probes | custom `zz_probe.test.js` (deleted afterwards) | 6 pass / 2 expected-fail → 8 confirmed defects (§3.5) |
| `ModelRegistry2` probes | custom test | ✅ 4 confirmed defects (§3.5) |
| IPFS emulator | 4 nodes on 5001-5004 | ✅ correct CIDv0 math · ❌ shared storage, `pin/add` hijacked by `/add`, unknown routes return 200 |
| Dashboard API | `curl` against running server | ✅ endpoints respond · ❌ data fabricated, diagnosis nonsense, round counter unbounded |
| Dashboard UI | served on `0.0.0.0:3000` | ✅ renders (preview available) |
| Full pipeline | **not run** | requires `torch` (~2 GB) *and* is meaningless without real training data path |

> Note: `npx hardhat test` cannot download the solc binary in a restricted network (`HH502`); the contracts were compiled with the npm `solc@0.8.28` package and the artifacts fed to Hardhat. This is an environment artefact, not a repo defect — but it also means **CI has never compiled these contracts**, since there is no CI.

---

## 5. Findings register

Severity: **C**ritical (invalidates the core claim / unsafe) · **H**igh · **M**edium · **L**ow.

### Critical

| ID | Finding | Evidence |
| :--- | :--- | :--- |
| **C-01** | **No federated learning actually happens.** Local "training" uses random tensors; the CSV is read and discarded; averaging three independently initialised random models yields a random model. No metric is computed. | `run_federated_pipeline.py:98,103-112,149-151` |
| **C-02** | **Fabricated metrics presented as measurements.** Dashboard shows 89.4 % accuracy; the only real number in the repo is 73.9 %. `/api/advance-round` adds +1.8 %/click up to 98.5 %. | `server.py:38,123-124`; notebook outputs; `README.md:323-341,527` |
| **C-03** | **Patient-shaped PII in Git.** Names, DOB, e-mail, phone, insurance, billing, emergency contacts committed as plain CSV, duplicated in `FL/` and `LocalTraining/`, permanent in history — in a project whose thesis is HIPAA/GDPR compliance. | `FL/Train&TestCSVs/*`, `LocalTraining/Train&TestCSVs/*` |
| **C-04** | **`/api/diagnose` produces clinically wrong output with confident percentages.** It substring-matches disease *names*, so dyspnoea returns "Open Wound Of The Chest 49 %". No model, no disclaimer, no uncertainty. | `server.py:89-114`; live transcript §A.6 |
| **C-05** | **Smart contract cannot distinguish a real submission from an empty one.** Empty CID + zero hash is accepted, counts toward quorum, and an empty global CID can be published. | `ModelUpdateTracker.sol:108-133,135-160`; probe P1 |

### High

| ID | Finding | Evidence |
| :--- | :--- | :--- |
| **H-01** | **The pipeline never touches the blockchain.** No `web3`/`ethers` in Python; `deployment_info.json` is only printed; the "on-chain audit trail" is never written. | `run_federated_pipeline.py:66-70,88-89`; `grep web3` → 0 hits |
| **H-02** | **IPFS integration is broken against real Kubo** (raw body instead of multipart) and **silently degrades to fake, content-independent CIDs** that are not valid CIDs but are displayed as such. | `run_federated_pipeline.py:47-55,141-143` |
| **H-03** | **`requiredSubmissions = 0` is accepted**, allowing the aggregator to "complete" rounds with zero data. | `ModelUpdateTracker.sol:74-80`; probe P2 |
| **H-04** | **Total admin centralization with no recovery path:** owner = aggregator = deployer; `setAggregator` accepts `address(0)` (permanent DoS) and emits no event; no hospital revocation; `pause()` unbounded; quorum immutable. | `ModelUpdateTracker.sol:74-80,95-101`; probes P4,P5,P7 |
| **H-05** | **Unauthenticated state-changing API on a single-threaded server.** Anyone can advance rounds; no authz, CSRF, TLS, CORS, or input limits. | `server.py:11,118-128,136` |
| **H-06** | **Model artefacts are mutually incompatible** (`encoder.*` vs `feature_extractor.*`); the notebook weights can never be loaded by the pipeline, so the two halves of the "FL system" cannot be combined. | `LocalTrainingNotebook.ipynb` cell 5/9 vs `run_federated_pipeline.py:29-38` |
| **H-07** | **`ModelRegistry2` breaks immutability:** global CID for a round can be silently overwritten; removed hospitals remain counted in quorum. | `ModelRegistry2.sol:139-152`; probe |
| **H-08** | **Federated averaging degrades the model** (81.2 % local → 73.9 % global) and nothing in the design addresses it. | notebook outputs |

### Medium

| ID | Finding | Evidence |
| :--- | :--- | :--- |
| **M-01** | Dashboard is a mockup: only 2 DOM fields are data-driven; hospitals, ledger, charts, SHAP, counts are literals (incl. 2023 timestamps and `0xdeadbeef…`). | `app.js:40-57`; `index.html:119-126,274,409-417,595-606,768-800` |
| **M-02** | Three competing registry contracts + boilerplate `Lock.sol`; `add_hospitals.js` uses the wrong ABI/address; `.env.example` disagrees with `deployment_info.json`. | `contracts/`, `scripts/add_hospitals.js:12-13`, `.env.example` |
| **M-03** | **No CI, no LICENSE, no Python/frontend tests**, `package.json` `test` script still the default `echo "Error: no test specified"`. | repo root |
| **M-04** | Repository hygiene: 67 MB of duplicated CSVs and notebooks; stale committed `.pyc`; docs tracked despite being gitignored; `deployment_info.json` both tracked and ignored; deploy screenshots committed. | `.gitignore`, `FL/__pycache__/`, `Blockchain/DeploymentPics/` |
| **M-05** | Reproducibility: no seeds, unpinned deps, Colab-only paths (`/content/drive/MyDrive/MedXChAIn`), Windows-flavoured emulator identity (`amd64/windows`), `e:/Fedacre/` in the README. | notebooks, `ipfs_service.py:70`, `README.md:137` |
| **M-06** | **Privacy guarantees are asserted, not implemented:** no DP-SGD/clipping/noise, no secure aggregation, no gradient encryption, no access control on IPFS; weights travel in clear text. | `README.md:341-348` vs codebase (0 hits for `noise`, `clip`, `opacus`) |
| **M-07** | Backend performance/robustness: single-threaded `HTTPServer`, unused `torch` import, unbounded `Content-Length`, bare `except`, global mutable state. | `server.py:11,79,83,136` |
| **M-08** | Data quality: 737/793 classes present, 68 singleton classes, long-tail → top-1 accuracy misleading; **7.2 %** exact symptom leakage train→test; IID splits only. | measured §3.3 |
| **M-09** | No error handling in the pipeline; failure is the normal path; success banner is unconditional. | `run_federated_pipeline.py:136-146,192-196` |
| **M-10** | Documentation ↔ ABI mismatch: README documents a `ModelUpdate` struct, `submitUpdate(...)`, `RoundCompleted`, `getRoundSubmissions` — none exist in `ModelUpdateTracker.sol`. | `README.md:362-404,814-846` |

### Low

| ID | Finding |
| :--- | :--- |
| **L-01** | Zero `aria-*`/`role=` attributes, emoji-only iconography, external Google Fonts (breaks offline). |
| **L-02** | Dead code: unreachable block in `test_ipfs_connection.js`, unused imports in `server.py` (`parse_qs`, `torch`, `nn`). |
| **L-03** | 13 hard-coded contract addresses; no config module; no `.env` loading anywhere (`python-dotenv` absent). |
| **L-04** | No logging discipline (prints + emoji as the only observability); no structured audit log. |
| **L-05** | `ipfs-http-client` deprecated; `ipfs_service.py` emulator can mask genuine integration failures. |
| **L-06** | Notebooks shipped with outputs but stripped `execution_count`, and with a missing output for the main training cell — provenance is unverifiable. |

---

## 6. Documentation drift matrix

| README claim | Reality |
| :--- | :--- |
| "Only encrypted model parameter deltas leave the hospital" | Raw `.pt` weights; no encryption anywhere |
| "DP-SGD with gradient clipping + Gaussian noise" | Not implemented (no such code, no `opacus`) |
| "FedAvg weighted by sample count `n_k`" | Uniform `mean(dim=0)`; snippet in README does not match the file |
| "Pipeline dispatches on-chain transactions via JSON-RPC" | No blockchain client at all in Python |
| "deployment_info.json stores address **and full ABI**" | 7-line JSON: address, owner, requiredSubmissions, network, timestamp |
| "deploy.js … registers the 3 hospital accounts" | It only deploys |
| "Contract ≈120 000 gas per submission" | 177 817–232 481 (avg ≈200 k) |
| "ModelUpdateTracker has `submitUpdate`, `RoundCompleted`, `getRoundSubmissions`" | Those symbols do not exist |
| "ModelRegistry2 provides penalty scoring and Byzantine fault tolerance" | No penalty, no BFT, no reputation |
| "Multi-threaded HTTP server" | `HTTPServer`, single-threaded |
| "793-class ontology: index 0 = Cardiac Arrhythmia, 14 = Hypertension, 42 = Acute Bronchospasm, 89 = T2DM, 105 = Sleep Apnea, 240 = Migraine" | Actual: 0 = abdominal aortic aneurysm, 14 = acute glaucoma, 42 = anemia due to malignancy, 89 = brain cancer, 105 = cataract, 240 = esophageal cancer. (Cardiac arrhythmia = 52; migraine = 465; hypertension = 360/361/362/424/453) |
| "Model: 7.2 M parameters" | `MedCPTClassifier` = **800 537** params; MedCPT encoder ≈110 M |
| "SHAP value consensus" | No SHAP; bars are hard-coded `div` heights |
| "train_1..3 hold 62 000 records each, N = 186 000" | 49 613 train + 12 387 test = 62 000 per hospital (186 000 incl. test); pipeline reads 500 rows and ignores them |
| "89.4 % converged accuracy" | Only measured value: 73.8–74.0 % (global), 81.23 % (single local) |
| "IPFS CIDs verified: Yes" | Printed unconditionally; with Docker absent the CIDs are fabricated strings |
| "Dashboard live-syncs blockchain ledger" | Static HTML table dated 2023-10-24 |

---

## 7. Privacy, safety and legal

1. **PHI-shaped data in a public repo.** Even if synthetic, the file format trains contributors to handle real PHI carelessly; if any row is real, this is a HIPAA/GDPR incident. Recommendation: keep only schema + generator upstream, distribute data out-of-band (encrypted bucket / LFS with access control), and scrub history (`git filter-repo`) before any public release.
2. **No privacy mechanism despite the title.** Federated learning alone is not privacy: raw weights are invertible (deep leakage from gradients), and here weights are additionally published to IPFS with no access control. Minimum viable: DP-SGD (per-example clipping + calibrated noise, `opacus`), secure aggregation, and encrypted IPFS payloads (e.g. `age`/AES-GCM with per-round keys).
3. **Clinical decision support without a disclaimer.** The diagnosis endpoint returns "confidence" percentages from a substring match. Any UI screenshot of it is a liability. Add a persistent "research prototype — not for clinical use" banner and gate the endpoint behind a demo flag.
4. **Audit-trail integrity is weaker than advertised.** Between empty CIDs (C-05) and silent overwrite (H-07), an on-chain "record" can be produced for an artefact that does not exist, or replaced after the fact.
5. **License ambiguity.** README badge says MIT, repository has no `LICENSE`. Add one, and a `DATA_LICENSE`/provenance note for the CSVs.

---

## 8. Performance & scalability observations

- **Per-round traffic:** realistic deployment would move the full MedCPT encoder (≈110 M params ≈ 440 MB fp32) per hospital per round — 1.3 GB/round for 3 hospitals, over IPFS HTTP, at 10 s timeouts. The pipeline's 0.8 M-param toy (3.2 MB) hides this entirely. Real systems aggregate adapters/LoRA or use compression + quantization.
- **Gas:** ~200 k per submission × 3 hospitals + ~100 k publish ≈ 0.7 M gas/round. Fine on a local chain, ~0.02 ETH/round on mainnet at 20 gwei — economical only because nothing is actually stored (CID strings + hash).
- **Dashboard:** single-threaded server; the `torch` import adds seconds of startup and a 2 GB dependency for zero functionality; charts recompute on every tab switch.
- **Data loading:** `read_csv` without `usecols`/`dtype` on 18 MB × 31-column files; the pipeline loads 4.6-18 MB files to use none of the content.
- **Chain writes are not batched** (no Merkle root per round) — a Merkle-root-per-round design would cut cost by ~10× and strengthen the audit trail.

---

## 9. What is genuinely good

- **Contract engineering basics are sound:** clean compile with zero warnings, sensible modifiers, per-round replay protection (`hasSubmitted`), role separation in `ModelRegistry2`, real unit tests for the lifecycle, correct use of `bytes32` for hashes.
- **CIDv0 implementation is correct** — the base58/multihash math is right (verified against an independent computation).
- **Dashboard craft:** coherent design system, 6 well-structured views, responsive layout, no framework bloat.
- **Documentation ambition:** the README explains the architecture, the math and the runbook better than most student projects; it is the *claims*, not the writing, that need fixing.
- **Clear module boundaries** (`FL/`, `Blockchain/`, `ipfs-hospitals/`, `UI-DashBoard/`) make the project easy to fix incrementally.

---

## 10. Prioritized remediation plan

### P0 — make it honest and safe (1-2 days)

1. **Stop lying in the UI and README.** Gate fabricated metrics behind a `DEMO_MODE` flag; replace the 89.4 % with either a measured value or "—". Add a "research prototype, not for clinical use" banner on the diagnosis view.
2. **Remove the diagnosis endpoint or make it real.** Until a real model is wired, return HTTP 501 or run the actual classifier. Never return substring-match percentages.
3. **Strip PII columns from committed data** (`Patient_*`, `Doctor_*`, `Billing`, emergency contacts) and move datasets out of Git (LFS/bucket); add `git filter-repo` scrub before publishing.
4. **Harden the contract** (`ModelUpdateTracker.sol`):
   ```solidity
   constructor(uint256 _requiredSubmissions) {
       require(_requiredSubmissions > 0, "quorum=0");
       ...
   }
   function submitLocalModel(string calldata cid, bytes32 fileHash) external ... {
       require(bytes(cid).length > 0, "empty cid");
       require(fileHash != bytes32(0), "empty hash");
       ...
   }
   function setAggregator(address a) external onlyOwner {
       require(a != address(0), "zero addr");
       emit AggregatorChanged(aggregator, a);
       aggregator = a;
   }
   function setRequiredSubmissions(uint256 n) external onlyOwner { require(n > 0); ... emit }
   function removeHospital(address h) external onlyOwner { ... emit }
   function publishGlobalModel(...) external onlyAggregator {
       require(bytes(globalModels[currentRound].cid).length == 0, "already published");
       ...
   }
   ```
   Add `Ownable2Step`, a `whenNotPaused` guard on `registerHospital`, and tests for every new revert.
5. **Fix the IPFS client:** multipart upload with `pin=true`, verify the returned CID against the local SHA-256, raise on mismatch, and **never invent a CID** — surface the failure instead.

### P1 — close the loop (1-2 weeks)

6. **Actually submit to the chain from Python** (`web3.py`): register → `submitLocalModel(cid, sha256)` → wait for receipts → aggregator `publishGlobalModel`; store tx hashes in a round manifest. Delete the hard-coded address; read it from `deployment_info.json`/env.
7. **Reconnect the dashboard to reality:** read the contract (`currentRound`, `getRoundModel`, events) and IPFS CIDs server-side, expose them via `/api/status`, and render hospital/ledger tables from JSON instead of literals. If a dependency is down, show an error state — never cached fake data.
8. **Rebuild the training path:** real `symptoms → label` training (the notebook code is the starting point), one checkpoint format shared by pipeline and notebooks (`encoder + head`), fixed seeds, and a saved `metrics.json` per round (macro-F1, top-5, per-class recall).
9. **Server hygiene:** `ThreadingHTTPServer`, auth token for POSTs, `Content-Length` cap, JSON validation, structured logging, remove the unused `torch` import, bind configurable host/port.
10. **Repo hygiene:** delete `LocalTraining/` duplicate tree (or symlink), drop `FL/__pycache__`, remove `Lock.sol`/`Lock.js`, unify the three registry contracts into one, add `LICENSE`, fix both `.gitignore` files, remove the 2023/fake ledger rows.

### P2 — make it credible (2-8 weeks)

11. **Differential privacy** (Opacus DP-SGD with a stated ε,δ) or **remove the DP claims**; add secure aggregation and encrypted IPFS blobs.
12. **Address non-IID:** Dirichlet label-skew partitions, FedProx/SCAFFOLD baselines, and an honest local-vs-global accuracy table — the current 81.2 % → 73.9 % regression must be explained or fixed.
13. **Byzantine robustness:** reputation/stake, hash-verified model fetching, and a "reject update" path (currently impossible on-chain).
14. **CI:** GitHub Actions with `hardhat test`, `solc` compile, `ruff`, `mypy`, `pytest` (API tests with `pytest-httpx`), `solhint`, and a dependency audit.
15. **Observability & ops:** Prometheus metrics, round manifests, a Dockerfile for the app + compose profile for the full stack, and a single `make dev` entrypoint instead of six manual terminals.

---

## Appendix A — Reproducible command log

**A.1 Compilation (network-restricted workaround)**
```bash
npm install --no-save solc@0.8.28
# custom script compiled contracts/ with optimizer(200) and emitted
# Hardhat-format artifacts to Blockchain/artifacts/contracts/**.json
# → 5 artifacts, 0 errors, 0 warnings
```

**A.2 Test suite**
```bash
npx hardhat test --no-compile     # → 14 passing (231ms)
```

**A.3 Contract probes (temporary, deleted after running)**
```text
P1 empty CID accepted; quorum = 3; global published with empty cid, round → 2
P2 ModelUpdateTracker(0) deploys; publish with 0 submissions, round → 2
P3 setRequiredSubmissions does not exist (TypeError)
P4 aggregator → 0x000…000 (no event)
P5 functions: … no removeHospital / unregister
P6 per-round overwrite works; totalSubmissions increments to 2
P7 pause blocks submissions
ModelRegistry2: deployer auto-whitelisted = true
ModelRegistry2: round1 cid QmGLOBAL-1 → QmGLOBAL-2-SILENTLY-REPLACED
ModelRegistry2: submitters after removal = 3
ModelRegistry: blocks re-submission same round = true
```

**A.4 IPFS emulator**
```text
expected cid: QmYjyGJrNaqN9RuKUjW3QKtRZNNe2n2aiHTan9r3Lx1R2L (len 46)
add → same hash (✅ math correct)
cat from 5004 of file added on 5001 → b'hello model weights'  (❌ shared storage)
POST /api/v0/pin/add?arg=…  → stored an empty file, returned QmdfTbBq… (❌ /add suffix match)
POST /api/v0/swarm/peers    → HTTP 200, empty body (❌)
```

**A.5 Gas report (from `hardhat test`)**
```text
registerHospital   79 132 – 96 244   avg 84 840
submitLocalModel  177 817 – 232 481
publishGlobalModel 88 272 – 129 226
ModelUpdateTracker deployment ≈ 1 022 944 (3.4 % of block gas limit)
```

**A.6 Dashboard API transcript**
```text
GET /api/status → {"currentRound":2,"globalAccuracy":89.4,...,"loss":0.042,...}   (static literal)

POST /api/diagnose {"symptoms":"shortness of breath, chest tightness, wheezing, cough"}
 → {"results":[{"disease":"Open Wound Of The Chest","confidence":49.0},
               {"disease":"Whooping Cough","confidence":49.0}]}

POST /api/diagnose {"symptoms":"heart failure"}
 → Heart Failure 33.3 | Congenital Heart Defect 17.7 | Heart Attack 17.7 | Heart Block 17.7 | Heart Contusion 17.7

POST /api/diagnose (body "not json")
 → Acute Bronchospasm 76.4 | Upper Respiratory Tract Infection 18.2 | Seasonal Allergic Rhinitis 5.4

POST /api/advance-round ×22 → round 24, globalAccuracy 98.5  (no auth, no training)
GET /../../../../etc/passwd → 404 (path traversal correctly blocked)
GET /api/labels → 22 925 bytes
GET /           → 200
```

**A.7 Dataset measurements**
```text
train_1 49 613 rows | train_2 49 614 | train_3 49 613
test_1  12 387 rows | test_2  12 386 | test_3  12 387
columns 31 · labels 0-791 · 737 classes in train_1 · 68 singleton classes · max class 350
hospital partitions mutually disjoint (0 exact-row overlap)
test_1 symptom strings duplicated from train_1: 889 / 12 387 (7.2 %)
```

**A.8 Notebook outputs (as shipped)**
```text
LocalTraining … cell 9:  Test Accuracy: 81.23 %
FL/Global… cell 4:  Hospital 1 → 73.84 % | Hospital 2 → 73.87 % | Hospital 3 → 73.97 %
(cell 8, the 10-epoch training loop, has no stored output)
```

---

## Appendix B — Artefacts produced with this audit

| File | Purpose |
| :--- | :--- |
| `TECHNICAL_AUDIT.md` | This document — evidence, findings register, claim-vs-reality matrix |
| `ENHANCEMENT_ROADMAP.md` | What to build: 12 quick wins, 11 tracks, 18 new features, SLOs, first 10 PRs |
| `AGENT_BRIEF.md` | Working contract for the implementing agent: rules, gates, landmines, definition of done |
| `agent_backlog.yaml` | Machine-readable backlog: 18 tasks with acceptance criteria, verify commands, stop conditions |
| `MEDXCHAIN_AUDIT_AND_ROADMAP.pdf` | The three documents above as one navigable PDF (regenerate with `tools/md_to_pdf.py`) |
| `tools/md_to_pdf.py` | Reproducible Markdown → PDF builder (reportlab) |

Temporary probe tests (`Blockchain/test/zz_probe*.test.js`) and the `solc` compile helper used during the audit were removed; `Blockchain/node_modules/` and `Blockchain/artifacts/` are gitignored build output.
