# ValutaTrade Hub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete local final project with a USD `deposit` command and verified CLI flows.

**Architecture:** Keep business rules in `core`, persistence and settings in `infra`, remote rate updates in `parser_service`, and command parsing in `cli`. Store money as `Decimal` strings and commit each user transaction in one atomic portfolio write.

**Tech Stack:** Python 3.12, uv, requests, prettytable, pytest, ruff.

**Spec:** `docs/superpowers/specs/2026-11-08-valutatrade-design.md`

## Global Constraints

- Project name `finalproject_toporin_M26-555`.
- Currency codes: USD, EUR, GBP, RUB, BTC, ETH, SOL.
- No real money or external submission.

## Review Focus

- `NaN`, infinity, zero and negative amounts must fail before storage changes.
- Insufficient USD or currency balance must leave both wallets unchanged.
- Invalid or stale rates must prevent trade and provide an actionable error.
- A failed source must not discard another source's valid rates.
- Duplicate username and wrong password must not create a session.

---

### Task 1: Core models and storage

**Files:** `valutatrade_hub/core/{currencies,exceptions,models,utils}.py`, `valutatrade_hub/infra/{settings,database}.py`, `tests/test_core.py`.

**Interfaces:** `parse_amount(value)->Decimal`, `Wallet.deposit/withdraw`, `DatabaseManager.read/write(name, payload)`, `SettingsLoader.get(key)`.

- [ ] Write tests for positive finite amount, no negative balance, and atomic JSON persistence.
- [ ] Run `pytest tests/test_core.py -q` and confirm failure.
- [ ] Implement models and storage.
- [ ] Run `pytest tests/test_core.py -q` and confirm success.
- [ ] Commit this component.

### Task 2: Rates and HTTP clients

**Files:** `valutatrade_hub/parser_service/{api_clients,storage,updater,scheduler}.py`, `valutatrade_hub/core/usecases.py`, `tests/test_rates.py`.

**Interfaces:** `RatesUpdater.run_update(source=None)->dict`, `RateService.rate(from_code,to_code)->Decimal`, `RatesStorage.save/read`.

- [ ] Write mocked HTTP and cross-rate tests, including partial failure and stale rate.
- [ ] Run `pytest tests/test_rates.py -q` and confirm failure.
- [ ] Implement clients, updater, storage, rate service.
- [ ] Run `pytest tests/test_rates.py -q` and confirm success.
- [ ] Commit this component.

### Task 3: User flows and CLI

**Files:** `valutatrade_hub/core/usecases.py`, `valutatrade_hub/cli/interface.py`, `valutatrade_hub/{decorators,logging_config}.py`, `main.py`, `tests/test_cli.py`.

**Interfaces:** `TradingService.register/login/deposit/buy/sell/portfolio`, `run_command(argv, service)->str`.

- [ ] Write tests for registration, login, deposit, buy, sell and error invariants.
- [ ] Run `pytest tests/test_cli.py -q` and confirm failure.
- [ ] Implement user flows and command parser.
- [ ] Run `pytest tests/test_cli.py -q` and confirm success.
- [ ] Commit this component.

### Task 4: Packaging and documentation

**Files:** `pyproject.toml`, `uv.lock`, `README.md`, `.gitignore`, `data/*.json`, `demo.cast`.

**Interfaces:** `uv run python main.py --help` and interactive `uv run python main.py`.

- [ ] Document setup, commands, API key, pricing semantics, and demo.
- [ ] Generate lockfile and local terminal recording.
- [ ] Run `uv run pytest -q`, `uv run ruff check .`, and a CLI smoke test.
- [ ] Commit deliverable.
