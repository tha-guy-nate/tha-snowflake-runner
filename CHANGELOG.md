# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-09-26
### Changed
- **Breaking:** `query(desc=...)` on `ThaSnowflake` and `Session` is now the whole status message, used verbatim, instead of a prefix that had `": Getting data from Snowflake"` appended. Callers who passed a step label like `desc="[2/7]"` should now pass the full text (e.g. `desc="[2/7]: Getting data from Snowflake"`). With `desc=None` the default message is now `"Getting data from Snowflake ..."`.
- The tqdm progress bar is gone. `cursor.execute()` blocks for the whole query and the bar only wrapped the row iteration afterwards, so it printed a meaningless `2819it [00:00, 4616it/s]` after the wait was already over. The message is now sent through `status_cb` *before* the query runs. `show_progress=False` still works and suppresses the message; it is accepted for compatibility.
- Removed the `tqdm` dependency and the internal `_progress` module.

### Fixed
- `__version__` was `0.3.3` while `pyproject.toml` was `0.3.4`; resynced.

## [0.3.4] - 2026-09-07
### Fixed
- Raised `snowflake-connector-python` floor to `>=4.7.1` — `>=3.6` was resolving to `4.6.0`, which has a known vulnerability (CVE-2026-15925: improper TLS hostname verification that could let an on-path attacker bypass certificate hostname validation) fixed in `4.7.1`. Flagged by `pip-audit`.

## [0.3.3] - 2026-08-21
### Fixed
- Re-locked transitive `pip` (pulled in via `deptry` -> `pip-api`) from `26.1.2` to `26.2.1`, resolving a known CVE (PYSEC-2026-3721) flagged by `pip-audit`.

## [0.3.2] - 2026-08-06
### Fixed
- `query()`'s step label (`desc`/"Getting data from Snowflake") is now emitted before `cursor.execute()` instead of after — previously the label only appeared once the query had already finished, since `execute()` blocks with no progress signal of its own. The label now shows immediately when the query kicks off, and the `tqdm` bar still tracks the row-fetch step as before.

## [0.3.1] - 2026-08-05
### Changed
- Pull in `snowflake-connector-python`'s `secure-local-storage` extra (adds `keyring`), enabling the connector's built-in secure local token cache for `authenticator="externalbrowser"` (Okta SSO) connections — avoids re-prompting for MFA/SSO on every connect on platforms with a supported OS keychain.
- Raised `cryptography` floor to `>=50.0.0` — `>=48.0.1` was resolving to `49.0.0`, which has a known vulnerability (PYSEC-2026-3552) fixed in `50.0.0`.

## [0.3.0] - 2026-07-16
### Added
- `desc` and `show_progress` params on `ThaSnowflake.query()` and `Session.query()` — mirrors `ThaCSV.read`'s progress-bar ergonomic. A `tqdm` bar labeled "Getting data from Snowflake" now prints while rows are fetched, on by default; `desc="..."` prefixes it with a step label (e.g. `desc="Step 1 of 7"` → `"Step 1 of 7: Getting data from Snowflake"`); `show_progress=False` suppresses it entirely.
### Changed
- `query()` now iterates the cursor (via `tqdm`) instead of calling `fetchall()` in one shot, so progress can be reported per-row. Return shape is unchanged.

## [0.2.3] - 2026-07-04
### Fixed
- Added missing `data` to `pyproject.toml` `keywords` to align with the GitHub topic list.

## [0.2.2] - 2026-07-04
### Fixed
- Test coverage gaps (93% → 100%): added tests for `_suppress_stdout`, `set_context`'s warehouse/schema branches, `build_connect_kwargs`'s database/schema inclusion, and `query()`'s own-connection path (previously always bypassed via an injected `conn=`) in `client.py`; a new `test_profiles.py` covering the standalone `list_profiles()` function and `_load_all_profiles`'s non-dict-key skip (previously untested — only the `ThaSnowflake.list_profiles()` method wrapper had tests); and `Session._status` in `session.py` (defined but never covered).

## [0.2.1] - 2026-07-03
### Added
- Python 3.13 and 3.14 classifiers and CI support.
- PR template (What/Why/How + Test Plan sections), part of a cross-repo consistency sweep.

## [0.2.0] - 2026-07-03
### Added
- `private_key` param for key-pair auth — accepts a PEM string, PEM bytes, or raw DER bytes directly, so callers can inject a key from a secrets manager without writing it to disk. Mutually exclusive with `private_key_file`. DER bytes are assumed pre-decrypted; `private_key_passphrase` only applies to the PEM path.
### Changed
- Dropped the `pyarrow` dependency — never used by this library (only relevant to the connector's `[pandas]` extra, which `tha-snowflake-runner` doesn't use).
- Added `cryptography` as an explicit dependency (previously relied on transitively via `snowflake-connector-python`) — needed directly for the new `private_key` PEM/DER handling.

## [0.1.4] - 2026-06-27
### Added
- mypy strict mode enabled.
- Auto-tag reusable workflow in CI.
- actionlint pre-commit hook for GitHub Actions workflow validation.
### Fixed
- Inline publish workflow for PyPI OIDC compatibility.
- Pinned mypy `python_version` to 3.10 to match minimum supported version.

## [0.1.3] - 2026-06-25
### Added
- Pre-commit hooks; centralized publish workflow.
### Fixed
- Floored `pyarrow>=16.0.0` to enforce NumPy 2.x ABI compatibility.
- Pinned `setup-uv` to v8.2.0; bumped `checkout` to v7, `upload-artifact` to v7.
### Changed
- Trimmed Python classifiers to match CI matrix.

## [0.1.2] - 2026-06-16
### Added
- Python 3.13 and 3.14 classifier and CI support.
- Format and build steps in CI.
- Dependabot for automated dependency updates.
### Changed
- Bumped minimum dev dependency floors (pytest ≥ 9.1.0, ruff ≥ 0.15.17, mypy ≥ 2.1.0).

## [0.1.1] - 2026-05-30
### Added
- `open_session()` method for explicit session lifecycle management.
- SQL file support — pass a `.sql` file path to `query()` in place of an inline string.
- Read-only connection scope note in documentation.

## [0.1.0] - 2026-05-30
### Added
- Initial release with `ThaSnowflake` client: connection management, multi-format profile support, normalized query return shape.
