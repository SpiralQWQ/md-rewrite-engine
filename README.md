# md-rewrite-engine

<p align="center">
  <kbd>English</kbd> · <kbd><a href="README_zh.md">简体中文</a></kbd>
</p>

<p align="center">
  <a href="https://github.com/SpiralQWQ/md-rewrite-engine/releases"><img src="https://img.shields.io/github/v/tag/SpiralQWQ/md-rewrite-engine?label=version" alt="version"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-3776AB" alt="Python 3.10+"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-AGPL%203.0%20%7C%20Commercial-blue" alt="license"></a>
  <a href="https://github.com/SpiralQWQ/md-rewrite-engine/stargazers"><img src="https://img.shields.io/github/stars/SpiralQWQ/md-rewrite-engine?style=social" alt="stars"></a>
</p>

**Cleaned markdown → AI-teachable notes. A human-machine relay pipeline with a fail-closed quality gate.**

`md-rewrite-engine` reshapes "plain cleaned markdown" (transcripts, OCR output, PDF
extraction) into **AI-teachable notes** — structured so an AI can read the note and
teach a total beginner from it. It ships a deterministic verification layer
(mechanical reconciliation / semantic reconciliation / LLM quality check / scoring
gate), rolling compilation that survives long documents, and a fixed teaching
scaffold (OKF-aligned).

## Why

LLM rewrites of study notes drift: they drop concepts, invent terms, and *claim*
quality without evidence. This project makes quality **measurable and enforced**:

- every rewrite passes a **mechanical gate** (numbers reconciled ≥90%, all 6
  teaching sections present, Feynman demo, LLM score threshold) — fail any and the
  block is **rejected**, never "accepted on trust";
- every rejection comes with a **defect list** for a targeted fix (feedback
  accumulates, ≤4 attempts per block, then it suspends for a human);
- the teaching scaffold is **fixed in config** (6-part structure + 4-angle Feynman
  demo), so output shape never depends on the model's mood.

## Features

- **Human-machine relay** — rewrite/reconcile run in conversation (you + your AI
  assistant); scripts expose the machine-runnable parts as a capability library.
  The gate, not goodwill, carries the quality.
- **Per-stage executors** — 4 stages (rewrite / reconcile / quality_check /
  scoring) each bind their own executor: `claude / glm / deepseek / anthropic`.
- **Fail-closed gate** — one-shot check via `scripts/gate_check.py`: mechanical
  reconciliation, 6-part completeness, Feynman demo, scoring. Not passing means
  not passing.
- **Anti-loop** — per-block repair budget (4 attempts) with accumulating feedback;
  exceeded → suspend for human review.
- **Fixed teaching scaffold** — 6 sections (definition / analogy / principle /
  example / why it matters / common pitfalls) + Feynman 4 angles + appendices kept
  out of the teaching context.
- **Long-document discipline** — concept map first; every block carries the global
  map, previous-block summary, next-block preview, and block overlap.

## Quick start

```bash
# 1. install
pip install -r requirements.txt

# 2. configure (copy .env.example to .env, fill your key)
GLM_API_KEY=your-zhipu-key

# 3. rewrite a cleaned markdown
python cli.py input.md --output output.md

# 4. course-level tools
python cli.py --index course_dir            # build index.md
python cli.py --validate-links course_dir   # find dangling [[links]]
python cli.py --concepts course_dir         # build concept pages
python cli.py --search keyword --input course_dir
```

> **Recommended (human-in-the-loop)**: hand the transcript to your AI assistant in
> conversation and follow the 10-step orchestration in
> `docs/orchestration-manual.md`; scripts do the machine work (check / score /
> reconcile / write). See `docs/user-guide.md`.

## Executor configuration

Defaults in `configs/executors.yaml`:

| Stage | Executor | Rationale |
|---|---|---|
| rewrite | claude (in-conversation) | needs full context, richest output |
| reconcile | claude (in-conversation) | needs to *understand* to check coverage |
| quality_check | glm | machine pre-check, human confirms |
| scoring | glm | machine scores, human confirms |

Override per stage via `configs/executors.yaml` or env vars
`MD_REWRITE_PROVIDER_<KEY>` / `MD_REWRITE_MODEL_<KEY>`.

## Architecture

```
cli.py ──→ services ──→ core (pure algorithms)
              │  ├─→ providers (LLM / file / git / executors)
              └──→ configs (spec / prefs / models / executors)
```

- **core/** — pure algorithms, zero external deps (assemble / chunk / rewrite /
  verify / concepts / md_index / search)
- **services/** — orchestration + LLM prompts (orchestrator / llm)
- **providers/** — external adapters (llm_client / file_io / git_io / executors)
- **configs/** — note_style_spec (teaching scaffold) / executors / models / user_prefs

Contract details: `docs/directory-contract.md`.

## Tests

```bash
python -m pytest tests/ -q          # 169 unit tests
python tests/exhaustive/s2_exhaustive.py   # 137 exhaustive cases (fully mocked)
python scripts/gate_check.py note.md --src source.md   # gate check (PASS/FAIL + defect list)
```

## Documentation

| Doc | Content |
|---|---|
| `docs/user-guide.md` | how to run / configure / switch executors / resume across sessions |
| `docs/orchestration-manual.md` | 10-step in-conversation orchestration |
| `docs/capability-functions.md` | capability function catalogue |
| `docs/prompt-family-p1-p5.md` | P1–P5 prompt family |
| `docs/directory-contract.md` | layering contract |
| `docs/` | acceptance reports, plans, benchmarks (see `docs/archive/` for history) |

## Roadmap

See `ROADMAP.md`. Near term: diff-only gate review, executor auto-fallback,
English note scaffold.

## License

[AGPL-3.0](LICENSE) for the open-source version. Commercial licensing available —
see [COMMERCIAL.md](COMMERCIAL.md).

## Support

If this project helps you, feel free to buy me a coffee ☕. Donation is entirely
optional — the project stays free and open source forever.

<p align="center">
  <img src="assets/donate_wechat.jpg" alt="WeChat Pay" width="200">
  <img src="assets/donate_alipay.jpg" alt="Alipay" width="200">
</p>
