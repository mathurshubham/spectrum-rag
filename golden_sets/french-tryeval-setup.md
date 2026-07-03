# French RAG → TryEval setup

Files in this folder:

| File | Role |
| --- | --- |
| `french-tryeval-live-dataset.csv` | **Live run.** 300 questions; TryEval calls the RAG endpoint per row, then the rubrics judge the answer. ~95 (~32%) are hard (refusal/edge/guard) the RAG is likely to fail. |
| `french-tryeval-calibration-dataset.csv` | **Judge calibration (direct-eval).** 300 rows with a *pre-filled* `output` (no endpoint call). Judge scores the fixed answers; compare to the gold labels to trust the judge before believing the live run. |
| `french-judge-dataset.csv` | **Gold side-file** (full labels: 3 scores, verdict, failure_mode, error_span). NOT uploaded — TryEval has no columns for it. Used to score the judge. |
| `french-metrics.json` | The 3 rubric Metrics to create in TryEval. |
| `_build_french_judge.py` | Regenerates all CSVs (`--emit all --verify`, deterministic seed 1234). |
| `_score_french_judge.py` | Scores a judge export vs gold (κ, fail-class P/R, per-rubric threshold-crossing, borderline flip-rate, matched pairs). |

**Language note:** the study bot's default reply mode is `fr` ("Réponds uniquement en français"), so every reference answer, model `output`, and judge rationale in these files is **in French**. Questions (`input`) are a mix of French and English, mirroring `golden_sets/french-dataset.csv`. The two refusal strings and the rubric option descriptions are in **English** exactly as the system prompt / `french-metrics.json` define them — keep them verbatim.

## Column mapping (TryEval canonical headers)
- `input` → prompt / `${PROMPT}` (required)
- `eval_context` → context / `${CONTEXT}` — **the only field the LLM judge sees.** The gold reference answer + expected citations are packed here so Task/Factuality can grade against them.
- `expected_output` → statistical reference only (F1/ROUGE); **never** seen by the LLM judge.
- `output` → aiOutput (direct-eval only; becomes the judge's "Model Output").

**No leak:** the endpoint Input Template is `{"q":"${PROMPT}"}` — it does not reference `${CONTEXT}`, so the reference in `eval_context` reaches the judge but never the model under test. Keep it that way (don't add `${CONTEXT}` to the input template on the live run).

## Create the 3 Metrics
From `french-metrics.json`. All grading guidance lives in the **option descriptions** — TryEval's judge sees only metric `name` + each option's `{score, label, description}`, nothing else.
- **Task Completion** — 1–5, pass if `>= 3`
- **Format Adherence** — 0/1, pass if `>= 1`
- **Factuality** — 1–5, pass if `>= 4`

Row passes only if **all selected metrics pass**. Verdict = Task≥3 AND Format≥1 AND Factuality≥4.

**Miscitation ownership** (stated in the Format & Factuality descriptions): a missing/malformed inline citation pattern is a **Format** failure (fmt=0); the right fact attributed to the **wrong** lesson/section is a **Factuality** failure (fact=3), not Format.

## Run each metric as its OWN evaluation (important)
TryEval scores all selected metrics in **one** LLM call → rubric-collapse risk (scores drift into one latent quality dimension). Mitigate: create **3 evaluations**, each selecting **one** metric. Same dataset + endpoint; evaluations are independent.
- Cost: 3 evals ≈ 3× the shared prompt/context/output tokens. On the **live** set that also means 3× endpoint generation — avoid it by running the 3 isolated evals against the **calibration** (direct-eval) set, and reserving the live set for a single combined run if budget matters.

## Format is better code-checked
Format Adherence is regex-detectable (the `**(short §section — full title)**` citation pattern, the two exact refusal strings). The LLM-judge metric is provided, but for a cleaner signal, code-check format offline (`_score_french_judge.py` can be extended) and LLM-judge only Task + Factuality.

## Calibration: score the judge vs gold
1. Run the 3 metrics over `french-tryeval-calibration-dataset.csv` (direct-eval).
2. Export TryEval results (prompt + aiOutput + `metric_{id}_score`).
3. Map the 3 metric ids → `judge_task` / `judge_format` / `judge_factuality`, join to `french-judge-dataset.csv` on **(input, output)** (identical pairs carry identical gold, so the join is unambiguous in effect), then run `_score_french_judge.py --preds <mapped.csv>`.
4. Watch borderline accuracy + flip-rate. If the judge is noisy on the borderline band (fact 3↔4, task 3), tighten the option descriptions or route those rows to HITL — the calibration set is exactly the fact-3/fact-4 boundary probe.

## Domain quirk (for reviewers)
Unlike insurance (where `guard` = answerable exclusion clauses), the French study bot has no answerable "guard" content: `guard` rows are content-policy / out-of-scope requests (insults, stereotypes, violence, homework) whose **correct** behaviour is to decline. They are therefore treated like `refusal` rows — the correct output is the exact refusal string — and are excluded from the answerable-only bands (bpass/hall_f3/task). There is **no disclaimer footer** in this domain, so `format0` failures have only two variants (stripped inline citation / botched refusal wording).
