# Contributing to md-rewrite-engine

First off, thank you for considering a contribution — this project grew out of a
real study-notes pipeline and every outside perspective makes it better.

## The one thing to understand before you start

This project is **human-machine relay, not a chatbot wrapper**: the quality gate
(`core/verify.py` + `scripts/gate_check.py`) is the contract. Any change that
loosens the gate (lowering thresholds, skipping checks, swallowing failures) will
be rejected in review unless it comes with a strong argument and updated tests.

## How to set up

```bash
git clone https://github.com/SpiralQWQ/md-rewrite-engine.git
cd md-rewrite-engine
pip install -r requirements.txt
cp .env.example .env        # fill GLM_API_KEY (only needed for LLM-backed tests)
python -m pytest tests/ -q  # should be all green before you touch anything
```

## How to contribute

1. **Open an issue first** for anything beyond a typo fix — describe the problem
   you hit with a minimal repro (an input md + the wrong output is ideal).
2. **Fork & branch** — `feat/<short-name>` or `fix/<short-name>`.
3. **Keep the layering** — `cli → services → core + providers + configs`, no
   upward imports; `core/` stays zero-dependency (see
   `docs/directory-contract.md`).
4. **Add tests** — mirror the package structure under `tests/`; behaviour changes
   need a failing-then-passing test. Exhaustive harness:
   `python tests/exhaustive/s2_exhaustive.py`.
5. **Run the gate on your own PR text** — if you edited the rewrite prompts or
   spec, run `python scripts/gate_check.py` against a sample to prove no
   regression.
6. **Update docs** — user-facing changes go into `docs/user-guide.md` and both
   READMEs; notable changes append to `CHANGELOG.md` (and `CHANGELOG_zh.md`).

## Commit style

Conventional-ish, one line, imperative: `fix: ...`, `feat: ...`, `docs: ...`,
`test: ...`, `refactor: ...`.

## Code style

- Python 3.10+, stdlib-first (the whole point is a tiny dependency footprint).
- Chinese comments/messages are fine — the project's working language is
  bilingual; keep user-facing strings consistent with the surrounding code.
- No hardcoded keys, paths, or model names — env vars and `configs/` only.

## License

By contributing, you agree that your contributions are licensed under
AGPL-3.0, same as the project.
