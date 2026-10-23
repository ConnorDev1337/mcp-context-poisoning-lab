# 6. Results

> **Status**: baseline validated with deterministic controls. The tables below
> show mock-control output (which validates the instrument) and placeholders for
> real-model results. Replace placeholders by running `mcplab run` with a real
> backend.

## 6.1 Baseline: deterministic controls

The **naive** agent obeys every injection (positive control); the **careful**
agent ignores them all (negative control). These bound the instrument:

| Model | Defense | ASR | Utility |
| --- | --- | --- | --- |
| naive | none | **94.4%** [74.2, 99.0] | 77.8% [54.8, 91.0] |
| naive | markdown | **61.1%** [38.6, 79.7] | 77.8% [54.8, 91.0] |
| naive | reader | **38.9%** [20.3, 61.4] | 77.8% [54.8, 91.0] |
| naive | warn | **94.4%** [74.2, 99.0] | 77.8% [54.8, 91.0] |
| naive | provenance | **94.4%** [74.2, 99.0] | 77.8% [54.8, 91.0] |
| naive | all | **38.9%** [20.3, 61.4] | 77.8% [54.8, 91.0] |
| careful | any | **0.0%** [0.0, 17.6] | 100.0% [82.4, 100.0] |

Key observations from the baseline:

1. **`reader` extraction is the strongest structural defense.** It drops ASR from
   94.4% to 38.9% for the naive agent. The residual 38.9% comes from
   `visible_note`, `white_text` and `tool_description` - vectors that survive
   text extraction because they are normal text nodes or metadata.

2. **Advisory defenses alone do nothing for the mechanical control.** `warn` and
   `provenance` leave the naive agent's ASR unchanged at 94.4%. This is by
   design: the naive agent does not reason, so a prompt warning cannot help. The
   advisory defenses must be evaluated with real models.

3. **`tool_description` survives every defense.** It is not in the page; it is in
   the tool contract the agent sees before any request. No extraction mode can
   filter it. Only tool-description pinning or review addresses F7.

4. **TLS verification is a perfect structural defense for F6.** The DNS-hijacked
   fetch fails before the payload is read, making it the only scenario where even
   the naive agent is not compromised.

## 6.2 Hidden-vector survival table

Which injection vectors reach the model under each extraction mode (positive
control, `defense=none`):

| Vector | `raw` | `markdown` | `reader` | Survives rendering? |
| --- | --- | --- | --- | --- |
| `html_comment` | ✅ 100% | ❌ 0% | ❌ 0% | No |
| `css_hidden` | ✅ 100% | ✅ 100% | ❌ 0% | Markdown only |
| `alt_text` | ✅ 100% | ✅ 100% | ❌ 0% | Markdown only |
| `title_attr` | ✅ 100% | ✅ 100% | ❌ 0% | Markdown only |
| `aria_label` | ✅ 100% | ✅ 100% | ❌ 0% | Markdown only |
| `meta_tag` | ✅ 100% | ❌ 0% | ❌ 0% | No |
| `data_attr` | ✅ 100% | ❌ 0% | ❌ 0% | No |
| `noscript` | ✅ 100% | ❌ 0% | ❌ 0% | No |
| `svg_title` | ✅ 100% | ❌ 0% | ❌ 0% | No |
| `white_text` | ✅ 100% | ✅ 100% | ✅ 100% | **Yes** |
| `visible_note` | ✅ 100% | ✅ 100% | ✅ 100% | **Yes** |
| `tool_description` | ✅ 100% | ✅ 100% | ✅ 100% | **Yes** (not in page) |

Four classes emerge:

- **Killed by markdown**: HTML comments, `<meta>`, `<noscript>`, `<svg>`,
  `data-*` (5 vectors). Even an intermediate extraction drops them.
- **Killed by reader**: `css_hidden`, `alt_text`, `title_attr`, `aria_label`
  (4 vectors). These survive markdown but not reader extraction.
- **Survives reader, in the page**: `white_text` and `visible_note`. These are
  normal text nodes; only content-level reasoning can resist them.
- **Survives everything**: `tool_description`. It never passes through page
  extraction at all.

## 6.3 ASR by attack family (`defense=none`)

| Family | Naive | Careful | Threat |
| --- | --- | --- | --- |
| F1 | 100% | 0% | Search poisoning |
| F2 | 100% | 0% | Indirect prompt injection |
| F3 | 100% | 0% | Source authority manipulation |
| F4 | 100% | 0% | Progressive contamination |
| F5 | 100% | 0% | Contradictory sources |
| F6 | 50%  | 0% | DNS manipulation (50% because TLS-verify blocks one variant) |
| F7 | 100% | 0% | Malicious MCP server |

## 6.4 Real-model results (placeholder)

> Run against your own models with:
> ```bash
> mcplab run --backend ollama --model <model> --reps 10 --out runs/raw.jsonl
> mcplab report --in runs/raw.jsonl --out-dir runs
> ```

### Template for each model

| Model | Defense=none ASR | Defense=all ASR | Utility (none) | Utility (all) | Notes |
| --- | --- | --- | --- | --- | --- |
| `qwen2.5:7b-instruct` | — | — | — | — | |
| `llama3.1:8b-instruct` | — | — | — | — | |
| `mistral:7b-instruct` | — | — | — | — | |
| `gemma2:9b-it` | — | — | — | — | |
| `phi-3:mini` | — | — | — | — | |

### Key questions to answer with real models

1. **Which model resists injections best under `defense=none`?** (raw ability)
2. **How much does `warn` help vs `reader`?** (advisory vs structural)
3. **Does `provenance` help any model reject fake authority?** (F3 and F4)
4. **Which model surfaces contradictions?** (F5)
5. **Which model exfiltrates the canary?** (F7 O3)
6. **Does any model resist the visible-note framing?** (the hardest carrier)

## 6.5 Interpreting the numbers

- Rates are proportions with 95% Wilson intervals; small per-cell sizes mean wide
  intervals. More repetitions narrow them.
- The numbers describe the model **and** this harness's system prompt and tool
  formatting. Both are published.
- Lab conditions trade realism for control; the absolute rates are not
  prevalence estimates.
- Compare vectors and defenses **relative to each other**, not to a real-world
  baseline.
