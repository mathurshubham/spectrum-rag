#!/usr/bin/env python3
"""Build golden_sets/insurance-judge-dataset.csv — a labeled LLM-judge / HITL benchmark.

Deterministic (fixed RNG seed), no API calls. 200 rows, 30% baked-in failure rate,
grounded in the 3 IRDAI policy PDFs (SJB / SSB / Arogya). Each row carries an actual
model-style `output`, three gold rubric scores, a derived pass/fail `verdict`, a
`failure_mode`, an `error_span`, a `judge_rationale`, and analysis columns
(`seed_id`, `pair_id`, `difficulty`, `judge_type`).

Design rationale lives in /Users/.../.claude/plans/typed-wiggling-volcano.md.
Run `python _build_insurance_judge.py --verify` to build + assert all invariants.
"""
from __future__ import annotations
import argparse
import csv
import os
import random

# ---------------------------------------------------------------------------
# Constants (from demos/insurance/prompts/system_v1.md + manifest.yaml)
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "insurance-judge-dataset.csv")

DISCLAIMER = (
    "*This is not financial or medical advice. Your actual policy document supersedes "
    "any general wording. For specific claims or coverage queries, contact your insurer.*"
)
REFUSAL = (
    "I cannot answer based on the indexed policy wordings. The clause may not be covered, "
    "or this question may fall outside the policies in this corpus. Please refer to your "
    "actual policy document or speak to your insurer."
)
POLICY = {
    "SJB": "Saral Jeevan Bima Standard Term Life Policy",
    "SSB": "Saral Suraksha Bima Standard Personal Accident Policy",
    "Arogya": "Arogya Sanjeevani Standard Health Policy",
}
# True-but-generic sentence per doc, used to build on-format off-topic (task) failures.
DOC_BLURB = {
    "SJB": "Saral Jeevan Bima is an IRDAI-standard individual pure-risk term life plan",
    "SSB": "Saral Suraksha Bima is an IRDAI-standard personal accident policy",
    "Arogya": "Arogya Sanjeevani is an IRDAI-standard health insurance product",
}
FAKE_DOCS = ("Motor Policy", "Home Shield Policy", "Travel Policy")  # out-of-corpus markers

CSV_FIELDS = [
    "id", "seed_id", "pair_id", "eval_context", "difficulty",
    "input", "output", "expected_answer", "expected_citations", "expected_assertions",
    "task_completion_score", "format_adherence_score", "factuality_score",
    "verdict", "failure_mode", "error_span", "judge_rationale", "judge_type",
]


def verdict_of(task: int, fmt: int, fact: int) -> str:
    """Single source of truth: Task>=3 AND Format>=1 AND Factuality>=4."""
    return "pass" if (task >= 3 and fmt >= 1 and fact >= 4) else "fail"


# ---------------------------------------------------------------------------
# Seed bank (~56 seeds), grounded in extracted clause text.
# Fields: id, ctx, doc, cite, wrong_cite, inline_cite (edge multi-doc), q[],
#   ans (full correct body), core (drops a secondary key point) + secondary,
#   minor (fact4 loosely-imprecise body),
#   drift/drift_span (fact3 subtle-wrong), invented/invented_span (fact2),
#   fabricated/fab_span (fact1), exp_ans, exp_cite, exp_assert, topic (refusal).
# ---------------------------------------------------------------------------
SEEDS: list[dict] = []


def seed(**kw):
    SEEDS.append(kw)


# ---- SJB (Saral Jeevan Bima) --------------------------------------------------
seed(id="sjb-what", ctx="retrieval", doc="SJB", cite="SJB cl.1", wrong_cite="SJB cl.7",
     q=["What does Saral Jeevan Bima cover?",
        "What is covered under Saral Jeevan Bima?",
        "What benefit does Saral Jeevan Bima provide?"],
     ans="Saral Jeevan Bima is a non-linked, non-participating pure-risk term life plan that pays the Sum Assured as a lump sum to the nominee on the life assured's death during the policy term",
     core="Saral Jeevan Bima pays the Sum Assured to the nominee on the life assured's death during the policy term",
     secondary="that it is a non-linked, non-participating pure-risk plan",
     drift="Saral Jeevan Bima pays the Sum Assured to the nominee on death, and also returns about 105% of premiums if the life assured survives the term",
     drift_span="also returns about 105% of premiums if the life assured survives the term",
     exp_ans="Pure-risk term life; pays Sum Assured lump sum to nominee on death during the term.",
     exp_cite="SJB cl.1", exp_assert="must_cite=SJB cl.1;must_contain=death|Sum Assured;should_refuse=false")

seed(id="sjb-maturity", ctx="retrieval", doc="SJB", cite="SJB cl.7", wrong_cite="SJB cl.1",
     q=["Is there a maturity benefit under Saral Jeevan Bima?",
        "Does Saral Jeevan Bima pay anything on maturity?",
        "What do I get if I survive the Saral Jeevan Bima term?"],
     ans="No maturity benefit is payable — Saral Jeevan Bima is a pure term insurance plan",
     minor="There is essentially no maturity payout, since this is a pure term plan",
     drift="No maturity benefit is payable as such, though roughly 105% of premiums are returned on survival",
     drift_span="roughly 105% of premiums are returned on survival",
     invented="A maturity benefit of about 5% of the sum assured is paid if you survive the term",
     invented_span="maturity benefit of about 5% of the sum assured",
     exp_ans="No maturity benefit; pure term plan.",
     exp_cite="SJB cl.7", exp_assert="must_cite=SJB cl.7;must_contain=no|maturity;should_refuse=false")

seed(id="sjb-entry-age", ctx="retrieval", doc="SJB", cite="SJB cl.2", wrong_cite="SJB cl.3",
     q=["What is the entry age for Saral Jeevan Bima?",
        "What are the minimum and maximum ages to buy Saral Jeevan Bima?",
        "At what age can I take a Saral Jeevan Bima policy?"],
     ans="The minimum age at entry is 18 years and the maximum is 65 years",
     core="The minimum age at entry is 18 years",
     secondary="the maximum entry age of 65 years",
     minor="Entry is broadly for adults from about 18 up to around 65 years",
     drift="The minimum age at entry is 18 years and the maximum is 60 years",
     drift_span="maximum is 60 years",
     invented="The entry age is 21 to 70 years, with a premium loading above age 55",
     invented_span="21 to 70 years, with a premium loading above age 55",
     fabricated="Entry age is 18 to 65 years as set out in the Motor Policy cl.2 — Motor Policy",
     fab_span="Motor Policy cl.2 — Motor Policy",
     exp_ans="Minimum entry age 18, maximum 65.",
     exp_cite="SJB cl.2", exp_assert="must_cite=SJB cl.2;must_contain=18|65;should_refuse=false")

seed(id="sjb-term", ctx="retrieval", doc="SJB", cite="SJB cl.3", wrong_cite="SJB cl.2",
     q=["What is the policy term range for Saral Jeevan Bima?",
        "What is the minimum and maximum term of Saral Jeevan Bima?",
        "For how long can I take Saral Jeevan Bima cover?"],
     ans="The minimum policy term is 5 years and the maximum is 40 years",
     minor="The term runs from roughly 5 up to 40 years",
     drift="The minimum policy term is 5 years and the maximum is 35 years",
     drift_span="maximum is 35 years",
     invented="The policy term is fixed between 10 and 30 years only",
     invented_span="fixed between 10 and 30 years only",
     exp_ans="Term 5 to 40 years.",
     exp_cite="SJB cl.3", exp_assert="must_cite=SJB cl.3;must_contain=5|40;should_refuse=false")

seed(id="sjb-sum-assured", ctx="retrieval", doc="SJB", cite="SJB cl.4", wrong_cite="SJB cl.3",
     q=["What sum assured is available under Saral Jeevan Bima?",
        "What is the minimum and maximum sum assured for Saral Jeevan Bima?",
        "How much cover can I get under Saral Jeevan Bima?"],
     ans="The minimum sum assured is Rs.5,00,000 and the maximum is Rs.25,00,000; insurers may also offer higher amounts",
     core="The minimum sum assured is Rs.5,00,000",
     secondary="the Rs.25,00,000 maximum (higher amounts optional)",
     minor="Cover runs from about Rs.5 lakh up to Rs.25 lakh, with higher amounts on request",
     drift="The minimum sum assured is Rs.5,00,000 and the maximum is Rs.20,00,000",
     drift_span="maximum is Rs.20,00,000",
     invented="The sum assured ranges from Rs.2,00,000 to Rs.1,00,00,000",
     invented_span="Rs.2,00,000 to Rs.1,00,00,000",
     exp_ans="Min Rs.5 lakh, max Rs.25 lakh (higher optional).",
     exp_cite="SJB cl.4", exp_assert="must_cite=SJB cl.4;must_contain=5,00,000|25,00,000;should_refuse=false")

seed(id="sjb-premium-options", ctx="retrieval", doc="SJB", cite="SJB cl.5", wrong_cite="SJB cl.6",
     q=["What premium payment options does Saral Jeevan Bima offer?",
        "How can I pay premiums under Saral Jeevan Bima?"],
     ans="Premiums can be paid as a single premium, a limited term of 5 or 10 years, or regular premium equal to the policy term",
     minor="You can pay as a lump sum, over a limited period, or regularly through the term",
     exp_ans="Single, limited (5/10 yr), or regular premium.",
     exp_cite="SJB cl.5", exp_assert="must_cite=SJB cl.5;must_contain=single|regular;should_refuse=false")

seed(id="sjb-waiting", ctx="retrieval", doc="SJB", cite="SJB cl.9", wrong_cite="SJB cl.8",
     q=["Is there a waiting period under Saral Jeevan Bima?",
        "What is the waiting period before Saral Jeevan Bima risk cover starts?"],
     ans="A waiting period of 45 days applies from commencement of risk; during it, non-accidental death claims are limited to 100% of the premiums paid excluding taxes",
     core="A waiting period of 45 days applies from commencement of risk",
     secondary="that non-accidental death during it is limited to premiums paid",
     minor="About a 45-day initial waiting period applies before full non-accidental cover begins",
     drift="A waiting period of 30 days applies from commencement of risk, during which non-accidental death claims are limited to premiums paid",
     drift_span="waiting period of 30 days",
     invented="A 90-day waiting period applies and only 50% of premiums are returned on early death",
     invented_span="90-day waiting period ... only 50% of premiums",
     exp_ans="45-day waiting period; non-accidental death limited to premiums paid.",
     exp_cite="SJB cl.9", exp_assert="must_cite=SJB cl.9;must_contain=45|waiting;should_refuse=false")

seed(id="sjb-freelook", ctx="retrieval", doc="SJB", cite="SJB cl.11", wrong_cite="SJB cl.12",
     q=["What is the free-look period for Saral Jeevan Bima?",
        "Can I cancel Saral Jeevan Bima soon after buying and get a refund?"],
     ans="Premiums can be refunded within the 15-day free-look period (30 days for online purchase), less medical, stamp-duty and proportionate risk-premium deductions",
     minor="There is roughly a 15-day free-look window (longer if bought online) for a refund",
     drift="Premiums can be refunded within the 30-day free-look period (45 days for online purchase)",
     drift_span="30-day free-look period (45 days for online",
     exp_ans="15-day free-look (30 for online), refund less deductions.",
     exp_cite="SJB cl.11", exp_assert="must_cite=SJB cl.11;must_contain=15|free-look;should_refuse=false")

seed(id="sjb-surrender", ctx="retrieval", doc="SJB", cite="SJB cl.12", wrong_cite="SJB cl.7",
     q=["Does Saral Jeevan Bima have a surrender value?",
        "What happens if I stop paying Saral Jeevan Bima premiums?"],
     ans="No surrender value is payable; however a policy cancellation value applies for single premium and for limited premium after at least 2 years' premiums",
     core="No surrender value is payable under the plan",
     secondary="that a policy cancellation value applies for single/limited premium",
     exp_ans="No surrender value; cancellation value for single/limited premium.",
     exp_cite="SJB cl.12", exp_assert="must_cite=SJB cl.12;must_contain=no|surrender;should_refuse=false")

seed(id="sjb-suicide", ctx="guard", doc="SJB", cite="SJB cl.8", wrong_cite="SJB cl.9",
     q=["Is suicide covered under Saral Jeevan Bima?",
        "What is the suicide clause in Saral Jeevan Bima?",
        "Does Saral Jeevan Bima exclude suicide?"],
     ans="The only exclusion is the suicide clause, which applies for a period of 12 months",
     minor="Suicide is excluded for roughly the first year of the policy",
     drift="The suicide clause under the plan applies for a period of 6 months",
     drift_span="period of 6 months",
     invented="Suicide is excluded for the first 24 months, and death from any pre-existing illness for 36 months",
     invented_span="24 months ... 36 months",
     exp_ans="Suicide excluded for 12 months (only exclusion).",
     exp_cite="SJB cl.8", exp_assert="guard=exclusion;must_contain=suicide|12;should_refuse=false")

# ---- SSB (Saral Suraksha Bima) ------------------------------------------------
seed(id="ssb-what", ctx="retrieval", doc="SSB", cite="SSB cl.1", wrong_cite="SSB cl.2",
     q=["What does Saral Suraksha Bima cover?",
        "What is Saral Suraksha Bima in simple terms?",
        "What is covered under Saral Suraksha Bima?"],
     ans="Saral Suraksha Bima is a personal accident policy covering accidental death, permanent total disability and permanent partial disability, with a critical-illness section",
     core="Saral Suraksha Bima covers accidental death and disability",
     secondary="that it also has a critical-illness section",
     exp_ans="Personal accident cover: accidental death, PTD, PPD; plus critical illness.",
     exp_cite="SSB cl.1", exp_assert="must_contain=accident|disability;should_refuse=false")

seed(id="ssb-death-benefit", ctx="retrieval", doc="SSB", cite="SSB cl.2", wrong_cite="SSB cl.3",
     q=["What does Saral Suraksha Bima pay for accidental death?",
        "How much is paid on accidental death under Saral Suraksha Bima?"],
     ans="Accidental death is compensated at 100% of the Capital Sum Insured under the Table of Benefits",
     minor="Accidental death is covered up to the full sum insured",
     drift="Accidental death is compensated at 75% of the Capital Sum Insured",
     drift_span="75% of the Capital Sum Insured",
     invented="Accidental death pays 150% of the sum insured plus a Rs.1,00,000 funeral benefit",
     invented_span="150% of the sum insured plus a Rs.1,00,000 funeral benefit",
     exp_ans="Accidental death = 100% of Capital Sum Insured.",
     exp_cite="SSB cl.2", exp_assert="must_contain=accidental|100;should_refuse=false")

seed(id="ssb-ptd", ctx="retrieval", doc="SSB", cite="SSB cl.2", wrong_cite="SSB cl.1",
     q=["What is covered under permanent total disability in Saral Suraksha Bima?",
        "How much does Saral Suraksha Bima pay for permanent total disablement?"],
     ans="Permanent total and absolute disablement is compensated at 100% of the Capital Sum Insured",
     minor="Permanent total disablement pays essentially the whole sum insured",
     drift="Permanent total and absolute disablement is compensated at 80% of the Capital Sum Insured",
     drift_span="80% of the Capital Sum Insured",
     exp_ans="PTD = 100% of Capital Sum Insured.",
     exp_cite="SSB cl.2", exp_assert="must_contain=disability|100;should_refuse=false")

seed(id="ssb-partial", ctx="retrieval", doc="SSB", cite="SSB cl.2", wrong_cite="SSB cl.3",
     q=["What does Saral Suraksha Bima pay for partial disability?",
        "How much is paid for loss of one eye or one limb under Saral Suraksha Bima?"],
     ans="Loss of sight in one eye, or of one hand or one foot, is compensated at 50% of the Capital Sum Insured",
     minor="Losing one eye or one limb pays roughly half the sum insured",
     drift="Loss of sight in one eye is compensated at 25% of the Capital Sum Insured",
     drift_span="25% of the Capital Sum Insured",
     invented="Partial disability pays a fixed Rs.3,00,000 regardless of severity",
     invented_span="fixed Rs.3,00,000 regardless of severity",
     exp_ans="Loss of one eye/hand/foot = 50% of Capital Sum Insured.",
     exp_cite="SSB cl.2", exp_assert="must_contain=50|disability;should_refuse=false")

seed(id="ssb-ci-waiting", ctx="guard", doc="SSB", cite="SSB cl.1", wrong_cite="SSB cl.2",
     q=["Is there a waiting period for critical illness under Saral Suraksha Bima?",
        "When does critical-illness cover start under Saral Suraksha Bima?"],
     ans="Critical illness cover has a 90-day waiting period from commencement, and death within 30 days of diagnosis is excluded",
     core="Critical illness cover has a 90-day waiting period from commencement",
     secondary="that death within 30 days of diagnosis is excluded",
     minor="Critical-illness cover begins after roughly a 3-month initial period",
     drift="Critical illness cover has a 60-day waiting period from commencement, and death within 30 days of diagnosis is excluded",
     drift_span="60-day waiting period",
     invented="Critical illness has a 6-month waiting period and a Rs.5,00,000 sub-limit",
     invented_span="6-month waiting period and a Rs.5,00,000 sub-limit",
     exp_ans="CI: 90-day wait; death within 30 days of diagnosis excluded.",
     exp_cite="SSB cl.1", exp_assert="guard=exclusion;must_contain=90|waiting;should_refuse=false")

seed(id="ssb-ped", ctx="retrieval", doc="SSB", cite="SSB cl.1", wrong_cite="SSB cl.2",
     q=["How is a pre-existing condition defined under Saral Suraksha Bima?",
        "What counts as a pre-existing condition in Saral Suraksha Bima?"],
     ans="A pre-existing condition is any condition for which you had signs, symptoms, diagnosis or treatment within 48 months prior to your first policy",
     minor="Pre-existing conditions are those going back roughly four years before your first policy",
     drift="A pre-existing condition is any condition treated within 36 months prior to your first policy",
     drift_span="within 36 months",
     exp_ans="PED = signs/diagnosis/treatment within 48 months before first policy.",
     exp_cite="SSB cl.1", exp_assert="must_contain=48|pre-existing;should_refuse=false")

seed(id="ssb-nuclear", ctx="guard", doc="SSB", cite="SSB cl.3", wrong_cite="SSB cl.4",
     q=["Does Saral Suraksha Bima cover nuclear damage?",
        "Is nuclear or radioactive damage excluded under Saral Suraksha Bima?"],
     ans="No — the radioactive, toxic or explosive hazards of any nuclear assembly or nuclear component are explicitly excluded",
     minor="Nuclear and radioactive hazards are among the excluded causes",
     exp_ans="Nuclear/radioactive hazards excluded.",
     exp_cite="SSB cl.3", exp_assert="guard=exclusion;must_contain=nuclear|excluded;should_refuse=false")

seed(id="ssb-war", ctx="guard", doc="SSB", cite="SSB cl.3", wrong_cite="SSB cl.4",
     q=["Is war damage excluded under Saral Suraksha Bima?",
        "Does Saral Suraksha Bima cover injury from war?"],
     ans="No — death, injury or disablement arising from war, invasion, hostilities or civil war is excluded",
     minor="War and related hostilities are excluded causes",
     exp_ans="War/invasion/hostilities excluded.",
     exp_cite="SSB cl.3", exp_assert="guard=exclusion;must_contain=war|exclusion;should_refuse=false")

seed(id="ssb-suicide-excl", ctx="guard", doc="SSB", cite="SSB cl.3", wrong_cite="SSB cl.4",
     q=["Does Saral Suraksha Bima cover suicide?",
        "Is intentional self-injury excluded under Saral Suraksha Bima?"],
     ans="Committing or attempting suicide and intentional self-injury are excluded from the personal accident cover",
     exp_ans="Suicide/self-injury excluded from PA cover.",
     exp_cite="SSB cl.3", exp_assert="guard=exclusion;must_contain=suicide|excluded;should_refuse=false")

seed(id="ssb-intox", ctx="guard", doc="SSB", cite="SSB cl.3", wrong_cite="SSB cl.4",
     q=["Are claims covered if the insured was drunk under Saral Suraksha Bima?",
        "Does Saral Suraksha Bima pay if the accident happened under the influence of alcohol?"],
     ans="No — claims arising whilst under the influence of intoxicating liquor are excluded",
     exp_ans="Under-influence-of-liquor claims excluded.",
     exp_cite="SSB cl.3", exp_assert="guard=exclusion;must_contain=liquor|excluded;should_refuse=false")

seed(id="ssb-adventure", ctx="guard", doc="SSB", cite="SSB cl.3", wrong_cite="SSB cl.4",
     q=["Does Saral Suraksha Bima cover adventure sports injuries?",
        "Are adventurous sports excluded under Saral Suraksha Bima?"],
     ans="Injuries sustained whilst engaged in adventurous sports are excluded",
     exp_ans="Adventurous-sports injuries excluded.",
     exp_cite="SSB cl.3", exp_assert="guard=exclusion;must_contain=sports|excluded;should_refuse=false")

seed(id="ssb-fraud", ctx="guard", doc="SSB", cite="SSB cl.4", wrong_cite="SSB cl.3",
     q=["What happens if a fraudulent claim is made under Saral Suraksha Bima?",
        "What if I give false information in a Saral Suraksha Bima claim?"],
     ans="All benefits are forfeited and the policy is treated as void in the case of any fraudulent claim or fraudulent means",
     minor="Fraud causes the policy benefits to be lost and the policy voided",
     exp_ans="Fraud -> all benefits forfeited, policy void.",
     exp_cite="SSB cl.4", exp_assert="guard=exclusion;must_contain=fraud|forfeited|void;should_refuse=false")

seed(id="ssb-misdesc", ctx="guard", doc="SSB", cite="SSB cl.4", wrong_cite="SSB cl.3",
     q=["What happens if I misrepresent facts when buying Saral Suraksha Bima?",
        "What is the consequence of non-disclosure under Saral Suraksha Bima?"],
     ans="The policy is void ab initio and premium is forfeited in the event of misrepresentation, mis-description or non-disclosure of material facts",
     exp_ans="Misrepresentation/non-disclosure -> void ab initio, premium forfeited.",
     exp_cite="SSB cl.4", exp_assert="guard=exclusion;must_contain=void|forfeited;should_refuse=false")

seed(id="ssb-death-docs", ctx="retrieval", doc="SSB", cite="SSB cl.3", wrong_cite="SSB cl.4",
     q=["What documents are needed for a death claim under Saral Suraksha Bima?",
        "What paperwork does a Saral Suraksha Bima death claim require?"],
     ans="A death claim requires a completed claim form, the Death Certificate and original FIR, the original Panchnama and the post-mortem report",
     core="A death claim requires the claim form, Death Certificate and original FIR",
     secondary="the original Panchnama and the post-mortem report",
     drift="A death claim requires a completed claim form, the Death Certificate, an original FIR and a hospital discharge summary",
     drift_span="a hospital discharge summary",
     exp_ans="Claim form, Death Certificate, FIR, Panchnama, post-mortem.",
     exp_cite="SSB cl.3", exp_assert="must_cite=SSB cl.3;must_contain=death certificate|FIR;should_refuse=false")

seed(id="ssb-claim-notice", ctx="retrieval", doc="SSB", cite="SSB cl.3", wrong_cite="SSB cl.4",
     q=["How soon must I notify a claim under Saral Suraksha Bima?",
        "What is the claim-intimation timeline under Saral Suraksha Bima?"],
     ans="Notice must be given to the call centre immediately and in writing, and in any case within one calendar month after the death",
     minor="You should notify the insurer promptly, within about a month of the death",
     drift="Notice must be given to the call centre immediately, and in any case within two calendar months after the death",
     drift_span="within two calendar months",
     invented="Claims must be intimated within 24 hours of the accident or they are rejected",
     invented_span="within 24 hours of the accident or they are rejected",
     exp_ans="Notify immediately; within one calendar month after death.",
     exp_cite="SSB cl.3", exp_assert="must_contain=notice|claim;should_refuse=false")

seed(id="ssb-arbitration", ctx="retrieval", doc="SSB", cite="SSB cl.4", wrong_cite="SSB cl.3",
     q=["How are disputes resolved under Saral Suraksha Bima?",
        "What is the arbitration process under Saral Suraksha Bima?"],
     ans="Disputes over quantum go to a sole arbitrator, or a panel of three if the parties cannot agree within 30 days, under the Arbitration and Conciliation Act 1996",
     minor="Quantum disputes go to arbitration under the 1996 Act",
     exp_ans="Sole arbitrator / panel of 3; Arbitration & Conciliation Act 1996.",
     exp_cite="SSB cl.4", exp_assert="must_contain=arbitrat;should_refuse=false")

seed(id="ssb-geo", ctx="retrieval", doc="SSB", cite="SSB cl.4", wrong_cite="SSB cl.1",
     q=["What is the geographical scope of Saral Suraksha Bima?",
        "Where are Saral Suraksha Bima claims payable?"],
     ans="The geographical scope is India, and all claims are payable in Indian currency only",
     exp_ans="India only; claims in Indian currency.",
     exp_cite="SSB cl.4", exp_assert="must_contain=India;should_refuse=false")

seed(id="ssb-renewal", ctx="retrieval", doc="SSB", cite="SSB cl.4", wrong_cite="SSB cl.1",
     q=["Up to what age is Saral Suraksha Bima renewable?",
        "What is the renewal condition for Saral Suraksha Bima?"],
     ans="The policy is renewable with a ceasing age of 80 years, and must be renewed within 15 days of expiry to maintain continuity",
     minor="It is renewable up to around age 80 if renewed on time",
     drift="The policy is renewable with a ceasing age of 75 years, and must be renewed within 15 days of expiry",
     drift_span="ceasing age of 75 years",
     invented="The policy can be renewed only up to age 60",
     invented_span="only up to age 60",
     exp_ans="Ceasing age 80; renew within 15 days of expiry.",
     exp_cite="SSB cl.4", exp_assert="must_contain=80|renew;should_refuse=false")

seed(id="ssb-shortperiod", ctx="retrieval", doc="SSB", cite="SSB cl.4", wrong_cite="SSB cl.1",
     q=["What refund do I get if I cancel Saral Suraksha Bima early?",
        "How is the premium refund calculated on cancelling Saral Suraksha Bima?"],
     ans="On cancellation by you, 25% of the annual premium is retained if cancelled within one month, rising to 50% up to three months (provided no claim was made)",
     minor="Early cancellation retains roughly a quarter of the annual premium",
     drift="On cancellation by you, 30% of the annual premium is retained if cancelled within one month",
     drift_span="30% of the annual premium",
     exp_ans="Short-period: 25% retained <=1mo, 50% <=3mo, etc.",
     exp_cite="SSB cl.4", exp_assert="must_contain=premium|refund;should_refuse=false")

seed(id="ssb-settlement", ctx="retrieval", doc="SSB", cite="SSB cl.4", wrong_cite="SSB cl.3",
     q=["How quickly is a settled claim paid under Saral Suraksha Bima?",
        "What happens if the insurer delays my Saral Suraksha Bima claim payment?"],
     ans="Once a settlement offer is accepted, payment is made within 7 days; delayed payment carries interest at 2% above the bank rate",
     minor="Accepted claims are paid within about a week, with interest for delays",
     drift="Once a settlement offer is accepted, payment is made within 15 days; delayed payment carries interest at 2% above the bank rate",
     drift_span="within 15 days",
     exp_ans="Pay within 7 days of acceptance; delay interest 2% above bank rate.",
     exp_cite="SSB cl.4", exp_assert="must_contain=7|interest;should_refuse=false")

seed(id="ssb-contribution", ctx="retrieval", doc="SSB", cite="SSB cl.4", wrong_cite="SSB cl.1",
     q=["What if I have other insurance covering the same loss under Saral Suraksha Bima?",
        "How does contribution work under Saral Suraksha Bima?"],
     ans="If other insurance covers the same loss, the insurer pays only its rateable proportion, except critical-illness cover, which is paid in excess",
     exp_ans="Rateable proportion if other cover exists; CI paid in excess.",
     exp_cite="SSB cl.4", exp_assert="must_contain=rateable|contribution;should_refuse=false")

# ---- Arogya (amendment circular) ---------------------------------------------
seed(id="arogya-si-range", ctx="retrieval", doc="Arogya", cite="Arogya cl.1", wrong_cite="Arogya cl.2",
     q=["What sum insured range does Arogya Sanjeevani offer?",
        "What are the sum insured options for Arogya Sanjeevani?"],
     ans="Sum insured options range from Rs.1,00,000 to Rs.5,00,000, in multiples of Rs.50,000",
     core="Sum insured options range from Rs.1,00,000 to Rs.5,00,000",
     secondary="that they are offered in multiples of Rs.50,000",
     minor="The sum insured sits broadly in the Rs.1–5 lakh band in Rs.50,000 steps",
     drift="Sum insured options range from Rs.1,00,000 to Rs.4,00,000, in multiples of Rs.50,000",
     drift_span="Rs.1,00,000 to Rs.4,00,000",
     invented="Sum insured ranges from Rs.3,00,000 to Rs.50,00,000 with a mandatory 20% co-pay",
     invented_span="Rs.3,00,000 to Rs.50,00,000 with a mandatory 20% co-pay",
     exp_ans="SI Rs.1 lakh to Rs.5 lakh, in multiples of Rs.50,000.",
     exp_cite="Arogya cl.1", exp_assert="must_cite=Arogya cl.1;must_contain=sum insured;should_refuse=false")

seed(id="arogya-extension", ctx="retrieval", doc="Arogya", cite="Arogya cl.2", wrong_cite="Arogya cl.1",
     q=["Can Arogya Sanjeevani offer sum insured above Rs.5 lakh?",
        "What did the Arogya Sanjeevani amendment change about sum insured?"],
     ans="Insurers may now offer sum insured below Rs.1 lakh or above Rs.5 lakh, subject to their underwriting policy, in multiples of Rs.50,000",
     minor="The amendment lets insurers go below Rs.1 lakh or above Rs.5 lakh subject to underwriting",
     exp_ans="Amendment allows SI below Rs.1 lakh / above Rs.5 lakh, subject to underwriting.",
     exp_cite="Arogya cl.2", exp_assert="must_cite=Arogya cl.2;must_contain=sum insured;should_refuse=false")

seed(id="arogya-who", ctx="retrieval", doc="Arogya", cite="Arogya cl.1", wrong_cite="Arogya cl.2",
     q=["Who offers the Arogya Sanjeevani Policy?",
        "Which insurers must offer Arogya Sanjeevani?"],
     ans="Arogya Sanjeevani is a standard health product that IRDAI requires all general and health insurers to offer",
     exp_ans="IRDAI-mandated standard product; all general/health insurers.",
     exp_cite="Arogya cl.1", exp_assert="must_cite=Arogya cl.1;must_contain=IRDAI|insurer;should_refuse=false")

seed(id="arogya-premium-filing", ctx="retrieval", doc="Arogya", cite="Arogya cl.3", wrong_cite="Arogya cl.1",
     q=["How are Arogya Sanjeevani premium rates filed after the amendment?",
        "What does the Arogya circular say about premium tables?"],
     ans="Premium-rate tables for the revised sum-insured slabs are filed on a certification basis under the minor-modifications guidelines",
     exp_ans="Premium tables filed on certification basis for revised SI slabs.",
     exp_cite="Arogya cl.3", exp_assert="must_cite=Arogya cl.3;must_contain=premium;should_refuse=false")

seed(id="arogya-what", ctx="retrieval", doc="Arogya", cite="Arogya cl.1", wrong_cite="Arogya cl.3",
     q=["What is the indexed Arogya Sanjeevani document?",
        "What does the Arogya Sanjeevani document in this corpus contain?"],
     ans="The indexed Arogya Sanjeevani document is an IRDAI amendment circular dated 7 July 2020 dealing with sum-insured extension and premium filing",
     exp_ans="IRDAI amendment circular (7 Jul 2020): SI extension + premium filing.",
     exp_cite="Arogya cl.1", exp_assert="must_contain=IRDAI|amendment;should_refuse=false")

# ---- Edge / comparison --------------------------------------------------------
seed(id="edge-sjb-vs-ssb", ctx="edge", doc="SJB",
     inline_cite="(SJB cl.1 — Saral Jeevan Bima Standard Term Life Policy; SSB cl.1 — Saral Suraksha Bima Standard Personal Accident Policy)",
     cite="SJB cl.1|SSB cl.1",
     q=["What is the difference between Saral Jeevan Bima and Saral Suraksha Bima?",
        "How do Saral Jeevan Bima and Saral Suraksha Bima differ?"],
     ans="Saral Jeevan Bima is term life cover paying on death, while Saral Suraksha Bima is a personal accident policy paying on accidental death or disability; both are IRDAI-standard but cover different risks",
     core="Saral Jeevan Bima covers death; Saral Suraksha Bima covers accidents and disability",
     secondary="that both are IRDAI-standard products",
     exp_ans="SJB = term life (death); SSB = personal accident (accidental death/disability).",
     exp_cite="SJB cl.1|SSB cl.1", exp_assert="should_refuse=false;must_contain=life|accident")

seed(id="edge-both", ctx="edge", doc="SJB",
     inline_cite="(SJB cl.1 — Saral Jeevan Bima Standard Term Life Policy; SSB cl.1 — Saral Suraksha Bima Standard Personal Accident Policy)",
     cite="SJB cl.1|SSB cl.1",
     q=["Can I hold both Saral Jeevan Bima and Saral Suraksha Bima?",
        "Am I allowed to take both the Saral life and accident policies?"],
     ans="The indexed wordings do not restrict holding both; they are separate IRDAI-standard products covering different risks — confirm eligibility with the insurer",
     exp_ans="Not restricted in the corpus; separate products; confirm with insurer.",
     exp_cite="SJB cl.1|SSB cl.1", exp_assert="should_refuse=false")

seed(id="edge-irdai", ctx="edge", doc="Arogya", cite="Arogya cl.1", wrong_cite="Arogya cl.2",
     q=["What is IRDAI and what is its role in these policies?",
        "What role does IRDAI play in Arogya Sanjeevani?"],
     ans="IRDAI is the Insurance Regulatory and Development Authority of India; it mandated these standard products and issued the Arogya Sanjeevani circular in this corpus",
     exp_ans="IRDAI = insurance regulator; mandated the standard products.",
     exp_cite="Arogya cl.1", exp_assert="must_contain=IRDAI;should_refuse=false")

seed(id="edge-which-accident", ctx="edge", doc="SSB",
     inline_cite="(SSB cl.2 — Saral Suraksha Bima Standard Personal Accident Policy; SJB cl.1 — Saral Jeevan Bima Standard Term Life Policy)",
     cite="SSB cl.2|SJB cl.1",
     q=["Which policy covers accidental death?",
        "If I want accidental death cover, which of these policies applies?"],
     ans="Accidental death is covered under Saral Suraksha Bima; Saral Jeevan Bima covers death generally as a term plan",
     exp_ans="Accidental death -> Saral Suraksha Bima; general death -> SJB.",
     exp_cite="SSB cl.2|SJB cl.1", exp_assert="should_refuse=false;must_contain=accident")

seed(id="edge-which-natural", ctx="edge", doc="SJB",
     inline_cite="(SJB cl.1 — Saral Jeevan Bima Standard Term Life Policy; SSB cl.2 — Saral Suraksha Bima Standard Personal Accident Policy)",
     cite="SJB cl.1|SSB cl.2",
     q=["Which policy pays if I die of natural causes?",
        "Which of these covers death from illness rather than accident?"],
     ans="Saral Jeevan Bima pays the Sum Assured on death during the term including natural causes, whereas Saral Suraksha Bima pays only for accidental death",
     exp_ans="Natural-cause death -> SJB; SSB is accident-only.",
     exp_cite="SJB cl.1|SSB cl.2", exp_assert="should_refuse=false;must_contain=life|accident")

seed(id="edge-standard", ctx="edge", doc="SJB", cite="SJB cl.1", wrong_cite="SJB cl.2",
     q=["Why are these called standard products?",
        "What does it mean that Saral Jeevan Bima is a standard product?"],
     ans="IRDAI mandated standard individual products with uniform features and wording to aid comparison and reduce mis-selling",
     exp_ans="IRDAI-standardised features/wording for comparability and less mis-selling.",
     exp_cite="SJB cl.1", exp_assert="must_contain=standard;should_refuse=false")

seed(id="edge-arogya-family", ctx="edge", doc="Arogya",
     inline_cite="(Arogya cl.1 — Arogya Sanjeevani Standard Health Policy; SJB cl.1 — Saral Jeevan Bima Standard Term Life Policy)",
     cite="Arogya cl.1|SJB cl.1",
     q=["Is Arogya Sanjeevani related to the Saral products?",
        "How does Arogya Sanjeevani relate to Saral Jeevan Bima and Saral Suraksha Bima?"],
     ans="All three are IRDAI-standard products, but Arogya Sanjeevani is health cover while the Saral products are life and personal-accident cover",
     exp_ans="All IRDAI-standard; Arogya = health, Saral = life/accident.",
     exp_cite="Arogya cl.1|SJB cl.1", exp_assert="must_contain=IRDAI|health;should_refuse=false")

# ---- Refusal (topic not in the indexed corpus) --------------------------------
def refusal(id, topic, q, fabricated, fab_span, invented=None, invented_span=None):
    seed(id=id, ctx="refusal", doc=None, cite="", q=q, topic=topic,
         fabricated=fabricated, fab_span=fab_span,
         invented=invented or fabricated, invented_span=invented_span or fab_span,
         exp_ans=f"Refusal — {topic} is not present in the indexed policy wordings.",
         exp_cite="", exp_assert="should_refuse=true")


refusal("ref-roomrent", "the room rent limit under Arogya Sanjeevani",
        ["What is the room rent limit under Arogya Sanjeevani?",
         "Does Arogya Sanjeevani cap room rent?"],
        "The room rent under Arogya Sanjeevani is capped at 1% of the sum insured per day (Arogya cl.6 — Arogya Sanjeevani Standard Health Policy).",
        "room rent under Arogya Sanjeevani is capped at 1% of the sum insured per day",
        invented="Room rent under Arogya Sanjeevani is limited to Rs.5,000 per day, with ICU at Rs.10,000 per day.",
        invented_span="limited to Rs.5,000 per day, with ICU at Rs.10,000")
refusal("ref-copay", "the co-payment clause under Arogya Sanjeevani",
        ["What is the co-payment under Arogya Sanjeevani?",
         "Does Arogya Sanjeevani have a co-pay?"],
        "Arogya Sanjeevani applies a mandatory 5% co-payment on every claim (Arogya cl.5 — Arogya Sanjeevani Standard Health Policy).",
        "mandatory 5% co-payment on every claim")
refusal("ref-hosp", "the hospitalisation cover under Arogya Sanjeevani",
        ["What is the hospitalisation cover under Arogya Sanjeevani?",
         "What hospital expenses does Arogya Sanjeevani pay?"],
        "Arogya Sanjeevani covers hospitalisation up to the full sum insured after a 24-hour admission (Arogya cl.4 — Arogya Sanjeevani Standard Health Policy).",
        "covers hospitalisation up to the full sum insured after a 24-hour admission")
refusal("ref-ped-wait", "the pre-existing disease waiting period under Arogya Sanjeevani",
        ["What is the waiting period for pre-existing diseases under Arogya Sanjeevani?",
         "How long is the PED waiting period in Arogya Sanjeevani?"],
        "Pre-existing diseases have a 48-month waiting period under Arogya Sanjeevani (Arogya cl.7 — Arogya Sanjeevani Standard Health Policy).",
        "48-month waiting period under Arogya Sanjeevani")
refusal("ref-maternity", "maternity cover under Arogya Sanjeevani",
        ["Does Arogya Sanjeevani cover maternity?",
         "Is childbirth covered under Arogya Sanjeevani?"],
        "Arogya Sanjeevani covers maternity after a 9-month waiting period (Arogya cl.8 — Arogya Sanjeevani Standard Health Policy).",
        "covers maternity after a 9-month waiting period")
refusal("ref-daycare", "day-care procedure cover under Arogya Sanjeevani",
        ["Are day-care procedures covered under Arogya Sanjeevani?",
         "Does Arogya Sanjeevani pay for day-care treatments?"],
        "All day-care procedures are covered up to the sum insured under Arogya Sanjeevani (Arogya cl.9 — Arogya Sanjeevani Standard Health Policy).",
        "All day-care procedures are covered up to the sum insured")
refusal("ref-motor", "third-party motor insurance cover",
        ["What does third-party motor insurance cover?",
         "Is motor third-party liability covered here?"],
        "Third-party motor liability is covered up to Rs.7.5 lakh (Motor Policy cl.3 — Motor Policy).",
        "Motor Policy cl.3 — Motor Policy")
refusal("ref-home", "home insurance cover in India",
        ["What is covered under home insurance in India?",
         "Does this corpus cover home insurance?"],
        "Home structure and contents are covered up to Rs.10 lakh (Home Shield Policy cl.2 — Home Shield Policy).",
        "Home Shield Policy cl.2 — Home Shield Policy")
refusal("ref-travel", "travel insurance cover",
        ["What does travel insurance cover?",
         "Is overseas travel medical cover included here?"],
        "Overseas medical expenses are covered up to USD 50,000 (Travel Policy cl.4 — Travel Policy).",
        "Travel Policy cl.4 — Travel Policy")
refusal("ref-sjb-grace", "the premium grace period under Saral Jeevan Bima",
        ["What is the grace period for premium payment under Saral Jeevan Bima?",
         "How many days' grace does Saral Jeevan Bima give for premiums?"],
        "Saral Jeevan Bima allows a 30-day grace period for premium payment (SJB cl.13 — Saral Jeevan Bima Standard Term Life Policy).",
        "30-day grace period for premium payment (SJB cl.13")
refusal("ref-sjb-loan", "policy loans under Saral Jeevan Bima",
        ["Can I take a loan against Saral Jeevan Bima?",
         "Does Saral Jeevan Bima allow policy loans?"],
        "You can borrow up to 80% of the surrender value under Saral Jeevan Bima (SJB cl.14 — Saral Jeevan Bima Standard Term Life Policy).",
        "borrow up to 80% of the surrender value (SJB cl.14")
refusal("ref-topup", "top-up or super top-up health cover",
        ["Is a super top-up health cover available here?",
         "Does the corpus describe a top-up health plan?"],
        "A super top-up of Rs.10 lakh is available above a Rs.5 lakh deductible (Arogya cl.11 — Arogya Sanjeevani Standard Health Policy).",
        "super top-up of Rs.10 lakh ... above a Rs.5 lakh deductible")


# ---------------------------------------------------------------------------
# Output synthesizers
# ---------------------------------------------------------------------------
def inline_cite(s: dict) -> str:
    if s.get("inline_cite"):
        return s["inline_cite"]
    return f"({s['cite']} — {POLICY[s['doc']]})"


def faithful(body: str, s: dict) -> str:
    return f"{body} {inline_cite(s)}. {DISCLAIMER}"


def g_minor(s):
    return f"Broadly, {s['ans'][0].lower() + s['ans'][1:]} (exact figures depend on your schedule)"


def g_drift(s):
    body = f"{s['ans']}. A nominal co-payment of around 10% may also apply"
    return body, "A nominal co-payment of around 10% may also apply"


def g_invented(s):
    body = f"{s['ans']}. The benefit is capped at Rs.2,00,000 per policy year"
    return body, "capped at Rs.2,00,000 per policy year"


def g_fab(s):
    body = f"{s['ans']}, as detailed in the Motor Policy cl.9 — Motor Policy"
    return body, "Motor Policy cl.9 — Motor Policy"


# Each builder returns dict: output, task, fmt, fact, failure_mode, error_span,
# judge_rationale, difficulty, judge_type
def b_clear_pass(s):
    if s["ctx"] == "refusal":
        out = REFUSAL
        rat = "Correctly refused per template; nothing in the indexed corpus — pass."
    else:
        out = faithful(s["ans"], s)
        rat = f"Accurate, cites {s['cite']}, disclaimer present — task 5 / format 1 / fact 5."
    return dict(output=out, task=5, fmt=1, fact=5, failure_mode="none",
                error_span="", judge_rationale=rat, difficulty="clear", judge_type="llm")


def b_bpass_fact4(s):
    minor = s.get("minor") or g_minor(s)
    out = faithful(minor, s)
    return dict(output=out, task=5, fmt=1, fact=4, failure_mode="none", error_span="",
                judge_rationale="Correct with a minor imprecision; still accurate — factuality 4.",
                difficulty="borderline", judge_type="hitl")


def b_bpass_task3(s):
    core = s.get("core") or s["ans"]
    out = faithful(core, s)
    sec = s.get("secondary", "a secondary detail")
    return dict(output=out, task=3, fmt=1, fact=5, failure_mode="none", error_span="",
                judge_rationale=f"Core answer correct but omits {sec} — task 3.",
                difficulty="borderline", judge_type="hitl")


def b_hall_f3(s):
    if s.get("drift"):
        body, span = s["drift"], s["drift_span"]
    else:
        body, span = g_drift(s)
    out = faithful(body, s)
    return dict(output=out, task=5, fmt=1, fact=3, failure_mode="hallucination",
                error_span=span,
                judge_rationale=f"Subtle factual drift ('{span[:60]}') vs the clause — factuality 3.",
                difficulty="borderline", judge_type="hitl")


def b_hall_f2(s):
    if s.get("invented"):
        body, span = s["invented"], s["invented_span"]
    else:
        body, span = g_invented(s)
    if s["ctx"] == "refusal":
        out = f"{body} {DISCLAIMER}"
        rat = "Should have refused; instead invents figures absent from the corpus — factuality 2."
    else:
        out = faithful(body, s)
        rat = "Invents figures not supported by the clause — factuality 2."
    return dict(output=out, task=5, fmt=1, fact=2, failure_mode="hallucination",
                error_span=span, judge_rationale=rat, difficulty="clear", judge_type="llm")


def b_hall_f1(s):
    if s.get("fabricated"):
        body, span = s["fabricated"], s["fab_span"]
        out = f"{body} {DISCLAIMER}"
    else:
        body, span = g_fab(s)
        out = f"{body}. {DISCLAIMER}"
    if s["ctx"] == "refusal":
        rat = "Should have refused; fabricates an out-of-corpus answer — factuality 1."
    else:
        rat = "Cites a document/clause outside the corpus — fabrication, factuality 1."
    return dict(output=out, task=5, fmt=1, fact=1, failure_mode="hallucination",
                error_span=span, judge_rationale=rat, difficulty="clear", judge_type="llm")


def b_format0(s, variant):
    # content correct; only the format template is broken (halo probe)
    if s["ctx"] == "refusal":
        out = "Sorry, that specific information isn't in the policy documents I have."
        span = "(refusal wording does not match the required template)"
        rat = "Correctly declines but not in the exact refusal template — format 0."
    elif variant == 0:  # drop the inline citation
        out = f"{s['ans']}. {DISCLAIMER}"
        span = "(missing inline clause citation)"
        rat = "Answer correct but the inline clause citation is missing — format 0."
    else:  # drop the disclaimer footer
        out = f"{s['ans']} {inline_cite(s)}."
        span = "(missing mandatory disclaimer footer)"
        rat = "Answer correct and cited but the disclaimer footer is missing — format 0."
    return dict(output=out, task=5, fmt=0, fact=5, failure_mode="format_violation",
                error_span=span, judge_rationale=rat, difficulty="clear", judge_type="llm")


def b_task1(s):
    # on-format, factually-true, but does not answer the question asked
    blurb = DOC_BLURB.get(s["doc"], "These are IRDAI-standard insurance products")
    out = f"{blurb} {inline_cite(s)}. {DISCLAIMER}"
    return dict(output=out, task=1, fmt=1, fact=5, failure_mode="task_incomplete",
                error_span="(does not address the question asked)",
                judge_rationale="On-format and true, but never answers the question — task 1.",
                difficulty="clear", judge_type="llm")


def b_task2(s, border):
    # addresses the topic but omits the core answer
    out = (f"This is addressed in the policy, though the exact terms depend on your "
           f"schedule {inline_cite(s)}. {DISCLAIMER}")
    diff = "borderline" if border else "clear"
    jt = "hitl" if border else "llm"
    rat = ("Names the topic and mostly frames it but omits the specific answer — arguable task 2."
           if border else
           "Mentions the topic but gives no specific answer — task 2.")
    return dict(output=out, task=2, fmt=1, fact=5, failure_mode="task_incomplete",
                error_span="(omits the specific answer)", judge_rationale=rat,
                difficulty=diff, judge_type=jt)


# ---------------------------------------------------------------------------
# Slot plan (sums to 200; 60 fail; 36 borderline)
# ---------------------------------------------------------------------------
SLOTS: list[str] = (
    ["clear_pass"] * 120
    + ["bpass_fact4"] * 12
    + ["bpass_task3"] * 8
    + ["hall_f1"] * 4
    + ["hall_f2"] * 8
    + ["hall_f3"] * 12
    + ["format0"] * 20
    + ["task1"] * 4
    + ["task2_clear"] * 8
    + ["task2_border"] * 4
)

# Which seed fields a slot kind requires (None => any seed of a compatible ctx).
REQUIRES = {
    "hall_f3": None,     # uses drift or generic fallback
    "hall_f2": None,
    "hall_f1": None,
    "bpass_fact4": None,
    "bpass_task3": None,
}
# Kinds a refusal seed can serve (answered-anyway or refusal template).
REFUSAL_OK = {"clear_pass", "format0", "hall_f1", "hall_f2"}
# Kinds that need genuine answerable content (never a refusal seed).
ANSWERABLE_ONLY = {"bpass_fact4", "bpass_task3", "hall_f3", "task1", "task2_clear", "task2_border"}

CTX_TARGET = {"retrieval": 110, "guard": 25, "refusal": 40, "edge": 25}


def build_rows(rng: random.Random) -> list[dict]:
    seeds_by_ctx: dict[str, list[dict]] = {"retrieval": [], "guard": [], "refusal": [], "edge": []}
    for s in SEEDS:
        seeds_by_ctx[s["ctx"]].append(s)

    ctx_remaining = dict(CTX_TARGET)
    # round-robin pointer per (ctx) so seed usage spreads out
    ptr: dict[str, int] = {c: 0 for c in seeds_by_ctx}
    q_use: dict[str, int] = {}  # per-seed phrasing rotation

    order = SLOTS[:]
    rng.shuffle(order)

    rows: list[dict] = []
    for i, kind in enumerate(order):
        # contexts allowed for this kind
        if kind in ANSWERABLE_ONLY:
            allowed = ["retrieval", "guard", "edge"]
        elif kind in REFUSAL_OK:
            allowed = ["retrieval", "guard", "edge", "refusal"]
        else:
            allowed = ["retrieval", "guard", "edge", "refusal"]
        # pick the allowed ctx with the most remaining quota that has seeds
        allowed = [c for c in allowed if seeds_by_ctx[c]]
        ctx = max(allowed, key=lambda c: (ctx_remaining[c], -len(c)))
        ctx_remaining[ctx] -= 1

        pool = seeds_by_ctx[ctx]
        s = pool[ptr[ctx] % len(pool)]
        ptr[ctx] += 1

        qi = q_use.get(s["id"], 0)
        question = s["q"][qi % len(s["q"])]
        q_use[s["id"]] = qi + 1

        if kind == "clear_pass":
            b = b_clear_pass(s)
        elif kind == "bpass_fact4":
            b = b_bpass_fact4(s)
        elif kind == "bpass_task3":
            b = b_bpass_task3(s)
        elif kind == "hall_f1":
            b = b_hall_f1(s)
        elif kind == "hall_f2":
            b = b_hall_f2(s)
        elif kind == "hall_f3":
            b = b_hall_f3(s)
        elif kind == "format0":
            b = b_format0(s, variant=i % 2)
        elif kind == "task1":
            b = b_task1(s)
        elif kind == "task2_clear":
            b = b_task2(s, border=False)
        elif kind == "task2_border":
            b = b_task2(s, border=True)
        else:
            raise ValueError(kind)

        v = verdict_of(b["task"], b["fmt"], b["fact"])
        rows.append({
            "seed_id": s["id"], "pair_id": "", "eval_context": ctx,
            "difficulty": b["difficulty"], "input": question, "output": b["output"],
            "expected_answer": s["exp_ans"], "expected_citations": s["exp_cite"],
            "expected_assertions": s["exp_assert"],
            "task_completion_score": b["task"], "format_adherence_score": b["fmt"],
            "factuality_score": b["fact"], "verdict": v, "failure_mode": b["failure_mode"],
            "error_span": b["error_span"], "judge_rationale": b["judge_rationale"],
            "judge_type": b["judge_type"], "_q0": s["q"][0],
        })

    _assign_pairs(rows)
    for n, r in enumerate(rows, 1):
        r["id"] = f"ins-{n:04d}"
    return rows


def _assign_pairs(rows: list[dict], want: int = 18):
    """Link matched pass/fail pairs: same input, opposite verdict, shared seed."""
    by_seed: dict[str, dict[str, list[dict]]] = {}
    for r in rows:
        d = by_seed.setdefault(r["seed_id"], {"pass": [], "fail": []})
        d[r["verdict"]].append(r)
    made = 0
    for sid in sorted(by_seed):
        if made >= want:
            break
        d = by_seed[sid]
        if d["pass"] and d["fail"]:
            p, f = d["pass"][0], d["fail"][0]
            made += 1
            pid = f"pair-{made:02d}"
            for r in (p, f):
                r["pair_id"] = pid
                r["input"] = r["_q0"]  # force identical phrasing within the pair


def write_csv(rows: list[dict], path: str = OUT):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_cols(rows: list[dict], fields: list[str], path: str):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


# ---------------------------------------------------------------------------
# TryEval emitters
# ---------------------------------------------------------------------------
# TryEval canonical CSV columns (packages/shared-types/src/csv-validation.ts):
#   input          -> dataset_rows.prompt   (${PROMPT}; required)
#   eval_context   -> dataset_rows.context  (${CONTEXT} + the ONLY field the LLM judge sees)
#   expected_output-> dataset_rows.expectedOutput (statistical reference only; NOT seen by judge)
#   output         -> dataset_rows.aiOutput (direct-eval; becomes the judge's "Model Output")
# The gold reference is packed into eval_context because that is the only lever that reaches
# the judge. The export input template {"q":"${PROMPT}"} has no ${CONTEXT}, so the reference
# reaches the judge but never the model under test (no leak).
TRYEVAL_LIVE_FIELDS = ["input", "eval_context", "expected_output"]
TRYEVAL_CAL_FIELDS = ["input", "eval_context", "expected_output", "output"]
LIVE_CTX_TARGET = {"retrieval": 115, "guard": 25, "refusal": 40, "edge": 20}  # 60 hard = refusal+edge

LIVE_OUT = os.path.join(HERE, "insurance-tryeval-live-dataset.csv")
CAL_OUT = os.path.join(HERE, "insurance-tryeval-calibration-dataset.csv")


def ref_context(exp_ans: str, exp_cite: str) -> str:
    cites = exp_cite.strip() or "none — this question is outside the indexed corpus; a refusal is the correct response"
    return f"REFERENCE ANSWER: {exp_ans} | EXPECTED CITATIONS: {cites}"


def rephrase(base: str, k: int) -> str:
    if k == 0:
        return base
    bl = base[0].lower() + base[1:]
    wraps = [
        f"Could you tell me: {base}",
        f"Quick question — {base}",
        f"Please clarify: {bl}",
        f"I'd like to understand — {bl}",
        f"In these policies, {bl}",
        f"For my policy specifically, {bl}",
    ]
    return wraps[(k - 1) % len(wraps)]


def emit_live() -> list[dict]:
    by_ctx: dict[str, list[dict]] = {c: [] for c in LIVE_CTX_TARGET}
    for s in SEEDS:
        by_ctx[s["ctx"]].append(s)
    rows: list[dict] = []
    seen: set[str] = set()
    for ctx, target in LIVE_CTX_TARGET.items():
        pool = by_ctx[ctx]
        per_seed: dict[str, int] = {}
        made = attempt = 0
        while made < target:
            s = pool[attempt % len(pool)]
            attempt += 1
            k = per_seed.get(s["id"], 0)
            per_seed[s["id"]] = k + 1
            base = s["q"][k % len(s["q"])]
            q = rephrase(base, k // len(s["q"]))
            if q in seen:
                q = rephrase(base, k // len(s["q"]) + len(s["q"]))
                if q in seen:
                    continue
            seen.add(q)
            rows.append({
                "input": q,
                "eval_context": ref_context(s["exp_ans"], s["exp_cite"]),
                "expected_output": s["exp_ans"],
                "_ctx": ctx,
                "_difficulty": "hard" if ctx in ("refusal", "edge") else "easy",
            })
            made += 1
    return rows


def emit_calibration(rng: random.Random) -> list[dict]:
    """Gold-stripped, direct-eval version of the labeled set (judge scores the fixed output)."""
    labeled = build_rows(rng)
    out = []
    for r in labeled:
        out.append({
            "input": r["input"],
            "eval_context": ref_context(r["expected_answer"], r["expected_citations"]),
            "expected_output": r["expected_answer"],
            "output": r["output"],
        })
    return out


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------
def verify(rows: list[dict]):
    n = len(rows)
    assert n == 200, f"row count {n} != 200"

    fails = [r for r in rows if r["verdict"] == "fail"]
    assert len(fails) == 60, f"fail count {len(fails)} != 60 (30%)"

    # verdict integrity
    for r in rows:
        exp = verdict_of(int(r["task_completion_score"]), int(r["format_adherence_score"]),
                         int(r["factuality_score"]))
        assert exp == r["verdict"], f"{r['id']}: verdict {r['verdict']} != recomputed {exp}"

    # decision boundary present
    facts = [int(r["factuality_score"]) for r in rows]
    tasks = [int(r["task_completion_score"]) for r in rows]
    assert 3 in facts and 4 in facts, "no factuality boundary rows (need 3 and 4)"
    assert 3 in tasks, "no task_completion=3 boundary row"

    borderline = [r for r in rows if r["difficulty"] == "borderline"]
    assert 32 <= len(borderline) <= 40, f"borderline count {len(borderline)} not ~36"
    for r in borderline:
        f, t = int(r["factuality_score"]), int(r["task_completion_score"])
        assert f in (3, 4) or t in (2, 3), f"{r['id']}: borderline not adjacent to a threshold"

    # fail-mode split (exact, per slot plan)
    modes = {"hallucination": 0, "format_violation": 0, "task_incomplete": 0}
    for r in fails:
        modes[r["failure_mode"]] += 1
    assert modes == {"hallucination": 24, "format_violation": 20, "task_incomplete": 16}, modes

    # graded hallucination severity
    hall = [r for r in fails if r["failure_mode"] == "hallucination"]
    sev = {1: 0, 2: 0, 3: 0}
    for r in hall:
        sev[int(r["factuality_score"])] += 1
    assert sev == {1: 4, 2: 8, 3: 12}, f"hallucination severity {sev} != 4/8/12"

    # halo probes: format fails with perfect content
    halo = [r for r in fails if r["failure_mode"] == "format_violation"
            and int(r["task_completion_score"]) == 5 and int(r["factuality_score"]) == 5]
    assert len(halo) >= 8, f"only {len(halo)} halo-probe rows (<8)"

    # matched pairs
    pairs: dict[str, list[dict]] = {}
    for r in rows:
        if r["pair_id"]:
            pairs.setdefault(r["pair_id"], []).append(r)
    assert 15 <= len(pairs) <= 20, f"{len(pairs)} matched pairs (want 15-20)"
    for pid, members in pairs.items():
        assert len(members) == 2, f"{pid} has {len(members)} members"
        verdicts = sorted(m["verdict"] for m in members)
        assert verdicts == ["fail", "pass"], f"{pid} not one pass + one fail"
        assert members[0]["input"] == members[1]["input"], f"{pid} inputs differ"

    # format invariants on PASS rows
    for r in rows:
        if r["verdict"] != "pass":
            continue
        if r["eval_context"] == "refusal":
            assert r["output"] == REFUSAL, f"{r['id']}: refusal-pass not exact refusal string"
        else:
            assert "—" in r["output"], f"{r['id']}: pass output missing inline citation"
            assert DISCLAIMER in r["output"], f"{r['id']}: pass output missing disclaimer footer"

    # grounding: pass-row citations reference only real docs; no fake docs leak into pass/output
    for r in rows:
        if r["verdict"] == "pass":
            for tok in r["expected_citations"].split("|"):
                tok = tok.strip()
                if tok:
                    assert tok.split()[0] in ("SJB", "SSB", "Arogya"), f"{r['id']}: bad citation {tok}"
            for fake in FAKE_DOCS:
                assert fake not in r["output"], f"{r['id']}: fake doc '{fake}' in a PASS output"

    # every fail has a non-empty error_span
    for r in fails:
        assert r["error_span"].strip(), f"{r['id']}: fail has empty error_span"

    # context distribution (soft)
    ctxc = {c: 0 for c in CTX_TARGET}
    for r in rows:
        ctxc[r["eval_context"]] += 1
    for c, tgt in CTX_TARGET.items():
        assert abs(ctxc[c] - tgt) <= 12, f"ctx {c}={ctxc[c]} far from target {tgt}"

    print("VERIFY OK — 200 rows, 60 fail (30%), 36-band borderline, verdict integrity clean.")
    print(f"  fail modes      : {modes}")
    print(f"  hall severity   : fact1={sev[1]} fact2={sev[2]} fact3={sev[3]}")
    print(f"  halo probes     : {len(halo)}")
    print(f"  matched pairs   : {len(pairs)}")
    print(f"  borderline rows : {len(borderline)}")
    print(f"  context mix     : {ctxc}")
    print(f"  seeds used      : {len({r['seed_id'] for r in rows})} / {len(SEEDS)}")


def verify_live(rows: list[dict]):
    assert len(rows) == 200, f"live row count {len(rows)} != 200"
    inputs = [r["input"] for r in rows]
    assert len(set(inputs)) == 200, f"live inputs not unique ({len(set(inputs))} distinct)"
    hard = [r for r in rows if r["_difficulty"] == "hard"]
    assert 55 <= len(hard) <= 65, f"hard count {len(hard)} not ~60 (~30%)"
    for r in rows:
        assert r["expected_output"].strip(), "empty expected_output"
        assert "REFERENCE ANSWER:" in r["eval_context"], "reference not packed into eval_context"
    refusal = [r for r in rows if r["_ctx"] == "refusal"]
    for r in refusal:
        assert "a refusal is the correct response" in r["eval_context"], "refusal ref missing"
    ctxc = {c: 0 for c in LIVE_CTX_TARGET}
    for r in rows:
        ctxc[r["_ctx"]] += 1
    print(f"VERIFY LIVE OK — 200 rows, {len(hard)} hard (~30%), unique inputs.")
    print(f"  context mix : {ctxc}")


def verify_cal(rows: list[dict]):
    assert len(rows) == 200, f"cal row count {len(rows)} != 200"
    for r in rows:
        assert set(r) == set(TRYEVAL_CAL_FIELDS), f"unexpected cal columns: {set(r)}"
        assert r["output"].strip(), "empty output (direct-eval needs a filled output)"
        assert "REFERENCE ANSWER:" in r["eval_context"], "reference not packed into eval_context"
    # (input, output) join key to the gold side-file is unique-enough: identical pairs
    # necessarily carry identical gold labels, so any ambiguity is benign.
    print("VERIFY CAL OK — 200 direct-eval rows; gold stripped (join gold on input+output).")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="run invariant checks after build")
    ap.add_argument("--emit", choices=["labeled", "tryeval-live", "tryeval-calibration", "all"],
                    default="labeled", help="which artifact(s) to build")
    ap.add_argument("--out", default=OUT)
    args = ap.parse_args()

    if args.emit in ("labeled", "all"):
        rows = build_rows(random.Random(1234))
        write_csv(rows, args.out if args.emit == "labeled" else OUT)
        print(f"Wrote {len(rows)} labeled rows -> {OUT}")
        if args.verify:
            verify(rows)

    if args.emit in ("tryeval-live", "all"):
        live = emit_live()
        write_cols(live, TRYEVAL_LIVE_FIELDS, LIVE_OUT)
        print(f"Wrote {len(live)} live rows -> {LIVE_OUT}")
        if args.verify:
            verify_live(live)

    if args.emit in ("tryeval-calibration", "all"):
        cal = emit_calibration(random.Random(1234))
        write_cols(cal, TRYEVAL_CAL_FIELDS, CAL_OUT)
        print(f"Wrote {len(cal)} calibration rows -> {CAL_OUT}")
        if args.verify:
            verify_cal(cal)


if __name__ == "__main__":
    main()
