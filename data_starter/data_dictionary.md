# Data dictionary

## Actor (supporting) - `actors.csv` (PK: `actor_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| actor_id | STRING | Y | ACT-NNNN | - | Y | PK; zero-padded; ACT-0000 reserved for SYSTEM |
| display_name | STRING | Y | synthetic name | - | N | non-empty |
| role | STRING | Y | SYSTEM\|INSTRUCTOR\|ACADEMIC_ADMIN\|SUPPORT_STAFF\|PLATFORM_ADMIN | - | N | one of ROLES |
| email | STRING | Y | @example.org | - | Y | synthetic address on reserved domain |
| status | STRING | Y | ACTIVE\|INACTIVE | - | N |  |

## Issuer - `issuers.csv` (PK: `issuer_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| issuer_id | STRING | Y | ISS-NNN | - | Y | PK |
| issuer_name | STRING | Y | text | - | Y |  |
| issuer_type | STRING | Y | UNIVERSITY\|TRAINING_PROVIDER\|PROFESSIONAL_BODY | - | N |  |
| country | STRING | Y | ISO 3166-1 alpha-2 | - | N |  |
| status | STRING | Y | ACTIVE\|SUPERSEDED | - | N | SUPERSEDED iff effective_to is set |
| effective_from | DATE | Y | ISO-8601 YYYY-MM-DD | date | N | <= effective_to |
| effective_to | DATE | N | ISO-8601 YYYY-MM-DD | date | N | set when issuer is superseded |
| predecessor_issuer_id | STRING | N | FK issuers.issuer_id | - | N | issuer change lineage |
| signing_key_id | STRING | Y | <issuer_id>-K1 | - | Y | key used to sign credentials |
| key_fingerprint | STRING | Y | 16 hex | - | Y | sha256(key)[:16]; demo key, derived from seed |

## Learner - `learners.csv` (PK: `learner_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| learner_id | STRING | Y | LRN-NNNNNN | - | Y | PK; immutable |
| first_name | STRING | Y | synthetic | - | N | duplicates allowed |
| last_name | STRING | Y | synthetic | - | N | duplicates allowed |
| full_name | STRING | Y | first + ' ' + last | - | N | NOT unique, NOT an identity key |
| email | STRING | Y | @example.org | - | Y | lower-case; identity attribute |
| date_of_birth | DATE | Y | ISO-8601 YYYY-MM-DD | date | N | learner >= 18 on created_at; identity attribute |
| country | STRING | Y | ISO 3166-1 alpha-2 | - | N |  |
| status | STRING | Y | ACTIVE\|SUSPENDED\|CLOSED | - | N |  |
| created_at | DATE | Y | ISO-8601 YYYY-MM-DD | date | N | <= first enrolled_at |

## Course - `courses.csv` (PK: `course_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| course_id | STRING | Y | CRS-NNNN | - | Y | PK |
| title | STRING | Y | text | - | N | titles repeat across issuers |
| category | STRING | Y | text | - | N |  |
| level | STRING | Y | BEGINNER\|INTERMEDIATE\|ADVANCED | - | N |  |
| credit_hours | INTEGER | Y | 8..120 | hours | N |  |
| duration_days | INTEGER | Y | >= 14 | days | N | = 14 + 0.8 * credit_hours |
| num_assessments | INTEGER | Y | 3..5 | count | N | = rule.min_assessments |
| instructor_id | STRING | Y | FK actors.actor_id (role INSTRUCTOR) | - | N |  |
| issuer_id | STRING | Y | FK issuers.issuer_id | - | N | CURRENT issuer = last course_issuer_history row |
| status | STRING | Y | ACTIVE\|RETIRED | - | N | RETIRED iff effective_to set |
| effective_from | DATE | Y | ISO-8601 YYYY-MM-DD | date | N | <= effective_to |
| effective_to | DATE | N | ISO-8601 YYYY-MM-DD | date | N |  |

## Course-Issuer bridge (N:M over time) - `course_issuer_history.csv` (PK: `history_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| history_id | STRING | Y | CIH-NNNNNN | - | Y | PK |
| course_id | STRING | Y | FK courses.course_id | - | N |  |
| issuer_id | STRING | Y | FK issuers.issuer_id | - | N |  |
| effective_from | DATE | Y | ISO-8601 YYYY-MM-DD | date | N | periods per course do not overlap |
| effective_to | DATE | N | ISO-8601 YYYY-MM-DD | date | N | NULL = current |
| change_reason | STRING | Y | INITIAL\|ISSUER_SUCCESSION\|ISSUER_TRANSFER | - | N |  |

## CredentialRule - `credential_rules.csv` (PK: `rule_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| rule_id | STRING | Y | RUL-NNNN | - | Y | PK |
| course_id | STRING | Y | FK courses.course_id | - | N |  |
| rule_version | INTEGER | Y | 1..2 | - | N | (course_id, rule_version) unique |
| min_progress_pct | INTEGER | Y | 100 | % | N |  |
| min_assessments | INTEGER | Y | 3..5 | count | N |  |
| min_final_score | INTEGER | Y | 60..85 | points of 100 | N | inclusive threshold (>=) |
| min_attendance_pct | INTEGER | Y | 0\|70\|80 | % | N | 0 = no attendance requirement |
| validity_months | INTEGER | N | 6\|12\|24\|36\|60 | months | N | NULL = never expires |
| effective_from | DATE | Y | ISO-8601 YYYY-MM-DD | date | N | rule applies to enrollments on/after |
| effective_to | DATE | N | ISO-8601 YYYY-MM-DD | date | N |  |
| status | STRING | Y | ACTIVE\|SUPERSEDED\|RETIRED | - | N |  |

## CompletionRecord (Learner-Course bridge) - `completion_records.csv` (PK: `completion_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| completion_id | STRING | Y | CMP-<learner-id>-<course-id> | - | Y | PK; (learner,course) unique |
| learner_id | STRING | Y | FK learners.learner_id | - | N |  |
| course_id | STRING | Y | FK courses.course_id | - | N |  |
| rule_id | STRING | Y | FK credential_rules.rule_id | - | N | rule in force at enrolled_at |
| enrolled_at | DATE | Y | ISO-8601 YYYY-MM-DD | date | N | >= learner.created_at |
| closed_at | DATE | N | ISO-8601 YYYY-MM-DD | date | N | set for COMPLETED/FAILED/WITHDRAWN |
| completed_at | DATE | N | ISO-8601 YYYY-MM-DD | date | N | set only when COMPLETED (= closed_at) |
| status | STRING | Y | IN_PROGRESS\|COMPLETED\|FAILED\|WITHDRAWN | - | N | COMPLETED iff coursework finished AND rule met |
| progress_pct | INTEGER | Y | 0..100 | % | N |  |
| assessments_taken | INTEGER | Y | >= 0 | count | N | = count(assessments rows) |
| final_score | DECIMAL | N | 0..100 | points | N | = round(mean(assessment.score), 2) |
| attendance_pct | DECIMAL | Y | 0..100 | % | N |  |
| requirements_met | BOOLEAN | Y | 0\|1 | - | N | derived: evaluate_rule(rule, ...) |
| failure_reasons | STRING | N | PROGRESS_BELOW_MIN|ASSESSMENTS_MISSING|SCORE_BELOW_MIN|ATTENDANCE_BELOW_MIN | - | N | pipe-separated; set only for FAILED |

## Assessment (supporting) - `assessments.csv` (PK: `assessment_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| assessment_id | STRING | Y | AST-NNNNNNN | - | Y | PK |
| completion_id | STRING | Y | FK completion_records.completion_id | - | N |  |
| sequence_no | INTEGER | Y | 1..5 | - | N | (completion_id, sequence_no) unique |
| assessment_type | STRING | Y | QUIZ\|PROJECT\|FINAL_EXAM | - | N |  |
| score | INTEGER | Y | 0..100 | points | N |  |
| max_score | INTEGER | Y | 100 | points | N |  |
| taken_at | DATE | Y | ISO-8601 YYYY-MM-DD | date | N | within enrolment window |

## Credential - `credentials.csv` (PK: `credential_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| credential_id | STRING | Y | CRD-YYYY-NNNNNN | - | Y | PK (logical). Injected DUPLICATE_CREDENTIAL_ID rows violate this on purpose |
| completion_id | STRING | Y | FK completion_records.completion_id | - | Y | 1 completion -> at most 1 credential |
| learner_id | STRING | Y | FK learners.learner_id | - | N | = completion.learner_id |
| course_id | STRING | Y | FK courses.course_id | - | N | = completion.course_id |
| rule_id | STRING | Y | FK credential_rules.rule_id | - | N | = completion.rule_id |
| issuer_id | STRING | Y | FK issuers.issuer_id | - | N | issuer of the course ON issued_at date |
| issued_at | TIMESTAMP | Y | UTC, ISO-8601 YYYY-MM-DDTHH:MM:SSZ | UTC | N | >= completion.completed_at (anomaly otherwise) |
| expires_at | TIMESTAMP | N | UTC, ISO-8601 YYYY-MM-DDTHH:MM:SSZ | UTC | N | = issued_at + rule.validity_months |
| status | STRING | Y | ACTIVE\|REVOKED\|EXPIRED | - | N | snapshot at status_as_of, derived by replaying audit events |
| status_as_of | DATE | Y | ISO-8601 YYYY-MM-DD | date | N | dataset as-of date |
| payload_json | JSON | Y | canonical JSON | - | N | the signed payload |
| payload_hash | STRING | Y | 64 hex | - | N | SHA-256(payload_json) |
| hash_algo | STRING | Y | SHA-256 | - | N |  |
| signature | STRING | Y | 64 hex | - | N | HMAC-SHA256(issuer key, payload_hash) |
| signature_alg | STRING | Y | HMAC-SHA256 | - | N |  |
| signing_key_id | STRING | Y | FK issuers.signing_key_id | - | N |  |

## Revocation - `revocations.csv` (PK: `revocation_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| revocation_id | STRING | Y | REV-<credential-id>-NN | - | Y | PK; NN = revocation_seq |
| credential_id | STRING | Y | FK credentials.credential_id | - | N |  |
| revocation_seq | INTEGER | Y | 1..2 | - | N | contiguous per credential |
| revoked_at | TIMESTAMP | Y | UTC, ISO-8601 YYYY-MM-DDTHH:MM:SSZ | UTC | N | > credential.issued_at |
| reason_code | STRING | Y | ISSUED_IN_ERROR\|ACADEMIC_MISCONDUCT\|LEARNER_REQUEST\|FRAUD\|POLICY_VIOLATION\|COURSE_RETIRED | - | N |  |
| revoked_by_actor_id | STRING | Y | FK actors.actor_id | - | N | staff role by reason |

## VerificationRequest - `verification_requests.csv` (PK: `verification_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| verification_id | STRING | Y | VER-YYYY-NNNNNN | - | Y | PK; ordered by requested_at |
| credential_id | STRING | Y | credential ID as presented | - | N | logical FK; unknown IDs are legitimate (NOT_FOUND) |
| requested_at | TIMESTAMP | Y | UTC, ISO-8601 YYYY-MM-DDTHH:MM:SSZ | UTC | N |  |
| requester_type | STRING | Y | EMPLOYER\|UNIVERSITY\|BACKGROUND_CHECK\|LEARNER\|GOVERNMENT | - | N |  |
| requester_org | STRING | Y | text | - | N |  |
| channel | STRING | Y | API\|PORTAL\|EMAIL | - | N |  |
| claimed_name | STRING | N | text | - | N | informational only; never used for the decision |
| claimed_dob | DATE | N | ISO-8601 YYYY-MM-DD | date | N | identity attribute |
| claimed_email_hash | STRING | N | 64 hex | - | N | sha256(lower(email)) |
| presented_payload_hash | STRING | N | 64 hex | - | N | hash from QR/API if supplied |
| result | STRING | Y | VALID\|REVOKED\|EXPIRED\|NOT_FOUND\|HASH_MISMATCH\|IDENTITY_MISMATCH\|INSUFFICIENT_IDENTITY\|AMBIGUOUS_ID | - | N | RECORDED outcome of the platform at request time |
| result_detail | STRING | Y | text | - | N | standard text for result |
| response_ms | INTEGER | Y | 10..5000 | ms | N |  |

## AuditEvent (append-only, hash-chained) - `audit_events.csv` (PK: `audit_event_id`)

| field | type | req | allowed | unit | unique | rule |
|---|---|---|---|---|---|---|
| audit_event_id | STRING | Y | AUD-NNNNNNNN | - | Y | PK; strictly increasing |
| event_ts | TIMESTAMP | Y | UTC, ISO-8601 YYYY-MM-DDTHH:MM:SSZ | UTC | N | non-decreasing in audit_event_id order |
| entity_type | STRING | Y | Course\|CredentialRule\|CompletionRecord\|Credential\|VerificationRequest | - | N | polymorphic reference |
| entity_id | STRING | Y | ID of the entity | - | N | polymorphic FK (validated per entity_type) |
| event_type | STRING | Y | RULE_PUBLISHED\|ISSUER_CHANGED\|LEARNER_ENROLLED\|COMPLETION_STATE_CHANGED\|CREDENTIAL_ISSUED\|CREDENTIAL_REVOKED\|REVOCATION_REVERSED\|CREDENTIAL_EXPIRED\|VERIFICATION_PERFORMED | - | N |  |
| actor_type | STRING | Y | SYSTEM\|LEARNER\|STAFF\|EXTERNAL_VERIFIER | - | N |  |
| actor_id | STRING | Y | actor / learner / org | - | N | STAFF/SYSTEM -> actors.actor_id; LEARNER -> learner_id |
| old_state | STRING | N | state before | - | N |  |
| new_state | STRING | N | state after | - | N |  |
| details_json | JSON | Y | JSON | - | N |  |
| prev_event_hash | STRING | Y | 64 hex | - | N | event_hash of previous row (zeros for first) |
| event_hash | STRING | Y | 64 hex | - | Y | sha256(prev_event_hash|row fields) -> tamper evidence |

## Foreign keys

| child | column | parent | column | cardinality | optional |
|---|---|---|---|---|---|
| issuers | predecessor_issuer_id | issuers | issuer_id | 1:N | Y |
| courses | instructor_id | actors | actor_id | 1:N | N |
| courses | issuer_id | issuers | issuer_id | 1:N | N |
| course_issuer_history | course_id | courses | course_id | 1:N | N |
| course_issuer_history | issuer_id | issuers | issuer_id | 1:N | N |
| credential_rules | course_id | courses | course_id | 1:N | N |
| completion_records | learner_id | learners | learner_id | N:M via bridge | N |
| completion_records | course_id | courses | course_id | N:M via bridge | N |
| completion_records | rule_id | credential_rules | rule_id | 1:N | N |
| assessments | completion_id | completion_records | completion_id | 1:N | N |
| credentials | completion_id | completion_records | completion_id | 1:0..1 | N |
| credentials | learner_id | learners | learner_id | 1:N | N |
| credentials | course_id | courses | course_id | 1:N | N |
| credentials | rule_id | credential_rules | rule_id | 1:N | N |
| credentials | issuer_id | issuers | issuer_id | 1:N | N |
| revocations | credential_id | credentials | credential_id | 1:N | N |
| revocations | revoked_by_actor_id | actors | actor_id | 1:N | N |

## Cardinality and lifecycle notes

- Learner N:M Course via CompletionRecord (bridge, unique (learner_id, course_id), carries lifecycle state).
- Course N:M Issuer over time via course_issuer_history (effective-dated bridge; supports issuer changes).
- Course 1:N CredentialRule (versioned, effective-dated; rule in force at enrolled_at is bound to the completion).
- CompletionRecord 1:N Assessment; CompletionRecord 1:0..1 Credential (optional: eligible learners may not have been issued yet).
- Credential 1:N Revocation (sequence -01, -02 after a reversal); Credential 1:N VerificationRequest (optional/loose: unknown IDs are legitimate).
- AuditEvent is a polymorphic append-only log: (entity_type, entity_id) -> any lifecycle entity.
- Lifecycle - CompletionRecord: IN_PROGRESS -> COMPLETED | FAILED | WITHDRAWN.
- Lifecycle - Credential: (none) -> ACTIVE -> REVOKED -> ACTIVE (reversal) -> REVOKED ...; ACTIVE -> EXPIRED (time).
