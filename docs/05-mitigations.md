# 5. Mitigations

The lab treats defenses as experiment variables so their effect is measured, not
assumed. A **defense** combines three independent dimensions, each targeting a
different part of the threat model.

## 5.1 The three dimensions

### System-prompt arm (`plain` vs `warn`)

The `warn` arm tells the agent that tool output is untrusted third-party data,
not instructions; that it must never follow instructions found in results or
pages; that it should surface disagreements; and that the session setup code is a
secret it must never transmit.

- Targets: G1 (instruction integrity), G4 (context confidentiality), partly G2.
- Cost: none to utility; it is a prompt.
- Limit: it is itself inside the prompt the untrusted data is competing with, so
  a strong injection can still win. Measured, not assumed.

### Extraction mode (`raw` vs `markdown` vs `reader`)

How much of the page the browsing tool turns into model-visible text:

| Mode | What reaches the model |
| --- | --- |
| `raw` | the HTML as served - comments, metadata, hidden elements, everything |
| `markdown` | visible text, `alt`/`title`/`aria-label` text, link targets |
| `reader` | visible text only |

- Targets: every content-hiding vector (A2). A carrier the extractor drops cannot
  reach the model at all - a structural defense, independent of the model.
- Cost: `reader` can drop legitimately useful hidden text (image descriptions,
  link URLs); `markdown` is a middle ground.
- The hidden-vector survival table in the report quantifies exactly which carrier
  each mode removes.

### Provenance envelope (`off` vs `on`)

When on, every tool result is wrapped with its source (host, how it resolved,
whether TLS was verified) and an explicit marker that the content is untrusted
data, not instructions.

- Targets: G1, G5 - gives the model a clean boundary and the metadata to judge
  authority and detect a hijack.
- Cost: none to utility.
- Limit: like `warn`, it is advisory; its value depends on the model heeding it.

## 5.2 The headline ladder

| Defense | System | Extraction | Provenance | Idea |
| --- | --- | --- | --- | --- |
| `none` | plain | raw | off | worst case / baseline |
| `reader` | plain | reader | off | structural: starve hidden carriers |
| `warn` | warn | raw | off | advisory only |
| `provenance` | plain | raw | on | label the boundary |
| `all` | warn | reader | on | structural + advisory combined |

Comparing `reader` and `warn`/`provenance` separates the **structural** defense
(works regardless of the model, by removing the carrier) from the **advisory**
ones (depend on the model following guidance). In the mock demo only the
structural dimension moves the mechanical controls, which is exactly why the
advisory dimensions must be evaluated with real backends.

## 5.3 Transport: the clearest result

Family F6 shows a defense that does not depend on the model at all. A poisoned
resolver points a trusted name at the attacker; with plain HTTP the swap is
invisible and the attack succeeds, but with **certificate verification** the
hijacked name cannot present a valid certificate, the fetch fails, and the attack
never reaches the agent. An MCP browsing tool should verify TLS and refuse on
failure rather than fall back to plaintext.

## 5.4 Recommendations for MCP browsing tools

From the threat model and the measured effects, a browsing MCP server should:

1. **Return content as data, with provenance.** Wrap results in an envelope that
   names the source and marks the text untrusted; never present page text as if
   it were part of the conversation.
2. **Default to a reader extraction.** Offer richer modes explicitly, but do not
   surface comments, metadata and hidden elements by default - most concealment
   vectors die here.
3. **Verify the transport and the name.** Verify TLS and fail closed; refuse
   hosts outside the expected scope; do not follow redirects to new origins
   silently.
4. **Pin the tool contract.** The tool description is part of the trust surface
   (F7); a client should pin and review it, as the sibling
   [mcp-security-scanner](https://github.com/ConnorDev1337/mcp-security-scanner)
   does, so a server cannot smuggle instructions through its own metadata.
5. **Keep secrets out of reach.** Session material (the canary here) must not be
   placed where a tool result can round-trip it into an outbound request; pair
   with an egress guard such as
   [tool-call-guard](https://github.com/ConnorDev1337/tool-call-guard).

## 5.5 Residual risk

- Advisory defenses (`warn`, `provenance`) can be overcome by a sufficiently
  strong or well-framed injection; they raise the bar, they do not close the gap.
- A visible, on-topic instruction (the `visible_note` vector) survives every
  extraction mode - structural filtering does not help when the payload looks
  like legitimate content.
- Authority and consensus manipulation (F3-F5) target judgement, not parsing; no
  extraction mode addresses them. They need the model to weigh sources and
  surface conflict, which is what the report's per-family ASR measures.
- The lab measures these defenses in isolation and in one combination (`all`);
  real deployments should layer them and verify with their own model and wrapper.
