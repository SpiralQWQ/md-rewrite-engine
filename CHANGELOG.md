# Changelog

<p align="center"><kbd>🇺🇸 English</kbd> · <kbd><a href="CHANGELOG_zh.md">简体中文</a></kbd></p>

All notable changes to this project are documented here, following
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/).

## [0.4.3] - 2026-08-23

### Fixed

- **gate_check mechanical reconciliation false-positives on filename metadata**:
  source clean.md titles containing dates / video IDs (e.g. `2026-06-30`,
  19-digit Douyin IDs) were treated as "hard numbers that must survive", so their
  removal during rewrite triggered false FAILs (measured: 20% false FAILs on a
  real album sample). Fix: `core/verify.py` `extract_keypoints` now skips pure
  numbers ≥10 digits (IDs/hashes); `scripts/gate_check.py` strips dates
  (`YYYY-MM-DD`) via `_clean_meta`. Real album sample: 20% → **PASS**. Tests +2
  (long-ID skip / date stripping).

## [0.4.2] - 2026-08-20

### Changed

- **Internal-consistency overhaul (root-fixing "updated the new, kept the old")**:
  - `configs/note_style_spec.yaml`: dropped `traceability: per_claim` (conflicted
    with the knowledge-base + whitespace policy) → optional; removed dead
    traceability code in `services/llm.py`.
  - `configs/user_prefs.yaml`: Feynman density moved to
    `feynman_density.general: 2` (demo angles; removed stale 10/8/6 question
    counts); `scripts/gate_check.py` reads the minimum via `_feynman_min()`
    (no more hardcoded `_FEYNMAN_MIN=2`).
  - `docs/orchestration-manual.md`: step 10 finalised — "source data lives
    outside the note; the workflow input is the full cleaned source text".
  - `configs/executors.yaml`: anthropic marked as reserved/unverified fallback.

### Fixed

- **4 internal inconsistencies**: ① traceability vs whitespace conflict ② dead
  density tiers (10/8/6 unused) ③ unclear source-externalisation target ④
  unverified anthropic script path now labelled.
- **gate_check Feynman double-count bug**: `_FEYNMAN_MARK` matched both circled
  digits and "（restated/analogy…）" markers, so one "①（restated）" counted twice
  — inflating the per-point "≥2" into "≥4" and masking config changes. Now counts
  circled digits only.

### Security

- Maintained: API keys via env vars; no new dependencies.

## [0.4.1] - 2026-08-19

### Added

- **Reject-loop landed (human-in-the-loop)**: `scripts/gate_check.py` — one-shot
  gate check (note.md + source.md; auto-extracts 🎤 voice blocks as the
  reconciliation baseline; reports mechanical number coverage / 6-part
  completeness / Feynman demo counts / optional `--score` LLM scoring; PASS/FAIL
  + defect list; exit code 0/1).
- **Orchestration manual now enforces the loop**: steps 7–8 of
  `docs/orchestration-manual.md` changed to "rewrite → run gate_check → targeted
  repair from the defect list → re-verify ≤4 times → suspend"; passing means
  gate_check is green, not "feels right".
- P1 gains "self-check the 6 parts before delivering each knowledge point"; P4
  quality check now reports only in-source issues (no out-of-source suggestions).
- Tests: `tests/scripts/test_gate_check.py` 12 cases + 8 S2 exhaustive cases
  (paths / boundaries / endpoint consistency).

### Changed

- `docs/orchestration-manual.md` steps 7–8 (reject loop: from "self-discipline"
  to "machine gate").
- `services/llm.py` P4 de-noising (in-source issues only).

### Fixed

- **Reject loop had never actually run**: designed in v0.3.0 stage 5 but never
  executed on the human-in-the-loop path — now enforced via gate_check + mandated
  steps; real-world v4 sample FAIL→PASS.

### Security

- Maintained: API keys via env vars; no new dependencies.

## [0.4.0] - 2026-08-18

### Added

- **In-note TOC**: `core/toc.py` (pure algorithm; generates `## 📑 Table of
  Contents` from heading structure; idempotent; zero deps; skips the doc title);
  `services/orchestrator.py` `write_output` auto-inserts before writing;
  `configs/note_style_spec.yaml` gains a `toc` entry; standalone
  `scripts/toc_gen.py` for batch use.
- **Two-level navigation complete**: course-level `index.md` (D1) + in-note TOC —
  an AI never gets lost whether it starts at the course or a single note.
- 11 new TOC tests; totals **145/145** unit + **115/115** S2 exhaustive.
- **Rewrite output standard (knowledge base + teaching whitespace, new
  positioning)**: Feynman changed from "10 per point" to "2–4 demo angles";
  P1/P2 repositioned as "knowledge-complete + teaching whitespace" — 6 parts
  always present, Feynman gives 2–4 demonstration threads per point, timestamps
  no longer mandatory in citations; verbatim proof-reading folded into the P2
  self-check step 1 (scribe view over commands / proper nouns / numbers /
  typos).
- **Mechanical reconciliation repositioned (patch)**: `extract_keypoints` focuses
  on factual keypoints (Chinese extraction dropped — Chinese concepts belong to
  semantic reconciliation; numbers ≥2 significant digits filter ASR noise);
  `reconcile` hard-judges numbers (incl. merged matching `300 0`→`3000`) while
  missing English degrades to **warnings** → gate pass-rate on ASR/rewrite
  material up from an 11.9% deadlock to 93.8%.
- **P4/P5 aligned to knowledge+whitespace (patch)**: quality dimensions now
  knowledge-complete / factually accurate / teaching threads / locatable
  structure; scoring bands 90+ / 70–89 / <70.
- **Rewrite cleans as it goes (patch)**: P1 + rewrite prompt add "clean along the
  way" — fix ASR mis-hearings by context (mic→Mac, split digits 300 0→3000),
  no dictionary needed.

### Changed

- `write_output` auto-inserts the in-note TOC (idempotent).
- `note_style_spec.yaml` `feynman_per_kp` 10 → 2–4; citation rule D4 softened to
  "concrete accurate examples, timestamps optional".
- `docs/directory-contract.md` → v2.1 (core gains toc.py).

### Security

- Maintained: API keys via env vars; model names/paths from configs; only
  `.env.example` committed.

## [0.3.0] - 2026-08-16

### Added

- **Executor selector (stage 1)**: `configs/executors.yaml` +
  `providers/executors.py` — 4 stages independently bind executors (claude
  in-conversation / glm / deepseek / anthropic), mixable; resolution chain env
  var > executors.yaml > models.yaml > built-in default.
- **Capability function library (stage 2)**: `services/orchestrator.py` gains
  `assemble_chunks` / `concept_map` / `chunks_with_context` / `write_output`;
  `docs/capability-functions.md` + `docs/orchestration-manual.md` (10 steps).
- **Human-led global context (stage 3)**: concept map first; per-block global
  map / previous summary / next preview / block overlap.
- **Prompt family P1–P5 (stage 4)**: P1 rewrite / P2 self-check / P3 concept
  reconciliation / P4–P5 GLM check & score — codified in `services/llm.py`,
  documented in `docs/prompt-family-p1-p5.md`.
- **Verify-reject loop (stage 5)**: `core/verify.py` `gate()` fail-closed gate;
  per-block 4-attempt repair budget with accumulating feedback; suspend on
  exhaustion.
- **User guide**: `docs/user-guide.md`.
- **S2 exhaustive harness**: `tests/exhaustive/s2_exhaustive.py` (115 cases).

### Changed

- Reject-repair: `process` switched from redo-whole-block to targeted repair
  driven by the defect list; negative `max_rewrite_retries` clamps to 0.
- `resolve_model` unknown stage key falls back to `_DEFAULT_MODELS["rewrite"]`.

### Fixed

- `resolve_model` unknown key returned "" → now falls back (no empty model
  names hitting the API).
- Negative `max_rewrite_retries` silently skipped all verification → clamped to
  0 so fail-closed cannot be bypassed.

### Security

- Maintained: API keys via env vars; model names/paths from configs; only
  `.env.example` committed.

## [0.2.0] - 2026-08-14

### Added

- **A2 paragraph-boundary chunking**: `core/chunk.py` splits on blank-line
  paragraph boundaries (never mid-sentence; char-level hard split only as a
  last resort for oversized single paragraphs).
- **A3 titleless documents**: `core/assemble.py` preserves paragraph blank lines
  and returns one root block instead of fabricating a tree.
- **D1 course index**: `core/md_index.py` + `cli --index` (OKF-style index.md).
- **D2 wiki-links spec + validation**: `cli --validate-links` (dangling-link
  detection).
- **D3 frontmatter relation fields**: prerequisites/next/related + validation.
- **D4 citation discipline**: prompt-level enforcement + `find_missing_source`
  spot checks.
- **D5 `[AI-inferred]` tagging** with `inferred` counts.
- **D6 confidence values**: `confidence_policy` + `validate_confidence` +
  low-confidence notes auto-listed for human review.
- **D7 concept pages**: `core/concepts.py` + `cli --concepts`.
- **D8 lexical search**: `core/search.py` + `cli --search` (zero deps).
- **B1 git auto-commit**: `providers/git_io.py`.
- **B2 semantic reconciliation**: concept-level coverage check (catches
  paraphrases the lexical pass misses).
- **B3 resume**: state file with per-unit progress; input mtime change
  invalidates cache.
- **B4 low-confidence marking** with `low_conf` counts.
- **C2 git branch protection**: `process branch` param (rewrite branch +
  diff preview).
- **C3a incremental batch**: `process_course` (mtime-based).
- **C3b change rationale lines** required for deletions/edits.
- **C3d frontmatter schema validation**.
- Tests 41 → **133 cases**.

### Changed

- `note_style_spec.yaml` v1.2 → **v1.3** (linking / relation_fields /
  confidence_policy).
- `models.yaml` gains `reconcile`; model split: rewrite/reconcile via the
  Claude channel (anthropic protocol), quality_check/scoring via GLM.
- `providers/llm_client.py` gains the `anthropic` provider (Messages protocol,
  `ANTHROPIC_BASE_URL` + `ANTHROPIC_AUTH_TOKEN`); provider routing fixed
  (quality_check/scoring explicitly GLM).
- `process` returns `inferred / low_conf / diff / resumed`; unified failure
  contract.

### Fixed

- **BOM files lost their first heading**: `read_md` strips UTF-8 BOM.
- **Inconsistent failure keys** across missing-file/empty/LLM-error paths.
- **CLI mode-order defect**: `--validate-links`/`--concepts` without input were
  wrongly rejected.
- **Resume cache ignored input changes**: state now records `src_mtime`.
- **Dotted terms not extracted**: `**HMM 2.0**` regex char class gains `.`.
- **providers tests never ran**: `tests/providers/` was missing `__init__.py`;
  fixed and 2 stale model assertions updated.

### Security

- Maintained: API keys via env vars; model names/paths from configs; only
  `.env.example` committed.

## [0.1.0] - 2026-08-13

### Added

- Project skeleton per the directory contract: `configs/ core/ services/
  providers/ scripts/ tests/ docs/` (single-direction deps
  `cli → services → core+providers+configs`).
- **Pipeline core**:
  - `core/assemble.py`: cleaned md → heading tree / breadcrumbs.
  - `core/chunk.py`: mechanical chunking (size caps + overlap + breadcrumb).
  - `core/rewrite.py`: rolling-compilation scheduler (window roll + running
    summary + AI boundary merging).
  - `core/verify.py`: semantic reconciliation + quality scoring + combined
    checks.
- **LLM adapters**:
  - `providers/llm_client.py`: GLM/DeepSeek OpenAI-compatible client
    (config-driven model names, env overrides, timeout/retry, no retry on 4xx).
  - `services/llm.py`: three prompts (rewrite / check / score) with
    best-effort JSON parsing (incl. bare-newline repair).
  - `services/orchestrator.py`: main flow (read → chunk → rolling rewrite →
    verify → write) with reject-and-repair + LLM score gate.
- **CLI**: `cli.py` (thin entry; input validation; `--json` for integration).
- **Spec**: `note_style_spec.yaml` v1.2 (OKF-aligned).
- **Tests**: 41 cases mirroring the package structure.

### Fixed

- `core/assemble.py`: blank-only input returns an empty list.
- `core/assemble.py`: numeric-only sections no longer auto-detected (3.14 /
  years / versions misfired) — left to the AI rolling pass.
- `core/chunk.py`: oversized single lines hard-split; first chunk no longer
  mislabelled with overlap.
- `services/llm.py`: JSON with bare newlines auto-repaired before parsing.

### Security

- API keys only via env vars (`GLM_API_KEY`/`DEEPSEEK_API_KEY`), never
  hardcoded.
- Model names/paths only from `configs/` or env vars.
- Only `.env.example` committed; real `.env` never enters the repo.
