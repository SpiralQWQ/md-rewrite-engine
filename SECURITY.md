# Security Policy / 安全策略

## Supported Versions / 支持的版本

| Version | Supported |
|---------|-----------|
| 0.4.x   | ✅ actively maintained |
| < 0.4   | ❌ not supported |

## Reporting a Vulnerability / 报告漏洞

If you find a security issue, **please do not open a public issue first**. Instead:

1. Open a private report via **GitHub Security Advisories** → *New advisory* on this repository
   (or email the maintainer privately if you have a known contact).
2. Include: affected version, OS, a minimal repro, and the impact you observed.
3. We'll acknowledge within **7 days** and aim to ship a fix in the next release.

We're a small project — thank you for handling it discreetly and giving us time to fix it.

> 发现安全问题请**先走 GitHub 私密安全通告**，不要直接公开提 issue。附上：影响版本、系统、最小复现、影响面。7 天内确认，随下个版本修复。

## Security Notes / 安全说明

- **Secrets never belong in the repo.** `GLM_API_KEY` / `DEEPSEEK_API_KEY` / `ANTHROPIC_AUTH_TOKEN` are personal credentials — keep them in `.env` (git-ignored) or environment variables. If you accidentally commit one, rotate it immediately.
- **`.env` is git-ignored** — copy `.env.example` locally and never commit the real file.
- **LLM egress**: the engine sends note text to the LLM providers configured in `configs/executors.yaml` — do not feed it sensitive third-party material you have no right to process.
- **Content responsibility.** This tool can download third-party videos/images. Respect platform terms of service and copyright law — the README carries the same disclaimer. Don't use it to redistribute content you don't own.
- **Third-party dependencies** (PyYAML is the only direct one; GLM/DeepSeek/Anthropic are remote APIs) — keep local packages updated.
