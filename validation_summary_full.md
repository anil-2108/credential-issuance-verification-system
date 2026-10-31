# Validation summary - PASS

Seed `20261022`, as-of `2026-10-22`. 72/72 checks passed.

| status | category | check | found | explained by labelled anomaly | unexplained | labelled but missed |
|---|---|---|---|---|---|---|
| PASS | schema | CSV columns equal data dictionary | 0 | 0 | 0 | 0 |
| PASS | ids | ID formats (CRD-YYYY-NNNNNN, LRN-NNNNNN, CMP-<lrn>-<crs>, VER-YYYY-NNNNNN, REV-<crd>-NN ...) | 0 | 0 | 0 | 0 |
| PASS | enums | Allowed enum values | 0 | 0 | 0 | 0 |
| PASS | schema | Required fields populated | 0 | 0 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: actors.actor_id | 0 | 0 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: issuers.issuer_id | 0 | 0 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: learners.learner_id | 0 | 0 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: courses.course_id | 0 | 0 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: course_issuer_history.history_id | 0 | 0 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: credential_rules.rule_id | 0 | 0 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: completion_records.completion_id | 0 | 0 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: assessments.assessment_id | 0 | 0 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: credentials.credential_id | 40 | 40 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: revocations.revocation_id | 0 | 0 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: verification_requests.verification_id | 0 | 0 | 0 | 0 |
| PASS | primary_keys | PK uniqueness: audit_events.audit_event_id | 0 | 0 | 0 | 0 |
| PASS | duplicates | No duplicate (learner, course) completions | 0 | 0 | 0 | 0 |
| PASS | duplicates | Learner emails unique | 0 | 0 | 0 | 0 |
| PASS | duplicates | 1 completion -> at most 1 credential | 0 | 0 | 0 | 0 |
| PASS | duplicates | Duplicate learner names exist (by design) and emails differ | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK issuers.predecessor_issuer_id -> issuers.issuer_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK courses.instructor_id -> actors.actor_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK courses.issuer_id -> issuers.issuer_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK course_issuer_history.course_id -> courses.course_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK course_issuer_history.issuer_id -> issuers.issuer_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK credential_rules.course_id -> courses.course_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK completion_records.learner_id -> learners.learner_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK completion_records.course_id -> courses.course_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK completion_records.rule_id -> credential_rules.rule_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK assessments.completion_id -> completion_records.completion_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK credentials.completion_id -> completion_records.completion_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK credentials.learner_id -> learners.learner_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK credentials.course_id -> courses.course_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK credentials.rule_id -> credential_rules.rule_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK credentials.issuer_id -> issuers.issuer_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK revocations.credential_id -> credentials.credential_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | FK revocations.revoked_by_actor_id -> actors.actor_id | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | verification_requests.credential_id unknown only for UNKNOWN_ID scenario | 153 | 153 | 0 | 0 |
| PASS | foreign_keys | audit_events polymorphic entity reference valid | 0 | 0 | 0 | 0 |
| PASS | foreign_keys | audit_events STAFF/SYSTEM/LEARNER actor references valid | 0 | 0 | 0 | 0 |
| PASS | date_ordering | learner.created_at <= enrolled_at | 0 | 0 | 0 | 0 |
| PASS | date_ordering | enrolled_at <= closed_at; completed_at == closed_at when COMPLETED | 0 | 0 | 0 | 0 |
| PASS | date_ordering | assessment taken_at within enrolment window | 0 | 0 | 0 | 0 |
| PASS | date_ordering | Enrolment inside course effective window (no enrolments after retirement) | 0 | 0 | 0 | 0 |
| PASS | date_ordering | rule effective_from <= effective_to; enrolment inside rule window | 0 | 0 | 0 | 0 |
| PASS | date_ordering | Credential issued only AFTER a COMPLETED completion (issued_at >= completed_at) | 100 | 100 | 0 | 0 |
| PASS | date_ordering | issued_at <= expires_at | 0 | 0 | 0 | 0 |
| PASS | date_ordering | Issuer history periods contiguous and non-overlapping | 0 | 0 | 0 | 0 |
| PASS | lifecycle | Credential issuer = course issuer in force on issue date (issuer changes respected) | 0 | 0 | 0 | 0 |
| PASS | date_ordering | revoked_at > credential.issued_at | 0 | 0 | 0 | 0 |
| PASS | date_ordering | verification requested_at >= issued_at (known IDs) | 0 | 0 | 0 | 0 |
| PASS | reconciliation | assessments_taken = count(assessments); final_score = round(mean(scores),2) | 0 | 0 | 0 | 0 |
| PASS | reconciliation | Completion status/requirements_met re-derived from CredentialRule | 0 | 0 | 0 | 0 |
| PASS | reconciliation | Credential learner/course/rule agree with its completion | 0 | 0 | 0 | 0 |
| PASS | reconciliation | payload_hash = SHA-256(payload_json) | 0 | 0 | 0 | 0 |
| PASS | reconciliation | signature = HMAC-SHA256(issuer key, payload_hash) | 0 | 0 | 0 | 0 |
| PASS | reconciliation | payload_json equals canonical payload of the row | 0 | 0 | 0 | 0 |
| PASS | reconciliation | expires_at = issued_at + rule.validity_months | 0 | 0 | 0 | 0 |
| PASS | lifecycle | Audit log hash chain intact (append-only, tamper-evident) | 0 | 0 | 0 | 0 |
| PASS | lifecycle | Audit log ordered by id and non-decreasing timestamp | 0 | 0 | 0 | 0 |
| PASS | lifecycle | Lifecycle transitions valid (state machine replay; one ISSUED event per credential ID) | 40 | 40 | 0 | 0 |
| PASS | lifecycle | Credential.status equals replay of revocation/reversal events (revocation status is current) | 0 | 0 | 0 | 0 |
| PASS | lifecycle | Revocation sequence contiguous per credential; REV id embeds credential id + seq | 0 | 0 | 0 | 0 |
| PASS | lifecycle | Every Revocation row has exactly one CREDENTIAL_REVOKED audit event | 0 | 0 | 0 | 0 |
| PASS | lifecycle | Audit: CREDENTIAL_ISSUED never precedes the COMPLETED event | 100 | 100 | 0 | 0 |
| PASS | verification | Verification re-computed from published data equals ground-truth expected result (reproducible) | 0 | 0 | 0 | 0 |
| PASS | verification | Recorded verification result == recomputed (differences = labelled REVOKED_AS_ACTIVE / HASH_NOT_DETECTED anomalies) | 50 | 50 | 0 | 0 |
| PASS | verification | Verification decision never depends on claimed name (identity != name) | 0 | 0 | 0 | 0 |
| PASS | verification | Name-only / same-name requests are NOT accepted as proof of identity | 0 | 0 | 0 | 0 |
| PASS | ground_truth | Ground-truth columns never appear in input tables (no leakage) | 0 | 0 | 0 | 0 |
| PASS | ground_truth | ground_truth.csv references only existing entities | 0 | 0 | 0 | 0 |
| PASS | sql | seed.sql loads into SQLite; row counts match CSV; FK check clean | 0 | 0 | 0 | 0 |

## Coverage

```json
{
  "row_counts": {
    "actors": 57,
    "issuers": 12,
    "learners": 20000,
    "courses": 1000,
    "course_issuer_history": 1306,
    "credential_rules": 1096,
    "completion_records": 44045,
    "assessments": 153418,
    "credentials": 10000,
    "revocations": 597,
    "verification_requests": 5000,
    "audit_events": 101272
  },
  "completion_status": {
    "COMPLETED": 26439,
    "FAILED": 7700,
    "IN_PROGRESS": 4301,
    "WITHDRAWN": 5605
  },
  "credential_status_at_as_of": {
    "ACTIVE": 8975,
    "EXPIRED": 455,
    "REVOKED": 570
  },
  "verification_result_recorded": {
    "EXPIRED": 41,
    "HASH_MISMATCH": 115,
    "IDENTITY_MISMATCH": 198,
    "INSUFFICIENT_IDENTITY": 203,
    "NOT_FOUND": 153,
    "REVOKED": 470,
    "VALID": 3820
  },
  "verification_result_expected": {
    "EXPIRED": 41,
    "HASH_MISMATCH": 140,
    "IDENTITY_MISMATCH": 198,
    "INSUFFICIENT_IDENTITY": 203,
    "NOT_FOUND": 153,
    "REVOKED": 495,
    "VALID": 3770
  },
  "revocation_reasons": {
    "ACADEMIC_MISCONDUCT": 131,
    "COURSE_RETIRED": 71,
    "FRAUD": 90,
    "ISSUED_IN_ERROR": 159,
    "LEARNER_REQUEST": 98,
    "POLICY_VIOLATION": 48
  },
  "reinstated_revocations": 27,
  "re_revoked_credentials": 5,
  "credentials_issued_by_successor_issuers": 918,
  "courses_with_issuer_change": 306,
  "learners_sharing_a_full_name": 4767,
  "completions_score_exactly_at_threshold": 604,
  "failed_one_point_below_threshold": 575,
  "completed_but_no_credential_issued": 16469,
  "final_score_mean_sd": [
    78.77,
    9.34
  ],
  "anomalies_injected": {
    "ALTERED_PAYLOAD_HASH_NOT_DETECTED": 25,
    "CREDENTIAL_ISSUED_BEFORE_COMPLETION": 100,
    "DUPLICATE_CREDENTIAL_ID": 40,
    "REVOKED_CREDENTIAL_VERIFIES_AS_ACTIVE": 25
  }
}
```
