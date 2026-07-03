"""tha-snowflake-runner: typed Snowflake connector wrapper with connections.toml support."""

from tha_snowflake_runner.client import ThaSnowflake
from tha_snowflake_runner.errors import SnowflakeError
from tha_snowflake_runner.profiles import list_profiles
from tha_snowflake_runner.session import Session

__version__ = "0.2.1"
__all__ = [
    "Session",
    "SnowflakeError",
    "ThaSnowflake",
    "list_profiles",
]
