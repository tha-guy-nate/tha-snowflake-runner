"""tha-snowflake-runner: typed Snowflake connector wrapper with connections.toml support."""

from importlib.metadata import version

from tha_snowflake_runner.client import ThaSnowflake
from tha_snowflake_runner.errors import SnowflakeError
from tha_snowflake_runner.profiles import list_profiles
from tha_snowflake_runner.session import Session

__version__ = version("tha-snowflake-runner")
__all__ = [
    "Session",
    "SnowflakeError",
    "ThaSnowflake",
    "list_profiles",
]
