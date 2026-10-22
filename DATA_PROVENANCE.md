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

## 4. Privacy & Synthetic Data Notice
- The demographic columns (`Patient_First_Name`, `Patient_Last_Name`, `Patient_Email`, `Patient_Phone_Number`, `Patient_Date_Of_Birth`, `Patient_Insurance_Provider`, `Billing Amount`, emergency contacts) are synthetic benchmark representations (Faker-generated format).
- **Security Rule**: Machine learning pipelines must strictly exclude demographic and patient-identifying columns, loading **only** clinical features: `symptoms`, `label`, and `Disease_name`.
- **HIPAA Safeguards**: No real Protected Health Information (PHI) is transmitted across network sockets or written to the blockchain ledger.
