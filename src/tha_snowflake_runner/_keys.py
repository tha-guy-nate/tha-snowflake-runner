from __future__ import annotations

from cryptography.hazmat.primitives import serialization

from tha_snowflake_runner.errors import SnowflakeError

_PEM_PREFIX = b"-----BEGIN"


def resolve_private_key(private_key: bytes | str, passphrase: str | None) -> bytes:
    """Resolve a caller-supplied private key to DER bytes for snowflake.connector.connect.

    str is always treated as PEM text. bytes is disambiguated by sniffing the PEM header:
    PEM-as-bytes is decrypted with `passphrase` (if given) and re-serialized to DER; raw DER
    bytes are passed through unchanged and are assumed to already be decrypted — passphrase
    is ignored in that case, matching the connector's own contract for the `private_key` kwarg.
    """
    if isinstance(private_key, str):
        pem_bytes = private_key.encode("utf-8")
    elif private_key.lstrip().startswith(_PEM_PREFIX):
        pem_bytes = private_key
    else:
        return private_key

    try:
        key = serialization.load_pem_private_key(
            pem_bytes,
            password=passphrase.encode("utf-8") if passphrase else None,
        )
    except (ValueError, TypeError) as exc:
        raise SnowflakeError(f"Failed to load PEM private key: {exc}") from exc

    return key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
