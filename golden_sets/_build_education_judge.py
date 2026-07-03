#!/usr/bin/env python3
"""Build golden_sets/education-judge-dataset.csv — a labeled LLM-judge / HITL benchmark.

Deterministic (fixed RNG seed), no API calls. 300 rows, 30% baked-in failure rate,
grounded in the 9 NCERT Class 10 Social Science chapters (History Ch.1-3, Geography
Ch.1-2, Economics Ch.1-2, Political Science Ch.1-2). Each row carries an actual
model-style `output`, three gold rubric scores, a derived pass/fail `verdict`, a
`failure_mode`, an `error_span`, a `judge_rationale`, and analysis columns
(`seed_id`, `pair_id`, `difficulty`, `judge_type`).

Education has NO mandatory disclaimer footer, so faithful() = body + inline citation
only, and the format0 halo band has just two variants (strip citation / botch refusal
wording). Clone of _build_insurance_judge.py; run `python _build_education_judge.py
--emit all --verify` to build all artifacts + assert every invariant.
"""
from __future__ import annotations
import argparse
import csv
import os
import random

# ---------------------------------------------------------------------------
# Constants (from demos/education/prompts/system_v1.md + manifest.yaml)
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "education-judge-dataset.csv")

# Education has NO disclaimer footer. Refusal string is copied VERBATIM from system_v1.md.
REFUSAL = (
    "I cannot answer this from your indexed NCERT chapters. This topic may be outside "
    "the chapters available here. Check with your teacher or another reference book."
)
# Full chapter titles as they appear inside the inline citation, e.g.
#   **(Hist Ch.2 §1.2 — History Ch.2: Nationalism in India)**
DOC_MAP = {
    "Hist Ch.1": "History Ch.1: The Rise of Nationalism in Europe",
    "Hist Ch.2": "History Ch.2: Nationalism in India",
    "Hist Ch.3": "History Ch.3: The Making of a Global World",
    "Geo Ch.1": "Geography Ch.1: Resources and Development",
    "Geo Ch.2": "Geography Ch.2: Forest and Wildlife Resources",
    "Econ Ch.1": "Economics Ch.1: Development",
    "Econ Ch.2": "Economics Ch.2: Sectors of the Indian Economy",
    "Civics Ch.1": "Political Science Ch.1: Power Sharing",
    "Civics Ch.2": "Political Science Ch.2: Federalism",
}
# Valid first-token of any real citation short (used by the grounding invariant).
REAL_SHORT_HEADS = {"Hist", "Geo", "Econ", "Civics"}
# True-but-generic sentence per chapter, used to build on-format off-topic (task) failures.
DOC_BLURB = {
    "Hist Ch.1": "History Chapter 1 traces the rise of nationalism in nineteenth-century Europe",
    "Hist Ch.2": "History Chapter 2 explains the growth of the nationalist movement in India",
    "Hist Ch.3": "History Chapter 3 describes how the world became an interconnected global economy",
    "Geo Ch.1": "Geography Chapter 1 deals with types of resources and their development",
    "Geo Ch.2": "Geography Chapter 2 covers India's forest and wildlife resources and their conservation",
    "Econ Ch.1": "Economics Chapter 1 discusses how the development of a country is measured",
    "Econ Ch.2": "Economics Chapter 2 explains the sectors of the Indian economy",
    "Civics Ch.1": "Political Science Chapter 1 introduces the idea of power sharing in a democracy",
    "Civics Ch.2": "Political Science Chapter 2 explains federalism and the division of powers in India",
}
FAKE_DOCS = ("Science Ch.4: Chemical Reactions", "Maths Ch.6: Triangles",
             "History Ch.5: The Cold War")  # out-of-corpus markers (fact1 fabrication)

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
# Seed bank (~62 seeds), grounded in extracted NCERT chapter text.
# Fields: id, ctx, doc(short), cite, wrong_cite, inline_cite (edge multi-doc), q[],
#   ans (full correct body), core (drops a secondary key point) + secondary,
#   minor (fact4 loosely-imprecise body),
#   drift/drift_span (fact3 subtle-wrong), invented/invented_span (fact2),
#   fabricated/fab_span (fact1), exp_ans, exp_cite, exp_assert, topic (refusal).
# ---------------------------------------------------------------------------
SEEDS: list[dict] = []


def seed(**kw):
    SEEDS.append(kw)


# ---- History Ch.1 — The Rise of Nationalism in Europe -------------------------
seed(id="hist1-frenchrev", ctx="retrieval", doc="Hist Ch.1", cite="Hist Ch.1 §1.1", wrong_cite="Hist Ch.1 §1.2",
     q=["What was the role of the French Revolution in spreading nationalism in Europe?",
        "How did the French Revolution spread the idea of nationalism?",
        "Why is the French Revolution important for European nationalism?"],
     ans="The French Revolution of 1789 introduced the ideas of liberty, equality and fraternity and created the first clear expression of nationalism, transferring sovereignty from the monarch to a body of French citizens",
     core="The French Revolution of 1789 was the first clear expression of nationalism, shifting sovereignty from the monarch to the citizens",
     secondary="that it introduced the ideas of liberty, equality and fraternity",
     minor="The 1789 French Revolution first gave shape to nationalist ideas by making the people, rather than the king, the source of authority",
     drift="The French Revolution of 1799 introduced liberty, equality and fraternity and first expressed the idea of nationalism",
     drift_span="French Revolution of 1799",
     invented="The French Revolution of 1789 introduced nationalism and directly led to the unification of Germany within ten years",
     invented_span="directly led to the unification of Germany within ten years",
     exp_ans="1789 French Revolution: first expression of nationalism; sovereignty to citizens; liberty, equality, fraternity.",
     exp_cite="Hist Ch.1 §1.1", exp_assert="must_cite_doc_id=HIST_CH1_NATIONALISM_EUROPE;must_contain=French Revolution|nationalism;should_refuse=false")

seed(id="hist1-napcode", ctx="retrieval", doc="Hist Ch.1", cite="Hist Ch.1 §1.2", wrong_cite="Hist Ch.1 §1.1",
     q=["What did the Napoleonic Code do?",
        "What were the main features of the Civil Code of 1804?",
        "What changes did Napoleon's Civil Code introduce?"],
     ans="The Civil Code of 1804, known as the Napoleonic Code, did away with privileges based on birth, established equality before the law and secured the right to property",
     core="The Napoleonic Code abolished privileges based on birth and established equality before the law",
     secondary="that it also secured the right to property",
     minor="Napoleon's 1804 Civil Code broadly removed birth-based privileges and made everyone equal before the law",
     drift="The Civil Code of 1815, known as the Napoleonic Code, abolished privileges based on birth and secured equality before the law",
     drift_span="Civil Code of 1815",
     exp_ans="Napoleonic Code (1804): abolished birth privileges, equality before law, right to property.",
     exp_cite="Hist Ch.1 §1.2", exp_assert="must_cite_doc_id=HIST_CH1_NATIONALISM_EUROPE;must_contain=Napoleonic Code|equality;should_refuse=false")

seed(id="hist1-mazzini", ctx="retrieval", doc="Hist Ch.1", cite="Hist Ch.1 §2.2", wrong_cite="Hist Ch.1 §3.1",
     q=["Who was Giuseppe Mazzini and what was his role in European nationalism?",
        "What did Mazzini do for Italian nationalism?",
        "What secret societies did Mazzini found?"],
     ans="Giuseppe Mazzini was an Italian revolutionary who founded the secret societies Young Italy in Marseilles and Young Europe in Berne (1833); he believed nations were the natural units of mankind and worked to unite Italy",
     core="Mazzini was an Italian revolutionary who founded Young Italy and Young Europe and believed nations were the natural units of mankind",
     secondary="that Young Europe was founded in Berne in 1833",
     minor="Mazzini was an Italian revolutionary who set up youth societies to promote the idea of Italy as a unified nation",
     drift="Giuseppe Mazzini founded Young Italy in Rome and Young Europe in Berne in 1848 and believed nations were the natural units of mankind",
     drift_span="founded Young Italy in Rome ... in 1848",
     invented="Giuseppe Mazzini founded Young Italy and later became the first prime minister of a united Italy in 1861",
     invented_span="became the first prime minister of a united Italy in 1861",
     exp_ans="Mazzini: Italian revolutionary; founded Young Italy (Marseilles) and Young Europe (Berne, 1833); nations = natural units.",
     exp_cite="Hist Ch.1 §2.2", exp_assert="must_cite_doc_id=HIST_CH1_NATIONALISM_EUROPE;must_contain=Mazzini;should_refuse=false")

seed(id="hist1-zollverein", ctx="retrieval", doc="Hist Ch.1", cite="Hist Ch.1 §2.1", wrong_cite="Hist Ch.1 §3.1",
     q=["What was the zollverein?",
        "What did the German customs union (zollverein) do?"],
     ans="The zollverein was a customs union formed in 1834 at the initiative of Prussia; it abolished tariff barriers among the German states and reduced the number of currencies, binding the states economically",
     minor="The zollverein was a Prussia-led customs union that removed trade barriers between the German states",
     drift="The zollverein was a customs union formed in 1848 at the initiative of Austria that abolished tariff barriers among the German states",
     drift_span="formed in 1848 at the initiative of Austria",
     exp_ans="Zollverein: customs union (1834), Prussia's initiative; abolished tariff barriers among German states.",
     exp_cite="Hist Ch.1 §2.1", exp_assert="must_cite_doc_id=HIST_CH1_NATIONALISM_EUROPE;must_contain=zollverein|customs;should_refuse=false")

seed(id="hist1-frankfurt", ctx="retrieval", doc="Hist Ch.1", cite="Hist Ch.1 §3.1", wrong_cite="Hist Ch.1 §2.2",
     q=["What was the Frankfurt Parliament?",
        "What happened at the Frankfurt Parliament in 1848?"],
     ans="In 1848 elected representatives met in the Frankfurt Parliament, convened in the Church of St Paul, and drafted a constitution for a German nation to be headed by a monarch subject to a parliament",
     minor="The 1848 Frankfurt Parliament was an elected assembly that tried to draft a constitution for a united Germany",
     drift="In 1832 elected representatives met in the Frankfurt Parliament in the Church of St Paul and drafted a constitution for a German nation",
     drift_span="In 1832 elected representatives met",
     exp_ans="Frankfurt Parliament (1848), Church of St Paul; drafted a constitution for a German nation.",
     exp_cite="Hist Ch.1 §3.1", exp_assert="must_cite_doc_id=HIST_CH1_NATIONALISM_EUROPE;must_contain=Frankfurt;should_refuse=false")

seed(id="hist1-sorrieu", ctx="retrieval", doc="Hist Ch.1", cite="Hist Ch.1 §1", wrong_cite="Hist Ch.1 §1.1",
     q=["What did Frédéric Sorrieu's 1848 prints depict?",
        "What was the vision in Sorrieu's series of prints?"],
     ans="In 1848 the French artist Frédéric Sorrieu prepared a series of four prints visualising a utopian world made up of democratic and social Republics organised as nation-states",
     minor="Sorrieu's 1848 prints imagined a world of people grouped into democratic nation-states",
     exp_ans="Sorrieu's 1848 prints: utopian world of democratic and social Republics as nation-states.",
     exp_cite="Hist Ch.1 §1", exp_assert="must_cite_doc_id=HIST_CH1_NATIONALISM_EUROPE;must_contain=Sorrieu|nation;should_refuse=false")

# ---- History Ch.2 — Nationalism in India --------------------------------------
seed(id="hist2-noncoop", ctx="retrieval", doc="Hist Ch.2", cite="Hist Ch.2 §1.3", wrong_cite="Hist Ch.2 §1.2",
     q=["Why did Gandhi start the Non-Cooperation Movement?",
        "What was the idea behind the Non-Cooperation Movement?",
        "On what belief did Gandhi launch Non-Cooperation?"],
     ans="In Hind Swaraj (1909) Gandhi argued that British rule was established with the cooperation of Indians and survived only because of it, so if Indians refused to cooperate British rule would collapse and swaraj would come",
     core="Gandhi argued British rule survived only because Indians cooperated, so withdrawing cooperation would bring swaraj",
     secondary="that he set out this idea in Hind Swaraj (1909)",
     minor="Gandhi's idea was that British rule depended on Indian cooperation, so non-cooperation would force the British to leave",
     drift="In Hind Swaraj (1909) Gandhi argued that if Indians withdrew cooperation, British rule would collapse within two years and swaraj would come",
     drift_span="collapse within two years",
     invented="Gandhi launched Non-Cooperation after promising that armed rebellion in every district would end British rule in six months",
     invented_span="armed rebellion in every district would end British rule in six months",
     exp_ans="British rule ran on Indian cooperation; withdraw it and it collapses (Hind Swaraj, 1909).",
     exp_cite="Hist Ch.2 §1.3", exp_assert="must_cite_doc_id=HIST_CH2_NATIONALISM_INDIA;must_contain=cooperat|swaraj;should_refuse=false")

seed(id="hist2-rowlatt", ctx="retrieval", doc="Hist Ch.2", cite="Hist Ch.2 §1.2", wrong_cite="Hist Ch.2 §1.3",
     q=["What was the Rowlatt Act?",
        "Why did Gandhi oppose the Rowlatt Act?"],
     ans="The Rowlatt Act of 1919 gave the government enormous powers to repress political activities and allowed detention of political prisoners without trial, so Gandhi launched a nationwide satyagraha against it",
     core="The Rowlatt Act (1919) allowed detention without trial, and Gandhi launched a nationwide satyagraha against it",
     secondary="that it gave the government sweeping powers to repress political activity",
     minor="The Rowlatt Act let the British jail people without trial, which Gandhi resisted with satyagraha",
     drift="The Rowlatt Act of 1921 allowed detention of political prisoners without trial, so Gandhi launched a satyagraha against it",
     drift_span="Rowlatt Act of 1921",
     exp_ans="Rowlatt Act (1919): detention without trial; Gandhi's nationwide satyagraha.",
     exp_cite="Hist Ch.2 §1.2", exp_assert="must_cite_doc_id=HIST_CH2_NATIONALISM_INDIA;must_contain=Rowlatt|satyagraha;should_refuse=false")

seed(id="hist2-khilafat", ctx="retrieval", doc="Hist Ch.2", cite="Hist Ch.2 §1.1", wrong_cite="Hist Ch.2 §1.3",
     q=["What was the Khilafat issue?",
        "Why did Gandhi take up the Khilafat cause?"],
     ans="The Khilafat movement sought to defend the temporal powers of the Ottoman Khalifa after the First World War; a Khilafat Committee was formed and Gandhi took it up to bring Hindus and Muslims together in a united mass movement",
     minor="The Khilafat issue was about protecting the Ottoman Caliph, and Gandhi used it to unite Hindus and Muslims",
     drift="The Khilafat movement aimed to defend the powers of the Ottoman Khalifa after the Second World War, and Gandhi took it up to unite Hindus and Muslims",
     drift_span="after the Second World War",
     exp_ans="Khilafat: defend the Ottoman Khalifa; Gandhi joined to unite Hindus and Muslims.",
     exp_cite="Hist Ch.2 §1.1", exp_assert="must_cite_doc_id=HIST_CH2_NATIONALISM_INDIA;must_contain=Khilafat;should_refuse=false")

seed(id="hist2-dandi", ctx="retrieval", doc="Hist Ch.2", cite="Hist Ch.2 §3.1", wrong_cite="Hist Ch.2 §1.2",
     q=["What was the significance of the Dandi March?",
        "Why did Gandhi lead the Salt March?",
        "What was the Salt March of 1930?"],
     ans="In 1930 Gandhi led the Salt March to Dandi to break the British salt law by making salt, launching the Civil Disobedience Movement and drawing mass participation and international attention",
     core="Gandhi's 1930 Salt March broke the salt law and launched the Civil Disobedience Movement",
     secondary="that it drew mass participation and international attention",
     minor="The 1930 Dandi march defied the salt tax and began the civil disobedience campaign",
     drift="In 1919 Gandhi led the Salt March to Dandi to break the salt law and launch the Civil Disobedience Movement",
     drift_span="In 1919 Gandhi led the Salt March",
     invented="During the 1930 Salt March Gandhi collected a fixed tax of two rupees from every marcher to fund the movement",
     invented_span="collected a fixed tax of two rupees from every marcher",
     exp_ans="Salt/Dandi March (1930): broke the salt law; launched Civil Disobedience Movement.",
     exp_cite="Hist Ch.2 §3.1", exp_assert="must_cite_doc_id=HIST_CH2_NATIONALISM_INDIA;must_contain=salt|Dandi;should_refuse=false")

# ---- History Ch.3 — The Making of a Global World ------------------------------
seed(id="hist3-silk", ctx="retrieval", doc="Hist Ch.3", cite="Hist Ch.3 §1.1", wrong_cite="Hist Ch.3 §1.3",
     q=["What were the Silk Routes?",
        "How did the Silk Routes link the world?"],
     ans="The Silk Routes were a network of pre-modern trade routes linking Asia with Europe and North Africa, along which Chinese silk, other goods, precious metals and also religions and ideas travelled in both directions",
     core="The Silk Routes were pre-modern trade routes linking Asia with Europe and North Africa",
     secondary="that religions and ideas, not just goods, travelled along them",
     minor="The Silk Routes were old trade routes that connected distant parts of the world for exchange of goods and ideas",
     drift="The Silk Routes were pre-modern trade routes that linked only the cities of Europe with each other for the silk trade",
     drift_span="linked only the cities of Europe",
     exp_ans="Silk Routes: pre-modern trade routes linking Asia, Europe, N. Africa; carried goods and ideas.",
     exp_cite="Hist Ch.3 §1.1", exp_assert="must_cite_doc_id=HIST_CH3_GLOBAL_WORLD;must_contain=silk|trade;should_refuse=false")

seed(id="hist3-cornlaws", ctx="retrieval", doc="Hist Ch.3", cite="Hist Ch.3 §1.3", wrong_cite="Hist Ch.3 §1.1",
     q=["What were the Corn Laws?",
        "What happened after the Corn Laws were abolished in Britain?"],
     ans="The Corn Laws restricted the import of corn into Britain; after industrialists and urban dwellers forced their abolition, cheaper food was imported, British agriculture could not compete, and many people migrated to cities or overseas",
     core="The Corn Laws restricted corn imports into Britain; after abolition cheaper food was imported",
     secondary="that British agriculture declined and people migrated",
     minor="The Corn Laws limited food imports; scrapping them let cheaper grain in and hurt British farmers",
     drift="The Corn Laws restricted the import of corn into Britain; after they were abolished, British food prices rose sharply and farming expanded",
     drift_span="British food prices rose sharply and farming expanded",
     exp_ans="Corn Laws: restricted corn imports; abolition brought cheaper food, farm decline, migration.",
     exp_cite="Hist Ch.3 §1.3", exp_assert="must_cite_doc_id=HIST_CH3_GLOBAL_WORLD;must_contain=Corn Laws;should_refuse=false")

seed(id="hist3-rinderpest", ctx="retrieval", doc="Hist Ch.3", cite="Hist Ch.3 §2.4", wrong_cite="Hist Ch.3 §2.5",
     q=["What was Rinderpest and what impact did it have on Africa?",
        "How did the cattle plague affect Africa?"],
     ans="Rinderpest was a fast-spreading cattle plague that arrived in Africa in the late 1880s and killed about 90 per cent of the cattle, destroying African livelihoods and helping Europeans conquer and subdue Africa",
     core="Rinderpest was a cattle plague that reached Africa in the 1880s and killed most of the cattle",
     secondary="that it helped Europeans conquer Africa",
     minor="Rinderpest was a cattle disease that wiped out most African cattle and weakened local livelihoods",
     drift="Rinderpest was a cattle plague that arrived in Africa in the late 1880s and killed about 50 per cent of the cattle",
     drift_span="killed about 50 per cent of the cattle",
     invented="Rinderpest was a cattle plague that arrived in Africa in the late 1880s and was cured within a year by a vaccine developed in London",
     invented_span="cured within a year by a vaccine developed in London",
     exp_ans="Rinderpest: cattle plague, Africa late 1880s, killed ~90% of cattle; aided European conquest.",
     exp_cite="Hist Ch.3 §2.4", exp_assert="must_cite_doc_id=HIST_CH3_GLOBAL_WORLD;must_contain=Rinderpest|cattle;should_refuse=false")

seed(id="hist3-indentured", ctx="retrieval", doc="Hist Ch.3", cite="Hist Ch.3 §2.5", wrong_cite="Hist Ch.3 §2.4",
     q=["What was indentured labour migration from India?",
        "Who were the Indian indentured labourers?"],
     ans="Indentured labour migration from India involved bonded labourers hired under contracts promising return passage after working a set number of years on plantations in the Caribbean, Mauritius, Fiji and elsewhere",
     minor="Indentured labourers were Indians bound by contracts to work on far-off plantations for a fixed period",
     drift="Indentured labour migration from India involved free labourers who chose to settle permanently in Britain to work in factories",
     drift_span="free labourers who chose to settle permanently in Britain",
     exp_ans="Indentured labour: bonded Indian workers on contracts to plantations in Caribbean, Mauritius, Fiji.",
     exp_cite="Hist Ch.3 §2.5", exp_assert="must_cite_doc_id=HIST_CH3_GLOBAL_WORLD;must_contain=indentured;should_refuse=false")

seed(id="hist3-depression", ctx="retrieval", doc="Hist Ch.3", cite="Hist Ch.3 §3.1", wrong_cite="Hist Ch.3 §1.3",
     q=["What was the Great Depression?",
        "What caused the Great Depression according to the chapter?"],
     ans="The Great Depression began around 1929 and lasted through the mid-1930s; agricultural overproduction and falling prices, along with the withdrawal of US loans, led to collapsing incomes, mass unemployment and a fall in world trade",
     core="The Great Depression began around 1929 and caused falling prices, unemployment and a collapse in trade",
     secondary="that agricultural overproduction and withdrawal of US loans were key causes",
     minor="The Great Depression from about 1929 brought crashing prices, joblessness and shrinking world trade",
     drift="The Great Depression began around 1939 and was caused mainly by the Second World War and falling agricultural prices",
     drift_span="began around 1939",
     exp_ans="Great Depression (~1929): overproduction, falling prices, US loan withdrawal; mass unemployment.",
     exp_cite="Hist Ch.3 §3.1", exp_assert="must_cite_doc_id=HIST_CH3_GLOBAL_WORLD;must_contain=Depression;should_refuse=false")

# ---- Geography Ch.1 — Resources and Development -------------------------------
seed(id="geo1-classify", ctx="retrieval", doc="Geo Ch.1", cite="Geo Ch.1 §1.1", wrong_cite="Geo Ch.1 §2.1",
     q=["How are resources classified in Class 10 Geography?",
        "What are the main types of resources?",
        "On what bases are resources classified?"],
     ans="Resources are classified on the basis of origin (biotic and abiotic), exhaustibility (renewable and non-renewable), ownership (individual, community, national and international), and status of development (potential, developed, stock and reserves)",
     core="Resources are classified by origin, exhaustibility, ownership and status of development",
     secondary="that by origin they are biotic and abiotic",
     minor="Resources are grouped by their origin, how exhaustible they are, who owns them, and how developed they are",
     drift="Resources are classified on the basis of origin (biotic and abiotic), exhaustibility, colour, and status of development",
     drift_span="exhaustibility, colour, and status",
     exp_ans="By origin (biotic/abiotic), exhaustibility (renewable/non-renewable), ownership, status of development.",
     exp_cite="Geo Ch.1 §1.1", exp_assert="must_cite_doc_id=GEO_CH1_RESOURCES;must_contain=biotic|abiotic|renewable;should_refuse=false")

seed(id="geo1-renewable", ctx="retrieval", doc="Geo Ch.1", cite="Geo Ch.1 §1.1", wrong_cite="Geo Ch.1 §2.1",
     q=["What is the difference between renewable and non-renewable resources?",
        "How do renewable and non-renewable resources differ?"],
     ans="Renewable resources can be renewed or reproduced by physical, chemical or mechanical processes within a reasonable time, such as solar energy, water and forests, while non-renewable resources take millions of years to form and get exhausted with use, such as coal and petroleum",
     core="Renewable resources can be replenished in a reasonable time; non-renewable resources take millions of years and get exhausted",
     secondary="that solar energy and forests are renewable while coal and petroleum are non-renewable",
     minor="Renewable resources come back quickly, like water and forests; non-renewable ones like coal cannot be replaced quickly",
     drift="Renewable resources can be renewed within a reasonable time, while non-renewable resources like solar energy and water are used up in a few years",
     drift_span="non-renewable resources like solar energy and water",
     exp_ans="Renewable: replenished in reasonable time (solar, water, forests). Non-renewable: exhaustible (coal, petroleum).",
     exp_cite="Geo Ch.1 §1.1", exp_assert="must_cite_doc_id=GEO_CH1_RESOURCES;must_contain=renewable|non-renewable;should_refuse=false")

seed(id="geo1-erosion", ctx="retrieval", doc="Geo Ch.1", cite="Geo Ch.1 §2.2", wrong_cite="Geo Ch.1 §2.1",
     q=["What is soil erosion and how can it be prevented?",
        "How can soil erosion be controlled?"],
     ans="Soil erosion is the removal of the top fertile layer of soil by wind, water or human activity; it can be checked by contour ploughing, terrace farming, strip cropping and planting shelter belts of trees",
     core="Soil erosion is the removal of topsoil, prevented by contour ploughing, terracing and shelter belts",
     secondary="that strip cropping is also a control measure",
     minor="Soil erosion means the fertile topsoil being worn away, and it is reduced by methods like terracing and planting tree belts",
     drift="Soil erosion is the removal of the top fertile layer of soil and can be prevented mainly by heavy irrigation and using more chemical fertiliser",
     drift_span="prevented mainly by heavy irrigation and using more chemical fertiliser",
     exp_ans="Soil erosion = loss of topsoil; prevented by contour ploughing, terracing, strip cropping, shelter belts.",
     exp_cite="Geo Ch.1 §2.2", exp_assert="must_cite_doc_id=GEO_CH1_RESOURCES;must_contain=soil|erosion;should_refuse=false")

seed(id="geo1-black", ctx="retrieval", doc="Geo Ch.1", cite="Geo Ch.1 §2.1", wrong_cite="Geo Ch.1 §2.2",
     q=["What is black soil and what is it suitable for?",
        "What are the features of black (regur) soil?"],
     ans="Black soil, also called regur soil, is black in colour, made of fine clayey material, holds moisture well and is ideal for growing cotton; it is found in the Deccan trap region",
     minor="Black or regur soil is a moisture-retaining clayey soil that is very good for cotton",
     drift="Black soil, also called regur soil, is red in colour, drains water quickly and is ideal for growing cotton",
     drift_span="is red in colour, drains water quickly",
     exp_ans="Black (regur) soil: clayey, moisture-retentive, ideal for cotton; Deccan trap region.",
     exp_cite="Geo Ch.1 §2.1", exp_assert="must_cite_doc_id=GEO_CH1_RESOURCES;must_contain=black|regur|cotton;should_refuse=false")

seed(id="geo1-rio", ctx="retrieval", doc="Geo Ch.1", cite="Geo Ch.1 §1.3", wrong_cite="Geo Ch.1 §1.1",
     q=["What was the Rio de Janeiro Earth Summit?",
        "What happened at the 1992 Earth Summit in Rio?"],
     ans="At the Rio de Janeiro Earth Summit of 1992, more than 100 heads of state met at the UN Conference on Environment and Development to address global environmental protection and socio-economic development, and adopted Agenda 21",
     minor="The 1992 Rio Earth Summit was a UN meeting of world leaders on environment and sustainable development",
     drift="At the Rio de Janeiro Earth Summit of 1982, more than 100 heads of state adopted Agenda 21 on environment and development",
     drift_span="Earth Summit of 1982",
     exp_ans="Rio Earth Summit (1992): UN conference on environment and development; adopted Agenda 21.",
     exp_cite="Geo Ch.1 §1.3", exp_assert="must_cite_doc_id=GEO_CH1_RESOURCES;must_contain=Rio|1992;should_refuse=false")

# ---- Geography Ch.2 — Forest and Wildlife Resources ---------------------------
seed(id="geo2-biodiversity", ctx="retrieval", doc="Geo Ch.2", cite="Geo Ch.2 §1.1", wrong_cite="Geo Ch.2 §2.1",
     q=["What is biodiversity?",
        "What does biodiversity mean according to the chapter?"],
     ans="Biodiversity, or biological diversity, is the immense variety of life forms — plants, animals and micro-organisms — with which humans are intricately linked through a web of ecological interdependence",
     minor="Biodiversity is the rich variety of living things and the way they depend on one another",
     drift="Biodiversity, or biological diversity, refers only to the variety of large mammals found inside national parks",
     drift_span="only to the variety of large mammals found inside national parks",
     exp_ans="Biodiversity = variety of life forms linked by ecological interdependence.",
     exp_cite="Geo Ch.2 §1.1", exp_assert="must_cite_doc_id=GEO_CH2_FOREST_WILDLIFE;must_contain=biodiversity;should_refuse=false")

seed(id="geo2-wpa", ctx="retrieval", doc="Geo Ch.2", cite="Geo Ch.2 §2.1", wrong_cite="Geo Ch.2 §2.2",
     q=["What did the Wildlife Protection Act of 1972 do?",
        "How does the Wildlife Protection Act protect species?"],
     ans="The Indian Wildlife (Protection) Act was implemented in 1972 to protect habitats; it gave legal protection to listed species, banned hunting and restricted trade in wildlife",
     minor="The 1972 Wildlife Protection Act legally protected listed species and banned their hunting",
     drift="The Indian Wildlife (Protection) Act was implemented in 1982 to protect habitats and banned the hunting of listed species",
     drift_span="implemented in 1982",
     invented="The Indian Wildlife (Protection) Act of 1972 protects wildlife by paying farmers Rs.50,000 for every tiger sighted on their land",
     invented_span="paying farmers Rs.50,000 for every tiger sighted",
     exp_ans="Wildlife (Protection) Act 1972: legal protection for listed species; banned hunting.",
     exp_cite="Geo Ch.2 §2.1", exp_assert="must_cite_doc_id=GEO_CH2_FOREST_WILDLIFE;must_contain=Wildlife|1972;should_refuse=false")

seed(id="geo2-forests", ctx="retrieval", doc="Geo Ch.2", cite="Geo Ch.2 §3.1", wrong_cite="Geo Ch.2 §2.1",
     q=["What are reserved and protected forests?",
        "How are forests classified in India?"],
     ans="For administration, forests are classified as reserved forests (more than half the total forest area, the most valuable for conservation), protected forests (almost one-third, protected from further depletion) and unclassed forests",
     core="Forests are classified as reserved forests, protected forests and unclassed forests",
     secondary="that reserved forests are more than half and protected forests almost one-third of the area",
     minor="India's forests are grouped into reserved, protected and unclassed forests for management",
     drift="For administration, forests are classified as reserved forests (almost one-third) and protected forests (more than half the total forest area)",
     drift_span="reserved forests (almost one-third) and protected forests (more than half",
     exp_ans="Reserved (>half), protected (~one-third), unclassed forests.",
     exp_cite="Geo Ch.2 §3.1", exp_assert="must_cite_doc_id=GEO_CH2_FOREST_WILDLIFE;must_contain=reserved|protected;should_refuse=false")

seed(id="geo2-chipko", ctx="retrieval", doc="Geo Ch.2", cite="Geo Ch.2 §3.2", wrong_cite="Geo Ch.2 §3.1",
     q=["What was the Chipko movement?",
        "What is joint forest management?"],
     ans="The Chipko movement in the Himalayas was a community effort in which people hugged trees to resist deforestation and showed that community afforestation can succeed; joint forest management (JFM) involves local communities in protecting and managing degraded forests",
     minor="Chipko was a Himalayan movement of hugging trees to stop felling, and JFM lets communities help manage forests",
     drift="The Chipko movement in the Himalayas was a government scheme that cleared forests to build hydel dams",
     drift_span="government scheme that cleared forests to build hydel dams",
     exp_ans="Chipko: Himalayan tree-hugging conservation movement; JFM = community forest management.",
     exp_cite="Geo Ch.2 §3.2", exp_assert="must_cite_doc_id=GEO_CH2_FOREST_WILDLIFE;must_contain=Chipko;should_refuse=false")

# ---- Economics Ch.1 — Development ---------------------------------------------
seed(id="econ1-percapita", ctx="retrieval", doc="Econ Ch.1", cite="Econ Ch.1 §1.1", wrong_cite="Econ Ch.1 §1.3",
     q=["What is per capita income and how is it used to measure development?",
        "How is average income used to compare countries?",
        "What is per capita income?"],
     ans="Per capita income, also called average income, is the total income of a country divided by its total population; the World Bank uses it to classify and compare countries, though it hides how income is distributed",
     core="Per capita income is national income divided by population, used by the World Bank to compare countries",
     secondary="that it hides how income is distributed among people",
     minor="Per capita income is the average income per person, used to compare countries but ignoring inequality",
     drift="Per capita income, also called average income, is the total income of a country multiplied by its total population",
     drift_span="total income of a country multiplied by its total population",
     invented="Per capita income is national income divided by population; the World Bank calls any country above Rs.5,000 per year a developed country",
     invented_span="any country above Rs.5,000 per year a developed country",
     exp_ans="Per capita (average) income = national income / population; World Bank comparison; ignores distribution.",
     exp_cite="Econ Ch.1 §1.1", exp_assert="must_cite_doc_id=ECON_CH1_DEVELOPMENT;must_contain=per capita|income;should_refuse=false")

seed(id="econ1-hdi", ctx="retrieval", doc="Econ Ch.1", cite="Econ Ch.1 §1.3", wrong_cite="Econ Ch.1 §1.1",
     q=["What is the Human Development Index?",
        "What does the HDI measure?"],
     ans="The Human Development Index, published by the UNDP in its Human Development Report, ranks countries using per capita income together with health (life expectancy) and education (levels of schooling), because income alone is an inadequate measure of development",
     core="The HDI ranks countries using income, health and education rather than income alone",
     secondary="that it is published by the UNDP in the Human Development Report",
     minor="The HDI is a broader development measure combining income with health and education",
     drift="The Human Development Index, published by the World Bank, ranks countries using only per capita income",
     drift_span="published by the World Bank, ranks countries using only per capita income",
     invented="The Human Development Index ranks countries using income, health, education and the total number of cars per family",
     invented_span="the total number of cars per family",
     exp_ans="HDI (UNDP): combines income, health (life expectancy) and education to rank countries.",
     exp_cite="Econ Ch.1 §1.3", exp_assert="must_cite_doc_id=ECON_CH1_DEVELOPMENT;must_contain=Human Development|health|education;should_refuse=false")

seed(id="econ1-indicators", ctx="retrieval", doc="Econ Ch.1", cite="Econ Ch.1 §1.3", wrong_cite="Econ Ch.1 §2.1",
     q=["Besides income, what indicators are used to measure development?",
        "What non-income indicators of development does the chapter mention?"],
     ans="Besides per capita income, development is measured using indicators such as the infant mortality rate, literacy rate, net attendance ratio and life expectancy, which capture health and education",
     minor="Development is also judged by things like literacy, infant mortality and life expectancy, not just income",
     drift="Besides per capita income, development is measured using indicators such as the number of cinemas and the length of railway lines",
     drift_span="the number of cinemas and the length of railway lines",
     exp_ans="Non-income indicators: infant mortality rate, literacy rate, attendance ratio, life expectancy.",
     exp_cite="Econ Ch.1 §1.3", exp_assert="must_cite_doc_id=ECON_CH1_DEVELOPMENT;must_contain=literacy|mortality;should_refuse=false")

# ---- Economics Ch.2 — Sectors of the Indian Economy ---------------------------
seed(id="econ2-three", ctx="retrieval", doc="Econ Ch.2", cite="Econ Ch.2 §1.1", wrong_cite="Econ Ch.2 §1.2",
     q=["What is the difference between the primary, secondary and tertiary sectors?",
        "How are the three sectors of the economy defined?"],
     ans="The primary sector produces goods by exploiting natural resources (agriculture, mining, fishing); the secondary sector transforms raw materials into manufactured goods (industry); and the tertiary or service sector supports the other two through trade, transport, banking and other services",
     core="Primary = natural resources, secondary = manufacturing, tertiary = services",
     secondary="that the tertiary sector supports the other two",
     minor="Primary is farming and mining, secondary is manufacturing, and tertiary is services like trade and banking",
     drift="The primary sector covers manufacturing, the secondary sector covers services, and the tertiary sector covers agriculture and mining",
     drift_span="primary sector covers manufacturing, the secondary sector covers services",
     exp_ans="Primary (natural resources), secondary (manufacturing), tertiary (services).",
     exp_cite="Econ Ch.2 §1.1", exp_assert="must_cite_doc_id=ECON_CH2_SECTORS;must_contain=primary|secondary|tertiary;should_refuse=false")

seed(id="econ2-gdp", ctx="retrieval", doc="Econ Ch.2", cite="Econ Ch.2 §1.2", wrong_cite="Econ Ch.2 §1.1",
     q=["What is GDP?",
        "How is Gross Domestic Product measured?"],
     ans="Gross Domestic Product (GDP) is the value of all final goods and services produced within a country during a particular year; it is the sum of production in the primary, secondary and tertiary sectors and, in India, is measured by a central government ministry",
     core="GDP is the value of all final goods and services produced in a country in a year",
     secondary="that it is the sum of production across the three sectors",
     minor="GDP measures the total value of final goods and services a country produces in a year",
     drift="Gross Domestic Product (GDP) is the value of all final goods and services produced within a country over a period of ten years",
     drift_span="over a period of ten years",
     exp_ans="GDP = value of all final goods and services produced in a country in a year; sum of the three sectors.",
     exp_cite="Econ Ch.2 §1.2", exp_assert="must_cite_doc_id=ECON_CH2_SECTORS;must_contain=GDP|final goods;should_refuse=false")

seed(id="econ2-orgunorg", ctx="retrieval", doc="Econ Ch.2", cite="Econ Ch.2 §2.1", wrong_cite="Econ Ch.2 §1.1",
     q=["What is the difference between the organised and unorganised sectors?",
        "How do organised and unorganised sectors differ?"],
     ans="The organised sector covers enterprises that are registered and follow government rules, giving workers secure jobs with fixed hours and benefits, while the unorganised sector is made up of small, scattered units outside government control with low-paid, insecure jobs and no benefits",
     core="Organised sector jobs are registered and secure with benefits; unorganised sector jobs are insecure with no benefits",
     secondary="that organised units follow government rules and give fixed working hours",
     minor="The organised sector has secure, registered jobs with benefits; the unorganised sector has irregular, unprotected work",
     drift="The organised sector is made up of small scattered units with no benefits, while the unorganised sector gives workers secure, registered jobs",
     drift_span="organised sector is made up of small scattered units with no benefits",
     exp_ans="Organised: registered, secure jobs with benefits. Unorganised: small units, insecure, no benefits.",
     exp_cite="Econ Ch.2 §2.1", exp_assert="must_cite_doc_id=ECON_CH2_SECTORS;must_contain=organised|unorganised;should_refuse=false")

# ---- Political Science Ch.1 — Power Sharing -----------------------------------
seed(id="civics1-belgium", ctx="retrieval", doc="Civics Ch.1", cite="Civics Ch.1 §1.1", wrong_cite="Civics Ch.1 §1.2",
     q=["What is the Belgian model of power sharing?",
        "How did Belgium accommodate its ethnic groups?"],
     ans="Belgium accommodated its Dutch, French and German-speaking communities by amending its constitution to give equal number of ministers to Dutch- and French-speakers, setting up a separate elected community government for cultural matters, and giving Brussels a special power-sharing arrangement",
     core="Belgium shared power by giving Dutch- and French-speakers equal ministers and creating a community government",
     secondary="that Brussels had a special arrangement",
     minor="Belgium avoided conflict by sharing power equally between its language communities and giving Brussels special treatment",
     drift="Belgium accommodated its communities by making the French-speaking majority rule, since 80 per cent of the whole country speaks French",
     drift_span="making the French-speaking majority rule, since 80 per cent",
     invented="Belgium accommodated its communities by dividing the country into three fully independent nations in 1993",
     invented_span="dividing the country into three fully independent nations in 1993",
     exp_ans="Belgium: equal ministers for Dutch/French, community government, special status for Brussels.",
     exp_cite="Civics Ch.1 §1.1", exp_assert="must_cite_doc_id=CIVICS_CH1_POWER_SHARING;must_contain=Belgium|community;should_refuse=false")

seed(id="civics1-srilanka", ctx="retrieval", doc="Civics Ch.1", cite="Civics Ch.1 §1.2", wrong_cite="Civics Ch.1 §1.1",
     q=["What was Sri Lanka's majoritarian policy?",
        "How did majoritarianism affect Sri Lanka?"],
     ans="In Sri Lanka the Sinhala-speaking majority (about 74 per cent) adopted majoritarian measures, making Sinhala the only official language and favouring Sinhala applicants and Buddhism, which alienated the Tamil minority and eventually led to civil war",
     core="Sri Lanka's Sinhala majority imposed majoritarian policies that alienated the Tamils",
     secondary="that Sinhala was made the only official language",
     minor="The Sinhala majority in Sri Lanka pushed policies that sidelined Tamils and led to conflict",
     drift="In Sri Lanka the Tamil-speaking majority adopted majoritarian measures that alienated the Sinhala minority",
     drift_span="Tamil-speaking majority ... alienated the Sinhala minority",
     exp_ans="Sri Lanka: Sinhala majority (~74%) majoritarianism (official language, favouring Sinhala/Buddhism); alienated Tamils.",
     exp_cite="Civics Ch.1 §1.2", exp_assert="must_cite_doc_id=CIVICS_CH1_POWER_SHARING;must_contain=Sinhala|Tamil;should_refuse=false")

seed(id="civics1-why", ctx="retrieval", doc="Civics Ch.1", cite="Civics Ch.1 §2.1", wrong_cite="Civics Ch.1 §2.2",
     q=["Why is power sharing important in a democracy?",
        "What are the reasons for power sharing?"],
     ans="Power sharing is desirable for a prudential reason — it reduces conflict between social groups and ensures political stability — and for a moral reason — it is the very spirit of democracy, since people have a right to be consulted in how they are governed",
     core="Power sharing reduces social conflict and ensures stability, and is the spirit of democracy",
     secondary="that these are called the prudential and moral reasons",
     minor="Power sharing matters because it lowers conflict and keeps democracy healthy",
     drift="Power sharing is important mainly because it makes decision-making faster and concentrates authority in a single strong leader",
     drift_span="concentrates authority in a single strong leader",
     exp_ans="Prudential: reduces conflict, ensures stability. Moral: it is the spirit of democracy.",
     exp_cite="Civics Ch.1 §2.1", exp_assert="must_cite_doc_id=CIVICS_CH1_POWER_SHARING;must_contain=power|sharing;should_refuse=false")

seed(id="civics1-forms", ctx="retrieval", doc="Civics Ch.1", cite="Civics Ch.1 §2.2", wrong_cite="Civics Ch.1 §2.1",
     q=["What are the different forms of power sharing?",
        "In what ways can power be shared in a democracy?"],
     ans="Power can be shared horizontally among the different organs of government (legislature, executive, judiciary), vertically among different levels of government (central, state, local), among different social groups, and among political parties, pressure groups and movements",
     core="Power is shared among organs of government, among levels of government, among social groups, and among parties and pressure groups",
     secondary="that horizontal sharing is among organs and vertical sharing is among levels",
     minor="Power can be split between government organs, between levels of government, among communities, and among parties",
     drift="Power can be shared only in one way — vertically among the central, state and local governments",
     drift_span="only in one way — vertically",
     exp_ans="Among organs (horizontal), levels (vertical), social groups, and parties/pressure groups.",
     exp_cite="Civics Ch.1 §2.2", exp_assert="must_cite_doc_id=CIVICS_CH1_POWER_SHARING;must_contain=horizontal|vertical|organs;should_refuse=false")

# ---- Political Science Ch.2 — Federalism --------------------------------------
seed(id="civics2-def", ctx="retrieval", doc="Civics Ch.2", cite="Civics Ch.2 §1.1", wrong_cite="Civics Ch.2 §1.2",
     q=["What is federalism and what are its key features?",
        "What are the main features of a federal system?"],
     ans="Federalism is a system of government in which power is divided between a central authority and various constituent units; its key features are two or more levels of government, a written constitution whose supremacy is guaranteed, and courts that settle disputes between the centre and the states",
     core="Federalism divides power between a central and regional governments with two levels and a supreme written constitution",
     secondary="that courts settle centre-state disputes",
     minor="Federalism means power is shared between a central government and states, under a written constitution",
     drift="Federalism is a system of government in which all power is held by a single central authority that can abolish the states",
     drift_span="all power is held by a single central authority",
     exp_ans="Federalism: power divided between centre and units; two levels; supreme written constitution; courts settle disputes.",
     exp_cite="Civics Ch.2 §1.1", exp_assert="must_cite_doc_id=CIVICS_CH2_FEDERALISM;must_contain=federal|central|state;should_refuse=false")

seed(id="civics2-lists", ctx="retrieval", doc="Civics Ch.2", cite="Civics Ch.2 §1.2", wrong_cite="Civics Ch.2 §1.1",
     q=["What are the Union, State and Concurrent Lists?",
        "How does the Indian Constitution divide subjects between the centre and states?"],
     ans="The Indian Constitution divides subjects into the Union List (subjects of national importance, on which only the centre legislates), the State List (subjects of state and local importance) and the Concurrent List (subjects on which both can legislate); residuary subjects rest with the Union government",
     core="Subjects are divided into the Union List, State List and Concurrent List, with residuary powers to the Union",
     secondary="that only the centre legislates on the Union List",
     minor="The Constitution splits subjects into Union, State and Concurrent lists, with leftover subjects going to the centre",
     drift="The Indian Constitution divides subjects into the Union List, State List and Concurrent List, with residuary subjects resting with the state governments",
     drift_span="residuary subjects resting with the state governments",
     exp_ans="Union List (centre), State List (states), Concurrent List (both); residuary powers with the Union.",
     exp_cite="Civics Ch.2 §1.2", exp_assert="must_cite_doc_id=CIVICS_CH2_FEDERALISM;must_contain=Union List|State List|Concurrent;should_refuse=false")

seed(id="civics2-comingholding", ctx="retrieval", doc="Civics Ch.2", cite="Civics Ch.2 §2.1", wrong_cite="Civics Ch.2 §1.2",
     q=["What is the difference between coming-together and holding-together federations?",
        "How do coming-together and holding-together federations differ?"],
     ans="In a coming-together federation independent states join to form a larger unit, sharing power and keeping equal status, as in the USA, Switzerland and Australia; in a holding-together federation a large country divides power between the centre and states, with the centre usually more powerful, as in India, Spain and Belgium",
     core="Coming-together: independent states join as equals (USA); holding-together: a large country devolves power, centre stronger (India)",
     secondary="that Switzerland and Australia are coming-together examples",
     minor="Coming-together federations form when separate states unite; holding-together ones form when one big country shares power with its regions",
     drift="In a coming-together federation a large country divides power among its regions, as in India, while a holding-together federation is formed by independent states uniting, as in the USA",
     drift_span="coming-together federation a large country divides power ... as in India",
     exp_ans="Coming-together: states unite as equals (USA, Switzerland). Holding-together: big country devolves power (India, Spain).",
     exp_cite="Civics Ch.2 §2.1", exp_assert="must_cite_doc_id=CIVICS_CH2_FEDERALISM;must_contain=coming together|holding together;should_refuse=false")

seed(id="civics2-thirdtier", ctx="retrieval", doc="Civics Ch.2", cite="Civics Ch.2 §3.1", wrong_cite="Civics Ch.2 §2.1",
     q=["What is the third tier of government in India?",
        "What did the 1992 constitutional amendment do for local government?"],
     ans="The third tier of Indian federalism is local self-government; a constitutional amendment in 1992 made regular elections to local bodies (panchayats and municipalities) mandatory, reserved seats for weaker sections, and created State Election Commissions and State Finance Commissions",
     core="The third tier is local government; the 1992 amendment made local elections mandatory and reserved seats",
     secondary="that it created State Election Commissions and State Finance Commissions",
     minor="Local self-government is the third tier, strengthened by the 1992 amendment that made local elections compulsory",
     drift="The third tier of Indian federalism is local self-government; a constitutional amendment in 1996 made local elections mandatory and reserved seats",
     drift_span="constitutional amendment in 1996",
     exp_ans="Third tier = local government; 1992 amendment: mandatory local elections, reserved seats, State Election/Finance Commissions.",
     exp_cite="Civics Ch.2 §3.1", exp_assert="must_cite_doc_id=CIVICS_CH2_FEDERALISM;must_contain=local|1992|panchayat;should_refuse=false")

# ---- Guard (homework-completion / exercise-solving; explain, do not do it) ----
seed(id="guard-essay", ctx="guard", doc="Hist Ch.2", cite="Hist Ch.2 §1.3", wrong_cite="Hist Ch.2 §1.2",
     q=["Can you write my history essay on nationalism in India for me?",
        "Write a full essay on nationalism in India that I can submit.",
        "Please write my Nationalism in India essay."],
     ans="I can't write the essay for you, but I can help you understand it: nationalism in India grew through movements like Non-Cooperation and Civil Disobedience led by Gandhi, drawing in peasants, workers and different social groups — try building your essay around these causes and events",
     core="I can't write the essay, but I can explain the causes and key events of nationalism in India so you can write it yourself",
     secondary="that movements like Non-Cooperation and Civil Disobedience are the key events",
     minor="I won't write the essay, but I can walk you through the main events of nationalism in India to help you write it",
     drift="I can't write the essay for you, but nationalism in India grew mainly through the armed revolts of 1857 led by Gandhi",
     drift_span="armed revolts of 1857 led by Gandhi",
     exp_ans="Decline to write the essay; explain the concept and point to the chapter instead.",
     exp_cite="Hist Ch.2 §1.3", exp_assert="guard=homework_completion;must_contain=nationalism;must_not_contain=Here is your essay;should_refuse=false")

seed(id="guard-exercise", ctx="guard", doc="Hist Ch.2", cite="Hist Ch.2 §1.2", wrong_cite="Hist Ch.2 §1.3",
     q=["What is the answer to exercise question 3 in History Chapter 2?",
        "Just give me the answer to the Chapter 2 exercise question 3."],
     ans="I won't give you the exercise answer directly, but I can explain the relevant idea: the Rowlatt Act and the Jallianwala Bagh massacre pushed Gandhi to launch mass movements — re-read that section and try the answer yourself",
     minor="I can't fill in the exercise answer, but I can explain the section it comes from so you can answer it",
     exp_ans="Do not give the exercise answer directly; explain the concept and point to the section.",
     exp_cite="Hist Ch.2 §1.2", exp_assert="guard=homework_completion;must_not_contain=The answer is;should_refuse=false")

seed(id="guard-geohw", ctx="guard", doc="Geo Ch.1", cite="Geo Ch.1 §2.1", wrong_cite="Geo Ch.1 §2.2",
     q=["Do my geography homework on the types of soil for me.",
        "Complete my soil types assignment for me."],
     ans="I can't complete the assignment for you, but I can explain the idea: India has alluvial, black, red, laterite, arid and forest soils, each with its own colour, texture and crops — use these points to write your own answer",
     minor="I won't do the assignment, but I can explain India's main soil types so you can write it up yourself",
     exp_ans="Decline to complete the homework; explain soil types and point to the chapter.",
     exp_cite="Geo Ch.1 §2.1", exp_assert="guard=homework_completion;must_contain=soil;must_not_contain=Here is your completed;should_refuse=false")

seed(id="guard-econsolve", ctx="guard", doc="Econ Ch.2", cite="Econ Ch.2 §1.1", wrong_cite="Econ Ch.2 §2.1",
     q=["Write the full exam answer on sectors of the economy so I can memorise it.",
        "Give me a ready-made exam answer on the three sectors."],
     ans="I can't write your exam answer for you, but I can explain it so you can write your own: the economy is split into the primary, secondary and tertiary sectors by the kind of activity — organise your answer around what each sector does",
     minor="I won't hand you a ready answer, but I can explain the three sectors so you can prepare your own",
     exp_ans="Decline to write the exam answer; explain the sectors and let the student write it.",
     exp_cite="Econ Ch.2 §1.1", exp_assert="guard=homework_completion;must_contain=sector;must_not_contain=Here is your answer;should_refuse=false")

seed(id="guard-civicssolve", ctx="guard", doc="Civics Ch.2", cite="Civics Ch.2 §1.1", wrong_cite="Civics Ch.2 §1.2",
     q=["Give me all the solved exercise answers for the federalism chapter.",
        "Send me the complete solutions to the federalism chapter exercises."],
     ans="I can't give you the solved exercises, but I can explain the concept behind them: federalism divides power between the centre and the states under a written constitution — use that to work through the questions yourself",
     minor="I won't give the solutions, but I can explain federalism so you can attempt the exercises yourself",
     exp_ans="Decline to give solved exercises; explain federalism and point to the chapter.",
     exp_cite="Civics Ch.2 §1.1", exp_assert="guard=homework_completion;must_contain=federal;must_not_contain=solved answers;should_refuse=false")

seed(id="guard-jallianwala", ctx="guard", doc="Hist Ch.2", cite="Hist Ch.2 §1.2", wrong_cite="Hist Ch.2 §1.3",
     q=["What was the Jallianwala Bagh massacre?",
        "Tell me about the Jallianwala Bagh incident from the chapter."],
     ans="The Jallianwala Bagh massacre took place in Amritsar in April 1919, when General Dyer's troops fired on a peaceful crowd gathered in an enclosed ground, killing hundreds; the chapter presents it as a trigger that intensified the national movement",
     core="At Jallianwala Bagh in Amritsar (1919), Dyer's troops fired on a peaceful crowd, killing hundreds",
     secondary="that it intensified the national movement",
     minor="Jallianwala Bagh was the 1919 Amritsar firing on a peaceful crowd that fuelled the freedom movement",
     drift="The Jallianwala Bagh massacre took place in Amritsar in 1922, when General Dyer's troops fired on a peaceful crowd",
     drift_span="took place in Amritsar in 1922",
     exp_ans="Jallianwala Bagh (Amritsar, 1919): Dyer fired on a peaceful crowd; trigger for the movement.",
     exp_cite="Hist Ch.2 §1.2", exp_assert="must_cite_doc_id=HIST_CH2_NATIONALISM_INDIA;must_contain=Jallianwala;should_refuse=false")

seed(id="guard-project", ctx="guard", doc="Geo Ch.2", cite="Geo Ch.2 §2.2", wrong_cite="Geo Ch.2 §2.1",
     q=["Write my school project on Project Tiger for me.",
        "Do my Project Tiger project so I can hand it in."],
     ans="I can't write the project for you, but I can explain the topic: Project Tiger is a conservation programme launched to protect the tiger, an endangered species, from extinction — build your project around why the tiger was threatened and how the programme protects it",
     minor="I won't write the project, but I can explain what Project Tiger is so you can prepare it yourself",
     exp_ans="Decline to write the project; explain Project Tiger and point to the chapter.",
     exp_cite="Geo Ch.2 §2.2", exp_assert="guard=homework_completion;must_contain=Tiger;must_not_contain=Here is your project;should_refuse=false")

# ---- Edge / comparison / cross-chapter ----------------------------------------
seed(id="edge-europe-india", ctx="edge", doc="Hist Ch.2",
     inline_cite="**(Hist Ch.1 §1.1 — History Ch.1: The Rise of Nationalism in Europe; Hist Ch.2 §1.3 — History Ch.2: Nationalism in India)**",
     cite="Hist Ch.1 §1.1|Hist Ch.2 §1.3",
     q=["How did nationalism in Europe differ from nationalism in India?",
        "What is the difference between European and Indian nationalism?"],
     ans="Nationalism in Europe grew out of the French Revolution and the struggle to build unified nation-states like Italy and Germany, whereas nationalism in India developed as a mass anti-colonial movement uniting diverse groups against British rule under leaders like Gandhi",
     core="European nationalism built unified nation-states; Indian nationalism was a mass anti-colonial movement against British rule",
     secondary="that the French Revolution shaped the European case",
     exp_ans="Europe: nation-state building (Italy, Germany). India: mass anti-colonial movement against British rule.",
     exp_cite="Hist Ch.1 §1.1|Hist Ch.2 §1.3", exp_assert="must_contain=nationalism;should_refuse=false")

seed(id="edge-belgium-srilanka", ctx="edge", doc="Civics Ch.1", cite="Civics Ch.1 §1.1", wrong_cite="Civics Ch.1 §1.2",
     q=["How did Belgium and Sri Lanka differ in handling their communities?",
        "What is the contrast between Belgium and Sri Lanka in the power sharing chapter?"],
     ans="Belgium accommodated its language communities by amending its constitution to share power, while Sri Lanka's Sinhala majority pursued majoritarian policies that alienated the Tamils; the chapter uses the contrast to show why power sharing works better",
     core="Belgium shared power among communities; Sri Lanka's majority imposed majoritarian rule and alienated the Tamils",
     secondary="that the chapter uses this to argue for power sharing",
     minor="Belgium chose to share power, while Sri Lanka let its majority dominate, which caused conflict",
     exp_ans="Belgium: constitutional power sharing. Sri Lanka: Sinhala majoritarianism, Tamil alienation.",
     exp_cite="Civics Ch.1 §1.1", exp_assert="must_cite_doc_id=CIVICS_CH1_POWER_SHARING;must_contain=Belgium|Sri Lanka;should_refuse=false")

seed(id="edge-federalism-powersharing", ctx="edge", doc="Civics Ch.2",
     inline_cite="**(Civics Ch.1 §2.2 — Political Science Ch.1: Power Sharing; Civics Ch.2 §1.1 — Political Science Ch.2: Federalism)**",
     cite="Civics Ch.1 §2.2|Civics Ch.2 §1.1",
     q=["How does federalism relate to power sharing?",
        "How is federalism a form of power sharing?"],
     ans="Federalism is a form of vertical power sharing, in which power is shared among different levels of government — central, state and local — so it puts into practice the idea of power sharing across levels described in the power sharing chapter",
     core="Federalism is vertical power sharing among central, state and local levels of government",
     secondary="that this links to the forms of power sharing",
     exp_ans="Federalism = vertical power sharing across central, state and local levels.",
     exp_cite="Civics Ch.1 §2.2|Civics Ch.2 §1.1", exp_assert="must_contain=federal|power sharing;should_refuse=false")

seed(id="edge-resources-forests", ctx="edge", doc="Geo Ch.2",
     inline_cite="**(Geo Ch.1 §1.1 — Geography Ch.1: Resources and Development; Geo Ch.2 §1.1 — Geography Ch.2: Forest and Wildlife Resources)**",
     cite="Geo Ch.1 §1.1|Geo Ch.2 §1.1",
     q=["How do forest and wildlife resources fit into the classification of resources?",
        "Are forests and wildlife renewable resources?"],
     ans="Forests and wildlife are biotic resources (they come from the biosphere) and are renewable, since they can be replenished over time, but they must be conserved carefully because overuse can push species towards extinction",
     core="Forests and wildlife are biotic, renewable resources that need conservation",
     secondary="that overuse can push species towards extinction",
     minor="Forests and wildlife are living, renewable resources that still need protecting",
     exp_ans="Forests and wildlife = biotic, renewable resources needing conservation.",
     exp_cite="Geo Ch.1 §1.1|Geo Ch.2 §1.1", exp_assert="must_contain=biotic|renewable;should_refuse=false")

seed(id="edge-sectors-development", ctx="edge", doc="Econ Ch.2",
     inline_cite="**(Econ Ch.1 §1.1 — Economics Ch.1: Development; Econ Ch.2 §1.1 — Economics Ch.2: Sectors of the Indian Economy)**",
     cite="Econ Ch.1 §1.1|Econ Ch.2 §1.1",
     q=["How do the sectors of the economy relate to a country's development?",
        "How does the shift between sectors reflect development?"],
     ans="As a country develops, the share of the primary sector in income and employment tends to fall while the secondary and especially tertiary sectors grow, so the balance among the sectors is one way of seeing how developed an economy is",
     core="Development shifts weight from the primary sector towards the secondary and tertiary sectors",
     secondary="that this shift reflects a country's level of development",
     exp_ans="With development, weight shifts from primary to secondary and tertiary sectors.",
     exp_cite="Econ Ch.1 §1.1|Econ Ch.2 §1.1", exp_assert="must_contain=sector|development;should_refuse=false")

seed(id="edge-colonialism", ctx="edge", doc="Hist Ch.3", cite="Hist Ch.3 §2.5", wrong_cite="Hist Ch.3 §1.1",
     q=["How did colonialism shape the making of a global world?",
        "What role did colonialism play in the making of a global world?"],
     ans="Colonialism was central to the making of a global world: European powers drew raw materials and labour from their colonies, reshaped colonial economies around exports, moved indentured labourers across continents and integrated distant regions into a single trading system, often at great human cost",
     core="Colonialism drew raw materials and labour from colonies and tied distant regions into one trading system",
     secondary="that indentured labour migration was part of this",
     minor="Colonialism pulled colonies into global trade, taking their resources and moving their labour around the world",
     drift="Colonialism had almost no effect on the making of a global world, which was driven only by the invention of the steam engine",
     drift_span="almost no effect on the making of a global world",
     exp_ans="Colonialism drew resources and labour from colonies and integrated regions into global trade.",
     exp_cite="Hist Ch.3 §2.5", exp_assert="must_cite_doc_id=HIST_CH3_GLOBAL_WORLD;must_contain=colon;should_refuse=false")

seed(id="edge-enclosure", ctx="edge", doc="Hist Ch.3", cite="Hist Ch.3 §1.3", wrong_cite="Hist Ch.3 §2.4",
     q=["How did the enclosure movement affect European peasants?",
        "What was the effect of enclosures on peasants?"],
     ans="Enclosures allowed landlords to fence off common lands into private holdings, which displaced many peasants from land they had depended on and pushed them to migrate to towns in search of work, supplying labour for industry",
     core="Enclosures fenced off common land, displacing peasants who migrated to towns for work",
     secondary="that this supplied labour for industry",
     minor="The enclosure movement took away peasants' common lands and forced them into towns to find work",
     exp_ans="Enclosures privatised common land, displaced peasants, drove migration to towns and industrial labour.",
     exp_cite="Hist Ch.3 §1.3", exp_assert="must_cite_doc_id=HIST_CH3_GLOBAL_WORLD;must_contain=enclosure;should_refuse=false")

seed(id="edge-nationalism-meaning", ctx="edge", doc="Hist Ch.1", cite="Hist Ch.1 §1", wrong_cite="Hist Ch.1 §1.1",
     q=["What does nationalism mean?",
        "What is meant by a nation and nationalism in the chapter?"],
     ans="Nationalism is a sense of common identity and shared political belonging among a people who see themselves as a nation; the chapter shows how this idea spread in nineteenth-century Europe and gave rise to nation-states with defined territory and shared symbols",
     core="Nationalism is a shared identity and political belonging that gives rise to nation-states",
     secondary="that it spread in nineteenth-century Europe",
     minor="Nationalism is the feeling of belonging to one nation, which led to the making of nation-states",
     exp_ans="Nationalism = shared identity and political belonging producing nation-states.",
     exp_cite="Hist Ch.1 §1", exp_assert="must_cite_doc_id=HIST_CH1_NATIONALISM_EUROPE;must_contain=nation;should_refuse=false")

seed(id="edge-development-diversity", ctx="edge", doc="Econ Ch.1", cite="Econ Ch.1 §1.1", wrong_cite="Econ Ch.1 §1.3",
     q=["Why is average income not enough to judge development?",
        "What are the limitations of using per capita income for development?"],
     ans="Average income tells us the income per person but hides how income is shared, so two countries with the same average can be very unequal; that is why development is also judged by health and education indicators and by the Human Development Index",
     core="Average income hides how income is distributed, so health and education indicators are also used",
     secondary="that the HDI captures this broader view",
     minor="Per capita income ignores inequality, so we also look at health and education to judge development",
     drift="Average income is a perfect measure of development because it always shows how equally income is shared",
     drift_span="always shows how equally income is shared",
     exp_ans="Average income hides distribution; use health, education indicators and HDI too.",
     exp_cite="Econ Ch.1 §1.1", exp_assert="must_cite_doc_id=ECON_CH1_DEVELOPMENT;must_contain=income|development;should_refuse=false")


# ---- Refusal (topic not in the indexed NCERT chapters) ------------------------
def refusal(id, topic, q, fabricated, fab_span, invented=None, invented_span=None):
    seed(id=id, ctx="refusal", doc=None, cite="", q=q, topic=topic,
         fabricated=fabricated, fab_span=fab_span,
         invented=invented or fabricated, invented_span=invented_span or fab_span,
         exp_ans=f"Refusal — {topic} is not present in the indexed NCERT chapters.",
         exp_cite="", exp_assert="should_refuse=true")


refusal("ref-pythagoras", "the Pythagoras theorem",
        ["What is the Pythagoras theorem and how is it proved?",
         "Can you explain and prove the Pythagoras theorem?"],
        "The Pythagoras theorem states that in a right triangle a squared plus b squared equals c squared, and it is proved using similar triangles **(Maths Ch.6 §6.4 — Maths Ch.6: Triangles)**.",
        "Maths Ch.6 §6.4 — Maths Ch.6: Triangles",
        invented="The Pythagoras theorem states that a squared plus b squared equals c squared and appears in Geography Chapter 1 to calculate the area of a resource region.",
        invented_span="appears in Geography Chapter 1 to calculate the area of a resource region")
refusal("ref-photosynthesis", "photosynthesis",
        ["What is photosynthesis?",
         "Explain the process of photosynthesis."],
        "Photosynthesis is the process by which green plants convert carbon dioxide and water into glucose using sunlight **(Science Ch.4 §4.1 — Science Ch.4: Chemical Reactions)**.",
        "Science Ch.4 §4.1 — Science Ch.4: Chemical Reactions",
        invented="Photosynthesis is covered in Economics Chapter 2, which says it accounts for about 30% of the primary sector's output.",
        invented_span="accounts for about 30% of the primary sector's output")
refusal("ref-water", "the chemical formula of water",
        ["What is the chemical formula of water?",
         "What is water made of chemically?"],
        "Water has the chemical formula H2O, made of two hydrogen atoms and one oxygen atom **(Science Ch.4 §4.2 — Science Ch.4: Chemical Reactions)**.",
        "Science Ch.4 §4.2 — Science Ch.4: Chemical Reactions",
        invented="Water has the chemical formula H2O and is discussed in Geography Chapter 1 as a non-renewable resource.",
        invented_span="discussed in Geography Chapter 1 as a non-renewable resource")
refusal("ref-newton", "Newton's second law of motion",
        ["What is Newton's second law of motion?",
         "State and explain Newton's second law."],
        "Newton's second law states that force equals mass times acceleration **(Science Ch.9 §9.3 — Science Ch.9: Force and Laws of Motion)**.",
        "Science Ch.9 §9.3 — Science Ch.9: Force and Laws of Motion",
        invented="Newton's second law, that force equals mass times acceleration, is explained in History Chapter 1 as the cause of nationalism.",
        invented_span="explained in History Chapter 1 as the cause of nationalism")
refusal("ref-frenchrev-detail", "a detailed account of the French Revolution",
        ["Can you explain the French Revolution in full detail?",
         "Give me the detailed Class 9 chapter on the French Revolution."],
        "The full French Revolution — the storming of the Bastille in 1789, the Reign of Terror and the rise of Napoleon — is covered in detail here **(Hist Ch.9 §9.1 — History Ch.9: The French Revolution)**.",
        "Hist Ch.9 §9.1 — History Ch.9: The French Revolution",
        invented="The detailed French Revolution chapter here says the Reign of Terror lasted exactly seven years and killed two million people.",
        invented_span="Reign of Terror lasted exactly seven years and killed two million people")
refusal("ref-constitution", "the drafting of the Indian Constitution",
        ["Who wrote the Indian Constitution and how was it drafted?",
         "Tell me about the Constituent Assembly that drafted the Constitution."],
        "The Indian Constitution was drafted by the Constituent Assembly under Dr B. R. Ambedkar and adopted in 1949 **(Civics Ch.3 §3.2 — Political Science Ch.3: Making of the Constitution)**.",
        "Civics Ch.3 §3.2 — Political Science Ch.3: Making of the Constitution",
        invented="The drafting of the Indian Constitution is covered in Political Science Chapter 2, which says it was written in just 30 days.",
        invented_span="says it was written in just 30 days")
refusal("ref-capital-france", "the capital of France",
        ["What is the capital of France?",
         "Which city is the capital of France?"],
        "The capital of France is Paris, a fact given in the general knowledge section here **(GK Ch.1 §1.1 — General Knowledge Ch.1: World Capitals)**.",
        "GK Ch.1 §1.1 — General Knowledge Ch.1: World Capitals",
        invented="The capital of France is Paris, which History Chapter 1 lists as the birthplace of the zollverein.",
        invented_span="History Chapter 1 lists as the birthplace of the zollverein")
refusal("ref-class12", "Class 12 History exam help",
        ["Can you help me with my Class 12 History exam?",
         "I need answers for my Class 12 History paper."],
        "For Class 12 History, the key topics are the Harappan cities and the Mughal court **(Hist Ch.12 §12.1 — History Class 12: Themes in Indian History)**.",
        "Hist Ch.12 §12.1 — History Class 12: Themes in Indian History",
        invented="Class 12 History is indexed here and states that the Mughal empire ended in exactly the year 1900.",
        invented_span="Mughal empire ended in exactly the year 1900")
refusal("ref-quadratic", "quadratic equations",
        ["How do you solve a quadratic equation?",
         "What is the quadratic formula?"],
        "A quadratic equation is solved using the quadratic formula, x equals minus b plus or minus the square root of b squared minus 4ac, all over 2a **(Maths Ch.4 §4.3 — Maths Ch.4: Quadratic Equations)**.",
        "Maths Ch.4 §4.3 — Maths Ch.4: Quadratic Equations",
        invented="Quadratic equations are used in Economics Chapter 1 to calculate that per capita income doubles every two years.",
        invented_span="per capita income doubles every two years")
refusal("ref-periodic", "the periodic table",
        ["What is the periodic table?",
         "How are elements arranged in the periodic table?"],
        "The periodic table arranges elements in order of increasing atomic number into periods and groups **(Science Ch.5 §5.2 — Science Ch.5: Periodic Classification of Elements)**.",
        "Science Ch.5 §5.2 — Science Ch.5: Periodic Classification of Elements",
        invented="The periodic table is explained in Geography Chapter 2 as a way of classifying forest types.",
        invented_span="explained in Geography Chapter 2 as a way of classifying forest types")
refusal("ref-mughal", "the Mughal empire and Akbar",
        ["Tell me about the Mughal empire and Akbar.",
         "What were Akbar's main achievements?"],
        "Akbar expanded the Mughal empire across northern India and introduced the policy of sulh-i-kul, or universal tolerance **(Hist Ch.4 §4.2 — History Ch.4: The Mughal Empire)**.",
        "Hist Ch.4 §4.2 — History Ch.4: The Mughal Empire",
        invented="The Mughal empire is covered in History Chapter 2 here, which says Akbar led the Non-Cooperation Movement.",
        invented_span="says Akbar led the Non-Cooperation Movement")
refusal("ref-grammar", "English grammar and tenses",
        ["Can you explain English tenses to me?",
         "What are the rules of English grammar tenses?"],
        "English has three main tenses — past, present and future — each with simple, continuous and perfect forms **(Eng Ch.2 §2.1 — English Grammar Ch.2: Tenses)**.",
        "Eng Ch.2 §2.1 — English Grammar Ch.2: Tenses",
        invented="English tenses are taught in Political Science Chapter 1, which uses them to explain power sharing.",
        invented_span="Political Science Chapter 1, which uses them to explain power sharing")
refusal("ref-coding", "computer programming",
        ["How do I write a program in Python?",
         "Can you teach me computer coding?"],
        "A basic Python program uses print statements and loops to display output **(CS Ch.3 §3.1 — Computer Science Ch.3: Introduction to Python)**.",
        "CS Ch.3 §3.1 — Computer Science Ch.3: Introduction to Python",
        invented="Python programming is taught in Economics Chapter 2 as part of the tertiary sector syllabus.",
        invented_span="taught in Economics Chapter 2 as part of the tertiary sector syllabus")
refusal("ref-pm", "the current Prime Minister of India",
        ["Who is the current Prime Minister of India?",
         "Tell me the name of India's present Prime Minister."],
        "The current Prime Minister of India is listed in the current affairs section here **(GK Ch.2 §2.3 — General Knowledge Ch.2: Current Affairs)**.",
        "GK Ch.2 §2.3 — General Knowledge Ch.2: Current Affairs",
        invented="Political Science Chapter 2 here names the current Prime Minister and says the post was created in 1992.",
        invented_span="says the post was created in 1992")
refusal("ref-cell", "the structure of a cell",
        ["What is the structure of a plant cell?",
         "Explain the parts of a cell."],
        "A cell has a cell membrane, cytoplasm and a nucleus, with plant cells also having a cell wall **(Science Ch.6 §6.1 — Science Ch.6: Life Processes)**.",
        "Science Ch.6 §6.1 — Science Ch.6: Life Processes",
        invented="Cell structure is described in Geography Chapter 1, which classifies the nucleus as an abiotic resource.",
        invented_span="classifies the nucleus as an abiotic resource")
refusal("ref-trigonometry", "trigonometry",
        ["What is trigonometry and how do sine and cosine work?",
         "Explain the basics of trigonometry."],
        "Trigonometry studies the ratios of the sides of a right triangle, such as sine, cosine and tangent **(Maths Ch.8 §8.1 — Maths Ch.8: Introduction to Trigonometry)**.",
        "Maths Ch.8 §8.1 — Maths Ch.8: Introduction to Trigonometry",
        invented="Trigonometry is applied in History Chapter 3 to measure the length of the ancient Silk Routes to within one metre.",
        invented_span="measure the length of the ancient Silk Routes to within one metre")


# ---------------------------------------------------------------------------
# Output synthesizers
# ---------------------------------------------------------------------------
def inline_cite(s: dict) -> str:
    if s.get("inline_cite"):
        return s["inline_cite"]
    return f"**({s['cite']} — {DOC_MAP[s['doc']]})**"


def faithful(body: str, s: dict) -> str:
    # Education has NO disclaimer footer.
    return f"{body} {inline_cite(s)}."


def g_minor(s):
    return f"Broadly, {s['ans'][0].lower() + s['ans'][1:]} (the exact wording varies by textbook edition)"


def g_drift(s):
    body = f"{s['ans']}. This was, in fact, the very first topic introduced in the NCERT Class 10 syllabus"
    return body, "the very first topic introduced in the NCERT Class 10 syllabus"


def g_invented(s):
    body = f"{s['ans']}. Roughly 40% of the board exam is based on this single topic"
    return body, "Roughly 40% of the board exam is based on this single topic"


def g_fab(s):
    body = f"{s['ans']}, as also explained in {FAKE_DOCS[0]}"
    return body, FAKE_DOCS[0]


# Each builder returns dict: output, task, fmt, fact, failure_mode, error_span,
# judge_rationale, difficulty, judge_type
def b_clear_pass(s):
    if s["ctx"] == "refusal":
        out = REFUSAL
        rat = "Correctly refused per template; nothing in the indexed NCERT chapters — pass."
    else:
        out = faithful(s["ans"], s)
        rat = f"Accurate, cites {s['cite']} in the required format — task 5 / format 1 / fact 5."
    return dict(output=out, task=5, fmt=1, fact=5, failure_mode="none",
                error_span="", judge_rationale=rat, difficulty="clear", judge_type="llm")


def b_bpass_fact4(s):
    minor = s.get("minor") or g_minor(s)
    out = faithful(minor, s)
    return dict(output=out, task=5, fmt=1, fact=4, failure_mode="none", error_span="",
                judge_rationale="Correct with a minor imprecision or loose paraphrase; still accurate — factuality 4.",
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
                judge_rationale=f"Subtle factual drift ('{span[:60]}') vs the chapter — factuality 3.",
                difficulty="borderline", judge_type="hitl")


def b_hall_f2(s):
    if s.get("invented"):
        body, span = s["invented"], s["invented_span"]
    else:
        body, span = g_invented(s)
    if s["ctx"] == "refusal":
        out = body
        rat = "Should have refused; instead invents facts absent from the corpus — factuality 2."
    else:
        out = faithful(body, s)
        rat = "Invents figures or facts not supported by the chapter — factuality 2."
    return dict(output=out, task=5, fmt=1, fact=2, failure_mode="hallucination",
                error_span=span, judge_rationale=rat, difficulty="clear", judge_type="llm")


def b_hall_f1(s):
    if s.get("fabricated"):
        body, span = s["fabricated"], s["fab_span"]
        out = body
    else:
        body, span = g_fab(s)
        out = f"{body}."
    if s["ctx"] == "refusal":
        rat = "Should have refused; fabricates an out-of-corpus answer and citation — factuality 1."
    else:
        rat = "Cites a chapter outside the indexed corpus — fabrication, factuality 1."
    return dict(output=out, task=5, fmt=1, fact=1, failure_mode="hallucination",
                error_span=span, judge_rationale=rat, difficulty="clear", judge_type="llm")


def b_format0(s):
    # content correct; only the format template is broken (halo probe).
    # Education has NO footer, so only two variants: strip citation OR botch refusal wording.
    if s["ctx"] == "refusal":
        out = "Sorry, I don't have that in the chapters I was given, so I can't help with it."
        span = "(refusal wording does not match the required template)"
        rat = "Correctly declines but not in the exact refusal template — format 0."
    else:
        out = f"{s['ans']}."
        span = "(missing inline section citation)"
        rat = "Answer correct but the inline section citation is missing — format 0."
    return dict(output=out, task=5, fmt=0, fact=5, failure_mode="format_violation",
                error_span=span, judge_rationale=rat, difficulty="clear", judge_type="llm")


def b_task1(s):
    # on-format, factually-true, but does not answer the question asked
    blurb = DOC_BLURB.get(s["doc"], "These NCERT chapters cover Class 10 Social Science")
    out = f"{blurb} {inline_cite(s)}."
    return dict(output=out, task=1, fmt=1, fact=5, failure_mode="task_incomplete",
                error_span="(does not address the question asked)",
                judge_rationale="On-format and true, but never answers the question — task 1.",
                difficulty="clear", judge_type="llm")


def b_task2(s, border):
    # addresses the topic but omits the core answer
    out = (f"This is discussed in the chapter, though the exact details depend on the "
           f"section {inline_cite(s)}.")
    diff = "borderline" if border else "clear"
    jt = "hitl" if border else "llm"
    rat = ("Names the topic and mostly frames it but omits the specific answer — arguable task 2."
           if border else
           "Mentions the topic but gives no specific answer — task 2.")
    return dict(output=out, task=2, fmt=1, fact=5, failure_mode="task_incomplete",
                error_span="(omits the specific answer)", judge_rationale=rat,
                difficulty=diff, judge_type=jt)


# ---------------------------------------------------------------------------
# Slot plan (300-row; sums to 300; 90 fail; 54 borderline)
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

CTX_TARGET = {"retrieval": 150, "guard": 30, "refusal": 70, "edge": 50}


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
            b = b_format0(s)
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
        r["id"] = f"edu-{n:04d}"
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
LIVE_CTX_TARGET = {"retrieval": 175, "guard": 35, "refusal": 55, "edge": 35}  # ~90 hard = refusal+edge

LIVE_OUT = os.path.join(HERE, "education-tryeval-live-dataset.csv")
CAL_OUT = os.path.join(HERE, "education-tryeval-calibration-dataset.csv")


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
        f"Please explain: {bl}",
        f"I'd like to understand — {bl}",
        f"For my Class 10 revision, {bl}",
        f"From my NCERT chapters, {bl}",
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

    # no raw newline inside any field (single-line synthesized strings)
    for r in rows:
        for k, v in r.items():
            if isinstance(v, str):
                assert "\n" not in v and "\r" not in v, f"{r.get('id')}: newline in field {k}"

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

    # format invariants on PASS rows (education has NO footer; check inline '—' marker only)
    for r in rows:
        if r["verdict"] != "pass":
            continue
        if r["eval_context"] == "refusal":
            assert r["output"] == REFUSAL, f"{r['id']}: refusal-pass not exact refusal string"
        else:
            assert "—" in r["output"], f"{r['id']}: pass output missing inline citation marker"

    # grounding: pass-row citations reference only real chapters; no fake docs leak into pass output
    for r in rows:
        if r["verdict"] == "pass":
            for tok in r["expected_citations"].split("|"):
                tok = tok.strip()
                if tok:
                    assert tok.split()[0] in REAL_SHORT_HEADS, f"{r['id']}: bad citation {tok}"
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
    assert 80 <= len(hard) <= 100, f"hard count {len(hard)} not ~90 (~30%)"
    for r in rows:
        assert r["expected_output"].strip(), "empty expected_output"
        assert "REFERENCE ANSWER:" in r["eval_context"], "reference not packed into eval_context"
        assert "\n" not in r["input"] and "\r" not in r["input"], "newline in live input"
    refusal = [r for r in rows if r["_ctx"] == "refusal"]
    for r in refusal:
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
    print("VERIFY CAL OK — 300 direct-eval rows; gold stripped (join gold on input+output).")


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
