# Local Model Comparison: Findings (copy-paste text for slides and report)

## One-line takeaway

On a 6 GB laptop GPU, bigger local models did not produce measurably better documentation, only slower documentation. Qwen2.5-Coder 7B is the best speed/quality trade-off; Qwen3 8B follows the output format most reliably.

## Results table

| Model | Components | Seconds per component | Format warnings | Completeness | Truthfulness | Hallucinated |
|---|---|---|---|---|---|---|
| qwen2.5-coder:7b | 15 | 31 s | 13 | 100% | 60% | 1 / 15 |
| qwen3:8b | 15 | 99 s | 4 | 100% | 57% | 1 / 15 |
| qwen2.5-coder:14b | 15 | 167 s | 9 | 100% | 57% | 2 / 15 |

Per-repository generation time (seconds), for reference:

| Model | Java repo (8 components) | Python repo (7 components) |
|---|---|---|
| qwen2.5-coder:7b | 224 | 248 |
| qwen3:8b | 768 | 722 |
| qwen2.5-coder:14b | 1317 | 1186 |

## Suggested slides

**Slide 1: Experiment setup**
- Goal: pick the best free, locally run model for DocAgent (no paid APIs).
- Models: Qwen2.5-Coder 7B, Qwen3 8B, Qwen2.5-Coder 14B, all run through Ollama.
- Test set: 2 repositories, one Python (pypa/sampleproject) and one Java (Spring gs-rest-service), 15 documented components per model.
- Hardware: laptop with an RTX 3050 (6 GB VRAM), 15 GB RAM.
- Metrics: time per component, format compliance, completeness, truthfulness.

**Slide 2: Speed** (chart `1_speed_per_component.png`)
- The 7B takes 31 s per component, Qwen3 8B takes 99 s, the 14B takes 167 s.
- The 14B is about 5x slower than the 7B.
- Why: the 14B model (9 GB) does not fit in 6 GB of GPU memory, so part of it runs on the CPU.

**Slide 3: Quality** (chart `3_quality.png`)
- Completeness is 100% for every model: each fills all required docstring sections (summary, args, returns, and so on).
- Truthfulness is 60%, 57% and 57%. The gap is one component out of 15, which is within noise.

**Slide 4: Trade-off** (chart `4_speed_vs_truthfulness.png`)
- The fastest model is just as accurate as the slowest.
- Extra compute bought no measurable accuracy.

**Slide 5: Output format reliability** (chart `2_format_warnings.png`)
- Format warning = the model forgot the required `<DOCSTRING>` tags, so the system had to fall back to the raw reply.
- Qwen3 8B: 4 warnings. 14B: 9. 7B: 13.
- Qwen3 is the most reliable at following instructions, but it is 3x slower than the 7B.

**Slide 6: Conclusion and recommendation**
- Default model: Qwen2.5-Coder 7B (fastest, equal measured quality).
- Alternative: Qwen3 8B when format reliability matters more than time.
- Not recommended on this hardware: the 14B (5x slower, no measurable gain).
- Next: improve prompts and post-processing rather than model size, since all three models share the same weaknesses.

## Report paragraph (results)

We compared three locally hosted models (Qwen2.5-Coder 7B, Qwen3 8B and Qwen2.5-Coder 14B) on two repositories, one Python and one Java, totalling 15 documented components per model. All models achieved 100% completeness, meaning every required docstring or Javadoc section was present. Judged truthfulness was 60%, 57% and 57% respectively, a difference of one component. Generation time differed substantially: 31 s, 99 s and 167 s per component. The 14B model, at roughly 9 GB, exceeds the 6 GB of GPU memory available and partially runs on the CPU, which accounts for its slowdown. Qwen3 8B produced the fewest format violations (4, against 13 for the 7B and 9 for the 14B). On this hardware, increasing model size therefore yielded no measurable quality gain at a large cost in time, and the 7B model offers the best trade-off.

## Method (for the report)

- Pipeline: DocAgent's four agents (Reader, Searcher, Writer, Verifier) process components in dependency order. Only the model changes between runs; prompts, settings and test repositories are identical.
- Completeness: for Python, the project's completeness evaluator (presence of summary, description, arguments, returns, and similar sections). For Java, the share of required `@param` and `@return` tags present, plus presence of the Javadoc itself.
- Truthfulness: a separate language model (llama3.2, 3B) judges each generated docstring against its code and returns TRUTHFUL, PARTIALLY_TRUTHFUL or HALLUCINATED. Score = (TRUTHFUL + 0.5 x PARTIALLY_TRUTHFUL) / components judged.
- Format warnings: count of model replies missing the required `<DOCSTRING>` tags.
- Time: wall-clock generation time divided by components documented, with one model loaded at a time.
- Reproduce: `python compare_models.py` (raw outputs and per-component verdicts are stored in `eval_results/`).

## Limitations (state these; they make the report more credible)

1. Small sample: 15 components per model across 2 small repositories. Differences of a few points are not statistically meaningful.
2. Weak judge: truthfulness was scored by a 3B model. We saw it contradict itself (for example HALLUCINATED with "no issues" listed) and flag code it was not shown the imports for. Treat truthfulness as a rough signal, not ground truth.
3. Completeness is at its ceiling (100%) for all models, so it cannot separate them.
4. Single run per model, no repeats, so run-to-run variation is unmeasured.
5. Timing reflects this specific laptop. On a GPU with more memory the 14B would be much faster and the speed gap would shrink.
6. Possible follow-up: a stronger judge (for example Phi-4 14B), more repositories, and a manual blinded review of a sample of outputs.

## Speaker notes: likely questions

- *Why not use the paid APIs?* Cost; the project is meant to run free and offline.
- *Why is the 14B so slow?* It needs about 9 GB, the GPU has 6 GB, so roughly half runs on the CPU.
- *Is the 7B really as good?* On our metrics, yes; but the sample is small and the judge is weak, so we claim "no measurable difference", not "identical".
- *What would improve quality?* Better prompts and a verifier that rejects unsupported claims (for example invented exceptions), not a bigger model.
