# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| `v0.3.x` | ✅ Active |
| `v0.2.x` | ⚠️ Critical fixes only |
| `< v0.2.0` | ❌ End of life |

## Reporting a vulnerability

**Please do not open a public issue for security-sensitive reports.**

Use one of these private channels instead:

- GitHub Security Advisories: <https://github.com/suonian/vidknot/security/advisories/new>
- Email: see the latest maintainer contact published in `git log --format='%ae'` for the
  latest tagged commit (e.g. `v0.4.0`).

When reporting, please include:

1. VidkNot version (`python -m vidknot --version`)
2. Python and OS versions
3. A minimal reproduction (without secrets, cookies, or API keys)
4. The impact and how an attacker could exploit it

We aim to acknowledge reports within **3 business days** and ship a fix or mitigation within
**30 days** for critical issues, or include the fix in the next minor release otherwise.

## Scope

The following are in scope:

- Code execution, file overwrite, or arbitrary command execution via crafted inputs
- Credential leakage (cookies, API keys) via logs, error messages, or network requests
- Bypassing content moderation or platform authorization controls
- Supply-chain risks in declared dependencies

The following are **out of scope**:

- Platform-specific anti-scraping mechanisms (these are the user's responsibility)
- Behavior of third-party API providers (SiliconFlow, OpenAI, Feishu, Notion, Yuque)
- Issues only reproducible against an expired or revoked API key / cookie

## Best practices for users

- Never commit `.env`, `cookies/`, or any API key — `.gitignore` already excludes them
- Rotate cookies and keys periodically
- Use the minimal scope needed for the platforms you actually use
- Review [COOKIE_GUIDE.md](COOKIE_GUIDE.md) for cookie handling details