# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
