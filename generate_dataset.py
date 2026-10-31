#!/usr/bin/env python3
"""Synthetic data generator: credential issuance, revocation and verification.

Example (full baseline volume):
    python generate_dataset.py --seed 20261022 --out data_full
Starter dataset (same generator, smaller scale):
    python generate_dataset.py --seed 20261022 --scale 0.05 --out data_starter

Pipeline (documented rules -> outcomes; nothing is assigned independently at random):
  master data -> completions + assessments -> eligibility from CredentialRule ->
  credentials (only if rules pass) -> revocations/reversals -> verification requests
  -> labelled anomaly injection -> hash-chained audit log -> ground truth.
"""
import argparse
import csv
import hashlib
import itertools
import json
import os
import random
import sys
from datetime import date, datetime, timedelta

import credential_logic as L
import schema as S

DEFAULTS = {"learners": 20000, "courses": 1000, "credentials": 10000, "verifications": 5000}

FIRST = ["James", "Mary", "Wei", "Priya", "Mohammed", "Sofia", "Liam", "Olivia", "Noah", "Emma", "Arjun",
         "Fatima", "Carlos", "Anna", "Ahmed", "Yuki", "Hiroshi", "Elena", "Ivan", "Chloe", "Daniel", "Aisha",
         "Lucas", "Mei", "Ravi", "Sara", "Omar", "Julia", "Thomas", "Nina", "Kofi", "Amara", "Diego", "Lena",
         "Samuel", "Hana", "Pedro", "Zara", "Victor", "Ingrid", "Raj", "Layla", "Marco", "Tara", "Felix",
         "Nadia", "Oscar", "Bella", "Kenji", "Isabel", "Hassan", "Clara", "Arun", "Grace", "Tariq", "Mina",
         "Jonas", "Leila", "Andre", "Sana"]
LAST = ["Smith", "Johnson", "Wang", "Patel", "Khan", "Garcia", "Brown", "Kim", "Singh", "Nguyen", "Silva",
        "Mueller", "Rossi", "Ivanov", "Tanaka", "Ali", "Lopez", "Martin", "Cohen", "Okafor", "Reddy", "Chen",
        "Hernandez", "Jones", "Fernandez", "Sato", "Kumar", "Popov", "Dubois", "Andersen", "Costa", "Haddad",
        "Yamamoto", "Novak", "Mensah", "Sharma", "Moreau", "Larsen", "Gupta", "Bianchi", "Schmidt", "Lee",
        "Ortiz", "Rahman", "Petrov", "Santos", "Olsen", "Mehta", "Ito", "Costa", "Walker", "Young", "Iyer",
        "Murphy", "Jansen", "Bose", "Varga", "Diaz", "Nair", "Fischer"]
_FP = ["Ka", "Ma", "Sa", "Ra", "Da", "Le", "Jo", "Mi", "Al", "El", "No", "Vi", "Ta", "Be", "Ro", "Ni", "Ha", "Zo", "Lu", "Ge"]
_FS = ["ran", "dan", "lia", "mir", "tan", "ven", "sel", "rik", "bel", "nor", "dro", "mal", "tia", "ven", "lor"]
_LP = ["Ber", "Hal", "Kor", "Mon", "Tor", "Wen", "Sal", "Dun", "Pel", "Rav", "Gor", "Lin", "Mar", "Tay", "Vas", "Bro", "Cal", "Fen", "Har", "Jen"]
_LS = ["ton", "son", "berg", "ley", "ford", "man", "wick", "dale", "ström", "ova", "ini", "ez", "ski", "well", "ham"]
FIRST = FIRST + sorted({a + b for a in _FP for b in _FS})
LAST = LAST + sorted({(a + b).replace("ö", "o") for a in _LP for b in _LS})
COUNTRIES = ["US", "IN", "GB", "CA", "AU", "DE", "SG", "BR", "NG", "FR", "JP", "ZA"]
COUNTRY_W = [22, 20, 10, 8, 6, 6, 4, 6, 5, 4, 4, 5]

CATEGORIES = {
    "Data & Analytics": ["Data Analysis", "SQL Databases", "Machine Learning", "Data Visualization", "Statistics", "Big Data Pipelines", "Business Intelligence", "Applied AI"],
    "Software Engineering": ["Python Programming", "Web Development", "Cloud Computing", "DevOps Practice", "Software Testing", "API Design", "Mobile Development", "Systems Design"],
    "Cybersecurity": ["Network Security", "Secure Coding", "Risk Management", "Incident Response", "Cloud Security", "Identity Management", "Digital Forensics", "Security Governance"],
    "Business & Management": ["Project Management", "Agile Delivery", "Financial Analysis", "Operations Management", "Product Strategy", "Leadership Skills", "Supply Chain Basics", "Marketing Analytics"],
    "Healthcare": ["Clinical Documentation", "Health Informatics", "Patient Safety", "Medical Coding", "Public Health Basics", "Healthcare Compliance", "Telehealth Practice", "Nursing Leadership"],
    "Design & Media": ["UX Research", "Interface Design", "Digital Marketing", "Content Strategy", "Video Production", "Brand Design", "Accessibility Design", "Motion Graphics"],
    "Engineering & Trades": ["CAD Fundamentals", "Industrial Safety", "Renewable Energy", "Quality Assurance", "Electrical Systems", "Lean Manufacturing", "Construction Planning", "Robotics Basics"],
    "Languages & Communication": ["Business English", "Technical Writing", "Public Speaking", "Translation Basics", "Negotiation Skills", "Intercultural Communication", "Academic Writing", "Presentation Skills"],
}
LEVEL_SUFFIX = {"BEGINNER": "Fundamentals", "INTERMEDIATE": "Applied", "ADVANCED": "Advanced"}

BASE_ISSUERS = [("Northbridge University", "UNIVERSITY", "US"),
                ("Meridian Institute of Technology", "UNIVERSITY", "GB"),
                ("Lakeshore Training Academy", "TRAINING_PROVIDER", "CA"),
                ("Global Data Professionals Association", "PROFESSIONAL_BODY", "US"),
                ("Southern Cross College", "UNIVERSITY", "AU"),
                ("Brightpath Learning", "TRAINING_PROVIDER", "IN"),
                ("Eurotech Skills Council", "PROFESSIONAL_BODY", "DE"),
                ("Ridgeway Polytechnic", "UNIVERSITY", "SG")]
# index in BASE_ISSUERS -> (successor name, type, country, last day of predecessor)
SUCCESSIONS = {2: ("Lakeshore-Meridian Academy", "TRAINING_PROVIDER", "CA", date(2026, 3, 15)),
               4: ("Southern Cross University Group", "UNIVERSITY", "AU", date(2026, 5, 1)),
               5: ("Brightpath Global Learning", "TRAINING_PROVIDER", "IN", date(2026, 6, 30)),
               7: ("Ridgeway-Nanyang Polytechnic", "UNIVERSITY", "SG", date(2026, 8, 15))}
TRANSFER_DEST = [0, 1, 3, 6]  # issuers that stay ACTIVE all year

ORGS = ["Apex Talent Partners", "BlueRiver Staffing", "Cobalt Systems", "Delta Hiring Group", "Evergreen Health Trust",
        "Frontier Bank HR", "Granite Consulting", "Horizon University Admissions", "Ionic Labs", "Juniper Retail",
        "Keystone Logistics", "Lumen Analytics", "Maple Government Services", "Nimbus Cloud Co", "Orchid Pharma",
        "Pinnacle Verify", "Quartz Engineering", "Redwood College Registry", "Summit BG Checks", "Tidewater Energy",
        "Unity Public Sector", "Vertex Recruiters", "Willow Software", "Xenon Manufacturing", "Yellowstone Careers",
        "Zenith Credential Services"]


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def rand_ts(rng, d, lo, hi):
    return datetime(d.year, d.month, d.day, rng.randint(lo, hi), rng.randint(0, 59), rng.randint(0, 59))


def rand_date(rng, a, b):
    return a + timedelta(days=rng.randint(0, (b - a).days))


def dstr(d):
    return d.isoformat() if d else None


# =============================================================================== BUILD
def build(p):
    rng = random.Random(p["seed"])
    seed = p["seed"]
    as_of = date.fromisoformat(p["as_of"])
    as_end = datetime(as_of.year, as_of.month, as_of.day, 23, 59, 59)
    as_end_s = L.ts_str(as_end)
    audit = []

    def ev(dt, entity_type, entity_id, event_type, actor_type, actor_id, old, new, details):
        audit.append({"event_ts": L.ts_str(dt), "entity_type": entity_type, "entity_id": entity_id,
                      "event_type": event_type, "actor_type": actor_type, "actor_id": actor_id,
                      "old_state": old, "new_state": new, "details_json": L.canonical_json(details)})

    # ---------------------------------------------------------------- actors
    actors = [{"actor_id": "ACT-0000", "display_name": "Credential Service", "role": "SYSTEM",
               "email": "system@example.org", "status": "ACTIVE"}]
    n = 1
    for role, cnt in [("INSTRUCTOR", 30), ("ACADEMIC_ADMIN", 10), ("SUPPORT_STAFF", 12), ("PLATFORM_ADMIN", 4)]:
        for _ in range(cnt):
            f, l = rng.choice(FIRST), rng.choice(LAST)
            actors.append({"actor_id": f"ACT-{n:04d}", "display_name": f"{f} {l}", "role": role,
                           "email": f"staff{n:04d}@example.org", "status": "ACTIVE" if rng.random() > 0.05 else "INACTIVE"})
            n += 1
    by_role = {}
    for a in actors:
        by_role.setdefault(a["role"], []).append(a["actor_id"])

    # ---------------------------------------------------------------- issuers (+ issuer changes)
    issuers, succ_of = [], {}
    keys = {}
    for i, (name, typ, ctry) in enumerate(BASE_ISSUERS):
        iid = f"ISS-{i + 1:03d}"
        sw = SUCCESSIONS.get(i)
        issuers.append({"issuer_id": iid, "issuer_name": name, "issuer_type": typ, "country": ctry,
                        "status": "SUPERSEDED" if sw else "ACTIVE", "effective_from": "2018-01-01",
                        "effective_to": dstr(sw[3]) if sw else None, "predecessor_issuer_id": None,
                        "signing_key_id": f"{iid}-K1", "key_fingerprint": None})
    nxt = len(BASE_ISSUERS) + 1
    for i in sorted(SUCCESSIONS):
        name, typ, ctry, last_day = SUCCESSIONS[i]
        iid = f"ISS-{nxt:03d}"
        succ_of[i] = iid
        issuers.append({"issuer_id": iid, "issuer_name": name, "issuer_type": typ, "country": ctry,
                        "status": "ACTIVE", "effective_from": dstr(last_day + timedelta(days=1)),
                        "effective_to": None, "predecessor_issuer_id": f"ISS-{i + 1:03d}",
                        "signing_key_id": f"{iid}-K1", "key_fingerprint": None})
        nxt += 1
    for r in issuers:
        k = L.issuer_signing_key(seed, r["issuer_id"])
        keys[r["issuer_id"]] = k
        r["key_fingerprint"] = L.key_fingerprint(k)

    # ---------------------------------------------------------------- courses + issuer history + rules
    courses, history, rules = [], [], []
    hist_by_course, rules_by_course = {}, {}
    cat_names = sorted(CATEGORIES)
    hid, rid = 1, 1
    for ci in range(p["courses"]):
        cid = f"CRS-{ci + 1:04d}"
        cat = rng.choice(cat_names)
        topic = rng.choice(CATEGORIES[cat])
        level = rng.choices(S.LEVELS, [45, 35, 20])[0]
        lo, hi = {"BEGINNER": (8, 30), "INTERMEDIATE": (20, 60), "ADVANCED": (40, 120)}[level]
        hours = rng.randint(lo, hi)
        eff_from = rand_date(rng, date(2024, 1, 1), date(2025, 2, 1))
        retired = rng.random() < 0.03
        eff_to = rand_date(rng, date(2026, 8, 1), date(2026, 9, 30)) if retired else None
        n_ass = rng.randint(3, 5)
        base_idx = rng.choices(range(len(BASE_ISSUERS)), [16, 16, 6, 16, 6, 6, 16, 6])[0]
        h = []
        if base_idx in SUCCESSIONS:
            last_day = SUCCESSIONS[base_idx][3]
            h.append((f"ISS-{base_idx + 1:03d}", eff_from, last_day, "INITIAL"))
            h.append((succ_of[base_idx], last_day + timedelta(days=1), None, "ISSUER_SUCCESSION"))
        elif rng.random() < 0.04:
            dest = rng.choice([x for x in TRANSFER_DEST if x != base_idx])
            sw_day = rand_date(rng, date(2025, 6, 1), date(2026, 8, 31))
            h.append((f"ISS-{base_idx + 1:03d}", eff_from, sw_day, "INITIAL"))
            h.append((f"ISS-{dest + 1:03d}", sw_day + timedelta(days=1), None, "ISSUER_TRANSFER"))
        else:
            h.append((f"ISS-{base_idx + 1:03d}", eff_from, None, "INITIAL"))
        hist_by_course[cid] = h
        for (iss, f, t, why) in h:
            history.append({"history_id": f"CIH-{hid:06d}", "course_id": cid, "issuer_id": iss,
                            "effective_from": dstr(f), "effective_to": dstr(t), "change_reason": why})
            hid += 1
            if why != "INITIAL":
                ev(L.parse_ts(f"{f.isoformat()}T09:00:00Z"), "Course", cid, "ISSUER_CHANGED", "STAFF",
                   rng.choice(by_role["PLATFORM_ADMIN"]), h[0][0], iss, {"reason": why})
        courses.append({"course_id": cid, "title": f"{topic} {LEVEL_SUFFIX[level]}", "category": cat, "level": level,
                        "credit_hours": hours, "duration_days": int(14 + 0.8 * hours), "num_assessments": n_ass,
                        "instructor_id": rng.choice(by_role["INSTRUCTOR"]), "issuer_id": h[-1][0],
                        "status": "RETIRED" if retired else "ACTIVE", "effective_from": dstr(eff_from),
                        "effective_to": dstr(eff_to)})
        # rules (v1, and v2 for 10% of courses with a stricter score from 2025-11-01)
        min_score = rng.choice({"BEGINNER": [60, 65, 70], "INTERMEDIATE": [65, 70, 75], "ADVANCED": [70, 75, 80]}[level])
        att = rng.choices([0, 70, 80], [40, 35, 25])[0]
        val = rng.choices([None, 6, 12, 24, 36, 60], [40, 8, 15, 17, 12, 8])[0]
        has_v2 = rng.random() < 0.10
        r1 = {"rule_id": f"RUL-{rid:04d}", "course_id": cid, "rule_version": 1, "min_progress_pct": 100,
              "min_assessments": n_ass, "min_final_score": min_score, "min_attendance_pct": att,
              "validity_months": val, "effective_from": dstr(eff_from),
              "effective_to": "2025-10-31" if has_v2 else dstr(eff_to),
              "status": "SUPERSEDED" if has_v2 else ("RETIRED" if retired else "ACTIVE")}
        rid += 1
        rl = [r1]
        if has_v2:
            rl.append({"rule_id": f"RUL-{rid:04d}", "course_id": cid, "rule_version": 2, "min_progress_pct": 100,
                       "min_assessments": n_ass, "min_final_score": min_score + 5, "min_attendance_pct": att,
                       "validity_months": val, "effective_from": "2025-11-01", "effective_to": dstr(eff_to),
                       "status": "RETIRED" if retired else "ACTIVE"})
            rid += 1
        for r in rl:
            rules.append(r)
            ev(L.parse_ts(f"{r['effective_from']}T12:00:00Z"), "CredentialRule", r["rule_id"], "RULE_PUBLISHED",
               "STAFF", rng.choice(by_role["ACADEMIC_ADMIN"]), None, "ACTIVE",
               {"course_id": cid, "min_final_score": r["min_final_score"], "rule_version": r["rule_version"]})
        rules_by_course[cid] = rl
    course_by_id = {c["course_id"]: c for c in courses}

    def issuer_on(course_id, d):
        for (iss, f, t, _) in hist_by_course[course_id]:
            if f <= d and (t is None or d <= t):
                return iss
        raise ValueError(f"no issuer for {course_id} on {d}")

    def rule_on(course_id, d):
        ds = d.isoformat()
        for r in rules_by_course[course_id]:
            if r["effective_from"] <= ds and (r["effective_to"] is None or ds <= r["effective_to"]):
                return r
        return rules_by_course[course_id][-1]

    # ---------------------------------------------------------------- learners (duplicate names on purpose)
    fw = list(itertools.accumulate(1 / (i + 1) ** 0.30 for i in range(len(FIRST))))
    lw = list(itertools.accumulate(1 / (i + 1) ** 0.30 for i in range(len(LAST))))
    cw = list(itertools.accumulate(COUNTRY_W))
    learners, ability = [], {}
    for li in range(p["learners"]):
        lid = f"LRN-{li + 1:06d}"
        if learners and rng.random() < 0.04:  # forced duplicate full name (different person)
            src = rng.choice(learners)
            first, last = src["first_name"], src["last_name"]
        else:
            first = rng.choices(FIRST, cum_weights=fw)[0]
            last = rng.choices(LAST, cum_weights=lw)[0]
        dob = rand_date(rng, date(1960, 1, 1), date(2005, 12, 31))
        learners.append({"learner_id": lid, "first_name": first, "last_name": last,
                         "full_name": f"{first} {last}",
                         "email": f"{first}.{last}.{li + 1}@example.org".lower(),
                         "date_of_birth": dstr(dob), "country": rng.choices(COUNTRIES, cum_weights=cw)[0],
                         "status": rng.choices(["ACTIVE", "SUSPENDED", "CLOSED"], [97, 2, 1])[0],
                         "created_at": dstr(rand_date(rng, date(2024, 6, 1), date(2025, 12, 31)))})
        ability[lid] = rng.gauss(0, 1)
    learner_by_id = {l["learner_id"]: l for l in learners}

    # ---------------------------------------------------------------- completions + assessments
    pop_order = list(range(len(courses)))
    rng.shuffle(pop_order)
    pop_w = [0.0] * len(courses)
    for rank, idx in enumerate(pop_order):
        pop_w[idx] = 1 / (rank + 1) ** 0.45
    cum_pop = list(itertools.accumulate(pop_w))
    course_ids = [c["course_id"] for c in courses]
    level_off = {"BEGINNER": 0, "INTERMEDIATE": 4, "ADVANCED": 8}
    completions, assessments = [], []
    asm_n = 1
    enroll_lo, enroll_hi = date(2025, 3, 1), min(date(2026, 10, 15), as_of - timedelta(days=7))
    for l in learners:
        lid = l["learner_id"]
        a = ability[lid]
        created = date.fromisoformat(l["created_at"])
        k = rng.choices([1, 2, 3, 4, 5], [35, 30, 20, 10, 5])[0]
        chosen, tries = [], 0
        while len(chosen) < k and tries < 25:
            tries += 1
            c = rng.choices(course_ids, cum_weights=cum_pop)[0]
            if c not in chosen:
                chosen.append(c)
        for cid in chosen:
            course = course_by_id[cid]
            n_ass = course["num_assessments"]
            enrolled = rand_date(rng, max(created, enroll_lo), enroll_hi)
            if course["effective_to"] and enrolled > date.fromisoformat(course["effective_to"]):
                enrolled = rand_date(rng, max(created, enroll_lo), date.fromisoformat(course["effective_to"]))
            rule = rule_on(cid, enrolled)
            span = max(1, round(course["duration_days"] * rng.uniform(0.8, 1.6)))
            end = enrolled + timedelta(days=span)
            attendance = round(clamp(rng.gauss(91 + 3 * a, 7), 40, 100), 1)
            base = 82 + 8 * a - level_off[course["level"]]
            boundary = None
            status, progress, taken, closed = None, 0, 0, None
            if end > as_of - timedelta(days=3):
                status = "IN_PROGRESS"
                frac = clamp((as_of - enrolled).days / span, 0.05, 0.95)
                progress, taken, a_end = int(frac * 100), int(frac * n_ass), as_of
            elif rng.random() < clamp(0.14 - 0.04 * a, 0.03, 0.30):
                status = "WITHDRAWN"
                frac = rng.uniform(0.1, 0.9)
                closed = enrolled + timedelta(days=max(1, round(span * frac)))
                progress, taken, a_end = int(frac * 100), int(frac * n_ass), closed
            else:
                progress, closed, a_end = 100, end, end
                taken = n_ass - 1 if rng.random() < 0.03 else n_ass
                if taken == n_ass and rng.random() < 0.025:
                    boundary = rng.choice(["AT", "BELOW"])
                    attendance = max(attendance, float(rule["min_attendance_pct"]))
            comp_id = f"CMP-{lid}-{cid}"
            scores = []
            for s in range(taken):
                if boundary == "AT":
                    scores.append(rule["min_final_score"])
                elif boundary == "BELOW":
                    scores.append(rule["min_final_score"] - 1)
                else:
                    scores.append(int(clamp(round(base + rng.gauss(0, 7)), 0, 100)))
            if taken:
                days = sorted(rand_date(rng, enrolled, max(enrolled, a_end)) for _ in range(taken))
                if status is None:
                    days[-1] = a_end
            for s, sc in enumerate(scores):
                atype = "FINAL_EXAM" if s == n_ass - 1 else ("PROJECT" if s == n_ass - 2 else "QUIZ")
                assessments.append({"assessment_id": f"AST-{asm_n:07d}", "completion_id": comp_id,
                                    "sequence_no": s + 1, "assessment_type": atype, "score": sc,
                                    "max_score": 100, "taken_at": dstr(days[s])})
                asm_n += 1
            final = round(sum(scores) / len(scores), 2) if scores else None
            met, reasons = False, []
            failure = None
            if status is None:  # coursework finished -> rule decides COMPLETED vs FAILED
                met, reasons = L.evaluate_rule(rule, progress, taken, final, attendance)
                status = "COMPLETED" if met else "FAILED"
                failure = "|".join(reasons) if reasons else None
            completions.append({"completion_id": comp_id, "learner_id": lid, "course_id": cid,
                                "rule_id": rule["rule_id"], "enrolled_at": dstr(enrolled),
                                "closed_at": dstr(closed), "completed_at": dstr(closed) if status == "COMPLETED" else None,
                                "status": status, "progress_pct": progress, "assessments_taken": taken,
                                "final_score": final, "attendance_pct": attendance,
                                "requirements_met": 1 if met else 0, "failure_reasons": failure})
            ev(rand_ts(rng, enrolled, 8, 22), "CompletionRecord", comp_id, "LEARNER_ENROLLED", "LEARNER", lid,
               None, "IN_PROGRESS", {"course_id": cid, "rule_id": rule["rule_id"]})
            if closed:
                ev(rand_ts(rng, closed, 1, 5), "CompletionRecord", comp_id, "COMPLETION_STATE_CHANGED", "SYSTEM",
                   "ACT-0000", "IN_PROGRESS", status, {"final_score": final, "requirements_met": int(met)})
    comp_by_id = {c["completion_id"]: c for c in completions}
    rule_by_id = {r["rule_id"]: r for r in rules}

    # ---------------------------------------------------------------- credential selection
    n_total = p["credentials"]
    k_a = max(2, round(0.010 * n_total))   # issued before completion / rule not met
    k_d = max(2, round(0.004 * n_total))   # duplicate credential IDs
    n_base = n_total - k_a - k_d
    cutoff = as_of - timedelta(days=14)
    pool = sorted([c for c in completions if c["status"] == "COMPLETED" and date.fromisoformat(c["completed_at"]) <= cutoff],
                  key=lambda c: c["completion_id"])
    rng.shuffle(pool)
    if len(pool) < n_base + k_d + k_a:
        sys.exit(f"Not enough eligible completions ({len(pool)}) for {n_total} credentials; raise --learners.")
    base_comps = pool[:n_base]
    dup_comps = pool[n_base:n_base + k_d]
    remain = pool[n_base + k_d:]
    a1_n = round(k_a * 0.7)
    a1 = [c for c in remain if date.fromisoformat(c["completed_at"]) >= date(2026, 2, 15)
          and (date.fromisoformat(c["completed_at"]) - date.fromisoformat(c["enrolled_at"])).days >= 1][:a1_n]
    bad_pool = sorted([c for c in completions if c["status"] != "COMPLETED"
                       and date.fromisoformat(c["enrolled_at"]) <= as_of - timedelta(days=1)],
                      key=lambda c: c["completion_id"])
    a2 = rng.sample(bad_pool, k_a - len(a1))

    jan1 = date(2026, 1, 1)

    def normal_issue_dt(comp):
        d = date.fromisoformat(comp["completed_at"]) + timedelta(days=rng.choices([0, 1, 2, 3, 5, 7, 10, 14], [20, 25, 15, 10, 10, 8, 7, 5])[0])
        if d < jan1:
            d = jan1 + timedelta(days=rng.randint(0, 20))
        d = min(d, as_of)
        return rand_ts(rng, d, 8, 20)

    def make_cred(comp, issued_dt, cred_id):
        rule = rule_by_id[comp["rule_id"]]
        iss = issuer_on(comp["course_id"], issued_dt.date())
        exp = None
        if rule["validity_months"]:
            exp = datetime.combine(L.add_months(issued_dt.date(), rule["validity_months"]), issued_dt.time())
        row = {"credential_id": cred_id, "completion_id": comp["completion_id"], "learner_id": comp["learner_id"],
               "course_id": comp["course_id"], "rule_id": comp["rule_id"], "issuer_id": iss,
               "issued_at": L.ts_str(issued_dt), "expires_at": L.ts_str(exp) if exp else None}
        row["payload_json"] = L.build_payload(row)
        row["payload_hash"] = L.sha256_hex(row["payload_json"])
        row["hash_algo"] = L.HASH_ALGO
        row["signature"] = L.sign_hash(keys[iss], row["payload_hash"])
        row["signature_alg"] = L.SIGNATURE_ALGO
        row["signing_key_id"] = f"{iss}-K1"
        row["status"] = None
        row["status_as_of"] = p["as_of"]
        return row

    drafts = []  # (issued_dt, completion, anomaly_variant)
    for c in base_comps:
        drafts.append((normal_issue_dt(c), c, None))
    for c in a1:  # issued N days BEFORE the completion date
        comp_d = date.fromisoformat(c["completed_at"])
        gap = rng.randint(1, min(30, (comp_d - date.fromisoformat(c["enrolled_at"])).days))
        drafts.append((rand_ts(rng, comp_d - timedelta(days=gap), 8, 20), c, "BEFORE_COMPLETION_DATE"))
    for c in a2:  # issued although the completion never met the rule
        lo = max(date.fromisoformat(c["enrolled_at"]), jan1)
        drafts.append((rand_ts(rng, rand_date(rng, lo, as_of), 8, 20), c, "RULE_NOT_MET:" + c["status"]))
    drafts.sort(key=lambda t: (L.ts_str(t[0]), t[1]["completion_id"]))
    counters, credentials, anomalies = {}, [], []
    base_cred_rows = []
    for issued_dt, comp, variant in drafts:
        y = issued_dt.year
        counters[y] = counters.get(y, 0) + 1
        row = make_cred(comp, issued_dt, f"CRD-{y}-{counters[y]:06d}")
        credentials.append(row)
        if variant:
            anomalies.append(("CREDENTIAL_ISSUED_BEFORE_COMPLETION", row, variant))
        else:
            base_cred_rows.append(row)
    # duplicate credential IDs (collision) - a different, otherwise valid completion
    dup_sources = rng.sample(base_cred_rows, len(dup_comps))
    dup_ids = set()
    for comp, src in zip(dup_comps, dup_sources):
        row = make_cred(comp, normal_issue_dt(comp), src["credential_id"])
        credentials.append(row)
        dup_ids.add(src["credential_id"])
        anomalies.append(("DUPLICATE_CREDENTIAL_ID", row, "ID_COLLISION"))
    credentials.sort(key=lambda r: (r["issued_at"], r["credential_id"], r["completion_id"]))

    # ---------------------------------------------------------------- revocations (+ reversal / re-revocation)
    lifecycle = {}
    revocations = []
    eligible_rev = [r for r in base_cred_rows if r["credential_id"] not in dup_ids
                    and L.parse_ts(r["issued_at"]) <= as_end - timedelta(days=2)]
    n_rev = round(0.06 * len(base_cred_rows))
    revoked_rows = rng.sample(eligible_rev, min(n_rev, len(eligible_rev)))
    reason_role = {"ISSUED_IN_ERROR": "ACADEMIC_ADMIN", "ACADEMIC_MISCONDUCT": "ACADEMIC_ADMIN",
                   "LEARNER_REQUEST": "SUPPORT_STAFF", "FRAUD": "PLATFORM_ADMIN",
                   "POLICY_VIOLATION": "ACADEMIC_ADMIN", "COURSE_RETIRED": "PLATFORM_ADMIN"}
    reasons_l = list(reason_role)

    def add_rev(row, seq, when, reason):
        actor = rng.choice(by_role[reason_role[reason]])
        revocations.append({"revocation_id": f"REV-{row['credential_id']}-{seq:02d}", "credential_id": row["credential_id"],
                            "revocation_seq": seq, "revoked_at": L.ts_str(when), "reason_code": reason,
                            "revoked_by_actor_id": actor})
        return actor

    pending_events = []
    for row in revoked_rows:
        cid = row["credential_id"]
        issued = L.parse_ts(row["issued_at"])
        span = (as_end - issued - timedelta(days=1)).total_seconds()
        when = issued + timedelta(days=1, seconds=int(span * rng.random() ** 1.5))
        reason = rng.choices(reasons_l, [25, 20, 20, 15, 10, 10])[0]
        actor = add_rev(row, 1, when, reason)
        lifecycle.setdefault(cid, []).append((L.ts_str(when), "CREDENTIAL_REVOKED"))
        pending_events.append((when, row, "CREDENTIAL_REVOKED", "STAFF", actor, reason, f"REV-{cid}-01"))
        if rng.random() < 0.06:
            rev_at = when + timedelta(days=rng.randint(3, 60), seconds=rng.randint(0, 80000))
            if rev_at <= as_end:
                lifecycle[cid].append((L.ts_str(rev_at), "REVOCATION_REVERSED"))
                pending_events.append((rev_at, row, "REVOCATION_REVERSED", "STAFF", rng.choice(by_role["ACADEMIC_ADMIN"]),
                                       "REINSTATED", f"REV-{cid}-01"))
                if rng.random() < 0.35:
                    when2 = rev_at + timedelta(days=rng.randint(2, 60), seconds=rng.randint(0, 80000))
                    if when2 <= as_end:
                        reason2 = rng.choice(reasons_l)
                        actor2 = add_rev(row, 2, when2, reason2)
                        lifecycle[cid].append((L.ts_str(when2), "CREDENTIAL_REVOKED"))
                        pending_events.append((when2, row, "CREDENTIAL_REVOKED", "STAFF", actor2, reason2, f"REV-{cid}-02"))
    for cid in lifecycle:
        lifecycle[cid].sort()
    revocations.sort(key=lambda r: (r["revoked_at"], r["revocation_id"]))

    # credential current status (replayed) + credential audit events
    for row in credentials:
        cid = row["credential_id"]
        lc = lifecycle.get(cid, []) if cid not in dup_ids else []
        row["status"] = L.effective_status(lc, row["expires_at"], as_end_s)
        ev(L.parse_ts(row["issued_at"]), "Credential", cid, "CREDENTIAL_ISSUED", "SYSTEM", "ACT-0000", None, "ACTIVE",
           {"completion_id": row["completion_id"], "issuer_id": row["issuer_id"]})
        if row["expires_at"] and row["expires_at"] <= as_end_s and not L.revoked_at_time(lc, row["expires_at"]):
            ev(L.parse_ts(row["expires_at"]), "Credential", cid, "CREDENTIAL_EXPIRED", "SYSTEM", "ACT-0000",
               "ACTIVE", "EXPIRED", {})
    cred_by_unique = {r["credential_id"]: r for r in credentials if r["credential_id"] not in dup_ids}
    for (when, row, etype, atype, actor, reason, rev_id) in pending_events:
        cid = row["credential_id"]
        if etype == "CREDENTIAL_REVOKED":
            lc_before = [e for e in lifecycle[cid] if e[0] < L.ts_str(when)]
            old = L.effective_status(lc_before, row["expires_at"], L.ts_str(when))
            ev(when, "Credential", cid, etype, atype, actor, old, "REVOKED", {"revocation_id": rev_id, "reason_code": reason})
        else:
            lc_upto = [e for e in lifecycle[cid] if e[0] <= L.ts_str(when)]
            new = L.effective_status(lc_upto, row["expires_at"], L.ts_str(when))
            ev(when, "Credential", cid, etype, atype, actor, "REVOKED", new, {"revocation_id": rev_id, "reason_code": reason})

    # ---------------------------------------------------------------- verification requests
    ctx = L.VerificationContext(credentials, learner_by_id, lifecycle, seed)
    verifiable = [r for r in credentials if r["credential_id"] not in dup_ids]
    revoked_creds = [cred_by_unique[r["credential_id"]] for r in revoked_rows]
    name_groups = {}
    for l in learners:
        name_groups.setdefault(l["full_name"], []).append(l["learner_id"])
    twin_creds = [r for r in verifiable if len(name_groups[learner_by_id[r["learner_id"]]["full_name"]]) > 1]
    scen_names = ["GENERAL", "REVOKED_TARGET", "NAME_VARIANT", "NAME_ONLY", "IMPOSTOR_SAME_NAME", "TAMPERED_HASH", "UNKNOWN_ID"]
    scen_w = [66, 14, 6, 4, 4, 3, 3]
    max_seq = {y: c for y, c in counters.items()}
    reqs = []
    for _ in range(p["verifications"]):
        sc = rng.choices(scen_names, scen_w)[0]
        if sc == "REVOKED_TARGET" and not revoked_creds:
            sc = "GENERAL"
        if sc == "IMPOSTOR_SAME_NAME" and not twin_creds:
            sc = "GENERAL"
        cred = None
        if sc == "UNKNOWN_ID":
            y = rng.choice(sorted(max_seq))
            cid = f"CRD-{y}-{max_seq[y] + rng.randint(1000, 90000):06d}"
            t = rand_ts(rng, rand_date(rng, jan1, as_of), 0, 23)
        else:
            cred = rng.choice(revoked_creds if sc == "REVOKED_TARGET" else twin_creds if sc == "IMPOSTOR_SAME_NAME" else verifiable)
            cid = cred["credential_id"]
            issued = L.parse_ts(cred["issued_at"])
            f = rng.random() if sc == "REVOKED_TARGET" else rng.random() ** 1.4
            t = issued + timedelta(seconds=int((as_end - issued).total_seconds() * f))
        req = {"credential_id": cid, "requested_at": L.ts_str(t), "_scenario": sc,
               "requester_type": rng.choices(S.REQUESTER_TYPES, [50, 20, 15, 10, 5])[0],
               "requester_org": rng.choice(ORGS), "channel": rng.choices(S.CHANNELS, [45, 40, 15])[0],
               "claimed_name": None, "claimed_dob": None, "claimed_email_hash": None, "presented_payload_hash": None}
        if cred:
            lrn = learner_by_id[cred["learner_id"]]
            req["claimed_name"] = lrn["full_name"]
            req["claimed_dob"] = lrn["date_of_birth"]
            req["claimed_email_hash"] = L.sha256_hex(lrn["email"].lower())
            if rng.random() < 0.70:
                req["presented_payload_hash"] = cred["payload_hash"]
            if sc == "NAME_VARIANT":
                req["claimed_name"] = rng.choice([f"{lrn['first_name'][0]}. {lrn['last_name']}",
                                                  f"{lrn['last_name']}, {lrn['first_name']}", lrn["full_name"].upper()])
            elif sc == "NAME_ONLY":
                req["claimed_dob"], req["claimed_email_hash"] = None, None
            elif sc == "IMPOSTOR_SAME_NAME":  # same NAME, other person's DOB/email
                twins = [x for x in name_groups[lrn["full_name"]] if x != lrn["learner_id"]]
                tw = learner_by_id[rng.choice(twins)]
                req["claimed_dob"], req["claimed_email_hash"] = tw["date_of_birth"], L.sha256_hex(tw["email"].lower())
            elif sc == "TAMPERED_HASH":
                req["presented_payload_hash"] = L.tamper_hash(cred["payload_hash"])
        else:  # unknown id: requester still supplies a plausible identity
            lrn = rng.choice(learners)
            req["claimed_name"], req["claimed_dob"] = lrn["full_name"], lrn["date_of_birth"]
            req["claimed_email_hash"] = L.sha256_hex(lrn["email"].lower())
        reqs.append(req)
    reqs.sort(key=lambda r: (r["requested_at"], r["credential_id"]))
    vcount = {}
    for r in reqs:
        y = int(r["requested_at"][:4])
        vcount[y] = vcount.get(y, 0) + 1
        r["verification_id"] = f"VER-{y}-{vcount[y]:06d}"
        r["expected"] = ctx.verify(r)

    # inject verification anomalies (labelled; the recorded result is wrong on purpose)
    k_rv = max(2, round(0.005 * p["verifications"]))
    k_th = max(2, round(0.005 * p["verifications"]))
    rv_idx = [i for i, r in enumerate(reqs) if r["expected"] == "REVOKED"]
    th_idx = [i for i, r in enumerate(reqs) if r["_scenario"] == "TAMPERED_HASH" and r["expected"] == "HASH_MISMATCH"]
    inj = {}
    for i in rng.sample(rv_idx, min(k_rv, len(rv_idx))):
        inj[i] = "REVOKED_CREDENTIAL_VERIFIES_AS_ACTIVE"
    for i in rng.sample(th_idx, min(k_th, len(th_idx))):
        inj[i] = "ALTERED_PAYLOAD_HASH_NOT_DETECTED"
    verifications = []
    for i, r in enumerate(reqs):
        recorded = "VALID" if i in inj else r["expected"]
        r["recorded"] = recorded
        ms = int(clamp(rng.lognormvariate(5.0, 0.5), 10, 5000))
        verifications.append({"verification_id": r["verification_id"], "credential_id": r["credential_id"],
                              "requested_at": r["requested_at"], "requester_type": r["requester_type"],
                              "requester_org": r["requester_org"], "channel": r["channel"],
                              "claimed_name": r["claimed_name"], "claimed_dob": r["claimed_dob"],
                              "claimed_email_hash": r["claimed_email_hash"],
                              "presented_payload_hash": r["presented_payload_hash"],
                              "result": recorded, "result_detail": L.RESULT_DETAIL[recorded], "response_ms": ms})
        ev(L.parse_ts(r["requested_at"]), "VerificationRequest", r["verification_id"], "VERIFICATION_PERFORMED",
           "EXTERNAL_VERIFIER", r["requester_org"], None, recorded, {"credential_id": r["credential_id"], "channel": r["channel"]})

    # ---------------------------------------------------------------- audit log (immutable, hash-chained)
    audit.sort(key=lambda e: (e["event_ts"], e["entity_type"], e["entity_id"], e["event_type"], e["new_state"] or ""))
    prev = "0" * 64
    for i, e in enumerate(audit):
        e["audit_event_id"] = f"AUD-{i + 1:08d}"
        e["prev_event_hash"] = prev
        e["event_hash"] = L.sha256_hex("|".join([prev, e["audit_event_id"], e["event_ts"], e["entity_type"], e["entity_id"],
                                                  e["event_type"], e["actor_type"], e["actor_id"], e["old_state"] or "",
                                                  e["new_state"] or "", e["details_json"]]))
        prev = e["event_hash"]

    # ---------------------------------------------------------------- ground truth (SEPARATE FILE)
    gt = []

    def add_gt(etype, eid, ref, anomaly, issue, variant, expected, recorded, scenario, rule):
        gt.append({"gt_id": f"GT-{len(gt) + 1:06d}", "entity_type": etype, "entity_id": eid, "row_ref": ref,
                   "is_anomaly": 1 if anomaly else 0, "issue_type": issue, "variant": variant,
                   "expected_value": expected, "recorded_value": recorded, "scenario": scenario, "rule_reference": rule})

    for issue, row, variant in anomalies:
        if issue == "DUPLICATE_CREDENTIAL_ID":
            add_gt("Credential", row["credential_id"], row["completion_id"], True, issue, variant,
                   "REJECT_DUPLICATE_ID", "ISSUED", "", "credential_id must be unique (PK)")
        else:
            add_gt("Credential", row["credential_id"], row["completion_id"], True, issue, variant,
                   "ISSUANCE_BLOCKED", "ISSUED", "", "issue only after completion.requirements_met and issued_at >= completed_at")
    for i, r in enumerate(reqs):
        issue = inj.get(i, "NONE")
        add_gt("VerificationRequest", r["verification_id"], r["credential_id"], issue != "NONE", issue, "",
               r["expected"], r["recorded"], r["_scenario"],
               "verification decision order: NOT_FOUND>HASH>IDENTITY>REVOKED>EXPIRED>VALID")
    tables = {"actors": actors, "issuers": issuers, "learners": learners, "courses": courses,
              "course_issuer_history": history, "credential_rules": rules, "completion_records": completions,
              "assessments": assessments, "credentials": credentials, "revocations": revocations,
              "verification_requests": verifications, "audit_events": audit}
    return tables, gt


# =============================================================================== EXPORT
def csv_val(v):
    return "" if v is None else v


def write_csv(path, cols, rows):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow([csv_val(r.get(c)) for c in cols])


def sql_lit(v):
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def ddl():
    out = ["-- Generated seed schema (SQLite/PostgreSQL-compatible subset)", "PRAGMA foreign_keys = OFF;", ""]
    fk_by = {}
    for (ct, cc, pt, pc, card, opt, enf) in S.FKS:
        if enf:
            fk_by.setdefault(ct, []).append((cc, pt, pc))
    for t in S.TABLE_ORDER:
        lines = []
        for (name, typ, req, allowed, unit, uniq, rule) in S.DATA_DICT[t][3]:
            c = f"  {name} {S.sql_type(typ)}"
            if req:
                c += " NOT NULL"
            if t != "credentials" and name == S.pk(t):
                c += " PRIMARY KEY"
            elif uniq and name != S.pk(t):
                c += " UNIQUE"
            if isinstance(allowed, list) and typ in ("STRING",):
                c += " CHECK (" + name + " IN (" + ",".join(sql_lit(a) for a in allowed) + "))"
            lines.append(c)
        for (cc, pt, pc) in fk_by.get(t, []):
            lines.append(f"  FOREIGN KEY ({cc}) REFERENCES {pt}({pc})")
        out.append(f"CREATE TABLE {t} (\n" + ",\n".join(lines) + "\n);")
        if t == "credentials":
            out.append("-- credential_id is the LOGICAL primary key; it is deliberately not UNIQUE here because the\n"
                       "-- injected DUPLICATE_CREDENTIAL_ID anomaly rows must be loadable and detectable by validation.\n"
                       "CREATE INDEX idx_credentials_credential_id ON credentials(credential_id);")
        out.append("")
    return "\n".join(out)


def write_sql(path, tables):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(ddl() + "\n")
        for t in S.TABLE_ORDER:
            cols = S.fields(t)
            rows = tables[t]
            for i in range(0, len(rows), 500):
                chunk = rows[i:i + 500]
                vals = ",\n".join("(" + ",".join(sql_lit(r.get(c)) for c in cols) + ")" for r in chunk)
                fh.write(f"INSERT INTO {t} ({','.join(cols)}) VALUES\n{vals};\n")
        fh.write("\n-- Ground truth is intentionally NOT loaded here (see ground_truth.csv).\n")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_docs(out):
    with open(os.path.join(out, "data_dictionary.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(["entity", "file", "field", "type", "required", "allowed_values", "unit", "unique", "validation_rule", "is_primary_key"])
        for t in S.TABLE_ORDER:
            ent, fn, pkcol, flds = S.DATA_DICT[t]
            for (n, ty, req, allowed, unit, uniq, rule) in flds:
                al = "|".join(str(a) for a in allowed) if isinstance(allowed, list) else allowed
                w.writerow([ent, fn, n, ty, "Y" if req else "N", al, unit, "Y" if uniq else "N", rule, "Y" if n == pkcol else "N"])
    md = ["# Data dictionary", ""]
    for t in S.TABLE_ORDER:
        ent, fn, pkcol, flds = S.DATA_DICT[t]
        md += [f"## {ent} - `{fn}` (PK: `{pkcol}`)", "", "| field | type | req | allowed | unit | unique | rule |", "|---|---|---|---|---|---|---|"]
        for (n, ty, req, allowed, unit, uniq, rule) in flds:
            al = "\\|".join(str(a) for a in allowed) if isinstance(allowed, list) else allowed
            md.append(f"| {n} | {ty} | {'Y' if req else 'N'} | {al} | {unit} | {'Y' if uniq else 'N'} | {rule} |")
        md.append("")
    md += ["## Foreign keys", "", "| child | column | parent | column | cardinality | optional |", "|---|---|---|---|---|---|"]
    for (ct, cc, pt, pc, card, opt, enf) in S.FKS:
        md.append(f"| {ct} | {cc} | {pt} | {pc} | {card} | {'Y' if opt else 'N'} |")
    md += ["", "## Cardinality and lifecycle notes", ""] + [f"- {x}" for x in S.CARDINALITY_NOTES]
    with open(os.path.join(out, "data_dictionary.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(md) + "\n")
    schema = {t: {"entity": S.DATA_DICT[t][0], "file": S.DATA_DICT[t][1], "primary_key": S.DATA_DICT[t][2],
                  "fields": [{"name": f[0], "type": f[1], "required": f[2], "allowed": f[3], "unit": f[4],
                              "unique": f[5], "rule": f[6]} for f in S.DATA_DICT[t][3]]} for t in S.TABLE_ORDER}
    schema["_foreign_keys"] = [dict(zip(["child_table", "child_column", "parent_table", "parent_column", "cardinality", "optional", "enforced_in_sql"], f)) for f in S.FKS]
    schema["_notes"] = S.CARDINALITY_NOTES
    with open(os.path.join(out, "schema.json"), "w", encoding="utf-8") as fh:
        json.dump(schema, fh, indent=2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--seed", type=int, default=L.DEFAULT_SEED)
    ap.add_argument("--scale", type=float, default=1.0, help="multiplies default volumes (0.05 = starter set)")
    for k in DEFAULTS:
        ap.add_argument(f"--{k}", type=int, default=None, help=f"override (default {DEFAULTS[k]} x scale)")
    ap.add_argument("--as-of", default=L.DEFAULT_AS_OF, help="dataset snapshot date (YYYY-MM-DD)")
    ap.add_argument("--out", default="data_full")
    ap.add_argument("--formats", default="csv,json,sql", help="comma list of csv,json,sql")
    a = ap.parse_args()
    p = {k: (getattr(a, k) if getattr(a, k) is not None else max(10, round(DEFAULTS[k] * a.scale))) for k in DEFAULTS}
    p.update({"seed": a.seed, "as_of": a.as_of, "scale": a.scale})
    fmts = [f.strip() for f in a.formats.split(",")]
    os.makedirs(a.out, exist_ok=True)
    tables, gt = build(p)
    files = {}
    for t in S.TABLE_ORDER:
        cols, rows = S.fields(t), tables[t]
        fn = S.DATA_DICT[t][1]
        write_csv(os.path.join(a.out, fn), cols, rows)
        files[fn] = {"rows": len(rows)}
        if "json" in fmts:
            os.makedirs(os.path.join(a.out, "json"), exist_ok=True)
            with open(os.path.join(a.out, "json", t + ".json"), "w", encoding="utf-8") as fh:
                json.dump([{c: r.get(c) for c in cols} for r in rows], fh, separators=(",", ":"))
            files[f"json/{t}.json"] = {"rows": len(rows)}
    write_csv(os.path.join(a.out, "ground_truth.csv"), S.GROUND_TRUTH_FIELDS, gt)
    files["ground_truth.csv"] = {"rows": len(gt)}
    with open(os.path.join(a.out, "ground_truth.json"), "w", encoding="utf-8") as fh:
        json.dump(gt, fh, separators=(",", ":"))
    files["ground_truth.json"] = {"rows": len(gt)}
    summary = {}
    for g in gt:
        if g["is_anomaly"]:
            summary[g["issue_type"]] = summary.get(g["issue_type"], 0) + 1
    with open(os.path.join(a.out, "ground_truth_summary.json"), "w", encoding="utf-8") as fh:
        json.dump({"anomalies_by_type": summary, "verification_decisions": sum(1 for g in gt if g["entity_type"] == "VerificationRequest")}, fh, indent=2)
    if "sql" in fmts:
        write_sql(os.path.join(a.out, "seed.sql"), tables)
        files["seed.sql"] = {"rows": sum(len(v) for v in tables.values())}
    write_docs(a.out)
    for fn in files:
        files[fn]["sha256"] = sha256_file(os.path.join(a.out, fn))
    cmd = f"python generate_dataset.py --seed {p['seed']} --scale {a.scale} --as-of {a.as_of} --out {a.out}"
    for k in DEFAULTS:
        if getattr(a, k) is not None:
            cmd += f" --{k} {getattr(a, k)}"
    manifest = {"generator": "generate_dataset.py", "version": L.GENERATOR_VERSION, "command": cmd, "seed": p["seed"],
                "parameters": p, "external_data_used": [],
                "provenance": "Fully synthetic. Names come from invented pools, emails use the reserved example.org domain, "
                              "no real personal data, no scraped or licensed datasets. Signing keys are demo keys derived from the seed.",
                "files": files}
    with open(os.path.join(a.out, "source_manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    with open(os.path.join(a.out, "checksums.sha256"), "w", encoding="utf-8") as fh:
        for fn in sorted(files):
            fh.write(f"{files[fn]['sha256']}  {fn}\n")
    print(f"Generated {a.out}: " + ", ".join(f"{t}={len(tables[t])}" for t in S.TABLE_ORDER))
    print("Injected anomalies:", json.dumps(summary))


if __name__ == "__main__":
    main()
