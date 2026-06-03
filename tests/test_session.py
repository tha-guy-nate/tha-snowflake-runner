import threading
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, mock_open, patch

import pytest

from tha_snowflake_runner import Session, SnowflakeError, ThaSnowflake

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_conn(rows=None, rowcount=0):
    conn = MagicMock()
    conn.cursor.return_value.fetchall.return_value = rows or []
    conn.cursor.return_value.rowcount = rowcount
    return conn


# ---------------------------------------------------------------------------
# Session.query
# ---------------------------------------------------------------------------


class TestSessionQuery:
    def test_returns_dict_envelope(self):
        rows = [{"ID": "u1"}, {"ID": "u2"}]
        sess = Session(_mock_conn(rows=rows))
        assert sess.query("SELECT id FROM users") == {"rows": rows, "rowcount": 2, "status": None}

    def test_sets_rows(self):
        rows = [{"X": 1}]
        sess = Session(_mock_conn(rows=rows))
        sess.query("SELECT 1 AS x")
        assert sess.rows == {"rows": rows, "rowcount": 1, "status": None}

    def test_empty_result(self):
        sess = Session(_mock_conn(rows=[]))
        assert sess.query("SELECT 1 WHERE 1=0") == {"rows": [], "rowcount": 0, "status": None}

    def test_params_forwarded(self):
        conn = _mock_conn()
        sess = Session(conn)
        sess.query("SELECT * FROM t WHERE id = %s", params=("u1",))
        conn.cursor.return_value.execute.assert_called_once_with(
            "SELECT * FROM t WHERE id = %s", ("u1",)
        )

    def test_cursor_closed(self):
        conn = _mock_conn()
        sess = Session(conn)
        sess.query("SELECT 1")
        conn.cursor.return_value.close.assert_called_once()

    def test_default_replace_on_repeated_calls(self):
        conn = _mock_conn()
        conn.cursor.return_value.fetchall.side_effect = [[{"X": 1}], [{"X": 2}]]
        sess = Session(conn)
        sess.query("SELECT 1")
        sess.query("SELECT 2")
        assert sess.rows == {"rows": [{"X": 2}], "rowcount": 1, "status": None}

    def test_accumulate_appends_rows(self):
        conn = _mock_conn()
        conn.cursor.return_value.fetchall.side_effect = [
            [{"X": 1}],
            [{"X": 2}, {"X": 3}],
        ]
        sess = Session(conn, accumulate=True)
        sess.query("SELECT 1")
        sess.query("SELECT 2")
        assert sess.rows == {"rows": [{"X": 1}, {"X": 2}, {"X": 3}], "rowcount": 3, "status": None}

    def test_accumulate_return_value_is_current_query_only(self):
        conn = _mock_conn()
        conn.cursor.return_value.fetchall.side_effect = [[{"X": 1}], [{"X": 2}]]
        sess = Session(conn, accumulate=True)
        sess.query("SELECT 1")
        result = sess.query("SELECT 2")
        assert result == {"rows": [{"X": 2}], "rowcount": 1, "status": None}

    def test_query_error_returns_status_string(self):
        import snowflake.connector.errors
        conn = _mock_conn()
        conn.cursor.return_value.execute.side_effect = snowflake.connector.errors.Error(
            "bad query"
        )
        sess = Session(conn)
        result = sess.query("BAD SQL")
        assert result == {"rows": [], "rowcount": 0, "status": "bad query"}

    def test_no_sql_or_file_raises(self):
        sess = Session(_mock_conn())
        with pytest.raises(SnowflakeError, match="sql or file"):
            sess.query()

    def test_both_sql_and_file_raises(self):
        sess = Session(_mock_conn())
        with pytest.raises(SnowflakeError, match="not both"):
            sess.query("SELECT 1", file="q.sql")

    def test_file_sql_executed(self):
        conn = _mock_conn(rows=[{"N": 1}])
        sess = Session(conn)
        with patch("os.path.exists", return_value=True), \
                patch("builtins.open", mock_open(read_data="SELECT 1 AS n")):
            result = sess.query(file="queries/count.sql")
        assert result == {"rows": [{"N": 1}], "rowcount": 1, "status": None}
        conn.cursor.return_value.execute.assert_called_once_with("SELECT 1 AS n", ())

    def test_file_sql_stripped(self):
        conn = _mock_conn(rows=[])
        sess = Session(conn)
        with patch("os.path.exists", return_value=True), \
                patch("builtins.open", mock_open(read_data="\n  SELECT 1  \n")):
            sess.query(file="q.sql")
        conn.cursor.return_value.execute.assert_called_once_with("SELECT 1", ())

    def test_missing_file_raises(self):
        sess = Session(_mock_conn())
        with patch("os.path.exists", return_value=False):
            with pytest.raises(SnowflakeError, match="not found"):
                sess.query(file="missing.sql")


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


class TestSessionLifecycle:
    def test_close_closes_connection(self):
        conn = _mock_conn()
        sess = Session(conn)
        sess.close()
        conn.close.assert_called_once()

    def test_close_swallows_error(self):
        conn = _mock_conn()
        conn.close.side_effect = Exception("close failed")
        sess = Session(conn)
        sess.close()  # must not raise

    def test_context_manager_closes_on_normal_exit(self):
        conn = _mock_conn()
        with Session(conn):
            pass
        conn.close.assert_called_once()

    def test_context_manager_closes_on_exception(self):
        conn = _mock_conn()
        with pytest.raises(RuntimeError):
            with Session(conn):
                raise RuntimeError("boom")
        conn.close.assert_called_once()

    def test_context_manager_returns_session(self):
        conn = _mock_conn()
        with Session(conn) as sess:
            assert isinstance(sess, Session)


# ---------------------------------------------------------------------------
# ThaSnowflake.session()
# ---------------------------------------------------------------------------


class TestThaSnowflakeOpenSession:
    def _sf(self):
        return ThaSnowflake(account="myorg", quiet_connect=False)

    def test_returns_session_instance(self):
        sf = self._sf()
        mock_conn = MagicMock()
        with patch("snowflake.connector.connect", return_value=mock_conn):
            sess = sf.open_session()
        assert isinstance(sess, Session)
        sess.close()

    def test_session_can_query(self):
        sf = self._sf()
        mock_conn = _mock_conn(rows=[{"N": 1}])
        with patch("snowflake.connector.connect", return_value=mock_conn):
            sess = sf.open_session()
        result = sess.query("SELECT 1 AS n")
        assert result == {"rows": [{"N": 1}], "rowcount": 1, "status": None}
        sess.close()

    def test_close_closes_connection(self):
        sf = self._sf()
        mock_conn = MagicMock()
        with patch("snowflake.connector.connect", return_value=mock_conn):
            sess = sf.open_session()
        sess.close()
        mock_conn.close.assert_called_once()

    def test_passes_context_to_connection(self):
        sf = self._sf()
        mock_conn = MagicMock()
        with patch("snowflake.connector.connect", return_value=mock_conn) as mock_connect:
            sess = sf.open_session(role="ANALYST", warehouse="WH")
            sess.close()
        call_kwargs = mock_connect.call_args.kwargs
        assert call_kwargs.get("role") == "ANALYST"
        assert call_kwargs.get("warehouse") == "WH"


class TestThaSnowflakeSession:
    def _sf(self):
        return ThaSnowflake(account="myorg", quiet_connect=False)

    def test_session_yields_session_instance(self):
        sf = self._sf()
        mock_conn = MagicMock()
        with patch("snowflake.connector.connect", return_value=mock_conn):
            with sf.session() as sess:
                assert isinstance(sess, Session)

    def test_session_closes_connection_on_exit(self):
        sf = self._sf()
        mock_conn = MagicMock()
        with patch("snowflake.connector.connect", return_value=mock_conn):
            with sf.session():
                pass
        mock_conn.close.assert_called_once()

    def test_session_multiple_queries_one_connection(self):
        sf = self._sf()
        mock_conn = _mock_conn(rows=[{"N": 1}])
        with patch("snowflake.connector.connect", return_value=mock_conn) as mock_connect:
            with sf.session() as sess:
                sess.query("SELECT 1 AS n")
                sess.query("SELECT 1 AS n")
        mock_connect.assert_called_once()

    def test_session_passes_context_to_connection(self):
        sf = ThaSnowflake(account="myorg", quiet_connect=False)
        mock_conn = MagicMock()
        with patch("snowflake.connector.connect", return_value=mock_conn) as mock_connect:
            with sf.session(role="ANALYST", warehouse="WH"):
                pass
        call_kwargs = mock_connect.call_args.kwargs
        assert call_kwargs.get("role") == "ANALYST"
        assert call_kwargs.get("warehouse") == "WH"


# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------


class TestThreadSafety:
    def test_rows_is_thread_local(self):
        """Two threads writing sf.rows see only their own values."""
        sf = ThaSnowflake()
        results: dict[int, object] = {}
        barrier = threading.Barrier(2)

        def thread_fn(thread_id: int, value: object) -> None:
            sf.rows = value  # type: ignore[assignment]
            barrier.wait()
            results[thread_id] = sf.rows

        t1 = threading.Thread(target=thread_fn, args=(1, [{"thread": 1}]))
        t2 = threading.Thread(target=thread_fn, args=(2, [{"thread": 2}]))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results[1] == [{"thread": 1}]
        assert results[2] == [{"thread": 2}]

    def test_concurrent_sessions_get_separate_connections(self):
        """Each thread's sf.session() opens its own connection."""
        sf = ThaSnowflake(account="myorg", quiet_connect=False)
        connections_used: list[MagicMock] = []
        lock = threading.Lock()

        def worker(_: int) -> None:
            mock_conn = _mock_conn(rows=[])
            with patch("snowflake.connector.connect", return_value=mock_conn):
                with sf.session() as sess:
                    sess.query("SELECT 1")
            with lock:
                connections_used.append(mock_conn)

        with ThreadPoolExecutor(max_workers=4) as pool:
            list(pool.map(worker, range(4)))

        assert len(connections_used) == 4
        assert len({id(c) for c in connections_used}) == 4  # all distinct

    def test_main_thread_rows_unaffected_by_session_thread(self):
        """Session.rows in a worker thread does not bleed into sf.rows on main thread."""
        sf = ThaSnowflake()
        sf.rows = [{"main": True}]  # type: ignore[list-item]

        def worker() -> None:
            mock_conn = _mock_conn(rows=[{"worker": True}])
            with patch("snowflake.connector.connect", return_value=mock_conn):
                with sf.session(role="R") as sess:
                    sess.query("SELECT 1")
                    # session has its own rows, not sf.rows
                    assert sess.rows == {"rows": [{"worker": True}], "rowcount": 1, "status": None}

        t = threading.Thread(target=worker)
        t.start()
        t.join()

        # main thread sf.rows unchanged
        assert sf.rows == [{"main": True}]
