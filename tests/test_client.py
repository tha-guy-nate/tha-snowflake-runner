import os
from unittest.mock import MagicMock, mock_open, patch

import pytest

from tha_snowflake_runner import SnowflakeError, ThaSnowflake

# ---------------------------------------------------------------------------
# Context resolution / set_context
# ---------------------------------------------------------------------------


class TestContextResolution:
    def test_defaults_to_instance_attrs(self):
        sf = ThaSnowflake(role="R", warehouse="W", database="DB", schema="SCH")
        assert sf._resolve_context(None, None, None, None) == ("R", "W", "DB", "SCH")

    def test_per_call_args_override_instance(self):
        sf = ThaSnowflake(role="R", warehouse="W")
        assert sf._resolve_context("R2", "W2", None, None) == ("R2", "W2", None, None)

    def test_set_context_updates_instance_attrs(self):
        sf = ThaSnowflake(role="R", warehouse="W")
        sf.set_context(role="ADMIN", database="DEV")
        assert sf.role == "ADMIN"
        assert sf.database == "DEV"
        assert sf.warehouse == "W"  # unchanged

    def test_set_context_ignores_none_args(self):
        sf = ThaSnowflake(role="R", warehouse="W", database="DB")
        sf.set_context(database=None)
        assert sf.database == "DB"  # unchanged


# ---------------------------------------------------------------------------
# build_connect_kwargs — mode 1: native connections.toml
# ---------------------------------------------------------------------------


class TestBuildConnectKwargsNative:
    def test_passes_connection_name(self):
        sf = ThaSnowflake()
        kwargs = sf.build_connect_kwargs()
        assert kwargs["connection_name"] == "default"

    def test_custom_connection_name(self):
        sf = ThaSnowflake(connection_name="prod")
        kwargs = sf.build_connect_kwargs()
        assert kwargs["connection_name"] == "prod"

    def test_runtime_role_warehouse_included(self):
        sf = ThaSnowflake(role="ANALYST", warehouse="WH")
        kwargs = sf.build_connect_kwargs()
        assert kwargs["role"] == "ANALYST"
        assert kwargs["warehouse"] == "WH"

    def test_none_context_omitted(self):
        sf = ThaSnowflake()
        kwargs = sf.build_connect_kwargs()
        assert "role" not in kwargs
        assert "warehouse" not in kwargs
        assert "database" not in kwargs
        assert "schema" not in kwargs

    def test_per_call_role_overrides_instance(self):
        sf = ThaSnowflake(role="R", warehouse="W")
        kwargs = sf.build_connect_kwargs(role="ADMIN")
        assert kwargs["role"] == "ADMIN"
        assert kwargs["warehouse"] == "W"


# ---------------------------------------------------------------------------
# build_connect_kwargs — mode 2: custom TOML file
# ---------------------------------------------------------------------------

_TOML_FLAT = (
    b"[default]\naccount = 'myorg'\nuser = 'a@b.com'\nauthenticator = 'externalbrowser'\n"
)
_TOML_NESTED = b"[connections.default]\naccount = 'myorg'\nuser = 'a@b.com'\n"
_TOML_MULTI = b"[default]\naccount = 'dev'\n\n[prod]\naccount = 'prodorg'\n"

_INI_FLAT = "[default]\naccount = myorg\nuser = a@b.com\nauthenticator = externalbrowser\n"
_INI_MULTI = "[default]\naccount = dev\n\n[prod]\naccount = prodorg\n"

_JSON_FLAT = '{"default": {"account": "myorg", "user": "a@b.com"}}'
_JSON_NESTED = '{"connections": {"default": {"account": "myorg", "user": "a@b.com"}}}'
_JSON_MULTI = '{"default": {"account": "dev"}, "prod": {"account": "prodorg"}}'


def _file_patches(read_data: bytes | str):
    """Return a context manager that fakes os.path.exists=True and open() for a connections file."""
    import contextlib

    @contextlib.contextmanager
    def _ctx():
        with patch("os.path.exists", return_value=True), \
                patch("builtins.open", mock_open(read_data=read_data)):
            yield

    return _ctx()


class TestBuildConnectKwargsFile:
    def _sf(self, **kwargs):
        return ThaSnowflake(connections_file="~/my_connections.toml", **kwargs)

    def test_reads_flat_profile(self):
        sf = self._sf()
        with _file_patches(_TOML_FLAT):
            kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "myorg"
        assert kwargs["user"] == "a@b.com"
        assert "connection_name" not in kwargs

    def test_reads_nested_connections_profile(self):
        sf = self._sf()
        with _file_patches(_TOML_NESTED):
            kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "myorg"

    def test_named_profile(self):
        sf = ThaSnowflake(connections_file="~/f.toml", connection_name="prod")
        with _file_patches(_TOML_MULTI):
            kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "prodorg"

    def test_missing_profile_raises(self):
        sf = ThaSnowflake(connections_file="~/f.toml", connection_name="missing")
        with _file_patches(_TOML_FLAT):
            with pytest.raises(SnowflakeError, match="missing"):
                sf.build_connect_kwargs()

    def test_missing_file_raises(self):
        sf = self._sf()
        with patch("os.path.exists", return_value=False):
            with pytest.raises(SnowflakeError, match="not found"):
                sf.build_connect_kwargs()

    def test_runtime_context_overrides_file(self):
        toml = b"[default]\naccount = 'myorg'\nrole = 'FILE_ROLE'\nwarehouse = 'FILE_WH'\n"
        sf = ThaSnowflake(
            connections_file="~/f.toml", role="OVERRIDE_ROLE", warehouse="OVERRIDE_WH"
        )
        with _file_patches(toml):
            kwargs = sf.build_connect_kwargs()
        assert kwargs["role"] == "OVERRIDE_ROLE"
        assert kwargs["warehouse"] == "OVERRIDE_WH"


class TestBuildConnectKwargsIni:
    def _sf(self, name="default", **kwargs):
        return ThaSnowflake(
            connections_file="~/my_connections.ini", connection_name=name, **kwargs
        )

    def test_reads_flat_profile(self):
        sf = self._sf()
        with _file_patches(_INI_FLAT):
            kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "myorg"
        assert kwargs["user"] == "a@b.com"
        assert "connection_name" not in kwargs

    def test_named_profile(self):
        sf = self._sf(name="prod")
        with _file_patches(_INI_MULTI):
            kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "prodorg"

    def test_missing_profile_raises(self):
        sf = self._sf(name="missing")
        with _file_patches(_INI_FLAT):
            with pytest.raises(SnowflakeError, match="missing"):
                sf.build_connect_kwargs()

    def test_cfg_extension_also_supported(self):
        sf = ThaSnowflake(connections_file="~/my.cfg")
        with _file_patches(_INI_FLAT):
            kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "myorg"


class TestBuildConnectKwargsJson:
    def _sf(self, name="default", **kwargs):
        return ThaSnowflake(
            connections_file="~/my_connections.json", connection_name=name, **kwargs
        )

    def test_reads_flat_profile(self):
        sf = self._sf()
        with _file_patches(_JSON_FLAT):
            kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "myorg"
        assert kwargs["user"] == "a@b.com"
        assert "connection_name" not in kwargs

    def test_reads_nested_connections_profile(self):
        sf = self._sf()
        with _file_patches(_JSON_NESTED):
            kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "myorg"

    def test_named_profile(self):
        sf = self._sf(name="prod")
        with _file_patches(_JSON_MULTI):
            kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "prodorg"

    def test_missing_profile_raises(self):
        sf = self._sf(name="missing")
        with _file_patches(_JSON_FLAT):
            with pytest.raises(SnowflakeError, match="missing"):
                sf.build_connect_kwargs()


class TestUnsupportedFormat:
    def test_unsupported_extension_raises(self):
        sf = ThaSnowflake(connections_file="~/connections.csv")
        with patch("os.path.exists", return_value=True):
            with pytest.raises(SnowflakeError, match="Unsupported"):
                sf.build_connect_kwargs()


# ---------------------------------------------------------------------------
# list_profiles
# ---------------------------------------------------------------------------


class TestListProfiles:
    def test_toml_returns_profile_names(self):
        sf = ThaSnowflake(connections_file="~/f.toml")
        with _file_patches(_TOML_MULTI):
            names = sf.list_profiles()
        assert names == ["default", "prod"]

    def test_toml_nested_connections_style(self):
        toml = b"[connections.alpha]\naccount = 'a'\n\n[connections.beta]\naccount = 'b'\n"
        sf = ThaSnowflake(connections_file="~/f.toml")
        with _file_patches(toml):
            names = sf.list_profiles()
        assert names == ["alpha", "beta"]

    def test_ini_returns_profile_names(self):
        sf = ThaSnowflake(connections_file="~/f.ini")
        with _file_patches(_INI_MULTI):
            names = sf.list_profiles()
        assert names == ["default", "prod"]

    def test_json_returns_profile_names(self):
        sf = ThaSnowflake(connections_file="~/f.json")
        with _file_patches(_JSON_MULTI):
            names = sf.list_profiles()
        assert names == ["default", "prod"]

    def test_no_connections_file_raises(self):
        sf = ThaSnowflake()
        with pytest.raises(SnowflakeError, match="connections_file"):
            sf.list_profiles()

    def test_missing_file_raises(self):
        sf = ThaSnowflake(connections_file="~/f.toml")
        with patch("os.path.exists", return_value=False):
            with pytest.raises(SnowflakeError, match="not found"):
                sf.list_profiles()


# ---------------------------------------------------------------------------
# build_connect_kwargs — mode 3: inline
# ---------------------------------------------------------------------------


class TestBuildConnectKwargsInline:
    def test_passes_account(self):
        sf = ThaSnowflake(account="myorg", user="a@b.com", authenticator="externalbrowser")
        kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "myorg"
        assert kwargs["user"] == "a@b.com"
        assert kwargs["authenticator"] == "externalbrowser"
        assert "connection_name" not in kwargs

    def test_account_only_no_user_or_authenticator(self):
        sf = ThaSnowflake(account="myorg")
        kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "myorg"
        assert "user" not in kwargs
        assert "authenticator" not in kwargs

    def test_inline_takes_priority_over_connections_file(self):
        sf = ThaSnowflake(account="myorg", connections_file="~/f.toml")
        kwargs = sf.build_connect_kwargs()
        assert kwargs["account"] == "myorg"
        assert "connection_name" not in kwargs

    def test_runtime_context_included(self):
        sf = ThaSnowflake(account="myorg", role="ANALYST", warehouse="WH", database="DB")
        kwargs = sf.build_connect_kwargs()
        assert kwargs["role"] == "ANALYST"
        assert kwargs["warehouse"] == "WH"
        assert kwargs["database"] == "DB"

    def test_password_auth(self):
        sf = ThaSnowflake(account="myorg", user="svc@b.com", password="s3cr3t")
        kwargs = sf.build_connect_kwargs()
        assert kwargs["password"] == "s3cr3t"
        assert "authenticator" not in kwargs

    def test_keypair_auth_expands_path(self):
        sf = ThaSnowflake(
            account="myorg", user="svc@b.com", private_key_file="~/keys/rsa_key.p8"
        )
        kwargs = sf.build_connect_kwargs()
        assert kwargs["private_key_file"] == os.path.expanduser("~/keys/rsa_key.p8")
        assert "private_key_file_pwd" not in kwargs

    def test_keypair_auth_with_passphrase(self):
        sf = ThaSnowflake(
            account="myorg",
            user="svc@b.com",
            private_key_file="~/keys/rsa_key.p8",
            private_key_passphrase="mypass",
        )
        kwargs = sf.build_connect_kwargs()
        assert kwargs["private_key_file_pwd"] == "mypass"

    def test_oauth_token_auth(self):
        sf = ThaSnowflake(account="myorg", authenticator="oauth", token="tok123")
        kwargs = sf.build_connect_kwargs()
        assert kwargs["authenticator"] == "oauth"
        assert kwargs["token"] == "tok123"

    def test_token_omitted_when_none(self):
        sf = ThaSnowflake(account="myorg", authenticator="externalbrowser")
        kwargs = sf.build_connect_kwargs()
        assert "token" not in kwargs


# ---------------------------------------------------------------------------
# connect / connection context manager
# ---------------------------------------------------------------------------


class TestConnect:
    def _sf(self):
        return ThaSnowflake(account="myorg", user="a@b.com", quiet_connect=False)

    def test_connect_calls_snowflake_connector(self):
        sf = self._sf()
        mock_conn = MagicMock()
        with patch("snowflake.connector.connect", return_value=mock_conn) as mock_connect:
            conn = sf.connect()
        mock_connect.assert_called_once()
        assert conn is mock_conn

    def test_connection_closes_on_normal_exit(self):
        sf = self._sf()
        mock_conn = MagicMock()
        with patch("snowflake.connector.connect", return_value=mock_conn):
            with sf.connection():
                pass
        mock_conn.close.assert_called_once()

    def test_connection_closes_on_exception(self):
        sf = self._sf()
        mock_conn = MagicMock()
        with patch("snowflake.connector.connect", return_value=mock_conn):
            with pytest.raises(RuntimeError):
                with sf.connection():
                    raise RuntimeError("boom")
        mock_conn.close.assert_called_once()

    def test_connection_swallows_close_error(self):
        sf = self._sf()
        mock_conn = MagicMock()
        mock_conn.close.side_effect = Exception("close failed")
        with patch("snowflake.connector.connect", return_value=mock_conn):
            with sf.connection():
                pass  # should not raise even if close() fails

    def test_native_mode_passes_connection_name_to_connector(self):
        sf = ThaSnowflake(connection_name="prod", quiet_connect=False)
        mock_conn = MagicMock()
        with patch("snowflake.connector.connect", return_value=mock_conn) as mock_connect:
            sf.connect()
        call_kwargs = mock_connect.call_args.kwargs
        assert call_kwargs.get("connection_name") == "prod"


# ---------------------------------------------------------------------------
# connect — retry
# ---------------------------------------------------------------------------


class TestConnectRetry:
    def _sf(self, **kwargs):
        return ThaSnowflake(account="myorg", quiet_connect=False, **kwargs)

    def test_no_retry_by_default(self):
        sf = self._sf()
        mock_connect = MagicMock(side_effect=OSError("timeout"))
        with patch("snowflake.connector.connect", mock_connect):
            with pytest.raises(OSError):
                sf.connect()
        assert mock_connect.call_count == 1

    def test_retries_on_matching_error_and_succeeds(self):
        sf = self._sf(retry_connect=2, retry_on=(OSError,), retry_delay=0.0)
        good_conn = MagicMock()
        mock_connect = MagicMock(side_effect=[OSError("fail"), good_conn])
        with patch("snowflake.connector.connect", mock_connect):
            conn = sf.connect()
        assert mock_connect.call_count == 2
        assert conn is good_conn

    def test_raises_after_all_retries_exhausted(self):
        sf = self._sf(retry_connect=2, retry_on=(OSError,), retry_delay=0.0)
        with patch("snowflake.connector.connect", side_effect=OSError("fail")):
            with pytest.raises(OSError):
                sf.connect()

    def test_total_attempts_is_retry_connect_plus_one(self):
        sf = self._sf(retry_connect=3, retry_on=(OSError,), retry_delay=0.0)
        mock_connect = MagicMock(side_effect=OSError("fail"))
        with patch("snowflake.connector.connect", mock_connect):
            with pytest.raises(OSError):
                sf.connect()
        assert mock_connect.call_count == 4

    def test_does_not_retry_on_non_matching_error(self):
        sf = self._sf(retry_connect=3, retry_on=(OSError,), retry_delay=0.0)
        mock_connect = MagicMock(side_effect=ValueError("bad"))
        with patch("snowflake.connector.connect", mock_connect):
            with pytest.raises(ValueError):
                sf.connect()
        assert mock_connect.call_count == 1

    def test_single_exception_class_accepted(self):
        sf = self._sf(retry_connect=1, retry_on=OSError, retry_delay=0.0)
        good_conn = MagicMock()
        mock_connect = MagicMock(side_effect=[OSError("fail"), good_conn])
        with patch("snowflake.connector.connect", mock_connect):
            sf.connect()
        assert mock_connect.call_count == 2

    def test_retry_delay_passed_to_sleep(self):
        sf = self._sf(retry_connect=1, retry_on=(OSError,), retry_delay=2.5)
        mock_connect = MagicMock(side_effect=[OSError("fail"), MagicMock()])
        with patch("snowflake.connector.connect", mock_connect), \
                patch("time.sleep") as mock_sleep:
            sf.connect()
        mock_sleep.assert_called_once_with(2.5)

    def test_no_sleep_when_delay_is_zero(self):
        sf = self._sf(retry_connect=1, retry_on=(OSError,), retry_delay=0.0)
        mock_connect = MagicMock(side_effect=[OSError("fail"), MagicMock()])
        with patch("snowflake.connector.connect", mock_connect), \
                patch("time.sleep") as mock_sleep:
            sf.connect()
        mock_sleep.assert_not_called()

    def test_status_cb_called_on_each_failed_attempt(self):
        messages: list[str] = []
        sf = self._sf(
            retry_connect=2, retry_on=(OSError,), retry_delay=0.0,
            status_cb=messages.append,
        )
        mock_connect = MagicMock(side_effect=[OSError("f1"), OSError("f2"), MagicMock()])
        with patch("snowflake.connector.connect", mock_connect):
            sf.connect()
        assert len(messages) == 2
        assert all("retrying" in m.lower() for m in messages)


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


class TestQuery:
    def _conn_with_rows(self, rows):
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.fetchall.return_value = rows
        return mock_conn

    def test_returns_dict_envelope(self):
        sf = ThaSnowflake()
        rows = [{"ID": "u1", "NAME": "Alice"}, {"ID": "u2", "NAME": "Bob"}]
        result = sf.query("SELECT id, name FROM users", conn=self._conn_with_rows(rows))
        assert result == {"rows": rows, "rowcount": 2, "status": None}

    def test_sets_self_rows(self):
        sf = ThaSnowflake()
        rows = [{"X": 1}]
        sf.query("SELECT 1 AS x", conn=self._conn_with_rows(rows))
        assert sf.rows == {"rows": rows, "rowcount": 1, "status": None}

    def test_empty_result(self):
        sf = ThaSnowflake()
        result = sf.query("SELECT 1 WHERE 1=0", conn=self._conn_with_rows([]))
        assert result == {"rows": [], "rowcount": 0, "status": None}

    def test_repeated_calls_replace_rows(self):
        sf = ThaSnowflake()
        sf.query("SELECT 1", conn=self._conn_with_rows([{"N": 1}]))
        sf.query("SELECT 2", conn=self._conn_with_rows([{"N": 2}, {"N": 3}]))
        assert sf.rows == {"rows": [{"N": 2}, {"N": 3}], "rowcount": 2, "status": None}

    def test_params_passed_to_cursor(self):
        sf = ThaSnowflake()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.fetchall.return_value = []
        sf.query("SELECT * FROM t WHERE id = %s", params=("u1",), conn=mock_conn)
        mock_conn.cursor.return_value.execute.assert_called_once_with(
            "SELECT * FROM t WHERE id = %s", ("u1",)
        )

    def test_cursor_closed_after_query(self):
        sf = ThaSnowflake()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.fetchall.return_value = []
        sf.query("SELECT 1", conn=mock_conn)
        mock_conn.cursor.return_value.close.assert_called_once()

    def test_query_error_sets_status(self):
        import snowflake.connector.errors
        sf = ThaSnowflake()
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.execute.side_effect = snowflake.connector.errors.Error(
            "SQL compilation error"
        )
        result = sf.query("BAD SQL", conn=mock_conn)
        assert result == {"rows": [], "rowcount": 0, "status": "SQL compilation error"}

    def test_no_sql_or_file_raises(self):
        sf = ThaSnowflake()
        with pytest.raises(SnowflakeError, match="sql or file"):
            sf.query()

    def test_both_sql_and_file_raises(self):
        sf = ThaSnowflake()
        with pytest.raises(SnowflakeError, match="not both"):
            sf.query("SELECT 1", file="q.sql")


class TestQueryFile:
    def _conn_with_rows(self, rows):
        mock_conn = MagicMock()
        mock_conn.cursor.return_value.fetchall.return_value = rows
        return mock_conn

    def test_file_sql_executed(self):
        sf = ThaSnowflake()
        mock_conn = self._conn_with_rows([{"N": 1}])
        with patch("os.path.exists", return_value=True), \
                patch("builtins.open", mock_open(read_data="SELECT 1 AS n")):
            result = sf.query(file="queries/count.sql", conn=mock_conn)
        assert result == {"rows": [{"N": 1}], "rowcount": 1, "status": None}
        mock_conn.cursor.return_value.execute.assert_called_once_with("SELECT 1 AS n", ())

    def test_file_sql_stripped(self):
        sf = ThaSnowflake()
        mock_conn = self._conn_with_rows([])
        with patch("os.path.exists", return_value=True), \
                patch("builtins.open", mock_open(read_data="\n  SELECT 1  \n")):
            sf.query(file="q.sql", conn=mock_conn)
        mock_conn.cursor.return_value.execute.assert_called_once_with("SELECT 1", ())

    def test_missing_file_raises(self):
        sf = ThaSnowflake()
        with patch("os.path.exists", return_value=False):
            with pytest.raises(SnowflakeError, match="not found"):
                sf.query(file="missing.sql", conn=MagicMock())
