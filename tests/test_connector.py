"""Tests for SnowflakeConnector."""

import sys
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from prism.connector import SnowflakeConnector


class TestEnvVarDefaults:
    def test_params_from_env(self, monkeypatch):
        monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "acct1")
        monkeypatch.setenv("SNOWFLAKE_USER", "usr")
        monkeypatch.setenv("SNOWFLAKE_PASSWORD", "pw")
        monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "wh")
        monkeypatch.setenv("SNOWFLAKE_DATABASE", "db")
        monkeypatch.setenv("SNOWFLAKE_SCHEMA", "sch")
        monkeypatch.setenv("SNOWFLAKE_ROLE", "rl")

        conn = SnowflakeConnector()
        assert conn.account == "acct1"
        assert conn.user == "usr"
        assert conn.password == "pw"
        assert conn.warehouse == "wh"
        assert conn.database == "db"
        assert conn.schema == "sch"
        assert conn.role == "rl"

    def test_explicit_params_override_env(self, monkeypatch):
        monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "env_acct")
        conn = SnowflakeConnector(account="explicit_acct")
        assert conn.account == "explicit_acct"

    def test_defaults_to_empty_string(self, monkeypatch):
        for var in [
            "SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PASSWORD",
            "SNOWFLAKE_WAREHOUSE", "SNOWFLAKE_DATABASE", "SNOWFLAKE_SCHEMA",
            "SNOWFLAKE_ROLE",
        ]:
            monkeypatch.delenv(var, raising=False)
        conn = SnowflakeConnector()
        assert conn.account == ""


@pytest.fixture
def snowflake_mocks():
    """Provide wired-up mock Snowflake objects and patch sys.modules."""
    mock_sf = MagicMock()
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.is_closed.return_value = False
    mock_conn.cursor.return_value = mock_cursor
    mock_sf.connector.connect.return_value = mock_conn
    # Default: no fetch_pandas_all, so fallback path is used
    del mock_cursor.fetch_pandas_all
    mock_cursor.description = [("col1",), ("col2",)]
    mock_cursor.fetchall.return_value = [(1, "a"), (2, "b")]
    return mock_sf, mock_conn, mock_cursor


class TestLazyConnect:
    def test_no_connection_on_init(self):
        conn = SnowflakeConnector()
        assert conn._connection is None

    def test_connect_called_on_query(self, snowflake_mocks):
        """Connection is created lazily on first query."""
        mock_sf, mock_conn, mock_cursor = snowflake_mocks

        with patch.dict(sys.modules, {"snowflake": mock_sf, "snowflake.connector": mock_sf.connector}):
            connector = SnowflakeConnector(account="test")
            result = connector.query("SELECT 1")

        mock_sf.connector.connect.assert_called_once()
        assert isinstance(result, pd.DataFrame)
        assert list(result.columns) == ["col1", "col2"]
        assert len(result) == 2

    def test_second_query_reuses_connection(self, snowflake_mocks):
        mock_sf, mock_conn, mock_cursor = snowflake_mocks
        mock_cursor.description = [("x",)]
        mock_cursor.fetchall.return_value = [(1,)]

        with patch.dict(sys.modules, {"snowflake": mock_sf, "snowflake.connector": mock_sf.connector}):
            connector = SnowflakeConnector(account="test")
            connector.query("SELECT 1")
            connector.query("SELECT 2")

        mock_sf.connector.connect.assert_called_once()

    def test_reconnects_when_closed(self, snowflake_mocks):
        """Stale/closed connections are replaced automatically."""
        mock_sf, mock_conn, mock_cursor = snowflake_mocks
        mock_cursor.description = [("x",)]
        mock_cursor.fetchall.return_value = [(1,)]

        with patch.dict(sys.modules, {"snowflake": mock_sf, "snowflake.connector": mock_sf.connector}):
            connector = SnowflakeConnector(account="test")
            connector.query("SELECT 1")
            # Simulate connection dropping
            mock_conn.is_closed.return_value = True
            connector.query("SELECT 2")

        assert mock_sf.connector.connect.call_count == 2

    def test_uses_fetch_pandas_all_when_available(self, snowflake_mocks):
        """Prefers fetch_pandas_all() for better performance."""
        mock_sf, mock_conn, mock_cursor = snowflake_mocks
        expected_df = pd.DataFrame({"x": [1, 2]})
        mock_cursor.fetch_pandas_all = MagicMock(return_value=expected_df)

        with patch.dict(sys.modules, {"snowflake": mock_sf, "snowflake.connector": mock_sf.connector}):
            connector = SnowflakeConnector(account="test")
            result = connector.query("SELECT 1")

        mock_cursor.fetch_pandas_all.assert_called_once()
        pd.testing.assert_frame_equal(result, expected_df)


class TestContextManager:
    def test_close_called_on_exit(self, snowflake_mocks):
        mock_sf, mock_conn, mock_cursor = snowflake_mocks
        mock_cursor.description = [("x",)]
        mock_cursor.fetchall.return_value = []

        with patch.dict(sys.modules, {"snowflake": mock_sf, "snowflake.connector": mock_sf.connector}):
            with SnowflakeConnector(account="test") as connector:
                connector.query("SELECT 1")

        mock_conn.close.assert_called_once()

    def test_close_without_connection_is_noop(self):
        connector = SnowflakeConnector()
        connector.close()  # should not raise


class TestMissingPackage:
    def test_import_error_on_query(self, monkeypatch):
        """Clear error when snowflake-connector-python is not installed."""
        connector = SnowflakeConnector(account="test")

        # Remove snowflake from sys.modules and make import fail
        with patch.dict(sys.modules, {"snowflake": None, "snowflake.connector": None}):
            with pytest.raises(ImportError, match="snowflake-connector-python"):
                connector.query("SELECT 1")
