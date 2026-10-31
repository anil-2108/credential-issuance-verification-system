# Credential Issuance, Revocation & Verification - Synthetic Data Project

Pure-Python (3.9+, **standard library only**) generator, validator and reproducibility check.

## Quick start

```bash
# Full baseline: 20,000 learners / 1,000 courses / 10,000 credentials / 5,000 verification requests
python generate_dataset.py --seed 20261022 --out data_full

# Starter dataset (same generator, parameterised scale) - already included in data_starter/
python generate_dataset.py --seed 20261022 --scale 0.05 --out data_starter

# Validate (Step 8). --check-sql also loads seed.sql into SQLite with FK enforcement
python validate_dataset.py --data data_full --check-sql

# Reproducibility (Step 10): regenerate twice, compare row counts + SHA-256
python check_reproducibility.py            # full volume
python check_reproducibility.py --scale 0.05
```

Volumes can be overridden individually: `--learners --courses --credentials --verifications`.
Snapshot date: `--as-of 2026-10-22`. Formats: `--formats csv,json,sql`.

## Files

| File | Purpose |
|---|---|
| `credential_logic.py` | Shared business logic: rule evaluation, canonical payload, SHA-256 hash, HMAC signature, lifecycle replay, **verification decision** (used by generator *and* validator) |
| `schema.py` | Single source of truth: data dictionary, enums, PK/FK, cardinalities |
| `generate_dataset.py` | Generator (Steps 1-7, 9) |
| `validate_dataset.py` | Validation (Step 8) -> `validation_summary.json/.md` |
| `check_reproducibility.py` | Step 10 -> `reproducibility_report.json` |
| `data_starter/` | Ready-made starter dataset (scale 0.05) |
| `validation_summary_full.md`, `reproducibility_report_full.json`, `ground_truth_summary_full.json` | Results of the full-volume run |

Each generated dataset folder contains: 12 input CSVs (+ `json/`), `seed.sql`, **`ground_truth.csv/.json`** (separate),
`data_dictionary.csv/.md`, `schema.json`, `source_manifest.json` (command, seed, parameters, per-file rows + SHA-256),
`checksums.sha256`, `validation_summary.*`.

## Entities, keys and IDs

| Entity | File | PK | Format |
|---|---|---|---|
| Learner | learners.csv | learner_id | `LRN-000001` |
| Course | courses.csv | course_id | `CRS-0001` |
| CredentialRule | credential_rules.csv | rule_id | `RUL-0001` (versioned per course) |
| CompletionRecord | completion_records.csv | completion_id | `CMP-<learner-id>-<course-id>` e.g. `CMP-LRN-000001-CRS-0040` |
| Credential | credentials.csv | credential_id | `CRD-2026-000001` |
| Issuer | issuers.csv | issuer_id | `ISS-001` |
| VerificationRequest | verification_requests.csv | verification_id | `VER-2026-000001` |
| Revocation | revocations.csv | revocation_id | `REV-<credential-id>-01` e.g. `REV-CRD-2026-000123-01` |
| AuditEvent | audit_events.csv | audit_event_id | `AUD-00000001` |
| *Supporting:* Actor, Assessment, course_issuer_history (bridge) | | | `ACT-0001`, `AST-0000001`, `CIH-000001` |

Cardinality: Learner N:M Course via **CompletionRecord** (bridge, unique pair); Course N:M Issuer over time via
**course_issuer_history** (effective-dated, models issuer changes); Course 1:N CredentialRule (effective-dated versions);
CompletionRecord 1:N Assessment and 1:0..1 Credential; Credential 1:N Revocation and 1:N VerificationRequest (optional);
AuditEvent is a polymorphic append-only log. Full field-level dictionary: `data_dictionary.md`.

## How outcomes are derived (not randomly assigned)

1. Hidden learner ability + course difficulty drive **assessment scores, attendance and progress**.
2. `evaluate_rule()` compares those facts with the CredentialRule in force at enrolment ->
   `requirements_met` and status `COMPLETED` / `FAILED` (with `failure_reasons`). Boundary cases (score exactly at / 1 point below the threshold) are generated on purpose.
3. A credential is issued **only** for `COMPLETED` completions, on/after `completed_at`, by the issuer that owns the course on that date
   (issuer successions/transfers handled via `course_issuer_history`). Only a subset of eligible learners is issued (not everyone claims).
4. Payload = canonical JSON -> `payload_hash = SHA-256` -> `signature = HMAC-SHA256(issuer key, hash)`.
   *Demo keys are derived from the seed so the verifier is reproducible; they protect nothing real. In production use asymmetric signatures (e.g. Ed25519).*
5. Revocations (`-01`), reversals and re-revocations (`-02`) are **events**; `credentials.status` is a snapshot recomputed by replaying them. History is never overwritten.
6. Audit log is append-only and **hash-chained** (`prev_event_hash` -> `event_hash`).

### Verification decision order (`credential_logic.VerificationContext.verify`)
`NOT_FOUND -> AMBIGUOUS_ID -> HASH_MISMATCH -> INSUFFICIENT_IDENTITY -> IDENTITY_MISMATCH -> REVOKED -> EXPIRED -> VALID`

Identity = **credential ID + date of birth + email hash**. The claimed name is informational and never changes the result
(validated by perturbing the name). Same-name impostors and name-only requests are rejected. Revocation/expiry are evaluated **as of the request time**.

## Labelled anomalies (injected after valid baseline) -> `ground_truth.csv`

| issue_type | Count (full) | What is wrong |
|---|---|---|
| `CREDENTIAL_ISSUED_BEFORE_COMPLETION` | 100 | 70% issued days before `completed_at`; 30% issued although the completion never met the rule (`variant` column) |
| `DUPLICATE_CREDENTIAL_ID` | 40 | A second, different credential row re-uses an existing ID (`row_ref` = its completion_id) |
| `REVOKED_CREDENTIAL_VERIFIES_AS_ACTIVE` | 25 | Request after revocation, recorded `VALID`, expected `REVOKED` |
| `ALTERED_PAYLOAD_HASH_NOT_DETECTED` | 25 | Tampered presented hash, recorded `VALID`, expected `HASH_MISMATCH` |

`ground_truth.csv` also holds the **expected result for every verification request** (`expected_value` vs `recorded_value`, `scenario`).
It is a separate file; none of its columns exist in the input tables (checked by the validator). Use it only to score detectors.

## Validation (72 checks, all PASS on the full dataset)

PK uniqueness, ID formats, required fields, enums, all FKs (+ polymorphic audit refs), date ordering (including enrolment vs
course/rule windows), arithmetic reconciliation (score = mean of assessments, status re-derived from rules, hash, signature, expiry),
lifecycle state-machine replay, audit hash chain, revocation-status currency, verification reproducibility, name-independence,
ground-truth separation, optional SQL load. **Every violation must be explained by a labelled anomaly and every labelled anomaly must be detected**;
otherwise the run fails (exit code 1). The duplicate-ID anomaly is why `credentials` has no UNIQUE constraint in `seed.sql` (index only; logical PK enforced by validation).

## Reproducibility & provenance

* Single `random.Random(seed)` (default **20261022**), no wall-clock values, no set-ordering dependence -> identical bytes on every run
  (`reproducibility_report_full.json`: all 27 files identical across two runs).
* **No external data.** Names come from invented pools, emails use reserved `example.org`, no real personal data, no scraped or licensed sources
  (`source_manifest.json -> external_data_used: []`).

## Known simplifications

* Timestamps are UTC; completion dates are day-level.
* Credential-level tampering at rest (stored hash edited) is supported by the verifier but not injected; only the required presented-hash anomaly is.
* `verification_requests.result` is the platform's recorded outcome; the correct outcome lives only in `ground_truth`.
