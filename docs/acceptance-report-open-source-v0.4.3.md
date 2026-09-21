# Acceptance Report · Open-Source Release of md-rewrite-engine v0.4.3

> Date: 2026-09-20
> Scope: local pre-release codebase → public repo `SpiralQWQ/md-rewrite-engine`
> Verdict: **✅ PASS** — 14/14 tasks closed, 169 unit + 137 exhaustive tests green,
> privacy sweep zero-hit, git history clean from the first commit.

---

## 1. What was released

| Layer | Content |
|---|---|
| core/ | pure algorithms: assemble / chunk / rewrite / verify / concepts / md_index / search / toc |
| services/ | orchestration + P1–P5 prompt family |
| providers/ | GLM / DeepSeek / Anthropic clients, git io, executor selector |
| configs/ | teaching spec v1.3, executors, models, user prefs (all sanitized) |
| tests/ | 169 unit + tests/exhaustive/s2_exhaustive.py (137 cases, fully mocked) |
| docs/ | user guide, orchestration manual, capability catalogue, prompt family, directory contract, input spec (+ archive) |
| governance | README EN/zh, CHANGELOG EN/zh, LICENSE (AGPL-3.0 dual), COMMERCIAL, ROADMAP, CONTRIBUTING, CODE_OF_CONDUCT, SECURITY, donate banners |

## 2. Task closure (S1 → S4)

### Stage 1 — migration & sanitization (T1–T9)

| Task | Scope | Result | 4-round review findings |
|---|---|---|---|
| T1 | full privacy scan (7 patterns × all files) | 2 sh hard-coded paths, 3× internal project-name hits, 0 secrets | scan script itself excluded from results |
| T2 | sanitize py/yaml/sh | sh `cd` → `$(dirname $0)`; all drive-path hits verified as URL false-positives | regex misfire pattern documented |
| T3 | sanitize md | 3× internal project name + 24× internal module name + 9× local provider quirks → 0 | archive handoff doc had 9 hidden hits |
| T4 | README EN + zh | badges / language switch / Why / Features / Quick start / architecture / Roadmap / License / donate | structure aligned to sibling repos |
| T5 | CHANGELOG EN + zh | all 6 versions translated; LICENSE/COMMERCIAL rebranded | caught LICENSE carrying sibling repo's name |
| T6 | donate banners | assets/donate_{wechat,alipay}.jpg | — |
| T7 | config hygiene | .env.example generalized; configs de-localized; .gitignore + pytest_cache | test file + changelog history also swept |
| T8 | smoke | pytest 169 ✓ + S2 137 ✓ | — |
| T9 | git init + first commit | `7725709`; history 0 privacy hits from day one | caught temp/ not imported → README refs would break; moved s2 harness → tests/exhaustive, toc_gen → scripts |

### Stage 2 — open-source governance (T10–T14)

| Task | Scope | Result | Findings |
|---|---|---|---|
| T10 | README polish | FAQ (EN/zh): executor choice, gate FAILs, providers, i18n | ASCII architecture kept (mermaid renderer-dependent) |
| T11 | CONTRIBUTING / CoC / SECURITY | gate-first policy; SECURITY tailored to real deps (PyYAML only) & real secrets | template carried Douyin/setup.py leftovers → replaced |
| T12 | docs curation | 5 internal planning docs → docs/archive/; user-facing 6 kept; README tables synced; 0 broken refs | — |
| T13 | md lint | 0 issues (H1 uniqueness / fence closure / trailing spaces); pseudo-H1 inside bash fences correctly exempted | grep-based H1 check false-positives inside code fences — verified before "fixing" |
| T14 | this report + changelog | — | — |

## 3. Privacy & compliance

- Patterns swept: drive paths / usernames / internal dirs (AAA.*) / internal
  project names / secrets / QQ groups / emails — **0 hits in HEAD**.
- Retained by explicit decision: `SpiralQWQ` signature, donate banners (user's
  standing rule).
- License: AGPL-3.0 — dependency audit passed (MinerU AGPL compatible; PyYAML
  MIT; LLM providers are remote APIs, not derivatives).
- git history contains no pre-sanitization content (init happened after cleanup).

## 4. Known limitations (documented, not defects)

- `final_check.sh` / `run_gate_all.sh` ship with example chapter lists — they
  reference `temp/`-style local sample files; users run `gate_check.py` directly
  on their own material.
- Gate thresholds tuned for Chinese ASR/rewrite material (roadmap: English spec).

## 5. Hard-threshold recheck (promotion checklist v1.0)

| Item | Result |
|---|---|
| src/ layout | ✅ `src/md_rewrite_engine/` + `python -m md_rewrite_engine` + console script `md-rewrite` |
| pyproject.toml | ✅ version/deps/license/authors/keywords/classifiers/urls/scripts |
| dead code | ✅ heuristic sweep: 0 unreferenced module-level functions |
| secrets/paths | ✅ deep scan 0 hits (scanner kept outside repo) |
| git history | ✅ all 5 commits created post-sanitization; no pre-clean content ever committed |
| self-check | ✅ `python -m md_rewrite_engine` runs; `import md_rewrite_engine; __version__ == "0.4.3"`; git status clean |
| Bonus: CI | ✅ GitHub Actions matrix (3 OS × py3.10-3.12, unit + exhaustive) |
| Bonus: tag | ✅ `v0.4.3` annotated tag |
| Bonus: community | ✅ issue templates (bug / feature with gate-impact question), SECURITY.md |

## 6. Release mechanics

- Branch: `master`, 5 commits (`7725709` release → `84195f9` ci), tag `v0.4.3`.
- Remote push & GitHub repo creation: pending user go (out of scope here).
