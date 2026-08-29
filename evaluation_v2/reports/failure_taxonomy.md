# Failure Taxonomy

> **SYNTHETIC / FOR EVALUATION ONLY**

Automated reports may identify observable rank changes, missing locators, or document/version mismatches. They must not assert an uncertain root cause as fact.

| Label | Observable evidence required | Automatic conclusion allowed? |
|---|---|---|
| `semantic_mismatch` | Relevant locator absent while lexical overlap is low | No; manual review |
| `keyword_mismatch` | Relevant locator absent and query/source use materially different terms | No; manual review |
| `wrong_document` | Retrieved document is outside relevant documents | Yes, as retrieval observation |
| `wrong_version` | Same product, wrong version outranks expected version | Yes, as retrieval observation |
| `parent_context_missing` | Parent-context case misses child locator and parent path is absent from indexed representation | No; manual review |
| `rerank_regression` | Relevant locator is pre-rerank Top-K but not post-rerank Top-K | Yes |
| `hyde_drift` | HyDE text introduces unsupported specifics and changes ranks adversely | No; manual review |
| `table_parse_failure` | Source table locator cannot be found in ingested chunks | Yes for locator loss; cause needs review |
| `multi_document_incomplete` | Only a subset of required locators/documents is retrieved | Yes |
| `no_answer_false_positive` | System answers a negative query without evidence | Not available until an evidence gate/answer evaluator exists |

Unknown cases must set `needs_manual_review=true`.

