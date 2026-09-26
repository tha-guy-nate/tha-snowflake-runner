from __future__ import annotations

import os
from typing import Any

import snowflake.connector

from tha_snowflake_runner.errors import SnowflakeError

_DEFAULT_QUERY_LABEL = "Getting data from Snowflake ..."


def _compose_label(prefix: str | None, label: str | None) -> str:
    """Build the status message: ``"<prefix>: <text>"`` where text is ``label`` or the default."""
    text = label if label is not None else _DEFAULT_QUERY_LABEL
    return f"{prefix}: {text}" if prefix else text


class Session:
    """Persistent connection for running multiple queries without reconnecting.

    Obtain via ThaSnowflake.session(). Not thread-safe — one Session per thread.
    For concurrent workloads, open a Session inside each thread-pool worker:

        def worker(sql):
            with sf.session() as sess:
                return sess.query(sql)

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(worker, queries))
    """

    rows: dict[str, Any] | None = None

    def __init__(self, conn: Any, *, status_cb: Any = None, accumulate: bool = False) -> None:
        self._conn = conn
        self._status_cb = status_cb
        self._accumulate = accumulate

    def _status(self, message: str) -> None:
        if self._status_cb is not None:
            self._status_cb(message)

    def query(
        self,
        sql: str | None = None,
        *,
        file: str | None = None,
        params: tuple[Any, ...] | list[Any] | None = None,
        desc: str | None = None,
        label: str | None = None,
        show_progress: bool = True,
    ) -> dict[str, Any]:
        """Execute a SELECT and return {"rows": list[dict], "rowcount": int, "status": None|str}.

        Pass sql as an inline string or file= as a path to a .sql file (not both).
        Emits a "Getting data from Snowflake ..." message through status_cb before the query runs.
        desc is a step prefix put at the front (desc="[1/7]" -> "[1/7]: Getting data from ...");
        label replaces the default text; show_progress=False suppresses the message.
        Sets self.rows. When accumulate=True, appends rows across calls; otherwise replaces.
        status is None on success, or an error string on Snowflake query failure.
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

        rows: list[dict[str, Any]] = []
        status: str | None = None
        cursor = self._conn.cursor(snowflake.connector.DictCursor)
        try:
            if show_progress:
                self._status(_compose_label(desc, label))
            cursor.execute(sql, params or ())
            rows = list(cursor) if cursor.description else []
        except snowflake.connector.errors.Error as exc:
            status = str(exc)
        finally:
            cursor.close()
        result: dict[str, Any] = {"rows": rows, "rowcount": len(rows), "status": status}
        if status is not None:
            return result
        if self._accumulate and self.rows is not None:
            self.rows["rows"].extend(rows)
            self.rows["rowcount"] += len(rows)
        else:
            self.rows = {"rows": list(rows), "rowcount": len(rows), "status": None}
        return result

    def close(self) -> None:
        """Close the underlying connection."""
        try:
            self._conn.close()
        except Exception:
            pass

    def __enter__(self) -> Session:
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
