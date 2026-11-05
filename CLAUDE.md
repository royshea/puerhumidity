# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Git workflow

Never push directly to `main`. Branch, open a PR, wait for `CI / test` to pass, then merge. Branch prefixes: `feature/`, `fix/`, `audit/<finding-slug>`, `chore/`.

## Commands

```
pip install -r requirements.txt -r requirements-dev.txt

flask run --debug                                   # http://localhost:5000
python -m scripts.seed_data                         # populate data/readings.csv for the chart

ruff check . && mypy app/ tests/ && python -m pytest tests/ -q --tb=short   # same checks as CI
python -m pytest tests/test_webhook.py::TestWebhookRoutes::test_ping_lifecycle -q   # single test
```

Requires Python 3.13. mypy runs in strict mode over both `app/` and `tests/`, so tests need full type annotations too. The ruff line length is 100.

`TableStorage` tests skip unless Azurite is listening locally, so a green local run does not exercise the Azure backend. One production-config test in `tests/test_app.py` also skips unless `AZURE_STORAGE_CONNECTION_STRING` is set.

## Architecture

SmartThings pushes device events to `POST /webhook`; `GET /` reads them back and renders a Plotly chart.

**Write path:** `app/routes/webhook.py` dispatches on the `lifecycle` field. `EVENT` payloads become `SensorReading` objects (`app/models/reading.py`) and go to storage. `INSTALL` and `UPDATE` create the subscriptions that produce those events, via `app/services/smartthings.py`.

**Read path:** `app/routes/ui.py` fetches a time window from storage and passes it to `app/services/chart.py`. For `resampled` and `smoothed` modes, `app/services/data_transform.py` first forward-fills readings onto a regular grid (sensors only report on change), then `smoothed` applies a sliding average to that grid.

**Storage:** routes call `get_storage()`, a module-level singleton in `app/storage/__init__.py`, and never construct a backend. `StorageBase` has two implementations, `LocalStorage` (CSV) and `TableStorage` (Azure, Managed Identity), and changes to the interface must be made in both.

**Identity:** a sensor is `{device_label}-{Reading_type}`, e.g. `PuerHumidity-Humidity` (`SensorReading.sensor_name`), and this is the Table Storage PartitionKey. Device IDs map to labels through the hardcoded `DEVICE_LABELS` in `app/config.py`, and unknown devices fall back to their ID as the label. Changing a label therefore starts a new partition and a new chart series.

## Non-obvious behavior

- **Production runs `DevelopmentConfig`.** `app/__init__.py` creates `application = create_app()` with no config name, which is what gunicorn loads (`app:application`). `ProductionConfig` is unused in deployment and `init_app` validation is never called. The backend is selected by the `STORAGE_TYPE` env var, which Bicep sets to `azure`.
- **Importing `app` builds an app.** The module-level `create_app()` runs on import, including during test collection, and initializes storage from the environment. `create_app` overwrites the global storage singleton each time.
- **`TestingConfig` does not isolate storage.** The `app` fixture applies it after `create_app` has already built storage. Tests that write must call `init_storage(...)` with a temp file, as `tests/test_webhook.py` does.
- **`RowKey` is `9999999999 - unix_seconds`,** so rows sort newest-first, and "after cutoff" queries use `RowKey lt`. It has one-second resolution, so two readings for a sensor in the same second overwrite each other.
- **Webhook timestamps are receive time** (`datetime.now(UTC)`), not event time. The `/import` route, which is enabled by `ENABLE_IMPORT=true`, uses the timestamps from the SmartThings Activities API.
- **CONFIGURATION must return `permissions: ["r:devices:*", "r:locations:*"]`,** or SmartThings never sends INSTALL.
- **`.env` is only loaded by the `flask` CLI** (plus `scripts/migrate_csv.py`). pytest and gunicorn do not read it.
- **The app cannot use Azurite.** `_create_storage` only reads `AZURE_STORAGE_ACCOUNT_NAME` and always builds an `account_url`, despite what the README says about `AZURE_STORAGE_CONNECTION_STRING`. Only tests connect to Azurite, by constructing `TableStorage(connection_string=...)` directly.

## Deployment

- `deploy-app.yml` runs after CI succeeds on `main`, and skips when the latest commit only touches `infra/`, `docs/`, or `*.md`. It ends with a smoke test against `/health`.
- `deploy-infra.yml` runs on pushes to `main` that touch `infra/**`. It deliberately fails if any changed file path contains "rbac", because the CI service principal cannot create role assignments. Deploy those manually with `deployRbac=true` (see the README's RBAC Bootstrap section).
- Both deploy workflows share the `deploy-puerhumidity` concurrency group, so they queue rather than overlap. Don't remove it from either: an infra deploy that touches site config restarts the app, and if that lands mid zip-deploy the container boots from a half-written `wwwroot` and fails.
- Infrastructure lives in `infra/` and targets shared resources in `rg-shared-platform`. `SECRET_KEY` is set by hand on the web app, not in Bicep.
