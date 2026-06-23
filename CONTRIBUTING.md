# Contributing to Roxy Trading

Thanks for your interest in contributing — we welcome bug reports, documentation improvements, tests, and code contributions.

Getting started

- Fork the repository and create a feature branch from `main` named `feature/your-feature` or `fix/issue-number`.
- Keep changes small and focused. Open a pull request against `main` when ready.

Code style and checks

- We use `black` (line length 120), `isort`, and `flake8` for style. A `.pre-commit-config.yaml` is included; install and run `pre-commit` locally:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

- Type hints are appreciated. The project includes `mypy.ini` to guide checks; run `mypy` before opening a PR.

Tests

- Add unit tests under `tests/` using `pytest`.
- CI runs `pytest` on Python 3.10 and 3.11.

Pull request checklist

- [ ] My code follows the project's style guidelines
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] I have updated documentation where relevant (README, SECURITY.md, etc.)
- [ ] All CI checks pass

Security

- Do not commit secrets. Use environment variables for credentials and tokens, and consider using a secrets manager for production deployments.
- If you discover a security issue, please open an issue with the `security` label or email the maintainer directly.

Contact

For questions, open an issue or reach out via the repository discussions.
