# Law RAG → TryEval setup

Files in this folder:

| File | Role |
| --- | --- |
| `law-tryeval-live-dataset.csv` | **Live run.** 300 questions; TryEval calls the RAG endpoint per row, then the rubrics judge the answer. ~85 (~30%) are hard (refusal/edge) the RAG is likely to fail. |
| `law-tryeval-calibration-dataset.csv` | **Judge calibration (direct-eval).** 300 rows with a *pre-filled* `output` (no endpoint call). Judge scores the fixed answers; compare to the gold labels to trust the judge before believing the live run. |
| `law-judge-dataset.csv` | **Gold side-file** (full labels: 3 scores, verdict, failure_mode, error_span). NOT uploaded — TryEval has no columns for it. Used to score the judge. |
| `law-metrics.json` | The 3 rubric Metrics to create in TryEval. |
| `_build_law_judge.py` | Regenerates all CSVs (`--emit all --verify`, deterministic seed 1234). 300 rows. |
| `_score_law_judge.py` | Scores a judge export vs gold (κ, fail-class P/R, per-rubric threshold-crossing, borderline flip-rate, matched pairs). |

## Column mapping (TryEval canonical headers)
- `input` → prompt / `${PROMPT}` (required)
- `eval_context` → context / `${CONTEXT}` — **the only field the LLM judge sees.** The gold reference answer + expected citations are packed here so Task/Factuality can grade against them.
- `expected_output` → statistical reference only (F1/ROUGE); **never** seen by the LLM judge.
- `output` → aiOutput (direct-eval only; becomes the judge's "Model Output").

**No leak:** the endpoint Input Template is `{"q":"${PROMPT}"}` — it does not reference `${CONTEXT}`, so the reference in `eval_context` reaches the judge but never the model under test (no leak). Keep it that way (don't add `${CONTEXT}` to the input template on the live run).

## Create the 3 Metrics
From `law-metrics.json`. All grading guidance lives in the **option descriptions** — TryEval's judge sees only metric `name` + each option's `{score, label, description}`, nothing else.
- **Task Completion** — 1–5, pass if `>= 3`
- **Format Adherence** — 0/1, pass if `>= 1`
- **Factuality** — 1–5, pass if `>= 4`

Row passes only if **all selected metrics pass**. Verdict = Task≥3 AND Format≥1 AND Factuality≥4.

## Domain quirk: the repealed-statute guard (GUARD-HEAVY)
This domain is deliberately guard-heavy (75 of 300 gold rows). A query about a repealed provision
(IPC, CrPC, Indian Evidence Act, or the Consumer Protection Act 1986) must be answered by stating
the provision is **repealed** and naming the **replacement statute + section** drawn from the
`LAW_MAPPINGS` chunk (e.g. IPC s.302 → BNS s.103; CrPC s.154 → BNSS s.173; Indian Evidence Act
s.45 → BSA s.39; CP Act 1986 → CP Act 2019). This shapes how Factuality is graded on the guard band:
- **fact 1 (fabrication):** citing the repealed statute AS IF it were current law (e.g. answering with `**(IPC s.302 — Indian Penal Code 1860)**` as the governing authority).
- **fact 3 (drift, boundary-fails):** naming the WRONG replacement section (e.g. IPC 302 → BNS s.101 instead of BNS s.103).
- **pass:** names the repeal and the correct replacement section, cited to the mapping reference (`LAW_MAPPINGS:full`) and the current statute.

Because a correct guard/edge answer legitimately *names* the repealed statute in prose, the builder's
grounding check treats a repealed-statute name as a leak only when it appears in citation form
(`— <statute>)`), not when it is described in prose. Retrieval/refusal pass rows must not name a
repealed statute at all.

## Run each metric as its OWN evaluation (important)
TryEval scores all selected metrics in **one** LLM call → rubric-collapse risk (scores drift into one latent quality dimension). Mitigate: create **3 evaluations**, each selecting **one** metric. Same dataset + endpoint; evaluations are independent.
- Cost: 3 evals ≈ 3× the shared prompt/context/output tokens. On the **live** set that also means 3× endpoint generation — avoid it by running the 3 isolated evals against the **calibration** (direct-eval) set, and reserving the live set for a single combined run if budget matters.

## Format is better code-checked
Format Adherence is regex-detectable (the `**(section_ref — doc_title)**` citation pattern, the exact not-legal-advice footer, and the exact refusal string). The LLM-judge metric is provided, but for a cleaner signal, code-check format offline (`_score_law_judge.py` can be extended) and LLM-judge only Task + Factuality.

## Calibration: score the judge vs gold
1. Run the 3 metrics over `law-tryeval-calibration-dataset.csv` (direct-eval).
2. Export TryEval results (prompt + aiOutput + `metric_{id}_score`).
3. Map the 3 metric ids → `judge_task` / `judge_format` / `judge_factuality`, join to `law-judge-dataset.csv` on **(input, output)** (identical pairs carry identical gold, so the join is unambiguous in effect), then run `python _score_law_judge.py --preds <mapped.csv>`.
4. Watch borderline accuracy + flip-rate. If the judge is noisy on the borderline band (fact 3↔4, task 3), tighten the option descriptions or route those rows to HITL — the calibration set is exactly the fact-3/fact-4 boundary probe (here, the repealed-statute wrong-section rows sit right on that boundary).
