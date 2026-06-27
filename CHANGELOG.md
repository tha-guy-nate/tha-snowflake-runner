# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.4] - 2026-06-27
### Changed
- Enabled mypy strict mode; pinned mypy `python_version` to `3.10` for consistent analysis.

## [0.1.3] - 2026-06-22
### Fixed
- Floored `pyarrow>=16.0.0` to enforce NumPy 2.x ABI compatibility.
### Changed
- Pinned GitHub action versions (checkout v7, setup-uv v8.2.0).
- Trimmed Python classifiers to match CI matrix.

## [0.1.2] - 2026-06-16
### Added
- Python 3.13 and 3.14 classifier and CI support.
- Dependabot for automated updates.
### Changed
- Standardized CI and publish workflows.
- Bumped minimum dev dependency floors (pytest ≥ 9.1.0, ruff ≥ 0.15.17, mypy ≥ 2.1.0).

## [0.1.1] - 2026-06-03
### Added
- `open_session()` method for explicit connection lifecycle management.
- SQL file support — pass a `.sql` file path to `query()`.

## [0.1.0] - 2026-06-03
### Added
- Initial release with `ThaSnowflake` for typed Snowflake connection management, multi-format profile support, and normalized query results.
