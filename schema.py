"""Single source of truth for the data dictionary, enums, PK/FK and cardinalities.
Used to: export data_dictionary.csv/.md, schema.json, SQL DDL, and drive validation.

Field tuple: (name, type, required, allowed, unit, unique, rule)
  type    : STRING | INTEGER | DECIMAL | DATE | TIMESTAMP | BOOLEAN | JSON
  allowed : list => enum ; str => description of the allowed range/pattern
"""

TS = "UTC, ISO-8601 YYYY-MM-DDTHH:MM:SSZ"
DT = "ISO-8601 YYYY-MM-DD"

ROLES = ["SYSTEM", "INSTRUCTOR", "ACADEMIC_ADMIN", "SUPPORT_STAFF", "PLATFORM_ADMIN"]
LEVELS = ["BEGINNER", "INTERMEDIATE", "ADVANCED"]
COMPLETION_STATUS = ["IN_PROGRESS", "COMPLETED", "FAILED", "WITHDRAWN"]
CRED_STATUS = ["ACTIVE", "REVOKED", "EXPIRED"]
REASONS = ["ISSUED_IN_ERROR", "ACADEMIC_MISCONDUCT", "LEARNER_REQUEST", "FRAUD", "POLICY_VIOLATION", "COURSE_RETIRED"]
REQUESTER_TYPES = ["EMPLOYER", "UNIVERSITY", "BACKGROUND_CHECK", "LEARNER", "GOVERNMENT"]
CHANNELS = ["API", "PORTAL", "EMAIL"]
RESULTS = ["VALID", "REVOKED", "EXPIRED", "NOT_FOUND", "HASH_MISMATCH",
           "IDENTITY_MISMATCH", "INSUFFICIENT_IDENTITY", "AMBIGUOUS_ID"]
ENTITY_TYPES = ["Course", "CredentialRule", "CompletionRecord", "Credential", "VerificationRequest"]
EVENT_TYPES = ["RULE_PUBLISHED", "ISSUER_CHANGED", "LEARNER_ENROLLED", "COMPLETION_STATE_CHANGED",
               "CREDENTIAL_ISSUED", "CREDENTIAL_REVOKED", "REVOCATION_REVERSED",
               "CREDENTIAL_EXPIRED", "VERIFICATION_PERFORMED"]
ACTOR_TYPES = ["SYSTEM", "LEARNER", "STAFF", "EXTERNAL_VERIFIER"]

DATA_DICT = {
    "actors": ("Actor (supporting)", "actors.csv", "actor_id", [
        ("actor_id", "STRING", True, "ACT-NNNN", "-", True, "PK; zero-padded; ACT-0000 reserved for SYSTEM"),
        ("display_name", "STRING", True, "synthetic name", "-", False, "non-empty"),
        ("role", "STRING", True, ROLES, "-", False, "one of ROLES"),
        ("email", "STRING", True, "@example.org", "-", True, "synthetic address on reserved domain"),
        ("status", "STRING", True, ["ACTIVE", "INACTIVE"], "-", False, ""),
    ]),
    "issuers": ("Issuer", "issuers.csv", "issuer_id", [
        ("issuer_id", "STRING", True, "ISS-NNN", "-", True, "PK"),
        ("issuer_name", "STRING", True, "text", "-", True, ""),
        ("issuer_type", "STRING", True, ["UNIVERSITY", "TRAINING_PROVIDER", "PROFESSIONAL_BODY"], "-", False, ""),
        ("country", "STRING", True, "ISO 3166-1 alpha-2", "-", False, ""),
        ("status", "STRING", True, ["ACTIVE", "SUPERSEDED"], "-", False, "SUPERSEDED iff effective_to is set"),
        ("effective_from", "DATE", True, DT, "date", False, "<= effective_to"),
        ("effective_to", "DATE", False, DT, "date", False, "set when issuer is superseded"),
        ("predecessor_issuer_id", "STRING", False, "FK issuers.issuer_id", "-", False, "issuer change lineage"),
        ("signing_key_id", "STRING", True, "<issuer_id>-K1", "-", True, "key used to sign credentials"),
        ("key_fingerprint", "STRING", True, "16 hex", "-", True, "sha256(key)[:16]; demo key, derived from seed"),
    ]),
    "learners": ("Learner", "learners.csv", "learner_id", [
        ("learner_id", "STRING", True, "LRN-NNNNNN", "-", True, "PK; immutable"),
        ("first_name", "STRING", True, "synthetic", "-", False, "duplicates allowed"),
        ("last_name", "STRING", True, "synthetic", "-", False, "duplicates allowed"),
        ("full_name", "STRING", True, "first + ' ' + last", "-", False, "NOT unique, NOT an identity key"),
        ("email", "STRING", True, "@example.org", "-", True, "lower-case; identity attribute"),
        ("date_of_birth", "DATE", True, DT, "date", False, "learner >= 18 on created_at; identity attribute"),
        ("country", "STRING", True, "ISO 3166-1 alpha-2", "-", False, ""),
        ("status", "STRING", True, ["ACTIVE", "SUSPENDED", "CLOSED"], "-", False, ""),
        ("created_at", "DATE", True, DT, "date", False, "<= first enrolled_at"),
    ]),
    "courses": ("Course", "courses.csv", "course_id", [
        ("course_id", "STRING", True, "CRS-NNNN", "-", True, "PK"),
        ("title", "STRING", True, "text", "-", False, "titles repeat across issuers"),
        ("category", "STRING", True, "text", "-", False, ""),
        ("level", "STRING", True, LEVELS, "-", False, ""),
        ("credit_hours", "INTEGER", True, "8..120", "hours", False, ""),
        ("duration_days", "INTEGER", True, ">= 14", "days", False, "= 14 + 0.8 * credit_hours"),
        ("num_assessments", "INTEGER", True, "3..5", "count", False, "= rule.min_assessments"),
        ("instructor_id", "STRING", True, "FK actors.actor_id (role INSTRUCTOR)", "-", False, ""),
        ("issuer_id", "STRING", True, "FK issuers.issuer_id", "-", False, "CURRENT issuer = last course_issuer_history row"),
        ("status", "STRING", True, ["ACTIVE", "RETIRED"], "-", False, "RETIRED iff effective_to set"),
        ("effective_from", "DATE", True, DT, "date", False, "<= effective_to"),
        ("effective_to", "DATE", False, DT, "date", False, ""),
    ]),
    "course_issuer_history": ("Course-Issuer bridge (N:M over time)", "course_issuer_history.csv", "history_id", [
        ("history_id", "STRING", True, "CIH-NNNNNN", "-", True, "PK"),
        ("course_id", "STRING", True, "FK courses.course_id", "-", False, ""),
        ("issuer_id", "STRING", True, "FK issuers.issuer_id", "-", False, ""),
        ("effective_from", "DATE", True, DT, "date", False, "periods per course do not overlap"),
        ("effective_to", "DATE", False, DT, "date", False, "NULL = current"),
        ("change_reason", "STRING", True, ["INITIAL", "ISSUER_SUCCESSION", "ISSUER_TRANSFER"], "-", False, ""),
    ]),
    "credential_rules": ("CredentialRule", "credential_rules.csv", "rule_id", [
        ("rule_id", "STRING", True, "RUL-NNNN", "-", True, "PK"),
        ("course_id", "STRING", True, "FK courses.course_id", "-", False, ""),
        ("rule_version", "INTEGER", True, "1..2", "-", False, "(course_id, rule_version) unique"),
        ("min_progress_pct", "INTEGER", True, "100", "%", False, ""),
        ("min_assessments", "INTEGER", True, "3..5", "count", False, ""),
        ("min_final_score", "INTEGER", True, "60..85", "points of 100", False, "inclusive threshold (>=)"),
        ("min_attendance_pct", "INTEGER", True, [0, 70, 80], "%", False, "0 = no attendance requirement"),
        ("validity_months", "INTEGER", False, [6, 12, 24, 36, 60], "months", False, "NULL = never expires"),
        ("effective_from", "DATE", True, DT, "date", False, "rule applies to enrollments on/after"),
        ("effective_to", "DATE", False, DT, "date", False, ""),
        ("status", "STRING", True, ["ACTIVE", "SUPERSEDED", "RETIRED"], "-", False, ""),
    ]),
    "completion_records": ("CompletionRecord (Learner-Course bridge)", "completion_records.csv", "completion_id", [
        ("completion_id", "STRING", True, "CMP-<learner-id>-<course-id>", "-", True, "PK; (learner,course) unique"),
        ("learner_id", "STRING", True, "FK learners.learner_id", "-", False, ""),
        ("course_id", "STRING", True, "FK courses.course_id", "-", False, ""),
        ("rule_id", "STRING", True, "FK credential_rules.rule_id", "-", False, "rule in force at enrolled_at"),
        ("enrolled_at", "DATE", True, DT, "date", False, ">= learner.created_at"),
        ("closed_at", "DATE", False, DT, "date", False, "set for COMPLETED/FAILED/WITHDRAWN"),
        ("completed_at", "DATE", False, DT, "date", False, "set only when COMPLETED (= closed_at)"),
        ("status", "STRING", True, COMPLETION_STATUS, "-", False, "COMPLETED iff coursework finished AND rule met"),
        ("progress_pct", "INTEGER", True, "0..100", "%", False, ""),
        ("assessments_taken", "INTEGER", True, ">= 0", "count", False, "= count(assessments rows)"),
        ("final_score", "DECIMAL", False, "0..100", "points", False, "= round(mean(assessment.score), 2)"),
        ("attendance_pct", "DECIMAL", True, "0..100", "%", False, ""),
        ("requirements_met", "BOOLEAN", True, [0, 1], "-", False, "derived: evaluate_rule(rule, ...)"),
        ("failure_reasons", "STRING", False, "PROGRESS_BELOW_MIN|ASSESSMENTS_MISSING|SCORE_BELOW_MIN|ATTENDANCE_BELOW_MIN", "-", False, "pipe-separated; set only for FAILED"),
    ]),
    "assessments": ("Assessment (supporting)", "assessments.csv", "assessment_id", [
        ("assessment_id", "STRING", True, "AST-NNNNNNN", "-", True, "PK"),
        ("completion_id", "STRING", True, "FK completion_records.completion_id", "-", False, ""),
        ("sequence_no", "INTEGER", True, "1..5", "-", False, "(completion_id, sequence_no) unique"),
        ("assessment_type", "STRING", True, ["QUIZ", "PROJECT", "FINAL_EXAM"], "-", False, ""),
        ("score", "INTEGER", True, "0..100", "points", False, ""),
        ("max_score", "INTEGER", True, [100], "points", False, ""),
        ("taken_at", "DATE", True, DT, "date", False, "within enrolment window"),
    ]),
    "credentials": ("Credential", "credentials.csv", "credential_id", [
        ("credential_id", "STRING", True, "CRD-YYYY-NNNNNN", "-", True, "PK (logical). Injected DUPLICATE_CREDENTIAL_ID rows violate this on purpose"),
        ("completion_id", "STRING", True, "FK completion_records.completion_id", "-", True, "1 completion -> at most 1 credential"),
        ("learner_id", "STRING", True, "FK learners.learner_id", "-", False, "= completion.learner_id"),
        ("course_id", "STRING", True, "FK courses.course_id", "-", False, "= completion.course_id"),
        ("rule_id", "STRING", True, "FK credential_rules.rule_id", "-", False, "= completion.rule_id"),
        ("issuer_id", "STRING", True, "FK issuers.issuer_id", "-", False, "issuer of the course ON issued_at date"),
        ("issued_at", "TIMESTAMP", True, TS, "UTC", False, ">= completion.completed_at (anomaly otherwise)"),
        ("expires_at", "TIMESTAMP", False, TS, "UTC", False, "= issued_at + rule.validity_months"),
        ("status", "STRING", True, CRED_STATUS, "-", False, "snapshot at status_as_of, derived by replaying audit events"),
        ("status_as_of", "DATE", True, DT, "date", False, "dataset as-of date"),
        ("payload_json", "JSON", True, "canonical JSON", "-", False, "the signed payload"),
        ("payload_hash", "STRING", True, "64 hex", "-", False, "SHA-256(payload_json)"),
        ("hash_algo", "STRING", True, ["SHA-256"], "-", False, ""),
        ("signature", "STRING", True, "64 hex", "-", False, "HMAC-SHA256(issuer key, payload_hash)"),
        ("signature_alg", "STRING", True, ["HMAC-SHA256"], "-", False, ""),
        ("signing_key_id", "STRING", True, "FK issuers.signing_key_id", "-", False, ""),
    ]),
    "revocations": ("Revocation", "revocations.csv", "revocation_id", [
        ("revocation_id", "STRING", True, "REV-<credential-id>-NN", "-", True, "PK; NN = revocation_seq"),
        ("credential_id", "STRING", True, "FK credentials.credential_id", "-", False, ""),
        ("revocation_seq", "INTEGER", True, "1..2", "-", False, "contiguous per credential"),
        ("revoked_at", "TIMESTAMP", True, TS, "UTC", False, "> credential.issued_at"),
        ("reason_code", "STRING", True, REASONS, "-", False, ""),
        ("revoked_by_actor_id", "STRING", True, "FK actors.actor_id", "-", False, "staff role by reason"),
    ]),
    "verification_requests": ("VerificationRequest", "verification_requests.csv", "verification_id", [
        ("verification_id", "STRING", True, "VER-YYYY-NNNNNN", "-", True, "PK; ordered by requested_at"),
        ("credential_id", "STRING", True, "credential ID as presented", "-", False, "logical FK; unknown IDs are legitimate (NOT_FOUND)"),
        ("requested_at", "TIMESTAMP", True, TS, "UTC", False, ""),
        ("requester_type", "STRING", True, REQUESTER_TYPES, "-", False, ""),
        ("requester_org", "STRING", True, "text", "-", False, ""),
        ("channel", "STRING", True, CHANNELS, "-", False, ""),
        ("claimed_name", "STRING", False, "text", "-", False, "informational only; never used for the decision"),
        ("claimed_dob", "DATE", False, DT, "date", False, "identity attribute"),
        ("claimed_email_hash", "STRING", False, "64 hex", "-", False, "sha256(lower(email))"),
        ("presented_payload_hash", "STRING", False, "64 hex", "-", False, "hash from QR/API if supplied"),
        ("result", "STRING", True, RESULTS, "-", False, "RECORDED outcome of the platform at request time"),
        ("result_detail", "STRING", True, "text", "-", False, "standard text for result"),
        ("response_ms", "INTEGER", True, "10..5000", "ms", False, ""),
    ]),
    "audit_events": ("AuditEvent (append-only, hash-chained)", "audit_events.csv", "audit_event_id", [
        ("audit_event_id", "STRING", True, "AUD-NNNNNNNN", "-", True, "PK; strictly increasing"),
        ("event_ts", "TIMESTAMP", True, TS, "UTC", False, "non-decreasing in audit_event_id order"),
        ("entity_type", "STRING", True, ENTITY_TYPES, "-", False, "polymorphic reference"),
        ("entity_id", "STRING", True, "ID of the entity", "-", False, "polymorphic FK (validated per entity_type)"),
        ("event_type", "STRING", True, EVENT_TYPES, "-", False, ""),
        ("actor_type", "STRING", True, ACTOR_TYPES, "-", False, ""),
        ("actor_id", "STRING", True, "actor / learner / org", "-", False, "STAFF/SYSTEM -> actors.actor_id; LEARNER -> learner_id"),
        ("old_state", "STRING", False, "state before", "-", False, ""),
        ("new_state", "STRING", False, "state after", "-", False, ""),
        ("details_json", "JSON", True, "JSON", "-", False, ""),
        ("prev_event_hash", "STRING", True, "64 hex", "-", False, "event_hash of previous row (zeros for first)"),
        ("event_hash", "STRING", True, "64 hex", "-", True, "sha256(prev_event_hash|row fields) -> tamper evidence"),
    ]),
}

TABLE_ORDER = ["actors", "issuers", "learners", "courses", "course_issuer_history", "credential_rules",
               "completion_records", "assessments", "credentials", "revocations",
               "verification_requests", "audit_events"]

# (child_table, child_col, parent_table, parent_col, cardinality, optional, enforce_in_sql)
FKS = [
    ("issuers", "predecessor_issuer_id", "issuers", "issuer_id", "1:N", True, True),
    ("courses", "instructor_id", "actors", "actor_id", "1:N", False, True),
    ("courses", "issuer_id", "issuers", "issuer_id", "1:N", False, True),
    ("course_issuer_history", "course_id", "courses", "course_id", "1:N", False, True),
    ("course_issuer_history", "issuer_id", "issuers", "issuer_id", "1:N", False, True),
    ("credential_rules", "course_id", "courses", "course_id", "1:N", False, True),
    ("completion_records", "learner_id", "learners", "learner_id", "N:M via bridge", False, True),
    ("completion_records", "course_id", "courses", "course_id", "N:M via bridge", False, True),
    ("completion_records", "rule_id", "credential_rules", "rule_id", "1:N", False, True),
    ("assessments", "completion_id", "completion_records", "completion_id", "1:N", False, True),
    ("credentials", "completion_id", "completion_records", "completion_id", "1:0..1", False, True),
    ("credentials", "learner_id", "learners", "learner_id", "1:N", False, True),
    ("credentials", "course_id", "courses", "course_id", "1:N", False, True),
    ("credentials", "rule_id", "credential_rules", "rule_id", "1:N", False, True),
    ("credentials", "issuer_id", "issuers", "issuer_id", "1:N", False, True),
    ("revocations", "credential_id", "credentials", "credential_id", "1:N", False, False),
    ("revocations", "revoked_by_actor_id", "actors", "actor_id", "1:N", False, True),
]

CARDINALITY_NOTES = [
    "Learner N:M Course via CompletionRecord (bridge, unique (learner_id, course_id), carries lifecycle state).",
    "Course N:M Issuer over time via course_issuer_history (effective-dated bridge; supports issuer changes).",
    "Course 1:N CredentialRule (versioned, effective-dated; rule in force at enrolled_at is bound to the completion).",
    "CompletionRecord 1:N Assessment; CompletionRecord 1:0..1 Credential (optional: eligible learners may not have been issued yet).",
    "Credential 1:N Revocation (sequence -01, -02 after a reversal); Credential 1:N VerificationRequest (optional/loose: unknown IDs are legitimate).",
    "AuditEvent is a polymorphic append-only log: (entity_type, entity_id) -> any lifecycle entity.",
    "Lifecycle - CompletionRecord: IN_PROGRESS -> COMPLETED | FAILED | WITHDRAWN.",
    "Lifecycle - Credential: (none) -> ACTIVE -> REVOKED -> ACTIVE (reversal) -> REVOKED ...; ACTIVE -> EXPIRED (time).",
]

# Columns that exist ONLY in ground truth; must never appear in input tables
GROUND_TRUTH_FIELDS = ["gt_id", "entity_type", "entity_id", "row_ref", "is_anomaly", "issue_type",
                       "variant", "expected_value", "recorded_value", "scenario", "rule_reference"]
GROUND_TRUTH_ONLY_COLUMNS = ["issue_type", "is_anomaly", "expected_value", "scenario", "variant", "rule_reference"]


def fields(table):
    return [f[0] for f in DATA_DICT[table][3]]


def pk(table):
    return DATA_DICT[table][2]


def enums(table):
    return {f[0]: f[3] for f in DATA_DICT[table][3] if isinstance(f[3], list)}


def sql_type(t):
    return {"STRING": "TEXT", "INTEGER": "INTEGER", "DECIMAL": "REAL", "DATE": "TEXT",
            "TIMESTAMP": "TEXT", "BOOLEAN": "INTEGER", "JSON": "TEXT"}[t]
