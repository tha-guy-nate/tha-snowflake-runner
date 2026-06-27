import contextlib
import os
import sys
import threading
import time
from collections.abc import Generator
from typing import Any

import snowflake.connector

from tha_snowflake_runner.errors import SnowflakeError
from tha_snowflake_runner.profiles import _load_all_profiles
from tha_snowflake_runner.session import Session


@contextlib.contextmanager
def _suppress_stdout() -> Generator[None, None, None]:
    old_stdout = sys.stdout
    with open(os.devnull, "w") as devnull:
        sys.stdout = devnull
        try:
            yield
        finally:
            sys.stdout = old_stdout


class ThaSnowflake:
    """Typed Snowflake connector wrapper supporting three connection modes:

    Mode 1 — native connections.toml (default):
        ThaSnowflake(role="ANALYST", warehouse="WH")
        Delegates file lookup to the connector (respects SNOWFLAKE_HOME and OS defaults).

    Mode 2 — custom connections file:
        ThaSnowflake(connections_file="~/my_connections.toml", connection_name="prod", ...)
        Reads the named profile from a .toml, .ini/.cfg, or .json file. Use
        list_profiles() to see what profiles are available in the file.

    Mode 3 — inline:
        ThaSnowflake(account="myorg", user="me@example.com", authenticator="externalbrowser", ...)
        No file — all connection params supplied directly.

        Auth variants for Mode 3:
          externalbrowser:  authenticator="externalbrowser"  (Okta SSO, human accounts)
          password:         password="secret"                (service accounts)
          key-pair:         private_key_file="~/key.p8", private_key_passphrase="..."
          oauth token:      authenticator="oauth", token="..."

    In all modes, role/warehouse/database/schema passed here (or to connect()) override
    any values in the file.
    """

    def __init__(
        self,
        *,
        connection_name: str = "default",
        connections_file: str | None = None,
        account: str | None = None,
        user: str | None = None,
        authenticator: str | None = None,
        password: str | None = None,
        private_key_file: str | None = None,
        private_key_passphrase: str | None = None,
        token: str | None = None,
        role: str | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
        quiet_connect: bool = False,  # True suppresses connector stdout (e.g. externalbrowser SSO)
        status_cb: Any = None,
        mode: str = "app",
        retry_connect: int = 0,
        retry_on: type[Exception] | tuple[type[Exception], ...] = (),
        retry_delay: float = 1.0,
    ) -> None:
        self.connection_name = connection_name
        self.connections_file = connections_file
        self.account = account
        self.user = user
        self.authenticator = authenticator
        self.password = password
        self.private_key_file = private_key_file
        self.private_key_passphrase = private_key_passphrase
        self.token = token
        self.role = role
        self.warehouse = warehouse
        self.database = database
        self.schema = schema
        self.quiet_connect = quiet_connect
        self.status_cb = status_cb
        self.mode = mode
        self.retry_connect = retry_connect
        self.retry_on: tuple[type[Exception], ...] = (
            (retry_on,) if isinstance(retry_on, type) else tuple(retry_on)
        )
        self.retry_delay = retry_delay
        self._local = threading.local()

    @property
    def rows(self) -> dict[str, Any] | None:
        return getattr(self._local, "rows", None)

    @rows.setter
    def rows(self, value: dict[str, Any] | None) -> None:
        self._local.rows = value

    def _status(self, message: str) -> None:
        if self.status_cb is not None:
            self.status_cb(message)

    def set_context(
        self,
        *,
        role: str | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
    ) -> None:
        """Update default role/warehouse/database/schema for future connections."""
        if role is not None:
            self.role = role
        if warehouse is not None:
            self.warehouse = warehouse
        if database is not None:
            self.database = database
        if schema is not None:
            self.schema = schema

    def _resolve_context(
        self,
        role: str | None,
        warehouse: str | None,
        database: str | None,
        schema: str | None,
    ) -> tuple[str | None, str | None, str | None, str | None]:
        return (
            role if role is not None else self.role,
            warehouse if warehouse is not None else self.warehouse,
            database if database is not None else self.database,
            schema if schema is not None else self.schema,
        )

    def _read_profile(self) -> dict[str, Any]:
        assert self.connections_file is not None
        path = os.path.expanduser(self.connections_file)
        if not os.path.exists(path):
            raise SnowflakeError(f"connections_file not found: {path}")
        profiles = _load_all_profiles(path)
        profile = profiles.get(self.connection_name)
        if profile is None:
            raise SnowflakeError(f"Profile '{self.connection_name}' not found in {path}")
        return profile

    def list_profiles(self) -> list[str]:
        """Return available profile names from connections_file."""
        if self.connections_file is None:
            raise SnowflakeError("list_profiles requires connections_file to be set")
        path = os.path.expanduser(self.connections_file)
        if not os.path.exists(path):
            raise SnowflakeError(f"connections_file not found: {path}")
        return list(_load_all_profiles(path).keys())

    def build_connect_kwargs(
        self,
        *,
        role: str | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
    ) -> dict[str, Any]:
        """Return kwargs for snowflake.connector.connect. Useful for debugging."""
        role, warehouse, database, schema = self._resolve_context(role, warehouse, database, schema)

        kwargs: dict[str, Any] = {}

        if self.account is not None:
            kwargs["account"] = self.account
            if self.user is not None:
                kwargs["user"] = self.user
            if self.authenticator is not None:
                kwargs["authenticator"] = self.authenticator
            if self.password is not None:
                kwargs["password"] = self.password
            if self.private_key_file is not None:
                kwargs["private_key_file"] = os.path.expanduser(self.private_key_file)
                if self.private_key_passphrase is not None:
                    kwargs["private_key_file_pwd"] = self.private_key_passphrase
            if self.token is not None:
                kwargs["token"] = self.token
        elif self.connections_file is not None:
            kwargs.update(self._read_profile())
        else:
            kwargs["connection_name"] = self.connection_name

        if role is not None:
            kwargs["role"] = role
        if warehouse is not None:
            kwargs["warehouse"] = warehouse
        if database is not None:
            kwargs["database"] = database
        if schema is not None:
            kwargs["schema"] = schema

        return kwargs

    def connect(self, **kwargs: Any) -> Any:
        """Return a raw SnowflakeConnection.

        Retries up to retry_connect times when the exception matches retry_on.
        Waits retry_delay seconds between attempts.
        """
        connect_kwargs = self.build_connect_kwargs(**kwargs)
        last_exc: BaseException | None = None
        for attempt in range(self.retry_connect + 1):
            ctx: Any = _suppress_stdout() if self.quiet_connect else contextlib.nullcontext()
            try:
                with ctx:
                    return snowflake.connector.connect(**connect_kwargs)
            except self.retry_on as exc:
                last_exc = exc
                if attempt < self.retry_connect:
                    self._status(
                        f"Connection attempt {attempt + 1} failed "
                        f"({type(exc).__name__}), retrying in {self.retry_delay}s..."
                    )
                    if self.retry_delay > 0:
                        time.sleep(self.retry_delay)
        assert last_exc is not None
        raise last_exc

    @contextlib.contextmanager
    def connection(self, **kwargs: Any) -> Generator[Any, None, None]:
        """Context manager wrapping connect() — closes the connection on exit."""
        conn = self.connect(**kwargs)
        try:
            yield conn
        finally:
            try:
                conn.close()
            except Exception:
                pass

    @contextlib.contextmanager
    def session(self, *, accumulate: bool = False, **kwargs: Any) -> Generator[Session, None, None]:
        """Open a persistent Session for multiple queries on one connection.

        Pass accumulate=True to append self.rows across query() calls instead of replacing.
        One Session per thread — do not share across threads. For concurrent
        workloads, call sf.session() inside each thread-pool worker.
        """
        with self.connection(**kwargs) as conn:
            yield Session(conn, status_cb=self.status_cb, accumulate=accumulate)

    def open_session(self, *, accumulate: bool = False, **kwargs: Any) -> Session:
        """Open and return a Session without a context manager.

        Caller is responsible for calling sess.close() when done.
        Use sf.session() instead if you want automatic cleanup on exit.
        """
        conn = self.connect(**kwargs)
        return Session(conn, status_cb=self.status_cb, accumulate=accumulate)

    def query(
        self,
        sql: str | None = None,
        *,
        file: str | None = None,
        params: tuple[Any, ...] | list[Any] | None = None,
        conn: Any = None,
        role: str | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
    ) -> dict[str, Any]:
        """Execute a SELECT and return {"rows": list[dict], "rowcount": int, "status": None|str}.

        Pass sql as an inline string or file= as a path to a .sql file (not both).
        Pass conn to reuse an existing connection; otherwise a new one is opened and closed.
        Sets self.rows.
        """
        if sql is not None and file is not None:
            raise SnowflakeError("Provide sql or file, not both")
        if file is not None:
            expanded = os.path.expanduser(file)
            if not os.path.exists(expanded):
                raise SnowflakeError(f"SQL file not found: {expanded}")
            with open(expanded) as fh:
                sql = fh.read().strip()
        if sql is None:
            raise SnowflakeError("Provide either sql or file")

        def _run(c: Any) -> dict[str, Any]:
            cursor = c.cursor(snowflake.connector.DictCursor)
            try:
                cursor.execute(sql, params or ())
                rows: list[dict[str, Any]] = cursor.fetchall()
                return {"rows": rows, "rowcount": len(rows), "status": None}
            except snowflake.connector.errors.Error as exc:
                return {"rows": [], "rowcount": 0, "status": str(exc)}
            finally:
                cursor.close()

        if conn is not None:
            result = _run(conn)
            self.rows = result
            return result

        with self.connection(role=role, warehouse=warehouse, database=database, schema=schema) as c:
            result = _run(c)
            self.rows = result
            return result
