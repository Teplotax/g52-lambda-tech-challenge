import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from auth.config import Settings
from auth.logger import JsonLogger
from auth.repository import Cliente
from auth.service import AuthService
from auth.tokens import load_signing_key

CLIENTES = {
    "55563271064": Cliente(1, "Marcos Antônio Oliveira", "Maria Oliveira", "maria.oliveira@email.com", "CPF", True),
    "84673421027": Cliente(2, "Jonathan Douglas Pereira", None, "carlos.pereira@email.com", "CNPJ", True),
    "52998224725": Cliente(3, "Cliente Inativo", None, "inativo@email.com", "CPF", False),
}


class FakeRepository:
    def find_by_cpf(self, cpf):
        return CLIENTES.get(cpf)


@pytest.fixture(scope="session")
def signing_key():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return load_signing_key(pem)


@pytest.fixture
def settings():
    return Settings(
        db_host="localhost", db_port=5432, db_name="techchallenge", db_username="techchallenge",
        db_password="techchallenge", db_ssl=False, jwt_private_key_pem="", jwt_issuer="g52-lambda-auth",
        jwt_audience="tech-challenge-api",
        jwt_ttl_seconds=3600,
    )


@pytest.fixture
def service(settings, signing_key):
    return AuthService(settings, FakeRepository(), lambda: signing_key, JsonLogger)
