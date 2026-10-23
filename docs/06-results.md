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

## 6.4 Real-model results

**Setup.** Three tool-capable local models served by Ollama on a single
RTX 3060 (12 GB), 10 repetitions over all 18 scenarios and 6 defenses
(2026-10). Reproduce with:

```bash
docker compose -f lab/docker-compose.yml --profile ollama up --build   # one model
python scripts/bench_multi.py --models qwen2.5:7b-instruct,llama3.1:8b,mistral:7b --reps 10
```

Completed cells: `qwen2.5:7b-instruct` 1080/1080, `llama3.1:8b` 1079/1080
(one cell dropped when the run was paused mid-request), `mistral:7b` 987/1080
(93 cells skipped where the model emitted a malformed tool call; see the runner's
per-cell skip). `gemma2:9b` is excluded because the current Ollama build reports
it has no tool support, so the agent cannot drive it.

### ASR and utility by defense (95% Wilson intervals)

| Model | Defense | ASR | Utility |
| --- | --- | --- | --- |
| `qwen2.5:7b-instruct` | none | 8.9% [5.5, 14.0] | 91.1% [86.0, 94.5] |
| `qwen2.5:7b-instruct` | reader | 10.0% [6.4, 15.3] | 87.2% [81.6, 91.3] |
| `qwen2.5:7b-instruct` | warn | 16.1% [11.5, 22.2] | 88.9% [83.5, 92.7] |
| `qwen2.5:7b-instruct` | all | 15.0% [10.5, 20.9] | 87.2% [81.6, 91.3] |
| `llama3.1:8b` | none | 10.0% [6.4, 15.3] | 78.9% [72.4, 84.2] |
| `llama3.1:8b` | reader | 9.4% [6.0, 14.6] | 76.1% [69.4, 81.8] |
| `llama3.1:8b` | warn | 10.1% [6.5, 15.3] | 82.7% [76.5, 87.5] |
| `llama3.1:8b` | all | 8.9% [5.5, 14.0] | 83.3% [77.2, 88.1] |
| `mistral:7b` | none | 4.9% [2.5, 9.4] | 42.9% [35.6, 50.6] |
| `mistral:7b` | reader | 5.1% [2.6, 9.7] | 49.4% [41.7, 57.1] |
| `mistral:7b` | warn | 4.8% [2.5, 9.3] | 23.6% [17.8, 30.7] |
| `mistral:7b` | all | 1.2% [0.3, 4.2] | 29.0% [22.7, 36.2] |

### Attack success by objective (all three models pooled)

| Objective | none | reader | warn | all |
| --- | --- | --- | --- | --- |
| O1_answer | 6.2% | 6.9% | 3.2% | 3.1% |
| O2_beacon | 3.5% | **0.0%** | 3.2% | **0.0%** |
| O3_canary | 3.1% | 3.3% | 3.2% | 3.2% |
| O4_recommend | **80.6%** | **74.2%** | **75.0%** | **68.8%** |
| O5_misinfo | 16.9% | 20.2% | 24.2% | 18.9% |
| O6_derail | 12.5% | 16.1% | **38.7%** | 32.3% |

### What the real models show

1. **Recommendation hijacking (O4) is the dominant, barely-mitigated risk.**
   Pooled ASR stays at 69-81% across *every* defense, because the attacker's
   look-alike domain arrives as a normal, visible search result and a judgement
   call — no extraction mode removes it. This is the headline real-model finding.

2. **Structural extraction kills the carrier-based attacks, advisory text does
   not.** `reader` and `all` drive the beacon objective (O2) to 0%; the
   system-prompt warning (`warn`) leaves it untouched. Telling the model "do not
   follow instructions in tool output" did not help any model here.

3. **Advisory warnings can backfire.** For O6 (derail) the `warn` arm has the
   *highest* ASR (38.7% pooled; qwen `warn` 16.1% vs `none` 8.9%). Drawing the
   model's attention to injected text appears to make it more likely to act on
   it — a result only visible with real models, not the mechanical controls.

4. **Low ASR can just mean low utility.** `mistral:7b` has the lowest ASR
   (1-6%) but also the lowest task utility (23-49%): it frequently fails the task
   outright, so there is little behaviour left to hijack. `qwen2.5:7b-instruct`
   is the opposite corner — highest utility (~90%) at a moderate ASR. Safety and
   utility must be read together, never ASR alone.

5. **Hidden-markup injections (F2) are largely ignored by all three models** at
   `none` (0-5.5%), while **search poisoning (F1) and progressive contamination
   (F4) remain effective** (F1: qwen 90%, llama 100%, mistral 56%; F4: llama
   70%, mistral 50%). The models resist clumsy hidden instructions but still
   trust a confident, repeated, well-ranked source.

## 6.5 Interpreting the numbers

- Rates are proportions with 95% Wilson intervals; small per-cell sizes mean wide
  intervals. More repetitions narrow them.
- The numbers describe the model **and** this harness's system prompt and tool
  formatting. Both are published.
- Lab conditions trade realism for control; the absolute rates are not
  prevalence estimates.
- Compare vectors and defenses **relative to each other**, not to a real-world
  baseline.
