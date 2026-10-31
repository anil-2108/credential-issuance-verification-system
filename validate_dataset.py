#!/usr/bin/env python3
"""Validate a generated dataset (Step 8).

    python validate_dataset.py --data data_full [--check-sql]

Every violation found must be EXPLAINED by a labelled anomaly in ground_truth.csv
(and every labelled anomaly must be DETECTED). Anything else fails the run.
Ground truth is used here only for reconciliation, never to compute results.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sqlite3
import statistics
import sys
from datetime import date, datetime

import credential_logic as L
import schema as S


def load(data, table):
    with open(os.path.join(data, S.DATA_DICT[table][1]), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def nn(v):
    return None if v in ("", None) else v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data_full")
    ap.add_argument("--check-sql", action="store_true", help="load seed.sql into in-memory SQLite with FK enforcement")
    a = ap.parse_args()
    data = a.data
    manifest = json.load(open(os.path.join(data, "source_manifest.json")))
    seed, as_of = manifest["seed"], manifest["parameters"]["as_of"]
    as_end = as_of + "T23:59:59Z"
    T = {t: load(data, t) for t in S.TABLE_ORDER}
    gt = list(csv.DictReader(open(os.path.join(data, "ground_truth.csv"), newline="", encoding="utf-8")))
    results = []

    def check(name, cat, violations, expected=None, note=""):
        """violations: set of keys found. expected: keys that labelled anomalies say SHOULD be found."""
        violations = set(violations)
        expected = set(expected or [])
        unexplained = sorted(violations - expected)
        missed = sorted(expected - violations)
        ok = not unexplained and not missed
        results.append({"check": name, "category": cat, "status": "PASS" if ok else "FAIL",
                        "violations_found": len(violations), "explained_by_ground_truth": len(violations & expected),
                        "unexplained": len(unexplained), "labelled_but_not_detected": len(missed),
                        "examples": (unexplained + missed)[:5], "note": note})

    gt_a = [g for g in gt if g["is_anomaly"] == "1"]
    dup_ids = {g["entity_id"] for g in gt_a if g["issue_type"] == "DUPLICATE_CREDENTIAL_ID"}
    early_ids = {g["entity_id"] for g in gt_a if g["issue_type"] == "CREDENTIAL_ISSUED_BEFORE_COMPLETION"}
    bad_ver = {g["entity_id"] for g in gt_a if g["entity_type"] == "VerificationRequest"}

    # ---------------------------------------------------------------- columns / formats / enums / required
    col_bad = [t for t in S.TABLE_ORDER if list(T[t][0].keys()) != S.fields(t)] if all(T[t] for t in T) else ["empty table"]
    check("CSV columns equal data dictionary", "schema", col_bad)
    pat_bad = []
    for t in S.TABLE_ORDER:
        for col, rx in L.ID_PATTERNS.items():
            if col in S.fields(t) and not (t == "audit_events" and col == "actor_id"):
                pat_bad += [f"{t}.{col}={r[col]}" for r in T[t] if not re.match(rx, r[col])]
    check("ID formats (CRD-YYYY-NNNNNN, LRN-NNNNNN, CMP-<lrn>-<crs>, VER-YYYY-NNNNNN, REV-<crd>-NN ...)", "ids", pat_bad)
    enum_bad = []
    for t in S.TABLE_ORDER:
        for col, allowed in S.enums(t).items():
            al = {str(x) for x in allowed}
            enum_bad += [f"{t}.{col}={r[col]}" for r in T[t] if nn(r[col]) is not None and r[col] not in al]
    check("Allowed enum values", "enums", enum_bad)
    req_bad = []
    for t in S.TABLE_ORDER:
        for (n, ty, req, *_rest) in S.DATA_DICT[t][3]:
            if req:
                req_bad += [f"{t}.{n}" for r in T[t] if nn(r[n]) is None][:3]
    check("Required fields populated", "schema", req_bad)

    # ---------------------------------------------------------------- primary keys / duplicates
    for t in S.TABLE_ORDER:
        pkc = S.pk(t)
        seen, dups = set(), set()
        for r in T[t]:
            (dups if r[pkc] in seen else seen).add(r[pkc])
        check(f"PK uniqueness: {t}.{pkc}", "primary_keys", dups, dup_ids if t == "credentials" else None,
              "duplicates here are the labelled DUPLICATE_CREDENTIAL_ID anomaly" if t == "credentials" else "")
    seen, d = set(), set()
    for r in T["completion_records"]:
        k = (r["learner_id"], r["course_id"])
        (d if k in seen else seen).add(k)
    check("No duplicate (learner, course) completions", "duplicates", d)
    emails = [r["email"] for r in T["learners"]]
    seen_e, dup_e = set(), set()
    for e_ in emails:
        (dup_e if e_ in seen_e else seen_e).add(e_)
    check("Learner emails unique", "duplicates", dup_e)
    cc = [r["completion_id"] for r in T["credentials"]]
    seen_c, dup_c = set(), set()
    for c_ in cc:
        (dup_c if c_ in seen_c else seen_c).add(c_)
    check("1 completion -> at most 1 credential", "duplicates", dup_c)
    names = {}
    for r in T["learners"]:
        names.setdefault(r["full_name"], []).append(r["learner_id"])
    dup_names = sum(1 for v in names.values() if len(v) > 1)
    results.append({"check": "Duplicate learner names exist (by design) and emails differ", "category": "duplicates",
                    "status": "PASS" if dup_names > 0 else "FAIL", "violations_found": 0, "explained_by_ground_truth": 0,
                    "unexplained": 0, "labelled_but_not_detected": 0, "examples": [], "note": f"{dup_names} full names shared by >1 learner"})

    # ---------------------------------------------------------------- foreign keys
    idx = {t: {r[S.pk(t)] for r in T[t]} for t in S.TABLE_ORDER}
    for (ct, cc_, pt, pc, card, opt, enf) in S.FKS:
        bad = {f"{r[S.pk(ct)]}->{r[cc_]}" for r in T[ct] if nn(r[cc_]) is not None and r[cc_] not in idx[pt]}
        if not opt:
            bad |= {f"{r[S.pk(ct)]}:NULL" for r in T[ct] if nn(r[cc_]) is None}
        check(f"FK {ct}.{cc_} -> {pt}.{pc}", "foreign_keys", bad)
    unknown = {r["verification_id"] for r in T["verification_requests"] if r["credential_id"] not in idx["credentials"]}
    exp_unknown = {g["entity_id"] for g in gt if g["entity_type"] == "VerificationRequest" and g["scenario"] == "UNKNOWN_ID"}
    check("verification_requests.credential_id unknown only for UNKNOWN_ID scenario", "foreign_keys", unknown, exp_unknown)
    lrn_ids = idx["learners"]
    ent_ref = {"Course": "courses", "CredentialRule": "credential_rules", "CompletionRecord": "completion_records",
               "Credential": "credentials", "VerificationRequest": "verification_requests"}
    check("audit_events polymorphic entity reference valid", "foreign_keys",
          {r["audit_event_id"] for r in T["audit_events"] if r["entity_id"] not in idx[ent_ref[r["entity_type"]]]})
    act_ids = idx["actors"]
    check("audit_events STAFF/SYSTEM/LEARNER actor references valid", "foreign_keys",
          {r["audit_event_id"] for r in T["audit_events"]
           if (r["actor_type"] in ("STAFF", "SYSTEM") and r["actor_id"] not in act_ids) or (r["actor_type"] == "LEARNER" and r["actor_id"] not in lrn_ids)})

    # ---------------------------------------------------------------- date ordering
    L_by = {r["learner_id"]: r for r in T["learners"]}
    C = {r["completion_id"]: r for r in T["completion_records"]}
    R = {r["rule_id"]: r for r in T["credential_rules"]}
    Crs = {r["course_id"]: r for r in T["courses"]}
    check("learner.created_at <= enrolled_at", "date_ordering", {c["completion_id"] for c in C.values() if L_by[c["learner_id"]]["created_at"] > c["enrolled_at"]})
    check("enrolled_at <= closed_at; completed_at == closed_at when COMPLETED", "date_ordering",
          {c["completion_id"] for c in C.values() if (nn(c["closed_at"]) and c["closed_at"] < c["enrolled_at"])
           or (c["status"] == "COMPLETED" and c["completed_at"] != c["closed_at"])
           or (c["status"] != "COMPLETED" and nn(c["completed_at"]))})
    check("assessment taken_at within enrolment window", "date_ordering",
          {a_["assessment_id"] for a_ in T["assessments"]
           if a_["taken_at"] < C[a_["completion_id"]]["enrolled_at"] or a_["taken_at"] > (nn(C[a_["completion_id"]]["closed_at"]) or as_of)})
    check("Enrolment inside course effective window (no enrolments after retirement)", "date_ordering",
          {c["completion_id"] for c in C.values() if c["enrolled_at"] < Crs[c["course_id"]]["effective_from"]
           or (nn(Crs[c["course_id"]]["effective_to"]) and c["enrolled_at"] > Crs[c["course_id"]]["effective_to"])})
    check("rule effective_from <= effective_to; enrolment inside rule window", "date_ordering",
          {r["rule_id"] for r in R.values() if nn(r["effective_to"]) and r["effective_to"] < r["effective_from"]}
          | {c["completion_id"] for c in C.values() if not (R[c["rule_id"]]["effective_from"] <= c["enrolled_at"] and (not nn(R[c["rule_id"]]["effective_to"]) or c["enrolled_at"] <= R[c["rule_id"]]["effective_to"]))})
    # credential vs completion  (expected: labelled anomalies only)
    early = set()
    for cr in T["credentials"]:
        comp = C[cr["completion_id"]]
        if comp["status"] != "COMPLETED" or cr["issued_at"][:10] < comp["completed_at"]:
            early.add(cr["credential_id"])
    check("Credential issued only AFTER a COMPLETED completion (issued_at >= completed_at)", "date_ordering", early, early_ids,
          "violations must equal the labelled CREDENTIAL_ISSUED_BEFORE_COMPLETION rows")
    check("issued_at <= expires_at", "date_ordering", {r["credential_id"] for r in T["credentials"] if nn(r["expires_at"]) and r["expires_at"] <= r["issued_at"]})
    hist = {}
    for h in T["course_issuer_history"]:
        hist.setdefault(h["course_id"], []).append(h)
    ov = set()
    for cid, hs in hist.items():
        hs.sort(key=lambda h: h["effective_from"])
        for x, y in zip(hs, hs[1:]):
            if not nn(x["effective_to"]) or y["effective_from"] <= x["effective_to"]:
                ov.add(cid)
    check("Issuer history periods contiguous and non-overlapping", "date_ordering", ov)
    iss_bad = set()
    for cr in T["credentials"]:
        d = cr["issued_at"][:10]
        okh = [h for h in hist[cr["course_id"]] if h["effective_from"] <= d and (not nn(h["effective_to"]) or d <= h["effective_to"])]
        if len(okh) != 1 or okh[0]["issuer_id"] != cr["issuer_id"]:
            iss_bad.add(cr["credential_id"])
    check("Credential issuer = course issuer in force on issue date (issuer changes respected)", "lifecycle", iss_bad)
    cred_first = {}
    for cr in T["credentials"]:
        cred_first.setdefault(cr["credential_id"], cr["issued_at"])
    check("revoked_at > credential.issued_at", "date_ordering", {r["revocation_id"] for r in T["revocations"] if r["revoked_at"] <= cred_first[r["credential_id"]]})
    check("verification requested_at >= issued_at (known IDs)", "date_ordering",
          {r["verification_id"] for r in T["verification_requests"] if r["credential_id"] in cred_first and r["requested_at"] < cred_first[r["credential_id"]]})

    # ---------------------------------------------------------------- arithmetic reconciliation
    asm = {}
    for x in T["assessments"]:
        asm.setdefault(x["completion_id"], []).append(x)
    ar = set()
    for cid, c in C.items():
        sc = [int(x["score"]) for x in asm.get(cid, [])]
        if int(c["assessments_taken"]) != len(sc):
            ar.add(cid)
        exp_final = round(sum(sc) / len(sc), 2) if sc else None
        got = float(c["final_score"]) if nn(c["final_score"]) else None
        if exp_final != got:
            ar.add(cid)
    check("assessments_taken = count(assessments); final_score = round(mean(scores),2)", "reconciliation", ar)
    rr = set()
    for cid, c in C.items():
        rule = {k: (float(v) if k.startswith("min_") else v) for k, v in R[c["rule_id"]].items()}
        if c["status"] in ("COMPLETED", "FAILED"):
            met, reasons = L.evaluate_rule(rule, int(c["progress_pct"]), int(c["assessments_taken"]),
                                           float(c["final_score"]) if nn(c["final_score"]) else None, float(c["attendance_pct"]))
            if (c["status"] == "COMPLETED") != met or int(c["requirements_met"]) != int(met) or (c["failure_reasons"] or "") != "|".join(reasons):
                rr.add(cid)
        elif int(c["requirements_met"]) != 0 or int(c["progress_pct"]) >= 100:
            rr.add(cid)
    check("Completion status/requirements_met re-derived from CredentialRule", "reconciliation", rr)
    check("Credential learner/course/rule agree with its completion", "reconciliation",
          {r["credential_id"] + "/" + r["completion_id"] for r in T["credentials"]
           if (C[r["completion_id"]]["learner_id"], C[r["completion_id"]]["course_id"], C[r["completion_id"]]["rule_id"]) != (r["learner_id"], r["course_id"], r["rule_id"])})
    hb, sb, pb, eb = set(), set(), set(), set()
    for r in T["credentials"]:
        key = r["credential_id"] + "/" + r["completion_id"]
        if L.sha256_hex(r["payload_json"]) != r["payload_hash"]:
            hb.add(key)
        if L.sign_hash(L.issuer_signing_key(seed, r["issuer_id"]), r["payload_hash"]) != r["signature"]:
            sb.add(key)
        if L.build_payload({**r}) != r["payload_json"]:
            pb.add(key)
        rule = R[r["rule_id"]]
        exp_e = None
        if nn(rule["validity_months"]):
            exp_e = L.ts_str(datetime.combine(L.add_months(date.fromisoformat(r["issued_at"][:10]), int(rule["validity_months"])), L.parse_ts(r["issued_at"]).time()))
        if exp_e != nn(r["expires_at"]):
            eb.add(key)
    check("payload_hash = SHA-256(payload_json)", "reconciliation", hb)
    check("signature = HMAC-SHA256(issuer key, payload_hash)", "reconciliation", sb)
    check("payload_json equals canonical payload of the row", "reconciliation", pb)
    check("expires_at = issued_at + rule.validity_months", "reconciliation", eb)

    # ---------------------------------------------------------------- lifecycle (audit replay)
    life, order_bad, chain_bad = {}, set(), set()
    prev, last_ts, prev_id = "0" * 64, "", ""
    for e in T["audit_events"]:
        if e["prev_event_hash"] != prev:
            chain_bad.add(e["audit_event_id"])
        calc = L.sha256_hex("|".join([e["prev_event_hash"], e["audit_event_id"], e["event_ts"], e["entity_type"], e["entity_id"],
                                       e["event_type"], e["actor_type"], e["actor_id"], e["old_state"], e["new_state"], e["details_json"]]))
        if calc != e["event_hash"]:
            chain_bad.add(e["audit_event_id"])
        prev = e["event_hash"]
        if e["event_ts"] < last_ts or e["audit_event_id"] <= prev_id:
            order_bad.add(e["audit_event_id"])
        last_ts, prev_id = e["event_ts"], e["audit_event_id"]
        if e["event_type"] in ("CREDENTIAL_REVOKED", "REVOCATION_REVERSED"):
            life.setdefault(e["entity_id"], []).append((e["event_ts"], e["event_type"]))
    check("Audit log hash chain intact (append-only, tamper-evident)", "lifecycle", chain_bad)
    check("Audit log ordered by id and non-decreasing timestamp", "lifecycle", order_bad)
    allowed = {"Credential": {(None, "ACTIVE"), ("ACTIVE", "REVOKED"), ("EXPIRED", "REVOKED"), ("REVOKED", "ACTIVE"), ("REVOKED", "EXPIRED"), ("ACTIVE", "EXPIRED")},
               "CompletionRecord": {(None, "IN_PROGRESS"), ("IN_PROGRESS", "COMPLETED"), ("IN_PROGRESS", "FAILED"), ("IN_PROGRESS", "WITHDRAWN")}}
    state, tr_bad, seen_issue = {}, set(), {}
    for e in T["audit_events"]:
        if e["entity_type"] in allowed:
            k = (e["entity_type"], e["entity_id"])
            old, new = nn(e["old_state"]), nn(e["new_state"])
            if e["event_type"] == "CREDENTIAL_ISSUED":
                seen_issue[k] = seen_issue.get(k, 0) + 1
                if seen_issue[k] > 1:
                    tr_bad.add(e["entity_id"])
            elif old != state.get(k):
                tr_bad.add(e["entity_id"])
            if (old, new) not in allowed[e["entity_type"]]:
                tr_bad.add(e["entity_id"])
            state[k] = new
    check("Lifecycle transitions valid (state machine replay; one ISSUED event per credential ID)", "lifecycle", tr_bad, dup_ids,
          "duplicate credential IDs show up as a second ISSUED event for the same ID")
    st_bad = set()
    for r in T["credentials"]:
        if r["credential_id"] in dup_ids:
            continue
        if L.effective_status(sorted(life.get(r["credential_id"], [])), nn(r["expires_at"]) or "", as_end) != r["status"]:
            st_bad.add(r["credential_id"])
    check("Credential.status equals replay of revocation/reversal events (revocation status is current)", "lifecycle", st_bad)
    rv = {}
    for r in T["revocations"]:
        rv.setdefault(r["credential_id"], []).append(int(r["revocation_seq"]))
    check("Revocation sequence contiguous per credential; REV id embeds credential id + seq", "lifecycle",
          {c for c, s in rv.items() if sorted(s) != list(range(1, len(s) + 1))}
          | {r["revocation_id"] for r in T["revocations"] if r["revocation_id"] != f"REV-{r['credential_id']}-{int(r['revocation_seq']):02d}"})
    revoke_events = sum(1 for e in T["audit_events"] if e["event_type"] == "CREDENTIAL_REVOKED")
    check("Every Revocation row has exactly one CREDENTIAL_REVOKED audit event", "lifecycle", set() if revoke_events == len(T["revocations"]) else {"count_mismatch"})
    # credential issued event vs completion event ordering
    comp_done = {e["entity_id"]: e["event_ts"] for e in T["audit_events"] if e["event_type"] == "COMPLETION_STATE_CHANGED" and e["new_state"] == "COMPLETED"}
    ev_bad = {r["credential_id"] for r in T["credentials"] if r["completion_id"] not in comp_done or r["issued_at"] < comp_done[r["completion_id"]]}
    check("Audit: CREDENTIAL_ISSUED never precedes the COMPLETED event", "lifecycle", ev_bad, early_ids)

    # ---------------------------------------------------------------- verification: reproducible + identity
    learners = {r["learner_id"]: r for r in T["learners"]}
    creds = [{k: nn(v) if k == "expires_at" else v for k, v in r.items()} for r in T["credentials"]]
    ctx = L.VerificationContext(creds, learners, {k: sorted(v) for k, v in life.items()}, seed)
    recomputed, mismatch_recorded, mismatch_expected, name_dependent = {}, set(), set(), set()
    exp_val = {g["entity_id"]: g["expected_value"] for g in gt if g["entity_type"] == "VerificationRequest"}
    for r in T["verification_requests"]:
        q = {k: nn(v) for k, v in r.items()}
        res = ctx.verify(q)
        recomputed[r["verification_id"]] = res
        if res != r["result"]:
            mismatch_recorded.add(r["verification_id"])
        if res != exp_val[r["verification_id"]]:
            mismatch_expected.add(r["verification_id"])
        if ctx.verify({**q, "claimed_name": "Totally Different Name"}) != res or ctx.verify({**q, "claimed_name": None}) != res:
            name_dependent.add(r["verification_id"])
    check("Verification re-computed from published data equals ground-truth expected result (reproducible)", "verification", mismatch_expected)
    check("Recorded verification result == recomputed (differences = labelled REVOKED_AS_ACTIVE / HASH_NOT_DETECTED anomalies)", "verification", mismatch_recorded, bad_ver)
    check("Verification decision never depends on claimed name (identity != name)", "verification", name_dependent)
    imp = [r for r in T["verification_requests"] if recomputed[r["verification_id"]] == "IDENTITY_MISMATCH" and r["claimed_name"] == learners[next(c["learner_id"] for c in creds if c["credential_id"] == r["credential_id"])]["full_name"]]
    ins = [r for r in T["verification_requests"] if recomputed[r["verification_id"]] == "INSUFFICIENT_IDENTITY"]
    results.append({"check": "Name-only / same-name requests are NOT accepted as proof of identity", "category": "verification",
                    "status": "PASS" if imp and ins else "FAIL", "violations_found": 0, "explained_by_ground_truth": 0, "unexplained": 0,
                    "labelled_but_not_detected": 0, "examples": [], "note": f"{len(imp)} same-name impostor requests rejected; {len(ins)} name-only requests rejected"})

    # ---------------------------------------------------------------- ground-truth separation
    leak = [f"{t}.{c}" for t in S.TABLE_ORDER for c in S.fields(t) if c in S.GROUND_TRUTH_ONLY_COLUMNS]
    check("Ground-truth columns never appear in input tables (no leakage)", "ground_truth", leak)
    check("ground_truth.csv references only existing entities", "ground_truth",
          {g["gt_id"] for g in gt if g["entity_id"] not in (idx["verification_requests"] if g["entity_type"] == "VerificationRequest" else idx["credentials"])})

    # ---------------------------------------------------------------- optional SQL load
    if a.check_sql:
        con = sqlite3.connect(":memory:")
        con.executescript(open(os.path.join(data, "seed.sql"), encoding="utf-8").read())
        con.execute("PRAGMA foreign_keys = ON")
        fk_viol = con.execute("PRAGMA foreign_key_check").fetchall()
        cnt_bad = {t for t in S.TABLE_ORDER if con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] != len(T[t])}
        check("seed.sql loads into SQLite; row counts match CSV; FK check clean", "sql", {f"fk:{x[0]}" for x in fk_viol} | cnt_bad)

    # ---------------------------------------------------------------- coverage / distributions
    def dist(rows, col):
        d = {}
        for r in rows:
            d[r[col]] = d.get(r[col], 0) + 1
        return dict(sorted(d.items()))
    scores = [float(c["final_score"]) for c in C.values() if nn(c["final_score"])]
    boundary_at = sum(1 for c in C.values() if c["status"] in ("COMPLETED", "FAILED") and nn(c["final_score"]) and float(c["final_score"]) == float(R[c["rule_id"]]["min_final_score"]))
    boundary_below = sum(1 for c in C.values() if c["status"] == "FAILED" and nn(c["final_score"]) and float(c["final_score"]) == float(R[c["rule_id"]]["min_final_score"]) - 1)
    issued_comp = {r["completion_id"] for r in T["credentials"]}
    eligible_not_issued = sum(1 for c in C.values() if c["status"] == "COMPLETED" and c["completion_id"] not in issued_comp)
    succ = {i["issuer_id"] for i in T["issuers"] if nn(i["predecessor_issuer_id"])}
    coverage = {
        "row_counts": {t: len(T[t]) for t in S.TABLE_ORDER},
        "completion_status": dist(C.values(), "status"),
        "credential_status_at_as_of": dist(T["credentials"], "status"),
        "verification_result_recorded": dist(T["verification_requests"], "result"),
        "verification_result_expected": dict(sorted({v: list(exp_val.values()).count(v) for v in set(exp_val.values())}.items())),
        "revocation_reasons": dist(T["revocations"], "reason_code"),
        "reinstated_revocations": sum(1 for e in T["audit_events"] if e["event_type"] == "REVOCATION_REVERSED"),
        "re_revoked_credentials": sum(1 for c, s in rv.items() if len(s) > 1),
        "credentials_issued_by_successor_issuers": sum(1 for r in T["credentials"] if r["issuer_id"] in succ),
        "courses_with_issuer_change": sum(1 for h in hist.values() if len(h) > 1),
        "learners_sharing_a_full_name": sum(len(v) for v in names.values() if len(v) > 1),
        "completions_score_exactly_at_threshold": boundary_at,
        "failed_one_point_below_threshold": boundary_below,
        "completed_but_no_credential_issued": eligible_not_issued,
        "final_score_mean_sd": [round(statistics.mean(scores), 2), round(statistics.pstdev(scores), 2)],
        "anomalies_injected": dist(gt_a, "issue_type"),
    }
    failed = [r for r in results if r["status"] == "FAIL"]
    summary = {"dataset": data, "seed": seed, "as_of": as_of, "checks_total": len(results), "checks_passed": len(results) - len(failed),
               "checks_failed": len(failed), "overall": "PASS" if not failed else "FAIL", "results": results, "coverage": coverage}
    with open(os.path.join(data, "validation_summary.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)
    md = [f"# Validation summary - {summary['overall']}", "", f"Seed `{seed}`, as-of `{as_of}`. {summary['checks_passed']}/{summary['checks_total']} checks passed.", "",
          "| status | category | check | found | explained by labelled anomaly | unexplained | labelled but missed |", "|---|---|---|---|---|---|---|"]
    for r in results:
        md.append(f"| {r['status']} | {r['category']} | {r['check']} | {r['violations_found']} | {r['explained_by_ground_truth']} | {r['unexplained']} | {r['labelled_but_not_detected']} |")
    md += ["", "## Coverage", "", "```json", json.dumps(coverage, indent=2), "```"]
    with open(os.path.join(data, "validation_summary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    for r in results:
        print(f"[{r['status']}] {r['category']:<14} {r['check']}  (found={r['violations_found']}, explained={r['explained_by_ground_truth']}, unexplained={r['unexplained']}, missed={r['labelled_but_not_detected']})")
        if r["status"] == "FAIL":
            print("        examples:", r["examples"])
    print(f"\nOVERALL: {summary['overall']}  ({summary['checks_passed']}/{summary['checks_total']})")
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
