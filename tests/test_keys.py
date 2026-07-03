import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from tha_snowflake_runner._keys import resolve_private_key
from tha_snowflake_runner.errors import SnowflakeError

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_expected_der = _key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
_pem_unencrypted = _key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
_pem_encrypted = _key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.BestAvailableEncryption(b"mypass"),
)


class TestResolvePrivateKey:
    def test_pem_str_resolves_to_der(self):
        result = resolve_private_key(_pem_unencrypted.decode("utf-8"), None)
        assert result == _expected_der

    def test_pem_bytes_resolves_to_der(self):
        result = resolve_private_key(_pem_unencrypted, None)
        assert result == _expected_der

    def test_encrypted_pem_with_correct_passphrase(self):
        result = resolve_private_key(_pem_encrypted, "mypass")
        assert result == _expected_der

    def test_encrypted_pem_with_wrong_passphrase_raises(self):
        with pytest.raises(SnowflakeError, match="Failed to load PEM private key"):
            resolve_private_key(_pem_encrypted, "wrongpass")

    def test_encrypted_pem_without_passphrase_raises(self):
        with pytest.raises(SnowflakeError, match="Failed to load PEM private key"):
            resolve_private_key(_pem_encrypted, None)

    def test_raw_der_bytes_pass_through_unchanged(self):
        result = resolve_private_key(_expected_der, None)
        assert result == _expected_der

    def test_raw_der_bytes_ignore_passphrase(self):
        result = resolve_private_key(_expected_der, "irrelevant")
        assert result == _expected_der

    def test_invalid_pem_raises(self):
        with pytest.raises(SnowflakeError, match="Failed to load PEM private key"):
            resolve_private_key("-----BEGIN PRIVATE KEY-----\nnotarealkey\n-----END-----", None)
