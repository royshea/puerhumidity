# puerHumidity — Copilot Agent Instructions

## Project Overview
A Python Flask webhook receiver for SmartThings humidity and temperature
sensors, with Azure Table Storage backend and Plotly-based visualization.

## Git Workflow — MANDATORY

**NEVER push directly to `main`.** All changes must go through a pull request:

1. Create a feature branch: `git checkout -b <descriptive-branch-name>`
2. Make changes and commit to the branch
3. Push the branch: `git push origin <branch-name>`
4. Open a PR targeting `main`
5. Wait for CI (`CI / test`) to pass on the PR
6. Merge the PR (squash or merge commit, either is fine)

CI runs automatically on every push and PR. Deployment to Azure only
triggers after CI passes on `main` (via `workflow_run`).

Branch naming conventions:
- `feature/<description>` — new features
- `fix/<description>` — bug fixes
- `audit/<finding-slug>` — audit remediation PRs
- `chore/<description>` — maintenance (deps, docs, config)

## Tech Stack
- Python 3.13, Flask, Gunicorn
- Azure Table Storage (production), CSV file storage (local dev)
- Azure Monitor alerts + Application Insights (OpenTelemetry SDK)
- Plotly for data visualization
- GitHub Actions CI/CD → Azure App Service

## Development Environment

### Virtual environment
```
.\.venv\Scripts\Activate.ps1       # Windows PowerShell
source .venv/bin/activate           # bash/zsh
```

### Install dependencies
```
pip install -r requirements.txt -r requirements-dev.txt
```

### Run the app
```
flask run --debug
```
Serves on http://localhost:5000

### Linting (ruff)
```
ruff check .
```

### Type checking (mypy)
```
mypy app/ tests/
```

### Tests (pytest)
```
python -m pytest tests/ -q --tb=short
```

### Full CI validation (run before pushing)
```
ruff check . && mypy app/ tests/ && python -m pytest tests/ -q --tb=short
```

### Fix lint issues automatically
```
ruff check --fix .
```

## Code Conventions
- All Python files should have type annotations (enforced by mypy strict mode)
- Linting via ruff (config in pyproject.toml)
- Target Python version: 3.13
- Use `X | None` union syntax (Python 3.10+)

## Project Structure
```
app/                    # Flask application package
  __init__.py           # App factory + OpenTelemetry init
  config.py             # Configuration classes
  models/               # Data models
  routes/               # Flask blueprints (webhook, health, dashboard)
  services/             # Business logic
  storage/              # Storage abstraction (TableStorage, LocalStorage)
  templates/            # Jinja2 HTML templates
infra/                  # Azure Bicep infrastructure
  main.bicep            # Orchestrator
  main.bicepparam       # Parameter values
  modules/              # Bicep modules (alerts)
.github/workflows/      # CI + deploy pipelines
tests/                  # pytest test suite
docs/                   # Documentation
pyproject.toml          # Ruff, mypy, pytest configuration
```
