# 📊 Data Provenance & Dataset Card

## 1. Overview
The datasets stored under `FL/Train&TestCSVs/` (partitioned across hospital nodes 1, 2, and 3) were generated to evaluate multi-site federated learning algorithms on biomedical natural language queries and symptom texts.

## 2. Partition Structure & Row Counts

| File | Partition | Purpose | Row Count |
| :--- | :--- | :--- | :--- |
| `train_1.csv` | Hospital 1 | Local Training | 49,613 rows |
| `test_1.csv` | Hospital 1 | Local Validation/Test | 12,387 rows |
| `train_2.csv` | Hospital 2 | Local Training | 49,614 rows |
| `test_2.csv` | Hospital 2 | Local Validation/Test | 12,386 rows |
| `train_3.csv` | Hospital 3 | Local Training | 49,613 rows |
| `test_3.csv` | Hospital 3 | Local Validation/Test | 12,387 rows |
| **Total** | | | **186,000 rows** |

- **Hospital 1 Total**: 62,000 records
- **Hospital 2 Total**: 62,000 records
- **Hospital 3 Total**: 62,000 records

## 3. Class Distribution & Long-Tail Ontology
- **Total Disease Classes**: 793 classes defined in `FL/label_mapping.json`.
- **Observed Classes in Split 1**: 737 classes present.
- **Singleton Classes**: 68 classes contain exactly 1 training example.
- **Recommended Evaluation Metrics**: Because of class imbalance and the long tail, models must be evaluated using **Macro-F1**, **Top-5 Accuracy**, and **Per-Class Recall**, rather than relying solely on Top-1 Accuracy.

## 4. Privacy & Demographic PII Removal (C-03 Compliance)
- All 28 synthetic demographic and patient-identifying columns (`Patient_First_Name`, `Patient_Last_Name`, `Patient_Email`, `Patient_Phone_Number`, `Patient_Date_Of_Birth`, `Patient_Insurance_Provider`, `Billing Amount`, emergency contacts, doctor identifiers) were permanently stripped from committed CSVs in accordance with audit finding C-03.
- Shipped datasets contain strictly: `Disease_name`, `symptoms`, and `label`.
- Redundant 67 MB duplicate blobs (`LocalTraining/Train&TestCSVs/`) were eliminated, halving repository storage requirements.
- **Security Rule**: Machine learning pipelines load **only** non-identifying clinical features.
- **HIPAA Safeguards**: No Protected Health Information (PHI) or demographic proxies exist in committed datasets, across IPFS blocks, or within on-chain transaction data.
