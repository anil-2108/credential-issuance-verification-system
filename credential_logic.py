"""Shared business logic used by BOTH the generator and the validator.

Keeping issuance rules, hashing/signing and the verification decision in one
module is what makes verification results reproducible: the generator and the
validator call exactly the same code on exactly the same published data.

NOTE: signing keys are DERIVED from the dataset seed (demo keys). They protect
nothing real; they only make signatures deterministic and re-verifiable.
"""
import hashlib
import hmac
import json
import calendar
from datetime import date, datetime

GENERATOR_VERSION = "1.0.0"
DEFAULT_SEED = 20261022
DEFAULT_AS_OF = "2026-10-22"
HASH_ALGO = "SHA-256"
SIGNATURE_ALGO = "HMAC-SHA256"

ID_PATTERNS = {
    "actor_id": r"^ACT-\d{4}$",
    "issuer_id": r"^ISS-\d{3}$",
    "learner_id": r"^LRN-\d{6}$",
    "course_id": r"^CRS-\d{4,}$",
    "history_id": r"^CIH-\d{6}$",
    "rule_id": r"^RUL-\d{4,}$",
    "completion_id": r"^CMP-LRN-\d{6}-CRS-\d{4,}$",
    "assessment_id": r"^AST-\d{7}$",
    "credential_id": r"^CRD-\d{4}-\d{6}$",
    "revocation_id": r"^REV-CRD-\d{4}-\d{6}-\d{2}$",
    "verification_id": r"^VER-\d{4}-\d{6}$",
    "audit_event_id": r"^AUD-\d{8}$",
}

VERIFICATION_RESULTS = [
    "VALID", "REVOKED", "EXPIRED", "NOT_FOUND", "HASH_MISMATCH",
    "IDENTITY_MISMATCH", "INSUFFICIENT_IDENTITY", "AMBIGUOUS_ID",
]

RESULT_DETAIL = {
    "VALID": "Credential authentic, identity confirmed, active at request time",
    "REVOKED": "Credential revoked at request time",
    "EXPIRED": "Credential past its expiry date at request time",
    "NOT_FOUND": "No credential with this ID existed at request time",
    "HASH_MISMATCH": "Presented or stored payload hash does not match signed record",
    "IDENTITY_MISMATCH": "Supplied date of birth / email hash do not match credential holder",
    "INSUFFICIENT_IDENTITY": "Name alone is not enough: DOB and email hash are required",
    "AMBIGUOUS_ID": "More than one record carries this credential ID",
}


# ---------------------------------------------------------------- hashing / signing
def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def issuer_signing_key(seed, issuer_id):
    return hashlib.sha256(f"{seed}:{issuer_id}:demo-signing-key".encode()).digest()


def key_fingerprint(key):
    return hashlib.sha256(key).hexdigest()[:16]


def canonical_json(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_payload(cred):
    """Canonical signed payload. Anything not in here is NOT integrity-protected."""
    return canonical_json({
        "credential_id": cred["credential_id"],
        "completion_id": cred["completion_id"],
        "learner_id": cred["learner_id"],
        "course_id": cred["course_id"],
        "rule_id": cred["rule_id"],
        "issuer_id": cred["issuer_id"],
        "issued_at": cred["issued_at"],
        "expires_at": cred.get("expires_at") or None,
    })


def sign_hash(key, payload_hash):
    return hmac.new(key, payload_hash.encode(), hashlib.sha256).hexdigest()


def tamper_hash(h):
    """Deterministically alter a hash (flip first hex digit)."""
    first = "0" if h[0] != "0" else "1"
    return first + h[1:]


# ---------------------------------------------------------------- dates
def add_months(d, months):
    y, m = divmod(d.month - 1 + months, 12)
    y += d.year
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def ts_str(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ")


# ---------------------------------------------------------------- issuance rules
def evaluate_rule(rule, progress_pct, assessments_taken, final_score, attendance_pct):
    """Return (requirements_met, [failure reason codes]). Pure function of source data."""
    reasons = []
    if progress_pct < rule["min_progress_pct"]:
        reasons.append("PROGRESS_BELOW_MIN")
    if assessments_taken < rule["min_assessments"]:
        reasons.append("ASSESSMENTS_MISSING")
    if final_score is None or final_score < rule["min_final_score"]:
        reasons.append("SCORE_BELOW_MIN")
    if attendance_pct < rule["min_attendance_pct"]:
        reasons.append("ATTENDANCE_BELOW_MIN")
    return (len(reasons) == 0), reasons


# ---------------------------------------------------------------- lifecycle replay
def revoked_at_time(events, ts):
    """events: time-sorted list of (ts_str, event_type). Replays revoke/reverse."""
    revoked = False
    for e_ts, e_type in events:
        if e_ts > ts:
            break
        if e_type == "CREDENTIAL_REVOKED":
            revoked = True
        elif e_type == "REVOCATION_REVERSED":
            revoked = False
    return revoked


def effective_status(events, expires_at, ts):
    if revoked_at_time(events, ts):
        return "REVOKED"
    if expires_at and ts >= expires_at:
        return "EXPIRED"
    return "ACTIVE"


# ---------------------------------------------------------------- verification
class VerificationContext:
    """Deterministic verifier. Decision order (documented in README):
    NOT_FOUND -> AMBIGUOUS_ID -> HASH_MISMATCH -> INSUFFICIENT_IDENTITY ->
    IDENTITY_MISMATCH -> REVOKED -> EXPIRED -> VALID.
    The claimed NAME is never used for the decision (identity = DOB + email hash).
    """

    def __init__(self, credentials, learners, lifecycle, seed):
        self.by_id = {}
        for c in credentials:
            self.by_id.setdefault(c["credential_id"], []).append(c)
        self.learners = learners
        self.lifecycle = lifecycle
        self.seed = seed
        self._keys = {}

    def key(self, issuer_id):
        if issuer_id not in self._keys:
            self._keys[issuer_id] = issuer_signing_key(self.seed, issuer_id)
        return self._keys[issuer_id]

    def verify(self, req):
        cid = req.get("credential_id") or ""
        ts = req["requested_at"]
        rows = self.by_id.get(cid)
        if not rows or (len(rows) == 1 and ts < rows[0]["issued_at"]):
            return "NOT_FOUND"
        if len(rows) > 1:
            return "AMBIGUOUS_ID"
        c = rows[0]
        # 1) stored-record integrity (hash + signature)
        if sha256_hex(c["payload_json"]) != c["payload_hash"]:
            return "HASH_MISMATCH"
        expected_sig = sign_hash(self.key(c["issuer_id"]), c["payload_hash"])
        if not hmac.compare_digest(expected_sig, c["signature"]):
            return "HASH_MISMATCH"
        # 2) presented hash (QR / API payload) if supplied
        presented = req.get("presented_payload_hash") or ""
        if presented and presented != c["payload_hash"]:
            return "HASH_MISMATCH"
        # 3) identity: DOB + email hash, never name alone
        dob = req.get("claimed_dob") or ""
        eh = req.get("claimed_email_hash") or ""
        if not dob or not eh:
            return "INSUFFICIENT_IDENTITY"
        learner = self.learners[c["learner_id"]]
        if dob != learner["date_of_birth"] or eh != sha256_hex(learner["email"].lower()):
            return "IDENTITY_MISMATCH"
        # 4) current lifecycle status AT request time
        st = effective_status(self.lifecycle.get(cid, []), c.get("expires_at") or "", ts)
        return {"REVOKED": "REVOKED", "EXPIRED": "EXPIRED", "ACTIVE": "VALID"}[st]
