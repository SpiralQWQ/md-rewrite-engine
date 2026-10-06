# Roadmap

Ideas and direction for `md-rewrite-engine`. Nothing here is committed — priorities
shift with real usage. Feel free to open an issue to push something up the list.

## Near term

- **Diff-only gate review** — send the LLM gate only the changed blocks instead of
  the full file: cheaper, faster, fewer truncated-context misjudgements.
- **Executor auto-fallback** — when a configured executor errors or times out,
  fall back down the chain (`executors.yaml`) instead of failing the block.
- **English note scaffold** — a second `note_style_spec` variant so the six-part
  teaching structure works for English-language source material.

## Mid term

- **Gate-as-CI** — run `gate_check.py` on every commit of a notes repository
  (GitHub Actions example included in docs).
- **Cross-note reconciliation** — reuse the concept map to detect contradictions
  between notes in the same course.
- **Cost report** — per-stage token accounting so operators can see what the
  human-machine split actually costs.

## Exploring

- Streaming rewrite for very long transcripts (block-level results as they land).
- Alternative teaching scaffolds (pluggable instead of the fixed OKF six-part).
