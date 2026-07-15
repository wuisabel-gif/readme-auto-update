# Contributing

Issues and pull requests are welcome.

## Development

Use Python 3.12 or newer. README Auto Update deliberately has no runtime Python dependencies.

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
docker build -t readme-auto-update:test .
```

Keep changes small and include tests for behavior changes. AI-related changes must preserve the
rules-mode path. Discovery changes must preserve private-name redaction, avoid logging tokens, and
keep GraphQL result sizes bounded.

## Pull requests

- Explain the user-visible behavior.
- Add or update tests.
- Update `README.md` and `action.yml` when inputs change.
- Do not include real API keys, organization data, or private repository content in fixtures.
