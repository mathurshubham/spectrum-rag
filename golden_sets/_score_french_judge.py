#!/usr/bin/env python3
"""Score an LLM-judge (or HITL) against french-judge-dataset.csv.

Percent agreement is misleading at a 70/30 base rate (always-"pass" scores 70%), so the
verdict metric is Cohen's kappa + precision/recall on the *fail* class. Per rubric we report
threshold-crossing agreement (the primary signal) alongside exact / within-1. Also: per
failure-mode detection, clear-vs-borderline stratification, matched-pair sensitivity, a
"right verdict, wrong reason" count, and (with two judge runs) borderline flip-rate.

Judge predictions CSV must have column `id` plus any of:
    judge_task, judge_format, judge_factuality   (ints; rubric scores)
    judge_verdict                                (pass/fail; else derived from scores)
    judge_failure_mode                           (for right-reason analysis)

WITHHOLD gold from the judge under test: judge_rationale, failure_mode, error_span, all
gold scores and verdict must be stripped from any CSV shown to the judge — they sit in the
same file and are the most common contamination vector.

    python _score_french_judge.py --preds judge_run1.csv [--preds2 judge_run2.csv]
    python _score_french_judge.py --selftest      # synthetic noisy judge, proves metrics
"""
from __future__ import annotations
import argparse
import csv
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
GOLD = os.path.join(HERE, "french-judge-dataset.csv")
T_TASK, T_FMT, T_FACT = 3, 1, 4  # pass thresholds


def load_gold(path=GOLD):
    return {r["id"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}


def load_preds(path):
    return {r["id"]: r for r in csv.DictReader(open(path, encoding="utf-8"))}


def pred_verdict(p):
    if p.get("judge_verdict"):
        return p["judge_verdict"].strip()
    t = int(p["judge_task"]); f = int(p["judge_format"]); fa = int(p["judge_factuality"])
    return "pass" if (t >= T_TASK and f >= T_FMT and fa >= T_FACT) else "fail"


def cohen_kappa(y_true, y_pred, labels=("pass", "fail")):
    n = len(y_true)
    if n == 0:
        return float("nan")
    po = sum(a == b for a, b in zip(y_true, y_pred)) / n
    pe = 0.0
    for lab in labels:
        pe += (y_true.count(lab) / n) * (y_pred.count(lab) / n)
    return 1.0 if pe == 1.0 else (po - pe) / (1 - pe)


def prf_fail(y_true, y_pred):
    tp = sum(t == "fail" and p == "fail" for t, p in zip(y_true, y_pred))
    fp = sum(t == "pass" and p == "fail" for t, p in zip(y_true, y_pred))
    fn = sum(t == "fail" and p == "pass" for t, p in zip(y_true, y_pred))
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return prec, rec, f1, tp, fp, fn


def rubric_agreement(gold, preds, col_g, col_p, threshold, scale5=True):
    exact = within1 = cross = n = 0
    for gid, g in gold.items():
        p = preds.get(gid)
        if not p or col_p not in p or p[col_p] == "":
            continue
        gv, pv = int(g[col_g]), int(p[col_p])
        n += 1
        exact += gv == pv
        if scale5:
            within1 += abs(gv - pv) <= 1
        cross += (gv >= threshold) == (pv >= threshold)
    if n == 0:
        return None
    return dict(n=n, exact=exact / n, within1=within1 / n if scale5 else None, cross=cross / n)


def score(gold, preds, preds2=None):
    ids = [i for i in gold if i in preds]
    yt = [gold[i]["verdict"] for i in ids]
    yp = [pred_verdict(preds[i]) for i in ids]

    print(f"\n=== Verdict (n={len(ids)}; base rate fail={yt.count('fail')/len(ids):.0%}) ===")
    print(f"  raw agreement : {sum(a==b for a,b in zip(yt,yp))/len(ids):.3f}  (misleading at 70/30)")
    print(f"  Cohen's kappa : {cohen_kappa(yt, yp):.3f}")
    prec, rec, f1, tp, fp, fn = prf_fail(yt, yp)
    print(f"  FAIL class    : precision={prec:.3f} recall={rec:.3f} f1={f1:.3f} (tp={tp} fp={fp} fn={fn})")

    print("\n=== Per-rubric (threshold-crossing is primary) ===")
    for name, cg, cp, thr, s5 in [
        ("task_completion", "task_completion_score", "judge_task", T_TASK, True),
        ("format_adherence", "format_adherence_score", "judge_format", T_FMT, False),
        ("factuality", "factuality_score", "judge_factuality", T_FACT, True),
    ]:
        a = rubric_agreement(gold, preds, cg, cp, thr, s5)
        if a is None:
            print(f"  {name:16s}: (no judge column)")
            continue
        w = f" within1={a['within1']:.3f}" if a["within1"] is not None else ""
        print(f"  {name:16s}: cross={a['cross']:.3f} exact={a['exact']:.3f}{w}  (n={a['n']})")

    print("\n=== Failure-mode detection (did judge call the fail?) ===")
    modes = {}
    for i in ids:
        g = gold[i]
        if g["verdict"] != "fail":
            continue
        m = g["failure_mode"]
        d = modes.setdefault(m, [0, 0])
        d[1] += 1
        if pred_verdict(preds[i]) == "fail":
            d[0] += 1
    for m, (caught, tot) in sorted(modes.items()):
        print(f"  {m:16s}: {caught}/{tot} caught ({caught/tot:.0%})")

    print("\n=== Difficulty stratification (verdict accuracy) ===")
    for diff in ("clear", "borderline"):
        sub = [i for i in ids if gold[i]["difficulty"] == diff]
        if sub:
            acc = sum(gold[i]["verdict"] == pred_verdict(preds[i]) for i in sub) / len(sub)
            print(f"  {diff:10s}: acc={acc:.3f} (n={len(sub)})")

    print("\n=== Matched-pair sensitivity ===")
    pairs = {}
    for i in ids:
        pid = gold[i]["pair_id"]
        if pid:
            pairs.setdefault(pid, []).append(i)
    ok = full = 0
    for pid, mem in pairs.items():
        if len(mem) != 2:
            continue
        full += 1
        got = {gold[i]["verdict"]: pred_verdict(preds[i]) for i in mem}
        if got.get("pass") == "pass" and got.get("fail") == "fail":
            ok += 1
    if full:
        print(f"  {ok}/{full} pairs correctly separated ({ok/full:.0%})")

    print("\n=== Right verdict, wrong reason ===")
    if any("judge_failure_mode" in preds[i] for i in ids):
        wrong = 0
        for i in ids:
            g = gold[i]
            p = preds[i]
            if g["verdict"] == "fail" and pred_verdict(p) == "fail":
                jm = (p.get("judge_failure_mode") or "").strip()
                if jm and jm not in g["failure_mode"].split(";"):
                    wrong += 1
        print(f"  {wrong} rows: judge said fail but blamed the wrong rubric (silent in verdict-only)")
    else:
        print("  (no judge_failure_mode column — skipped)")

    if preds2 is not None:
        print("\n=== Self-consistency on the BORDERLINE band (flip rate) ===")
        bids = [i for i in ids if gold[i]["difficulty"] == "borderline" and i in preds2]
        flips = sum(pred_verdict(preds[i]) != pred_verdict(preds2[i]) for i in bids)
        rate = flips / len(bids) if bids else float("nan")
        flag = "  <-- >15%: threshold-crossing on this band is noise; tighten anchors or route to HITL" if rate > 0.15 else ""
        print(f"  borderline flip rate: {flips}/{len(bids)} = {rate:.1%}{flag}")


def selftest(gold):
    """Fabricate a noisy judge from gold to prove the metrics run end-to-end."""
    rng = random.Random(7)

    def mock(noise):
        out = {}
        for i, g in gold.items():
            t, f, fa = (int(g["task_completion_score"]), int(g["format_adherence_score"]),
                        int(g["factuality_score"]))
            # borderline rows get more noise (realistic judge behaviour)
            k = noise * (2 if g["difficulty"] == "borderline" else 1)
            if rng.random() < k:
                fa = max(1, min(5, fa + rng.choice([-1, 1])))
            if rng.random() < k:
                t = max(1, min(5, t + rng.choice([-1, 1])))
            jm = g["failure_mode"].split(";")[0]
            if g["verdict"] == "fail" and rng.random() < 0.2:
                jm = rng.choice(["hallucination", "format_violation", "task_incomplete"])
            out[i] = {"id": i, "judge_task": t, "judge_format": f,
                      "judge_factuality": fa, "judge_failure_mode": jm}
        return out

    print("SELFTEST: synthetic judge (run1 noise=0.12, run2 independent) — demonstrates metrics.")
    score(gold, mock(0.12), mock(0.12))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=GOLD)
    ap.add_argument("--preds", help="judge predictions CSV")
    ap.add_argument("--preds2", help="second judge run (for borderline flip-rate)")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()

    gold = load_gold(args.gold)
    if args.selftest:
        selftest(gold)
    elif args.preds:
        p2 = load_preds(args.preds2) if args.preds2 else None
        score(gold, load_preds(args.preds), p2)
    else:
        ap.error("pass --preds <file> or --selftest")


if __name__ == "__main__":
    main()
