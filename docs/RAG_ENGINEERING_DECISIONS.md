# RAG Engineering Decision Record

Use one entry per retrieval or generation change. Do not backfill unmeasured results.

## Decision: <short name>

- Date:
- Status: proposed / accepted / rejected / reverted
- Dataset version and SHA-256:
- Code commit:
- Problem:
- Evidence:
- Hypothesis:
- Change:
- Metric Before:
- Metric After:
- Latency Before:
- Latency After:
- Trade-off:
- Final Decision:
- Artifact links:

## Phase 2 measured decisions (Evaluation V2)

Dataset SHA-256: `6c99b11ffaa35142bc6dd3f7fd483a04fe090cfbb3210772f0db8b5cd5cd7634`  
Corpus manifest SHA-256: `0086b5357ff0c88cc0a5a78b660f8656d2b8814a133303a24dc4f08109ec682d`  
Code commit recorded at experiment start: `d7a66502d980ded067b95b8572676f4961c3aa3b`

### Hybrid retrieval — KEEP

- Problem: determine whether dense+sparse fusion contributes beyond either branch.
- Evidence: Hybrid had the best Recall@1 (0.6537) and MRR@5 (0.8167), but Recall@5 (0.8796) tied Dense and trailed Sparse (0.8833).
- Experiment: Dense only vs Sparse only vs current 0.8/0.2 Hybrid, same collection and Top-5.
- Measured Result: benefit is mainly early ranking, not comprehensive tail recall; category winners differ.
- Trade-off: negligible observed latency difference at this corpus size, with extra conceptual complexity.
- Final Decision: KEEP, but do not claim it dominates every category or metric.

### Parent heading enrichment — NEEDS_MORE_EVIDENCE

- Problem: verify the legacy claim that parent headings improve retrieval.
- Evidence: ON and OFF produced identical overall and per-category metrics, including Parent Context Recall@5=1.0.
- Experiment: isolated OFF collection with identical 39 chunk boundaries/content/locators and BGE-M3; only embedding input omitted parent heading.
- Measured Result: no measurable retrieval benefit on Frozen Evaluation V2.
- Trade-off: small ingestion complexity; no measured query-time cost.
- Final Decision: NEEDS_MORE_EVIDENCE. Do not repeat the legacy improvement claim for V2.

### HyDE — OPTIONAL

- Problem: test whether HyDE+RRF justifies generation latency and unsupported assertions.
- Evidence: ordinary Hybrid to Hybrid+HyDE+RRF changed Recall@5 0.8796→0.9019 and MRR@5 0.8167→0.8269; 4/90 queries improved, 0 degraded, 86 unchanged. Twenty of twenty no-answer prompts received corpus-unsupported assertive HyDE text.
- Experiment: identical ordinary candidates, with HyDE branch/RRF toggled by selecting recorded stages.
- Measured Result: P50 rose 129.9→2011.9 ms; P95 175.2→2762.7 ms.
- Trade-off: modest retrieval gain, roughly 1.88 s P50 added, and clear grounding risk.
- Final Decision: OPTIONAL, not default-required without a latency/grounding policy.

### Rerank — REMOVE

- Problem: verify whether current `gte-rerank-v2` improves ranking over RRF.
- Evidence: RRF vs rerank-no-cutoff changed Recall@1 0.6537→0.6444, Recall@5 stayed 0.9019, MRR@5 0.8269→0.8148. Rank improved in 7 cases and degraded in 11.
- Experiment: identical RRF candidate sets; only reranking toggled.
- Measured Result: P50 rose about 2011.9→2623.0 ms; P95 2762.7→3587.4 ms.
- Trade-off: added remote-service latency and worse aggregate early ranking.
- Final Decision: REMOVE from the recommended configuration; production remains unchanged.

### Cliff cutoff — REMOVE

- Problem: determine whether score-cliff truncation removes useful evidence.
- Evidence: cutoff removed 105 returned chunks across 110 queries and removed relevant locator `A100V2-PAIR` for `v2q030`.
- Experiment: same post-rerank Top-5 with cutoff ON/OFF.
- Measured Result: Recall@5 0.9019→0.8907 and MRR@5 0.8148→0.8120 when enabled; latency difference was negligible.
- Trade-off: shorter contexts, but no relevance/answer metric exists here to prove that removed chunks were beneficially irrelevant.
- Final Decision: REMOVE from the recommended configuration; production remains unchanged.

## Phase 3 targeted reliability decisions

### Candidate budget 10 without optional stages — PROMOTED TO DEFAULT

- Problem: obtain a simpler default while preserving retrieval quality.
- Evidence: complete 110-query run, no DashScope dependency.
- Experiment: BGE-M3 Hybrid 0.8/0.2, retrieve 10, evaluate final Top-5; HyDE/rerank/cutoff OFF.
- Result: R@1 .6481, R@3 .8574, R@5 .8944, MRR@5 .8204; Multi-document R@5 .80.
- Latency: P50 80.9 ms, P95 213.9 ms versus original 2623.1/3587.5 ms.
- Trade-off: much lower latency; R@3 fell .0167 while R@5 rose only .0037. Three multi-document locators remain outside Top10.
- Final Decision: PROMOTE retrieval configuration to the production default. Evidence Gate remains a separate rejected experiment and is not required for this retrieval promotion.

## Final production acceptance

- Production graph: history-aware prepare/rewrite → BGE-M3 Hybrid 0.8/0.2 → Candidate10 → Top5 → answer.
- Optional stages disabled by default: HyDE, custom RRF, `gte-rerank-v2`, cliff cutoff.
- Frozen production-node regression: R@1 .6481, R@3 .8574, R@5 .8944, MRR@5 .8204; 110/110 samples, 0 errors.
- Local wall-clock observation: P50 85.8 ms, P95 149.0 ms. This is not a production SLA.
- Trade-off retained: Recall@3 declined from .8741 to .8574 relative to the original full pipeline.

### Evidence Gate v1 — NEEDS_MORE_EVIDENCE

- Problem: distinguish evidence insufficiency from successful retrieval and prevent forced answers.
- Evidence: Frozen no-answer queries always return plausible candidates; scores are not probabilities.
- Experiment: separate 40-query Development Calibration Set (20/20), simple Hybrid Top1 threshold .75; threshold locked before one Frozen evaluation.
- Result: calibration precision .80, answerable recall .80, false accept 4, false reject 4. Frozen: rejection .55, false accept 9, false reject 15.
- Latency: local rule evaluation is negligible; retrieval remains 80.9/213.9 ms P50/P95.
- Trade-off: deterministic grounded refusal behavior, but unacceptable overlap and 16.7% Frozen answerable false rejection.
- Final Decision: NEEDS_MORE_EVIDENCE; do not promote to production or tune again on Frozen Test.

### Multi-document diversity — DO NOT ADD

- Problem: remaining incomplete multi-document evidence.
- Evidence: for v2q071, v2q073, and v2q076 the missing relevant locator is absent from Top10, not merely displaced by same-document duplicates.
- Experiment: inspect all relevant locators and document composition through Top10.
- Result: Candidate10 improves category R@5 .75→.80, but diversity over the existing pool cannot recover absent evidence.
- Latency: no extra runtime measured because no unsupported diversity algorithm was added.
- Trade-off: avoids complexity that does not address the observed failure stage.
- Final Decision: DO NOT ADD MMR/diversity in this phase.

### Markdown table normalization — REMOVE / NO EFFECT

- Problem: three bandwidth-table queries miss `DEPLOY-BANDWIDTH` before Top5 and Top10.
- Evidence: raw Markdown encodes model/mode/value through row-column intersections; Dense, Sparse, Hybrid and HyDE all miss it.
- Experiment: generic header:value serialization added only to embedding input for all Markdown tables; original stored context unchanged; full Frozen rerun.
- Result: overall and Table metrics were exactly unchanged (Table R@5 .625).
- Latency: P50 106.5 ms vs 80.9 ms across separate runs; not interpreted as causal.
- Trade-off: added ingestion complexity without measured benefit.
- Final Decision: REMOVE; retain original table content and investigate representation only with new development evidence.

## Final V3 promotion decisions

The Phase 2 entries above are retained as historical evidence. The following decisions use the final V3 production-compatible runs and supersede earlier wording where results differ. Production default did not change.

### Real `gte-rerank-v2` — KEEP_OPTIONAL / REJECT_DEFAULT

- Experiment: Weighted Hybrid Candidate10 -> real reranker -> Fixed Top5, all 110 Frozen queries.
- Result: R@1 `.6481→.6667`, R@3 `.8574→.8630`, R@5 `.8944→.9056`, MRR@5 unchanged at `.8204`; 8 improved, 9 degraded, 73 unchanged answerable queries.
- Latency: total retrieval/context P50/P95 `706.52/883.40 ms`; paired total-latency overhead proxy P50/P95 `603/765 ms` (not separately instrumented rerank-stage latency).
- Failure: `v2q030` relevant evidence moved from rank 2 to outside Top5.
- Final Decision: KEEP_OPTIONAL, REJECT_DEFAULT. Small recall gains do not offset inconsistent ranking and remote latency.

### Targeted HyDE — KEEP_OPTIONAL / REJECT_DEFAULT

- Experiment: 18 paraphrase/colloquial answerable queries plus all 20 Frozen no-answer queries, with saved real qwen-flash hypotheses.
- Result on answerable subset: R@1 `.5000→.5556`, R@3/R@5 unchanged at `.8333`, MRR `.6574→.6852`; 2 improved, 1 degraded, 15 unchanged.
- Latency: HyDE generation P50/P95 `1305.94/1661.57 ms`.
- Failure: manual review found unsupported concrete assertions in 20/20 no-answer hypotheses. This is hypothesis drift, not final-answer hallucination.
- Final Decision: KEEP_OPTIONAL for controlled experiments, REJECT_DEFAULT.

### Explicit RRF — KEEP_OPTIONAL / REJECT_DEFAULT

- Result: R@1 `.6481→.6389`, R@3 `.8574→.8611`, R@5 `.8944→.9056`, MRR `.8204→.8065`; local P50/P95 `384.20/530.46 ms`.
- Final Decision: KEEP_OPTIONAL, REJECT_DEFAULT because tail recall gain accompanied early-rank regression and latency.

### Dynamic Selector — KEEP_OPTIONAL / REJECT_DEFAULT

- Result: identical retrieval metrics, average context count and average context tokens to Fixed under locked parameters.
- Final Decision: KEEP_OPTIONAL, REJECT_DEFAULT; it did not demonstrate the required context reduction.

### Generation evaluation — DIAGNOSTIC ONLY

- Experiment: real qwen-flash generation for 110/110 Frozen queries using production-default retrieval contexts.
- Diagnostic/reference-based proxies on answerable queries: correctness `.7333`, faithfulness `.5477`, source/citation coverage `.9111`, context relevance `.2300`; LLM P50/P95 `933.45/2315.85 ms`.
- No-answer: 14 supported refusals, 5 unsupported factual claims, 1 needs review.
- Manual review: proxy/semantic disagreements and fabricated image URLs were observed; source coverage is not claim-level citation entailment.
- Final Decision: retain metrics for failure analysis only. Do not call them human accuracy, semantic accuracy, ground-truth accuracy, or proof that hallucination is solved.

### Final production default — FREEZE

- Pipeline: history-based rewrite -> BGE-M3 Weighted Hybrid `.8/.2` -> Candidate10 -> Fixed Top5 -> qwen-flash -> sources/SSE/Mongo.
- Fresh regression: R@1 `.6481`, R@3 `.8574`, R@5 `.8944`, MRR@5 `.8204`; local P50/P95 `75.89/120.85 ms`.
- Final Decision: FREEZE without promoting RRF, rerank, HyDE, Dynamic Selector, or Evidence Gate V1.
