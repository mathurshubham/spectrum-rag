#!/usr/bin/env python3
"""Build golden_sets/law-judge-dataset.csv — a labeled LLM-judge / HITL benchmark.

Deterministic (fixed RNG seed), no API calls. 300 rows, 30% baked-in failure rate,
grounded in the 8 indexed Indian statute documents (BNS 2023, BNSS 2023, BSA 2023,
Indian Contract Act 1872, Consumer Protection Act 2019, DPDP Act 2023, Constitution of
India, and the repeal-mapping reference). Each row carries an actual model-style `output`,
three gold rubric scores, a derived pass/fail `verdict`, a `failure_mode`, an `error_span`,
a `judge_rationale`, and analysis columns (`seed_id`, `pair_id`, `difficulty`, `judge_type`).

Domain quirk: this domain has a GUARD-HEAVY design built around REPEALED statutes. A query
about a repealed provision (IPC / CrPC / Indian Evidence Act / Consumer Protection Act 1986)
must be answered by stating the provision is repealed and naming the replacement statute +
section from the LAW_MAPPINGS chunk. In that band, a fact-drift (fact 3) = naming the WRONG
replacement section; a fabrication (fact 1) = citing the repealed statute AS IF it were the
current governing law.

Run `python _build_law_judge.py --emit all --verify` to build + assert all invariants.
"""
from __future__ import annotations
import argparse
import csv
import os
import random

# ---------------------------------------------------------------------------
# Constants (from demos/law/prompts/system_v1.md + manifest.yaml)
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "law-judge-dataset.csv")

FOOTER = "*This is not legal advice. For specific legal matters, consult a qualified advocate.*"
REFUSAL = (
    "I cannot answer this question based on the available legal corpus. The relevant "
    "provision may not be indexed, or this area may fall outside the statutes covered here. "
    "Please consult a qualified legal professional."
)
# short -> full doc_title (manifest doc_titles; Constitution section_ref = 'Art. {n}').
DOC = {
    "BNS": "Bharatiya Nyaya Sanhita 2023",
    "BNSS": "Bharatiya Nagarik Suraksha Sanhita 2023",
    "BSA": "Bharatiya Sakshya Adhiniyam 2023",
    "Contract Act": "Indian Contract Act 1872",
    "CP": "Consumer Protection Act 2019",
    "DPDP": "Digital Personal Data Protection Act 2023",
    "Constitution": "Constitution of India",
    "Mappings": "Law Repeal Mappings Reference",
}
# True-but-generic sentence per doc, used to build on-format off-topic (task) failures.
DOC_BLURB = {
    "BNS": "The Bharatiya Nyaya Sanhita 2023 is India's principal criminal code, replacing the Indian Penal Code",
    "BNSS": "The Bharatiya Nagarik Suraksha Sanhita 2023 is India's code of criminal procedure",
    "BSA": "The Bharatiya Sakshya Adhiniyam 2023 is India's law of evidence",
    "Contract Act": "The Indian Contract Act 1872 governs the general law of contracts in India",
    "CP": "The Consumer Protection Act 2019 protects and enforces the rights of consumers in India",
    "DPDP": "The Digital Personal Data Protection Act 2023 governs the processing of digital personal data",
    "Constitution": "The Constitution of India is the supreme law of the land",
    "Mappings": "The repeal-mapping reference cross-walks repealed statutes to their current replacements",
}
# Out-of-corpus / repealed statute names used as fabrication (fact1) markers. These are
# cited AS IF current in fabrication rows — never a real corpus doc.
FAKE_DOCS = ("Indian Penal Code 1860", "Code of Criminal Procedure 1973", "Indian Evidence Act 1872")
# Citation-token prefixes considered grounded (real doc shorts + Constitution's 'Art.' + mapping ref).
VALID_CITE_PREFIXES = (
    "BNS", "BNSS", "BSA", "Contract Act", "CP", "DPDP", "Art.", "LAW_MAPPINGS:full", "Mappings",
)

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
# Seed bank (~58 seeds), grounded in the corpus + validate_checks.yaml + LAW_MAPPINGS.
# ---------------------------------------------------------------------------
SEEDS: list[dict] = []


def seed(**kw):
    SEEDS.append(kw)


# ---- BNS 2023 (criminal code) -------------------------------------------------
seed(id="bns-murder", ctx="retrieval", doc="BNS", cite="BNS s.103", wrong_cite="BNS s.105",
     q=["What is the punishment for murder under BNS 2023?",
        "How does the Bharatiya Nyaya Sanhita punish murder?",
        "What does BNS Section 103 prescribe for murder?"],
     ans="Section 103 of the Bharatiya Nyaya Sanhita 2023 punishes murder with death or imprisonment for life, and the offender is also liable to a fine",
     core="Section 103 of the Bharatiya Nyaya Sanhita 2023 punishes murder with death or imprisonment for life",
     secondary="that the offender is also liable to a fine",
     minor="Murder under BNS Section 103 carries a maximum of death, or life imprisonment, plus a fine",
     drift="Section 103 punishes murder with imprisonment for life or death, and a mandatory minimum of 10 years",
     drift_span="mandatory minimum of 10 years",
     invented="Section 103 prescribes a fixed 25-year sentence and a Rs.5,00,000 fine for every murder",
     invented_span="fixed 25-year sentence and a Rs.5,00,000 fine",
     fabricated="The punishment for murder is death or life imprisonment under Section 302 **(IPC s.302 — Indian Penal Code 1860)**, which remains the governing provision",
     fab_span="IPC s.302 — Indian Penal Code 1860",
     exp_ans="BNS s.103: murder punishable by death or life imprisonment, plus fine.",
     exp_cite="BNS s.103", exp_assert="must_cite=BNS s.103;must_contain=death|imprisonment for life;should_refuse=false")

seed(id="bns-rape", ctx="retrieval", doc="BNS", cite="BNS s.63", wrong_cite="BNS s.64",
     q=["What is the punishment for rape under BNS 2023?",
        "How does the Bharatiya Nyaya Sanhita define rape?",
        "What does BNS Section 63 say about rape?"],
     ans="Section 63 of the Bharatiya Nyaya Sanhita 2023 defines rape, and Section 64 prescribes rigorous imprisonment of not less than ten years, extendable to imprisonment for life, along with a fine",
     core="Section 63 of the Bharatiya Nyaya Sanhita 2023 defines rape",
     secondary="that Section 64 sets punishment at not less than ten years' rigorous imprisonment",
     drift="Section 63 defines rape and prescribes rigorous imprisonment of not less than seven years",
     drift_span="not less than seven years",
     exp_ans="BNS s.63 defines rape; s.64 = >=10 yrs rigorous imprisonment to life, plus fine.",
     exp_cite="BNS s.63", exp_assert="must_cite=BNS s.63;must_contain=rape;should_refuse=false")

seed(id="bns-robbery", ctx="retrieval", doc="BNS", cite="BNS s.309", wrong_cite="BNS s.310",
     q=["What does BNS Section 309 say about robbery?",
        "How is robbery defined under the Bharatiya Nyaya Sanhita 2023?"],
     ans="Section 309 of the Bharatiya Nyaya Sanhita 2023 provides that in all robbery there is either theft or extortion, and theft becomes robbery where force or fear of instant hurt is used to commit it or carry away the property",
     minor="Robbery under BNS Section 309 is theft or extortion carried out with force or the threat of instant harm",
     drift="Section 309 provides that robbery is theft committed only at night with a deadly weapon",
     drift_span="only at night with a deadly weapon",
     exp_ans="BNS s.309: robbery is theft or extortion with force / fear of instant hurt.",
     exp_cite="BNS s.309", exp_assert="must_cite=BNS s.309;must_contain=robbery;should_refuse=false")

seed(id="bns-punishments", ctx="retrieval", doc="BNS", cite="BNS s.4", wrong_cite="BNS s.2",
     q=["What punishments are available under BNS 2023?",
        "What are the kinds of punishment under the Bharatiya Nyaya Sanhita?"],
     ans="Section 4 of the Bharatiya Nyaya Sanhita 2023 lists the punishments as death, imprisonment for life, imprisonment, forfeiture of property, fine, and community service",
     core="Section 4 lists punishments including death, imprisonment for life and imprisonment",
     secondary="that fine, forfeiture of property and community service are also punishments",
     minor="BNS Section 4 sets out punishments such as death, life imprisonment, fine and community service",
     exp_ans="BNS s.4: death, life imprisonment, imprisonment, forfeiture, fine, community service.",
     exp_cite="BNS s.4", exp_assert="must_cite=BNS s.4;must_contain=punishment;should_refuse=false")

seed(id="bns-definitions", ctx="retrieval", doc="BNS", cite="BNS s.2", wrong_cite="BNS s.4",
     q=["What does BNS Section 2 cover?",
        "Where are the definitions in the Bharatiya Nyaya Sanhita 2023?"],
     ans="Section 2 of the Bharatiya Nyaya Sanhita 2023 sets out the definitions used throughout the Sanhita",
     minor="BNS Section 2 is the definitions clause of the criminal code",
     exp_ans="BNS s.2 = definitions used across the Sanhita.",
     exp_cite="BNS s.2", exp_assert="must_cite=BNS s.2;must_contain=definitions;should_refuse=false")

# ---- Constitution of India (section_ref = 'Art. {n}') -------------------------
seed(id="const-life", ctx="retrieval", doc="Constitution", cite="Art. 21", wrong_cite="Art. 19",
     q=["What is Article 21 of the Constitution of India?",
        "What does Article 21 protect?",
        "What is the right to life under the Constitution?"],
     ans="Article 21 of the Constitution provides that no person shall be deprived of his life or personal liberty except according to procedure established by law",
     minor="Article 21 broadly protects life and personal liberty, subject to lawful procedure",
     drift="Article 21 provides that no person shall be deprived of life or property except by procedure established by law",
     drift_span="or property",
     exp_ans="Art. 21: no deprivation of life or personal liberty except by procedure established by law.",
     exp_cite="Art. 21", exp_assert="must_cite=Art. 21;must_contain=life and personal liberty;should_refuse=false")

seed(id="const-equality", ctx="retrieval", doc="Constitution", cite="Art. 14", wrong_cite="Art. 21",
     q=["What does Article 14 of the Constitution guarantee?",
        "What is the right to equality under the Constitution?"],
     ans="Article 14 provides that the State shall not deny to any person equality before the law or the equal protection of the laws within the territory of India",
     minor="Article 14 broadly guarantees equality before the law and equal protection of the laws",
     exp_ans="Art. 14: equality before the law and equal protection of the laws.",
     exp_cite="Art. 14", exp_assert="must_cite=Art. 14;must_contain=equality;should_refuse=false")

seed(id="const-freedom", ctx="retrieval", doc="Constitution", cite="Art. 19", wrong_cite="Art. 14",
     q=["What freedoms does Article 19 of the Constitution protect?",
        "What does Article 19 guarantee?"],
     ans="Article 19 guarantees to citizens freedoms including freedom of speech and expression, assembly, association, movement, residence and profession, subject to reasonable restrictions",
     core="Article 19 guarantees freedoms such as speech and expression, assembly and association",
     secondary="that these freedoms are subject to reasonable restrictions",
     drift="Article 19 guarantees the freedoms of speech, assembly and religion",
     drift_span="and religion",
     exp_ans="Art. 19: freedoms of speech, assembly, association, movement, residence, profession.",
     exp_cite="Art. 19", exp_assert="must_cite=Art. 19;must_contain=freedom;should_refuse=false")

seed(id="const-remedies", ctx="retrieval", doc="Constitution", cite="Art. 32", wrong_cite="Art. 226",
     q=["What is Article 32 of the Constitution about?",
        "What is the right to constitutional remedies?"],
     ans="Article 32 guarantees the right to move the Supreme Court for enforcement of fundamental rights and empowers it to issue writs such as habeas corpus, mandamus, prohibition, quo warranto and certiorari",
     core="Article 32 guarantees the right to move the Supreme Court to enforce fundamental rights",
     secondary="that the Court may issue writs such as habeas corpus and mandamus",
     minor="Article 32 lets a person approach the Supreme Court directly to enforce fundamental rights",
     exp_ans="Art. 32: right to move the Supreme Court for enforcement of fundamental rights; writs.",
     exp_cite="Art. 32", exp_assert="must_cite=Art. 32;must_contain=remedies;should_refuse=false")

seed(id="const-hc-writ", ctx="retrieval", doc="Constitution", cite="Art. 226", wrong_cite="Art. 32",
     q=["What is Article 226 of the Constitution about?",
        "What power do High Courts have under Article 226?"],
     ans="Article 226 confers power on High Courts to issue directions, orders or writs — including habeas corpus, mandamus, prohibition, quo warranto and certiorari — to any person or authority within their territorial jurisdiction",
     minor="Article 226 gives High Courts writ jurisdiction over persons and authorities in their territory",
     drift="Article 226 confers writ jurisdiction only on the Supreme Court, not the High Courts",
     drift_span="only on the Supreme Court, not the High Courts",
     exp_ans="Art. 226: High Court power to issue writs within its territorial jurisdiction.",
     exp_cite="Art. 226", exp_assert="must_cite=Art. 226;must_contain=High Court;should_refuse=false")

# ---- Indian Contract Act 1872 -------------------------------------------------
seed(id="contract-valid", ctx="retrieval", doc="Contract Act", cite="Contract Act s.10", wrong_cite="Contract Act s.2",
     q=["What constitutes a valid contract under the Indian Contract Act 1872?",
        "When is an agreement a contract under Section 10?"],
     ans="Under Section 10 of the Indian Contract Act 1872, an agreement is a contract if made by the free consent of parties competent to contract, for a lawful consideration and with a lawful object, and not expressly declared void",
     core="Under Section 10, an agreement is a contract if made by free consent of competent parties",
     secondary="that it also requires lawful consideration and a lawful object",
     minor="Section 10 requires free consent, competent parties, lawful consideration and a lawful object",
     drift="Under Section 10, an agreement is a contract only if it is in writing and registered",
     drift_span="only if it is in writing and registered",
     exp_ans="Contract Act s.10: free consent, competent parties, lawful consideration and object.",
     exp_cite="Contract Act s.10", exp_assert="must_cite=Contract Act s.10;must_contain=competent|free consent;should_refuse=false")

seed(id="contract-proposal", ctx="retrieval", doc="Contract Act", cite="Contract Act s.2", wrong_cite="Contract Act s.10",
     q=["How does the Contract Act define a proposal?",
        "What does Section 2 of the Indian Contract Act define?"],
     ans="Section 2 of the Indian Contract Act 1872 defines core terms — a proposal is when one person signifies to another his willingness to do or abstain from doing something with a view to obtaining assent, and covers acceptance, promise and consideration",
     minor="Section 2 defines a proposal as signifying willingness to act or abstain to obtain another's assent",
     exp_ans="Contract Act s.2: defines proposal, acceptance, promise and consideration.",
     exp_cite="Contract Act s.2", exp_assert="must_cite=Contract Act s.2;must_contain=proposal;should_refuse=false")

seed(id="contract-damages", ctx="retrieval", doc="Contract Act", cite="Contract Act s.73", wrong_cite="Contract Act s.74",
     q=["What does Section 73 of the Contract Act say about damages?",
        "What compensation is payable when a contract is broken?"],
     ans="Section 73 of the Indian Contract Act 1872 provides that when a contract is broken, the party who suffers is entitled to compensation for loss or damage that naturally arose in the usual course of things from the breach, but not for remote or indirect loss",
     core="Section 73 entitles the injured party to compensation for loss naturally arising from the breach",
     secondary="that compensation is not payable for remote or indirect loss",
     minor="Section 73 gives compensation for losses naturally flowing from a breach of contract",
     drift="Section 73 entitles the injured party to compensation, including remote and indirect losses",
     drift_span="including remote and indirect losses",
     invented="Section 73 fixes damages at a flat 10% of the contract value in every breach",
     invented_span="flat 10% of the contract value",
     exp_ans="Contract Act s.73: compensation for loss naturally arising from breach; not remote loss.",
     exp_cite="Contract Act s.73", exp_assert="must_cite=Contract Act s.73;must_contain=compensation|breach;should_refuse=false")

# ---- Consumer Protection Act 2019 --------------------------------------------
seed(id="cp-consumer", ctx="retrieval", doc="CP", cite="CP s.2", wrong_cite="CP s.35",
     q=["What is the definition of consumer under the Consumer Protection Act 2019?",
        "Who is a consumer under the CP Act 2019?"],
     ans="Section 2 of the Consumer Protection Act 2019 defines a consumer as a person who buys goods or hires services for consideration, but excludes a person who obtains goods for resale or for a commercial purpose",
     core="Section 2 defines a consumer as a person who buys goods or hires services for consideration",
     secondary="that it excludes purchases for resale or commercial purpose",
     minor="Under Section 2, a consumer buys goods or services for consideration, not for resale",
     drift="Section 2 defines a consumer as anyone who buys goods, including for resale and commercial purpose",
     drift_span="including for resale and commercial purpose",
     exp_ans="CP s.2: buyer of goods/services for consideration; excludes resale/commercial purpose.",
     exp_cite="CP s.2", exp_assert="must_cite=CP s.2;must_contain=consumer;should_refuse=false")

seed(id="cp-complaint", ctx="retrieval", doc="CP", cite="CP s.35", wrong_cite="CP s.2",
     q=["How does a consumer file a complaint under the CP Act 2019?",
        "What does Section 35 of the Consumer Protection Act say?"],
     ans="Section 35 of the Consumer Protection Act 2019 allows a consumer to file a complaint before the District Commission where the value of the goods or services and compensation claimed is within its pecuniary jurisdiction",
     minor="Section 35 lets a consumer complain to the District Commission within its pecuniary limits",
     exp_ans="CP s.35: complaint to the District Commission within its pecuniary jurisdiction.",
     exp_cite="CP s.35", exp_assert="must_cite=CP s.35;must_contain=complaint;should_refuse=false")

seed(id="cp-rights", ctx="retrieval", doc="CP", cite="CP s.17", wrong_cite="CP s.35",
     q=["How can violations of consumer rights be raised to the CCPA?",
        "What does Section 17 of the Consumer Protection Act cover?"],
     ans="Section 17 of the Consumer Protection Act 2019 allows a complaint about a violation of consumer rights to be forwarded to the Central Consumer Protection Authority (CCPA) by the District Collector",
     minor="Section 17 routes complaints on violation of consumer rights to the CCPA",
     exp_ans="CP s.17: violation of consumer rights may be raised to the CCPA.",
     exp_cite="CP s.17", exp_assert="must_cite=CP s.17;must_contain=consumer rights;should_refuse=false")

# ---- DPDP Act 2023 ------------------------------------------------------------
seed(id="dpdp-personal-data", ctx="retrieval", doc="DPDP", cite="DPDP s.2", wrong_cite="DPDP s.4",
     q=["What is personal data under the DPDP Act 2023?",
        "How does the DPDP Act define personal data?"],
     ans="Section 2 of the Digital Personal Data Protection Act 2023 defines personal data as any data about an individual who is identifiable by or in relation to such data",
     minor="Under Section 2, personal data is any data about an identifiable individual",
     exp_ans="DPDP s.2: personal data = data about an identifiable individual.",
     exp_cite="DPDP s.2", exp_assert="must_cite=DPDP s.2;must_contain=personal data;should_refuse=false")

seed(id="dpdp-processing", ctx="retrieval", doc="DPDP", cite="DPDP s.4", wrong_cite="DPDP s.8",
     q=["What are the grounds for processing personal data under the DPDP Act 2023?",
        "When may personal data be processed under the DPDP Act?"],
     ans="Section 4 of the Digital Personal Data Protection Act 2023 allows processing of personal data only for a lawful purpose for which the Data Principal has given consent, or for certain legitimate uses",
     core="Section 4 permits processing only for a lawful purpose with the Data Principal's consent",
     secondary="that processing is also allowed for certain legitimate uses",
     minor="Section 4 allows data processing for a lawful purpose based on consent or legitimate uses",
     drift="Section 4 allows processing of personal data for any commercial purpose without consent",
     drift_span="for any commercial purpose without consent",
     exp_ans="DPDP s.4: processing only for a lawful purpose, on consent or legitimate uses.",
     exp_cite="DPDP s.4", exp_assert="must_cite=DPDP s.4;must_contain=processing|consent;should_refuse=false")

seed(id="dpdp-obligations", ctx="retrieval", doc="DPDP", cite="DPDP s.8", wrong_cite="DPDP s.4",
     q=["What obligations does a Data Fiduciary have under the DPDP Act 2023?",
        "What does Section 8 of the DPDP Act require of a Data Fiduciary?"],
     ans="Section 8 of the Digital Personal Data Protection Act 2023 places general obligations on a Data Fiduciary, including ensuring accuracy of data, implementing reasonable security safeguards, and erasing personal data once the purpose is served",
     core="Section 8 obliges a Data Fiduciary to keep data accurate and secure",
     secondary="that it must erase personal data once the purpose is served",
     minor="Section 8 requires the Data Fiduciary to keep data accurate, secure it and erase it when done",
     exp_ans="DPDP s.8: Data Fiduciary duties — accuracy, security safeguards, erasure.",
     exp_cite="DPDP s.8", exp_assert="must_cite=DPDP s.8;must_contain=obligations|data fiduciary;should_refuse=false")

# ---- BNSS 2023 (criminal procedure) ------------------------------------------
seed(id="bnss-fir", ctx="retrieval", doc="BNSS", cite="BNSS s.173", wrong_cite="BNSS s.193",
     q=["What is the procedure for filing an FIR under BNSS 2023?",
        "What does BNSS Section 173 say about cognizable cases?"],
     ans="Section 173 of the Bharatiya Nagarik Suraksha Sanhita 2023 provides that information relating to a cognizable offence shall be reduced to writing by the officer in charge and signed by the informant (the FIR)",
     core="Section 173 requires information about a cognizable offence to be reduced to writing",
     secondary="that it must be signed by the informant",
     minor="BNSS Section 173 governs recording an FIR in cognizable cases",
     drift="Section 173 provides that FIRs may be registered only for non-cognizable offences",
     drift_span="only for non-cognizable offences",
     exp_ans="BNSS s.173: FIR — information on a cognizable offence recorded in writing.",
     exp_cite="BNSS s.173", exp_assert="must_cite=BNSS s.173;must_contain=cognizable;should_refuse=false")

seed(id="bnss-bail", ctx="retrieval", doc="BNSS", cite="BNSS s.480", wrong_cite="BNSS s.173",
     q=["What does BNSS 2023 say about bail in non-bailable offences?",
        "How is bail granted in non-bailable offences under BNSS?"],
     ans="Section 480 of the Bharatiya Nagarik Suraksha Sanhita 2023 empowers a court to grant bail in non-bailable offences subject to conditions, including whether there are reasonable grounds to believe the accused committed the offence",
     core="Section 480 empowers the court to grant bail in non-bailable offences subject to conditions",
     secondary="that the court weighs whether there are reasonable grounds of guilt",
     minor="BNSS Section 480 lets the court grant bail in non-bailable offences on conditions",
     exp_ans="BNSS s.480: bail in non-bailable offences, subject to conditions.",
     exp_cite="BNSS s.480", exp_assert="must_cite=BNSS s.480;must_contain=bail;should_refuse=false")

seed(id="bnss-definitions", ctx="retrieval", doc="BNSS", cite="BNSS s.2", wrong_cite="BNSS s.173",
     q=["What does BNSS Section 2 cover?",
        "Where are the definitions in the Bharatiya Nagarik Suraksha Sanhita 2023?"],
     ans="Section 2 of the Bharatiya Nagarik Suraksha Sanhita 2023 sets out the definitions used throughout the procedural code",
     minor="BNSS Section 2 is the definitions clause of the criminal procedure code",
     exp_ans="BNSS s.2 = definitions used across the procedural code.",
     exp_cite="BNSS s.2", exp_assert="must_cite=BNSS s.2;must_contain=definitions;should_refuse=false")

# ---- BSA 2023 (evidence) ------------------------------------------------------
seed(id="bsa-electronic", ctx="retrieval", doc="BSA", cite="BSA s.63", wrong_cite="BSA s.39",
     q=["What is the admissibility of electronic records under BSA 2023?",
        "What does BSA Section 63 say about electronic records?"],
     ans="Section 63 of the Bharatiya Sakshya Adhiniyam 2023 deals with the admissibility of electronic records and sets out the conditions under which they are admissible as evidence",
     minor="BSA Section 63 governs when electronic records are admissible as evidence",
     drift="Section 63 provides that electronic records are never admissible as evidence",
     drift_span="never admissible as evidence",
     exp_ans="BSA s.63: conditions for admissibility of electronic records.",
     exp_cite="BSA s.63", exp_assert="must_cite=BSA s.63;must_contain=electronic;should_refuse=false")

seed(id="bsa-expert", ctx="retrieval", doc="BSA", cite="BSA s.39", wrong_cite="BSA s.63",
     q=["What does BSA 2023 say about expert opinions?",
        "How are expert opinions treated under Section 39 of the BSA?"],
     ans="Section 39 of the Bharatiya Sakshya Adhiniyam 2023 provides that when the court has to form an opinion on a point of foreign law, science, art, handwriting or fingerprints, the opinions of experts on that point are relevant facts",
     minor="BSA Section 39 makes expert opinions on science, art or handwriting relevant facts",
     exp_ans="BSA s.39: opinions of experts are relevant facts on specialised points.",
     exp_cite="BSA s.39", exp_assert="must_cite=BSA s.39;must_contain=expert;should_refuse=false")

seed(id="bsa-definitions", ctx="retrieval", doc="BSA", cite="BSA s.2", wrong_cite="BSA s.39",
     q=["What does BSA Section 2 define?",
        "Where are the definitions in the Bharatiya Sakshya Adhiniyam 2023?"],
     ans="Section 2 of the Bharatiya Sakshya Adhiniyam 2023 defines core terms such as evidence, including statements and documents produced for the court's inspection",
     minor="BSA Section 2 is the definitions clause, including the meaning of evidence",
     exp_ans="BSA s.2: definitions, including 'evidence'.",
     exp_cite="BSA s.2", exp_assert="must_cite=BSA s.2;must_contain=evidence;should_refuse=false")


# ---- Guard: repealed-statute crosswalk (GUARD-HEAVY) --------------------------
def guard_seed(id, old, old_full, old_sec, repl_short, repl_cite, topic,
               ans_tail, drift_wrong_cite, minor=None):
    """Repealed-provision guard. Correct answer: state repeal + name replacement from LAW_MAPPINGS.
    drift (fact3) = WRONG replacement section; fabricated (fact1) = cite the repealed statute as current.
    """
    repl_title = DOC[repl_short]
    correct = (f"{old_sec} belongs to the now-repealed {old_full}; the current equivalent is "
               f"{repl_cite} of the {repl_title}, {ans_tail}")
    core = (f"{old_sec} belongs to the repealed {old_full}; the current equivalent is "
            f"{repl_cite} of the {repl_title}")
    drift = (f"{old_sec} is repealed; the equivalent provision is now {drift_wrong_cite} of the "
             f"{repl_title}, {ans_tail}")
    invented = (f"{old_sec} is repealed; {repl_cite} of the {repl_title} now imposes a fixed "
                f"20-year sentence and a Rs.10,00,000 fine in every case")
    fabricated = (f"{ans_tail.capitalize()} under {old_sec} **({old_sec} — {old_full})**, "
                  f"which remains the governing provision")
    inline = (f"**(LAW_MAPPINGS:full — {DOC['Mappings']}; {repl_cite} — {repl_title})**")
    seed(id=id, ctx="guard", doc="Mappings", cite=f"LAW_MAPPINGS:full|{repl_cite}",
         wrong_cite=drift_wrong_cite, inline_cite=inline,
         q=[topic[0], topic[1]] + ([topic[2]] if len(topic) > 2 else []),
         ans=correct, core=core, secondary=f"the detail that {ans_tail}",
         minor=minor or (f"{old_sec} is from the old law; it is now broadly covered by {repl_cite} of the {repl_title}"),
         drift=drift, drift_span=f"{drift_wrong_cite} of the {repl_title}",
         invented=invented, invented_span="fixed 20-year sentence and a Rs.10,00,000 fine",
         fabricated=fabricated, fab_span=f"{old_sec} — {old_full}",
         exp_ans=f"{old_sec} is repealed ({old_full}); current provision is {repl_cite} of the {repl_title}.",
         exp_cite=f"LAW_MAPPINGS:full|{repl_cite}",
         exp_assert=f"guard=old_law;must_contain=repealed|{repl_short};must_cite_doc_id=LAW_MAPPINGS;should_refuse=false")


guard_seed("guard-ipc302", "IPC", "Indian Penal Code 1860", "IPC Section 302", "BNS", "BNS s.103",
           ["What does IPC Section 302 say about murder?",
            "Is IPC 302 still the law for murder?",
            "What is the current provision for murder that replaced IPC 302?"],
           "which punishes murder with death or imprisonment for life and a fine",
           "BNS s.101")
guard_seed("guard-ipc375", "IPC", "Indian Penal Code 1860", "IPC Section 375", "BNS", "BNS s.63",
           ["What does Section 375 of IPC say about rape?",
            "Is IPC 375 still in force for rape?"],
           "which defines the offence of rape",
           "BNS s.65")
guard_seed("guard-ipc420", "IPC", "Indian Penal Code 1860", "IPC Section 420", "BNS", "BNS s.318",
           ["What does Section 420 IPC say about cheating?",
            "Is IPC 420 still the cheating provision?"],
           "which deals with cheating",
           "BNS s.316")
guard_seed("guard-ipc378", "IPC", "Indian Penal Code 1860", "IPC Section 378", "BNS", "BNS s.303",
           ["What does IPC Section 378 say about theft?",
            "Is IPC 378 still the theft provision?"],
           "which defines theft",
           "BNS s.305")
guard_seed("guard-ipc390", "IPC", "Indian Penal Code 1860", "IPC Section 390", "BNS", "BNS s.309",
           ["What does IPC Section 390 say about robbery?",
            "Is IPC 390 still in force for robbery?"],
           "which defines robbery",
           "BNS s.311")
guard_seed("guard-ipc120b", "IPC", "Indian Penal Code 1860", "IPC Section 120B", "BNS", "BNS s.61",
           ["What does IPC Section 120B say about criminal conspiracy?",
            "Is IPC 120B still the conspiracy provision?"],
           "which deals with criminal conspiracy",
           "BNS s.62")
guard_seed("guard-ipc498a", "IPC", "Indian Penal Code 1860", "IPC Section 498A", "BNS", "BNS s.85",
           ["What does IPC Section 498A say about cruelty by a husband?",
            "Is IPC 498A still in force?"],
           "which deals with cruelty by a husband or his relatives",
           "BNS s.86")
guard_seed("guard-crpc154", "CrPC", "Code of Criminal Procedure 1973", "CrPC Section 154", "BNSS", "BNSS s.173",
           ["What does CrPC Section 154 say about registering an FIR?",
            "Is CrPC 154 still the FIR provision?"],
           "which governs information in cognizable cases (the FIR)",
           "BNSS s.175")
guard_seed("guard-crpc437", "CrPC", "Code of Criminal Procedure 1973", "CrPC Section 437", "BNSS", "BNSS s.480",
           ["What does CrPC Section 437 say about bail in non-bailable offences?",
            "Is CrPC 437 still the bail provision?"],
           "which governs bail in non-bailable offences",
           "BNSS s.483")
guard_seed("guard-crpc482", "CrPC", "Code of Criminal Procedure 1973", "CrPC Section 482", "BNSS", "BNSS s.528",
           ["What does CrPC Section 482 say about the inherent powers of the High Court?",
            "Is CrPC 482 still in force?"],
           "which preserves the inherent powers of the High Court",
           "BNSS s.531")
guard_seed("guard-evidence45", "Indian Evidence Act", "Indian Evidence Act 1872", "Section 45 of the Indian Evidence Act",
           "BSA", "BSA s.39",
           ["What does the Indian Evidence Act say about opinions of experts?",
            "Is Section 45 of the Evidence Act still the law on expert opinion?"],
           "which makes the opinions of experts relevant facts",
           "BSA s.45")
guard_seed("guard-evidence65b", "Indian Evidence Act", "Indian Evidence Act 1872", "Section 65B of the Indian Evidence Act",
           "BSA", "BSA s.63",
           ["What does Section 65B of the Indian Evidence Act say about electronic records?",
            "Is Section 65B of the Evidence Act still in force?"],
           "which governs the admissibility of electronic records",
           "BSA s.65")

# Consumer Protection 1986 -> 2019 (whole-statute repeal; no BNS-style section replacement)
seed(id="guard-cp1986", ctx="guard", doc="Mappings", cite="LAW_MAPPINGS:full|CP s.2",
     wrong_cite="CP s.11",
     inline_cite=f"**(LAW_MAPPINGS:full — {DOC['Mappings']}; CP s.2 — {DOC['CP']})**",
     q=["What does the Consumer Protection Act 1986 say about who is a consumer?",
        "Is the Consumer Protection Act 1986 still in force?"],
     ans="The Consumer Protection Act 1986 has been repealed and replaced by the Consumer Protection Act 2019; the definition of consumer is now in Section 2 of the Consumer Protection Act 2019",
     core="The Consumer Protection Act 1986 is repealed and replaced by the Consumer Protection Act 2019",
     secondary="that the consumer definition is now in Section 2 of the 2019 Act",
     minor="The 1986 Consumer Protection Act is superseded by the 2019 Act, which now defines a consumer",
     drift="The Consumer Protection Act 1986 has been replaced by the Consumer Protection Act 2015",
     drift_span="Consumer Protection Act 2015",
     invented="The Consumer Protection Act 1986 was replaced by a 2019 Act that fixes all compensation at Rs.1,00,000",
     invented_span="fixes all compensation at Rs.1,00,000",
     fabricated="A consumer is defined under Section 2(d) of the Consumer Protection Act 1986, which remains the governing statute",
     fab_span="Consumer Protection Act 1986, which remains the governing statute",
     exp_ans="CP Act 1986 is repealed; replaced by Consumer Protection Act 2019 (consumer def in CP s.2).",
     exp_cite="LAW_MAPPINGS:full|CP s.2",
     exp_assert="guard=old_law;must_contain=repealed|2019;must_cite_doc_id=LAW_MAPPINGS;should_refuse=false")


# ---- Edge / comparison --------------------------------------------------------
seed(id="edge-bns-ipc", ctx="edge", doc="Mappings", cite="LAW_MAPPINGS:full",
     inline_cite=f"**(LAW_MAPPINGS:full — {DOC['Mappings']})**",
     wrong_cite="BNS s.1",
     q=["What is the difference between BNS and IPC?",
        "How does the Bharatiya Nyaya Sanhita differ from the Indian Penal Code?"],
     ans="The Bharatiya Nyaya Sanhita 2023 replaced the Indian Penal Code 1860 as India's principal criminal code with effect from 1 July 2024; the repeal-mapping reference cross-walks IPC sections to their BNS equivalents (for example, IPC 302 to BNS Section 103)",
     core="The Bharatiya Nyaya Sanhita 2023 replaced the Indian Penal Code 1860 as the criminal code",
     secondary="that the mapping reference cross-walks IPC sections to BNS equivalents",
     drift="The Bharatiya Nyaya Sanhita 2023 amended, but did not replace, the Indian Penal Code 1860",
     drift_span="amended, but did not replace",
     exp_ans="BNS 2023 replaced IPC 1860 (from 1 Jul 2024); mapping cross-walks the sections.",
     exp_cite="LAW_MAPPINGS:full", exp_assert="must_cite_doc_id=LAW_MAPPINGS;should_refuse=false")

seed(id="edge-crpc-bnss", ctx="edge", doc="Mappings", cite="LAW_MAPPINGS:full",
     inline_cite=f"**(LAW_MAPPINGS:full — {DOC['Mappings']})**",
     wrong_cite="BNSS s.1",
     q=["What is the difference between CrPC and BNSS?",
        "How does BNSS 2023 relate to the old Code of Criminal Procedure?"],
     ans="The Bharatiya Nagarik Suraksha Sanhita 2023 replaced the Code of Criminal Procedure 1973 as India's criminal-procedure code from 1 July 2024; the mapping reference cross-walks CrPC sections to their BNSS equivalents (for example, CrPC 154 to BNSS Section 173)",
     minor="BNSS 2023 replaced the CrPC 1973 as the procedure code, with a section-by-section mapping",
     exp_ans="BNSS 2023 replaced CrPC 1973; mapping cross-walks the sections.",
     exp_cite="LAW_MAPPINGS:full", exp_assert="must_cite_doc_id=LAW_MAPPINGS;should_refuse=false")

seed(id="edge-bsa-evidence", ctx="edge", doc="Mappings", cite="LAW_MAPPINGS:full",
     inline_cite=f"**(LAW_MAPPINGS:full — {DOC['Mappings']})**",
     wrong_cite="BSA s.1",
     q=["How does the BSA 2023 relate to the Indian Evidence Act?",
        "What replaced the Indian Evidence Act 1872?"],
     ans="The Bharatiya Sakshya Adhiniyam 2023 replaced the Indian Evidence Act 1872 as India's law of evidence from 1 July 2024; the mapping reference cross-walks Evidence Act sections to their BSA equivalents (for example, Section 45 to BSA Section 39)",
     minor="BSA 2023 replaced the Indian Evidence Act 1872, with a mapping between the sections",
     exp_ans="BSA 2023 replaced the Indian Evidence Act 1872; mapping cross-walks the sections.",
     exp_cite="LAW_MAPPINGS:full", exp_assert="must_cite_doc_id=LAW_MAPPINGS;should_refuse=false")

seed(id="edge-three-codes", ctx="edge", doc="Mappings",
     inline_cite=(f"**(LAW_MAPPINGS:full — {DOC['Mappings']}; BNS s.2 — {DOC['BNS']}; "
                  f"BNSS s.2 — {DOC['BNSS']})**"),
     cite="LAW_MAPPINGS:full|BNS s.2|BNSS s.2",
     q=["Which new laws replaced the old criminal statutes in India?",
        "What are the three new criminal codes of 2023?"],
     ans="The three new 2023 criminal codes are the Bharatiya Nyaya Sanhita (replacing the Indian Penal Code), the Bharatiya Nagarik Suraksha Sanhita (replacing the Code of Criminal Procedure), and the Bharatiya Sakshya Adhiniyam (replacing the Indian Evidence Act)",
     core="The three new codes are the BNS, the BNSS and the BSA",
     secondary="that they replace the IPC, CrPC and Indian Evidence Act respectively",
     exp_ans="BNS (IPC), BNSS (CrPC), BSA (Evidence Act) — the three 2023 criminal codes.",
     exp_cite="LAW_MAPPINGS:full|BNS s.2|BNSS s.2",
     exp_assert="must_cite_doc_id=LAW_MAPPINGS;should_refuse=false")

seed(id="edge-cp-versions", ctx="edge", doc="Mappings", cite="LAW_MAPPINGS:full|CP s.2",
     inline_cite=f"**(LAW_MAPPINGS:full — {DOC['Mappings']}; CP s.2 — {DOC['CP']})**",
     wrong_cite="CP s.11",
     q=["What is the difference between the Consumer Protection Act 1986 and 2019?",
        "How does the 2019 Consumer Protection Act differ from the 1986 Act?"],
     ans="The Consumer Protection Act 2019 repealed and replaced the 1986 Act, redefining the consumer, extending protection to e-commerce, and creating the Central Consumer Protection Authority",
     minor="The 2019 Act replaced the 1986 Act and modernised consumer protection, including e-commerce",
     exp_ans="CP 2019 replaced CP 1986; broadened consumer definition and added the CCPA.",
     exp_cite="LAW_MAPPINGS:full|CP s.2", exp_assert="must_cite_doc_id=LAW_MAPPINGS;should_refuse=false")

seed(id="edge-fund-rights", ctx="edge", doc="Constitution",
     inline_cite=(f"**(Art. 14 — {DOC['Constitution']}; Art. 21 — {DOC['Constitution']})**"),
     cite="Art. 14|Art. 21",
     q=["What are the fundamental rights guaranteed under the Constitution of India?",
        "Which fundamental rights does the Constitution protect?"],
     ans="The Constitution guarantees fundamental rights in Part III, including equality before the law (Article 14), the freedoms in Article 19, the right to life and personal liberty (Article 21) and the right to constitutional remedies (Article 32)",
     core="The Constitution guarantees fundamental rights such as equality (Art. 14) and life and liberty (Art. 21)",
     secondary="the freedoms under Article 19 and the remedies under Article 32",
     exp_ans="Fundamental rights (Part III): Art. 14 equality, Art. 19 freedoms, Art. 21 life, Art. 32 remedies.",
     exp_cite="Art. 14|Art. 21", exp_assert="must_cite=Art. 14;must_cite=Art. 21;should_refuse=false")

seed(id="edge-const-unaffected", ctx="edge", doc="Constitution", cite="Art. 21", wrong_cite="Art. 14",
     q=["Did the 2023 criminal law reforms change the Constitution?",
        "Is the Constitution affected by the new criminal codes?"],
     ans="No — the 2023 criminal codes replaced ordinary statutes such as the IPC, CrPC and Evidence Act, but the Constitution of India remains the supreme law and rights such as Article 21 are unchanged by them",
     minor="The new criminal codes did not amend the Constitution; Article 21 and other rights stand",
     exp_ans="Constitution unaffected by the 2023 codes; Art. 21 and other rights unchanged.",
     exp_cite="Art. 21", exp_assert="must_cite=Art. 21;should_refuse=false")


# ---- Refusal (topic not in the indexed corpus) --------------------------------
def refusal(id, topic, q, fabricated, fab_span, invented=None, invented_span=None):
    seed(id=id, ctx="refusal", doc=None, cite="", q=q, topic=topic,
         fabricated=fabricated, fab_span=fab_span,
         invented=invented or fabricated, invented_span=invented_span or fab_span,
         exp_ans=f"Refusal — {topic} is not present in the indexed legal corpus.",
         exp_cite="", exp_assert="should_refuse=true")


refusal("ref-companies", "the Companies Act 2013 provisions on board meetings",
        ["What does the Companies Act 2013 say about board meetings?",
         "How often must a company hold board meetings under the Companies Act?"],
        "Section 173 of the Companies Act 2013 requires a company to hold at least four board meetings a year **(Companies Act s.173 — Companies Act 2013)**.",
        "Companies Act s.173 — Companies Act 2013",
        invented="A company must hold at least six board meetings each year with no gap exceeding 60 days.",
        invented_span="at least six board meetings each year with no gap exceeding 60 days")
refusal("ref-incometax", "capital gains under the Income Tax Act",
        ["What does the Income Tax Act say about capital gains?",
         "How is capital gains tax computed under the Income Tax Act?"],
        "Long-term capital gains are taxed at 20% with indexation under Section 112 of the Income Tax Act 1961 **(IT Act s.112 — Income Tax Act 1961)**.",
        "IT Act s.112 — Income Tax Act 1961")
refusal("ref-arbitration", "the Arbitration and Conciliation Act procedures",
        ["What are the arbitration procedures under the Arbitration and Conciliation Act?",
         "How is an arbitral tribunal constituted under the Arbitration Act?"],
        "An arbitral tribunal is constituted under Section 11 of the Arbitration and Conciliation Act 1996 **(Arbitration Act s.11 — Arbitration and Conciliation Act 1996)**.",
        "Arbitration Act s.11 — Arbitration and Conciliation Act 1996")
refusal("ref-rti", "the Right to Information Act 2005",
        ["What does the Right to Information Act 2005 say about public authorities?",
         "What are the duties of a public authority under the RTI Act?"],
        "Every public authority must respond to an information request within 30 days under Section 7 of the Right to Information Act 2005 **(RTI Act s.7 — Right to Information Act 2005)**.",
        "RTI Act s.7 — Right to Information Act 2005")
refusal("ref-gst", "the GST legal framework in India",
        ["What is the legal framework for GST in India?",
         "How is GST levied under the CGST Act?"],
        "GST is levied on the supply of goods and services under Section 9 of the CGST Act 2017 **(CGST Act s.9 — Central Goods and Services Tax Act 2017)**.",
        "CGST Act s.9 — Central Goods and Services Tax Act 2017")
refusal("ref-hindumarriage", "the Hindu Marriage Act",
        ["What are the provisions of the Hindu Marriage Act?",
         "What are the conditions for a valid Hindu marriage?"],
        "A valid Hindu marriage requires that neither party has a living spouse under Section 5 of the Hindu Marriage Act 1955 **(HMA s.5 — Hindu Marriage Act 1955)**.",
        "HMA s.5 — Hindu Marriage Act 1955")
refusal("ref-motor", "the Motor Vehicles Act and insurance",
        ["What does the Motor Vehicles Act say about insurance?",
         "Is third-party motor insurance mandatory under the Motor Vehicles Act?"],
        "Third-party insurance is compulsory under Section 146 of the Motor Vehicles Act 1988 **(MV Act s.146 — Motor Vehicles Act 1988)**.",
        "MV Act s.146 — Motor Vehicles Act 1988")
refusal("ref-pmla", "bail under the Prevention of Money Laundering Act",
        ["What are the provisions for bail under the Prevention of Money Laundering Act?",
         "How does the PMLA treat bail applications?"],
        "Bail under the PMLA is governed by the twin conditions in Section 45 of the Prevention of Money Laundering Act 2002 **(PMLA s.45 — Prevention of Money Laundering Act 2002)**.",
        "PMLA s.45 — Prevention of Money Laundering Act 2002")
refusal("ref-nia", "the Negotiable Instruments Act and cheque bounce",
        ["What does the Negotiable Instruments Act say about a bounced cheque?",
         "What is the punishment for cheque dishonour under the NI Act?"],
        "Dishonour of a cheque is punishable with up to two years' imprisonment under Section 138 of the Negotiable Instruments Act 1881 **(NI Act s.138 — Negotiable Instruments Act 1881)**.",
        "NI Act s.138 — Negotiable Instruments Act 1881")
refusal("ref-tpa", "the Transfer of Property Act",
        ["What does the Transfer of Property Act say about a sale of immovable property?",
         "How is a sale of immovable property defined under the Transfer of Property Act?"],
        "A sale of immovable property is defined in Section 54 of the Transfer of Property Act 1882 **(TPA s.54 — Transfer of Property Act 1882)**.",
        "TPA s.54 — Transfer of Property Act 1882")
refusal("ref-specificrelief", "the Specific Relief Act",
        ["What does the Specific Relief Act say about specific performance?",
         "When can specific performance be granted under the Specific Relief Act?"],
        "Specific performance of a contract may be enforced under Section 10 of the Specific Relief Act 1963 **(SRA s.10 — Specific Relief Act 1963)**.",
        "SRA s.10 — Specific Relief Act 1963")
refusal("ref-idact", "the Industrial Disputes Act and retrenchment",
        ["What does the Industrial Disputes Act say about retrenchment?",
         "What compensation is payable on retrenchment under the Industrial Disputes Act?"],
        "Retrenchment compensation of 15 days' wages per year of service is payable under Section 25F of the Industrial Disputes Act 1947 **(ID Act s.25F — Industrial Disputes Act 1947)**.",
        "ID Act s.25F — Industrial Disputes Act 1947")


# ---------------------------------------------------------------------------
# Output synthesizers
# ---------------------------------------------------------------------------
def inline_cite(s: dict) -> str:
    if s.get("inline_cite"):
        return s["inline_cite"]
    return f"**({s['cite']} — {DOC[s['doc']]})**"


def faithful(body: str, s: dict) -> str:
    return f"{body} {inline_cite(s)}. {FOOTER}"


def g_minor(s):
    return f"Broadly, {s['ans'][0].lower() + s['ans'][1:]} (the precise wording is in the cited section)"


def g_drift(s):
    body = f"{s['ans']}. A fine of up to Rs.10,000 is also mandatory in every case"
    return body, "A fine of up to Rs.10,000 is also mandatory in every case"


def g_invented(s):
    body = f"{s['ans']}. This provision also carries a fixed penalty of Rs.50,000 in all cases"
    return body, "fixed penalty of Rs.50,000 in all cases"


def g_fab(s):
    body = f"{s['ans']}, as codified in Section 99 of the Indian Penal Code 1860 **(IPC s.99 — Indian Penal Code 1860)**"
    return body, "IPC s.99 — Indian Penal Code 1860"


# Each builder returns dict: output, task, fmt, fact, failure_mode, error_span,
# judge_rationale, difficulty, judge_type
def b_clear_pass(s):
    if s["ctx"] == "refusal":
        out = REFUSAL
        rat = "Correctly refused per template; nothing in the indexed corpus — pass."
    else:
        out = faithful(s["ans"], s)
        rat = f"Accurate, cites {s['cite']}, footer present — task 5 / format 1 / fact 5."
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
                judge_rationale=f"Subtle factual drift ('{span[:60]}') vs the cited section — factuality 3.",
                difficulty="borderline", judge_type="hitl")


def b_hall_f2(s):
    if s.get("invented"):
        body, span = s["invented"], s["invented_span"]
    else:
        body, span = g_invented(s)
    if s["ctx"] == "refusal":
        out = f"{body} {FOOTER}"
        rat = "Should have refused; instead invents provisions absent from the corpus — factuality 2."
    else:
        out = faithful(body, s)
        rat = "Invents figures/terms not supported by the cited section — factuality 2."
    return dict(output=out, task=5, fmt=1, fact=2, failure_mode="hallucination",
                error_span=span, judge_rationale=rat, difficulty="clear", judge_type="llm")


def b_hall_f1(s):
    if s.get("fabricated"):
        body, span = s["fabricated"], s["fab_span"]
        out = f"{body} {FOOTER}"
    else:
        body, span = g_fab(s)
        out = f"{body}. {FOOTER}"
    if s["ctx"] == "refusal":
        rat = "Should have refused; fabricates an out-of-corpus statute answer — factuality 1."
    elif s["ctx"] == "guard":
        rat = "Cites a repealed statute as if it were current law — fabrication, factuality 1."
    else:
        rat = "Cites a statute/section outside the corpus — fabrication, factuality 1."
    return dict(output=out, task=5, fmt=1, fact=1, failure_mode="hallucination",
                error_span=span, judge_rationale=rat, difficulty="clear", judge_type="llm")


def b_format0(s, variant):
    # content correct; only the format template is broken (halo probe)
    if s["ctx"] == "refusal":
        out = "Sorry, that specific area of law isn't in the statutes I have indexed."
        span = "(refusal wording does not match the required template)"
        rat = "Correctly declines but not in the exact refusal template — format 0."
    elif variant == 0:  # drop the inline citation
        out = f"{s['ans']}. {FOOTER}"
        span = "(missing inline section citation)"
        rat = "Answer correct but the inline section citation is missing — format 0."
    else:  # drop the mandatory footer
        out = f"{s['ans']} {inline_cite(s)}."
        span = "(missing mandatory not-legal-advice footer)"
        rat = "Answer correct and cited but the mandatory footer is missing — format 0."
    return dict(output=out, task=5, fmt=0, fact=5, failure_mode="format_violation",
                error_span=span, judge_rationale=rat, difficulty="clear", judge_type="llm")


def b_task1(s):
    # on-format, factually-true, but does not answer the question asked
    blurb = DOC_BLURB.get(s["doc"], "These are indexed Indian statutes")
    out = f"{blurb} {inline_cite(s)}. {FOOTER}"
    return dict(output=out, task=1, fmt=1, fact=5, failure_mode="task_incomplete",
                error_span="(does not address the question asked)",
                judge_rationale="On-format and true, but never answers the question — task 1.",
                difficulty="clear", judge_type="llm")


def b_task2(s, border):
    # addresses the topic but omits the core answer
    out = (f"This is addressed in the indexed statutes, though the precise section wording "
           f"should be checked {inline_cite(s)}. {FOOTER}")
    diff = "borderline" if border else "clear"
    jt = "hitl" if border else "llm"
    rat = ("Names the topic and mostly frames it but omits the specific answer — arguable task 2."
           if border else
           "Mentions the topic but gives no specific answer — task 2.")
    return dict(output=out, task=2, fmt=1, fact=5, failure_mode="task_incomplete",
                error_span="(omits the specific answer)", judge_rationale=rat,
                difficulty=diff, judge_type=jt)


# ---------------------------------------------------------------------------
# Slot plan (sums to 300; 90 fail; 54 borderline)
# ---------------------------------------------------------------------------
SLOTS: list[str] = (
    ["clear_pass"] * 180
    + ["bpass_fact4"] * 18
    + ["bpass_task3"] * 12
    + ["hall_f1"] * 6
    + ["hall_f2"] * 12
    + ["hall_f3"] * 18
    + ["format0"] * 30
    + ["task1"] * 6
    + ["task2_clear"] * 12
    + ["task2_border"] * 6
)

# Kinds a refusal seed can serve (answered-anyway or refusal template).
REFUSAL_OK = {"clear_pass", "format0", "hall_f1", "hall_f2"}
# Kinds that need genuine answerable content (never a refusal seed).
ANSWERABLE_ONLY = {"bpass_fact4", "bpass_task3", "hall_f3", "task1", "task2_clear", "task2_border"}

CTX_TARGET = {"retrieval": 140, "guard": 75, "refusal": 65, "edge": 20}


def build_rows(rng: random.Random) -> list[dict]:
    seeds_by_ctx: dict[str, list[dict]] = {"retrieval": [], "guard": [], "refusal": [], "edge": []}
    for s in SEEDS:
        seeds_by_ctx[s["ctx"]].append(s)

    ctx_remaining = dict(CTX_TARGET)
    ptr: dict[str, int] = {c: 0 for c in seeds_by_ctx}
    q_use: dict[str, int] = {}

    order = SLOTS[:]
    rng.shuffle(order)

    rows: list[dict] = []
    for i, kind in enumerate(order):
        if kind in ANSWERABLE_ONLY:
            allowed = ["retrieval", "guard", "edge"]
        else:
            allowed = ["retrieval", "guard", "edge", "refusal"]
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
        r["id"] = f"law-{n:04d}"
    return rows


def _assign_pairs(rows: list[dict], want: int = 27):
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
LIVE_CTX_TARGET = {"retrieval": 145, "guard": 70, "refusal": 65, "edge": 20}  # 85 hard = refusal+edge

LIVE_OUT = os.path.join(HERE, "law-tryeval-live-dataset.csv")
CAL_OUT = os.path.join(HERE, "law-tryeval-calibration-dataset.csv")


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
        f"Under Indian law, {bl}",
        f"For my situation specifically, {bl}",
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
    assert n == 300, f"row count {n} != 300"

    fails = [r for r in rows if r["verdict"] == "fail"]
    assert len(fails) == 90, f"fail count {len(fails)} != 90 (30%)"

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
    assert 48 <= len(borderline) <= 60, f"borderline count {len(borderline)} not ~54"
    for r in borderline:
        f, t = int(r["factuality_score"]), int(r["task_completion_score"])
        assert f in (3, 4) or t in (2, 3), f"{r['id']}: borderline not adjacent to a threshold"

    # fail-mode split (exact, per slot plan)
    modes = {"hallucination": 0, "format_violation": 0, "task_incomplete": 0}
    for r in fails:
        modes[r["failure_mode"]] += 1
    assert modes == {"hallucination": 36, "format_violation": 30, "task_incomplete": 24}, modes

    # graded hallucination severity
    hall = [r for r in fails if r["failure_mode"] == "hallucination"]
    sev = {1: 0, 2: 0, 3: 0}
    for r in hall:
        sev[int(r["factuality_score"])] += 1
    assert sev == {1: 6, 2: 12, 3: 18}, f"hallucination severity {sev} != 6/12/18"

    # halo probes: format fails with perfect content
    halo = [r for r in fails if r["failure_mode"] == "format_violation"
            and int(r["task_completion_score"]) == 5 and int(r["factuality_score"]) == 5]
    assert len(halo) >= 12, f"only {len(halo)} halo-probe rows (<12)"

    # matched pairs
    pairs: dict[str, list[dict]] = {}
    for r in rows:
        if r["pair_id"]:
            pairs.setdefault(r["pair_id"], []).append(r)
    assert 22 <= len(pairs) <= 30, f"{len(pairs)} matched pairs (want 22-30)"
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
            assert FOOTER in r["output"], f"{r['id']}: pass output missing mandatory footer"

    # grounding: pass-row citations reference only real docs; no fabricated (repealed-as-current)
    # citations leak into a PASS output. Guard AND edge pass rows legitimately NAME a repealed
    # statute in prose (that is the whole point of the repeal crosswalk), so the repealed-doc check
    # is citation-form (`— <fake>)`) for them; retrieval/refusal pass rows must not mention a
    # repealed statute name at all.
    for r in rows:
        if r["verdict"] != "pass":
            continue
        for tok in r["expected_citations"].split("|"):
            tok = tok.strip()
            if tok:
                assert tok.startswith(VALID_CITE_PREFIXES), f"{r['id']}: bad citation {tok}"
        for fake in FAKE_DOCS:
            assert f"— {fake})" not in r["output"], f"{r['id']}: repealed statute cited as current in a PASS output"
            if r["eval_context"] not in ("guard", "edge"):
                assert fake not in r["output"], f"{r['id']}: repealed doc '{fake}' in a retrieval/refusal PASS output"

    # every fail has a non-empty error_span
    for r in fails:
        assert r["error_span"].strip(), f"{r['id']}: fail has empty error_span"

    # context distribution (soft)
    ctxc = {c: 0 for c in CTX_TARGET}
    for r in rows:
        ctxc[r["eval_context"]] += 1
    for c, tgt in CTX_TARGET.items():
        assert abs(ctxc[c] - tgt) <= 15, f"ctx {c}={ctxc[c]} far from target {tgt}"

    print("VERIFY OK — 300 rows, 90 fail (30%), 54-band borderline, verdict integrity clean.")
    print(f"  fail modes      : {modes}")
    print(f"  hall severity   : fact1={sev[1]} fact2={sev[2]} fact3={sev[3]}")
    print(f"  halo probes     : {len(halo)}")
    print(f"  matched pairs   : {len(pairs)}")
    print(f"  borderline rows : {len(borderline)}")
    print(f"  context mix     : {ctxc}")
    print(f"  seeds used      : {len({r['seed_id'] for r in rows})} / {len(SEEDS)}")


def verify_live(rows: list[dict]):
    assert len(rows) == 300, f"live row count {len(rows)} != 300"
    inputs = [r["input"] for r in rows]
    assert len(set(inputs)) == 300, f"live inputs not unique ({len(set(inputs))} distinct)"
    hard = [r for r in rows if r["_difficulty"] == "hard"]
    assert 80 <= len(hard) <= 100, f"hard count {len(hard)} not ~85 (~30%)"
    for r in rows:
        assert r["expected_output"].strip(), "empty expected_output"
        assert "REFERENCE ANSWER:" in r["eval_context"], "reference not packed into eval_context"
    refusal_rows = [r for r in rows if r["_ctx"] == "refusal"]
    for r in refusal_rows:
        assert "a refusal is the correct response" in r["eval_context"], "refusal ref missing"
    ctxc = {c: 0 for c in LIVE_CTX_TARGET}
    for r in rows:
        ctxc[r["_ctx"]] += 1
    print(f"VERIFY LIVE OK — 300 rows, {len(hard)} hard (~30%), unique inputs.")
    print(f"  context mix : {ctxc}")


def verify_cal(rows: list[dict]):
    assert len(rows) == 300, f"cal row count {len(rows)} != 300"
    for r in rows:
        assert set(r) == set(TRYEVAL_CAL_FIELDS), f"unexpected cal columns: {set(r)}"
        assert r["output"].strip(), "empty output (direct-eval needs a filled output)"
        assert "REFERENCE ANSWER:" in r["eval_context"], "reference not packed into eval_context"
    print("VERIFY CAL OK — 300 direct-eval rows; output pre-filled, gold LABELS stripped (join gold on input+output).")


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
