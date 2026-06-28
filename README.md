# tha-snowflake-runner

[![CI](https://github.com/tha-guy-nate/tha-snowflake-runner/actions/workflows/ci.yml/badge.svg)](https://github.com/tha-guy-nate/tha-snowflake-runner/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/tha-snowflake-runner)](https://pypi.org/project/tha-snowflake-runner/)
[![Python](https://img.shields.io/pypi/pyversions/tha-snowflake-runner)](https://pypi.org/project/tha-snowflake-runner/)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](https://github.com/pre-commit/pre-commit)

A Tabular Helper API library that wraps snowflake-connector-python with typed connection management, multi-format profile support, and a normalized query return shape.

## Install

```bash
pip install tha-snowflake-runner
```

## Quick start

```python
from tha_snowflake_runner import ThaSnowflake

sf = ThaSnowflake(role="ANALYST", warehouse="COMPUTE_WH", database="PROD", schema="PUBLIC")

# inline SQL
result = sf.query("SELECT id, name FROM users WHERE active = %s", params=(True,))
# {"rows": [{"ID": "u1", "NAME": "Alice"}], "rowcount": 1, "status": None}

# or load SQL from a file
result = sf.query(file="queries/users.sql", params=(True,))
```

## Connection modes

### Mode 1 — native connections.toml (default)

Delegates profile lookup to the connector, which reads `~/.snowflake/connections.toml` (or the path in `SNOWFLAKE_HOME`).

```python
sf = ThaSnowflake(role="ANALYST", warehouse="WH")

# Named profile
sf = ThaSnowflake(connection_name="prod", role="ANALYST", warehouse="WH")
```

### Mode 2 — custom connections file

Pass any `.toml`, `.ini`/`.cfg`, or `.json` file. Both flat (`[profile]`) and nested (`[connections.profile]`) TOML styles are supported.

```python
sf = ThaSnowflake(
    connections_file="~/my_connections.toml",
    connection_name="prod",
    role="ANALYST",
    warehouse="WH",
)

# List available profile names from the file
names = sf.list_profiles()  # ["default", "prod", "dev"]

# Module-level convenience — no ThaSnowflake instance needed
from tha_snowflake_runner import list_profiles
names = list_profiles("~/my_connections.toml")
```

### Mode 3 — inline (no file)

Supply all connection parameters directly. `account` being set triggers inline mode.

```python
# Okta SSO — opens a browser window
sf = ThaSnowflake(account="myorg", user="me@example.com", authenticator="externalbrowser")

# Password (service accounts)
sf = ThaSnowflake(account="myorg", user="svc@example.com", password="secret")

# Key-pair
sf = ThaSnowflake(
    account="myorg",
    user="svc@example.com",
    private_key_file="~/keys/rsa_key.p8",
    private_key_passphrase="mypass",
)

# OAuth token
sf = ThaSnowflake(account="myorg", authenticator="oauth", token="...")
```

Pass `quiet_connect=True` to suppress connector stdout (e.g. the `externalbrowser` browser-open message).

## Query return shape

Every `query()` call returns a normalized dict:

```python
result = sf.query("SELECT * FROM orders WHERE id = %s", params=("o1",))
# {
#   "rows": [{"ID": "o1", "TOTAL": 99.0}],
#   "rowcount": 1,
#   "status": None,        # None on success, error string on Snowflake query failure
# }
```

`sf.rows` always holds the result of the most recent query (thread-local).

## Session — multiple queries on one connection

```python
with sf.session(role="ANALYST", warehouse="WH") as sess:
    users = sess.query("SELECT * FROM users")
    orders = sess.query("SELECT * FROM orders")
    # one connection opened, two queries run, connection closed on exit
```

For inline use without a `with` block, use `open_session()` — caller is responsible for closing:

```python
sess = sf.open_session(role="ANALYST", warehouse="WH")
result = sess.query("SELECT * FROM users")
sess.close()
```

Pass `accumulate=True` to append rows across queries into `sess.rows`:

```python
with sf.session(accumulate=True) as sess:
    sess.query("SELECT * FROM users WHERE region = 'US'")
    sess.query("SELECT * FROM users WHERE region = 'EU'")
    all_users = sess.rows  # combined result from both queries
```

The return value of each `sess.query()` is always the current query's result only — `sess.rows` is the accumulation point.

## Threading

`sf.rows` is thread-local — each thread sees only its own query results. For concurrent workloads, open a `Session` inside each worker:

```python
from concurrent.futures import ThreadPoolExecutor

def worker(sql):
    with sf.session() as sess:
        return sess.query(sql)

with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(worker, queries))
```

## Retry

```python
sf = ThaSnowflake(
    account="myorg",
    retry_connect=3,         # up to 3 retries (4 total attempts)
    retry_on=(OSError,),     # only retry on these exception types
    retry_delay=2.0,         # seconds between attempts
    status_cb=print,         # called with a message on each failed attempt
)
```

## API

### `ThaSnowflake(*, ...)`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `connection_name` | `str` | `"default"` | Profile name for Mode 1/2 |
| `connections_file` | `str \| None` | `None` | Path to custom connections file (Mode 2) |
| `account` | `str \| None` | `None` | Snowflake account identifier (Mode 3) |
| `user` | `str \| None` | `None` | Username (Mode 3) |
| `authenticator` | `str \| None` | `None` | `"externalbrowser"`, `"oauth"`, etc. |
| `password` | `str \| None` | `None` | Password auth (Mode 3) |
| `private_key_file` | `str \| None` | `None` | Path to `.p8` key file; `~` is expanded |
| `private_key_passphrase` | `str \| None` | `None` | Passphrase for encrypted private key |
| `token` | `str \| None` | `None` | OAuth token (Mode 3) |
| `role` | `str \| None` | `None` | Default Snowflake role |
| `warehouse` | `str \| None` | `None` | Default warehouse |
| `database` | `str \| None` | `None` | Default database |
| `schema` | `str \| None` | `None` | Default schema |
| `quiet_connect` | `bool` | `False` | Suppress connector stdout on connect |
| `status_cb` | `callable \| None` | `None` | Called with status strings (retry messages, etc.) |
| `mode` | `str` | `"app"` | Reserved — `"app"` or `"cli"` |
| `retry_connect` | `int` | `0` | Number of reconnect retries on failure |
| `retry_on` | `type \| tuple` | `()` | Exception types that trigger a retry |
| `retry_delay` | `float` | `1.0` | Seconds to wait between retry attempts |

### Methods

| Method | Returns | Description |
|--------|---------|-------------|
| `set_context(*, role, warehouse, database, schema)` | `None` | Update default context; only non-`None` values are applied |
| `build_connect_kwargs(*, role, warehouse, database, schema)` | `dict` | Return kwargs that would be passed to `snowflake.connector.connect` — useful for debugging |
| `connect(**kwargs)` | `SnowflakeConnection` | Open and return a raw connection |
| `connection(**kwargs)` | context manager | Open a connection, close it on exit |
| `session(*, accumulate=False, **kwargs)` | context manager → `Session` | Open a `Session` backed by one connection; closes on exit |
| `open_session(*, accumulate=False, **kwargs)` | `Session` | Open and return a `Session` without a context manager; caller must call `sess.close()` |
| `query(sql=None, *, file=None, params, conn, role, warehouse, database, schema)` | `dict` | Execute a SELECT; pass `sql` or `file=` (not both); returns `{"rows", "rowcount", "status"}` |
| `list_profiles()` | `list[str]` | Profile names from `connections_file` (requires Mode 2) |

### `Session`

Obtain via `sf.session()`. Not thread-safe — one `Session` per thread.

| Member | Description |
|--------|-------------|
| `query(sql=None, *, file=None, params)` | Execute a SELECT on the persistent connection; pass `sql` or `file=` (not both); returns `{"rows", "rowcount", "status"}` |
| `rows` | Running result — latest query only when `accumulate=False` (default), all queries combined when `accumulate=True` |
| `close()` | Close the underlying connection |

### `list_profiles(path)` — module-level

```python
from tha_snowflake_runner import list_profiles

names = list_profiles("~/connections.toml")  # ["default", "prod", "dev"]
```

Supports the same formats as Mode 2: `.toml`, `.ini`, `.cfg`, `.json`.

## Scope

`tha-snowflake-runner` is read-only by design — `query()` and `stream()` only. Write operations (INSERT, UPDATE, DELETE, MERGE, DDL) are intentionally not supported; use the raw connector directly for those.

## Alternatives

- **[snowflake-connector-python](https://docs.snowflake.com/en/developer-guide/python-connector/python-connector)** — the official Snowflake connector; `tha-snowflake-runner` is a thin typed convenience layer on top of it
- **[snowflake-sqlalchemy](https://docs.snowflake.com/en/developer-guide/python-connector/sqlalchemy)** — SQLAlchemy dialect for Snowflake with ORM support
- **[snowpark-python](https://docs.snowflake.com/en/developer-guide/snowpark/python/index)** — Snowflake's DataFrame/ML API for in-warehouse computation

`tha-snowflake-runner` is intentionally narrow: no ORM, no Snowpark, no async — just a thin typed wrapper for common query patterns and connection-file management.

## License

MIT
