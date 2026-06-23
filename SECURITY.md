# SECURITY

## Advisory: `filelock` (GHSA-w853-jp5j-5j7f)

A vulnerability was identified in `filelock` <= 3.19.1 (TOCTOU symlink race) that can allow local attackers to truncate or corrupt files via predictable lock file paths. The upstream fix is available in `filelock` 3.20.1.

Immediate mitigation steps

- Pin `filelock` to `3.20.1` in `requirements.txt` (already present). Note: this release may require Python >=3.10.
- If you cannot upgrade immediately, consider these partial mitigations:
  - Prefer `SoftFileLock` where acceptable (different semantics; not always a drop-in replacement).
  - Restrict permissions on lock directories (e.g., `chmod 0700`) so untrusted users cannot create symlinks.
  - Avoid creating predictable lock file paths in shared directories (e.g., `/tmp`).
  - Monitor lock directories for suspicious symlinks before running critical jobs.

Recommended next steps

1. Validate `filelock==3.20.1` on CI runners using Python 3.10/3.11 and run full test suite.
2. If tests pass, merge the pin and update deployment runtimes to Python >=3.10.
3. If tests fail, triage failing tests and update code or dependencies accordingly.
4. Add automated CI checks that run `pip-audit` and `detect-secrets` on PRs (already configured).

If you want, I can open a PR that adds this `SECURITY.md` and reference the existing `filelock` pin and CI tasks.

Badges

Add these badges to `README.md` to show CI and snapshot status:

```
[![CI](https://github.com/Rgrauferia/roxy_trading/actions/workflows/ci.yml/badge.svg)](https://github.com/Rgrauferia/roxy_trading/actions/workflows/ci.yml)
![Streamlit smoke](https://github.com/Rgrauferia/roxy_trading/actions/workflows/smoke.yml/badge.svg)
```
