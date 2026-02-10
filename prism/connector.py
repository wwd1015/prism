"""Reusable Snowflake data connector with lazy connection and env var defaults."""

from __future__ import annotations

import logging
import os
from typing import Any, Mapping, Sequence, Union

import pandas as pd

logger = logging.getLogger(__name__)


class SnowflakeConnector:
    """Manages a Snowflake connection with lazy initialization.

    Connection parameters default to environment variables:
        SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PASSWORD,
        SNOWFLAKE_WAREHOUSE, SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA, SNOWFLAKE_ROLE

    Usage:
        with SnowflakeConnector() as conn:
            df = conn.query("SELECT * FROM table")
    """

    def __init__(
        self,
        account: str | None = None,
        user: str | None = None,
        password: str | None = None,
        warehouse: str | None = None,
        database: str | None = None,
        schema: str | None = None,
        role: str | None = None,
    ):
        self.account = account or os.environ.get("SNOWFLAKE_ACCOUNT", "")
        self.user = user or os.environ.get("SNOWFLAKE_USER", "")
        self.password = password or os.environ.get("SNOWFLAKE_PASSWORD", "")
        self.warehouse = warehouse or os.environ.get("SNOWFLAKE_WAREHOUSE", "")
        self.database = database or os.environ.get("SNOWFLAKE_DATABASE", "")
        self.schema = schema or os.environ.get("SNOWFLAKE_SCHEMA", "")
        self.role = role or os.environ.get("SNOWFLAKE_ROLE", "")
        self._connection: Any = None

    def _get_snowflake_module(self) -> Any:
        """Import and return the snowflake.connector module."""
        try:
            import snowflake.connector

            return snowflake.connector
        except ImportError:
            raise ImportError(
                "snowflake-connector-python is required for SnowflakeConnector. "
                "Install it with: pip install snowflake-connector-python"
            )

    def _connect(self) -> Any:
        """Create or return an active Snowflake connection."""
        if self._connection is not None and not self._connection.is_closed():
            return self._connection

        sf = self._get_snowflake_module()
        self._connection = sf.connect(
            account=self.account,
            user=self.user,
            password=self.password,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema,
            role=self.role,
        )
        logger.info("Snowflake connection established")
        return self._connection

    def query(
        self,
        sql: str,
        params: Union[Mapping[str, Any], Sequence[Any], None] = None,
    ) -> pd.DataFrame:
        """Execute SQL and return results as a DataFrame.

        Args:
            sql: SQL query string.
            params: Optional bind parameters (dict for named, sequence for positional).

        Returns:
            Query results as a pandas DataFrame.
        """
        conn = self._connect()
        cursor = conn.cursor()
        try:
            cursor.execute(sql, params)
            if hasattr(cursor, "fetch_pandas_all"):
                return cursor.fetch_pandas_all()
            columns = [desc[0] for desc in cursor.description]
            data = cursor.fetchall()
            return pd.DataFrame(data, columns=columns)
        finally:
            cursor.close()

    def close(self) -> None:
        """Close the connection if open."""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            logger.info("Snowflake connection closed")

    def __enter__(self) -> SnowflakeConnector:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
