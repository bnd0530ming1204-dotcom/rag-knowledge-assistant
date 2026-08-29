# Evaluation V2 Pre-Freeze Review Log

> **SYNTHETIC / FOR EVALUATION ONLY**

Review date: 2026-08-29  
Review basis: source Markdown and Ground Truth only; no Retriever, Reranker, HyDE output, or metric was consulted.

## Parent Context review

All 12 `parent_context` cases were checked against their source heading path and nearby same-named or semantically similar sections. Each case depends on document/section scope to distinguish the intended meaning (for example, device-side pairing versus portal login lock, or an error-code subsection under a particular product/update chapter). No query text or locator was changed.

## No-answer corpus-wide review

All 22 draft negative cases were checked against all ten documents. Two objective labeling errors were found:

1. `v2q099` — “A200 能否连接 8 个 M20 阵列？” The A200 audio section explicitly states a maximum of four arrays, so the corpus directly supports “不能”. Changed from `no_answer` to `exact_fact`; added `EVAL-A200` / `A200-AUDIO` evidence.
2. `v2q105` — “本地 USB 录制一定符合 AES-256 吗？” The security policy explicitly states that local USB encryption depends on the USB device and ordinary drives are not automatically encrypted. Changed from `no_answer` to `exact_fact`; added `EVAL-SECURITY` / `SEC-ENCRYPT` evidence.

The remaining 20 negative cases lack corpus evidence for the requested fact, policy, price, deadline, model, specific root cause, or guarantee. They remain `answerable=false` with no relevant locator.

## Version consistency review

All 12 `version_confusion` cases were checked. `expected_version` values match the referenced source versions. Cases spanning multiple versions use pipe-separated version sets. No correction was required.

## Multi-document necessity review

All 10 `multi_document` cases contain at least two source locators from at least two distinct documents. Each reference answer has separate claims supported by those sources; removing either source would make the reference answer incomplete. No correction was required.

## Coverage decision

Six unqueried locators remain intentionally as corpus distractors / unqueried knowledge. No low-value questions were added to force 100% locator coverage.

## Performance independence

Both corrections above are objective answerability errors discovered from source evidence before baseline execution. Neither correction was motivated by retrieval difficulty or metric performance.

