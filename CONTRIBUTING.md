# Contributing to MindVault

## Development Setup

```bash
git clone <repo>
cd mindvault
make setup            # creates .venv, installs deps, copies .env
source .venv/bin/activate
# fill in config/.env with your API keys
make db-init
make dev
```

## Before Committing

```bash
make check            # lint + typecheck + unit tests
```

Install pre-commit hooks (runs automatically on `git commit`):
```bash
pip install pre-commit
pre-commit install
```

## Branch Strategy

| Branch | Purpose |
|---|---|
| `main` | Production-ready code only |
| `develop` | Integration branch |
| `feature/*` | New features |
| `fix/*` | Bug fixes |
| `chore/*` | Tooling, deps, docs |

Never commit directly to `main`.

## Adding a New Connector

1. Create `app/connectors/your_connector.py` extending `BaseConnector`
2. Implement `async def extract(source, filename) -> RawDocument`
3. Register extension in `app/ingestion/pipeline.py` → `_CONNECTOR_MAP`
4. Add unit tests in `tests/unit/test_connectors.py`
5. Document any new env vars in `config/.env.example` and `app/core/config.py`

## Code Style

- Line length: 100
- Formatter: `black`
- Linter: `ruff`
- All public functions must have type hints
- No business logic in route handlers — use service/repo layer
