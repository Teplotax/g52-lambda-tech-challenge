import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from auth.tokens import load_signing_key, sign_token
from authorizer import lambda_handler

METHOD_ARN = "arn:aws:execute-api:us-east-1:679084116705:uqjslc5lb8/dev/GET/ordensDeServico/1"


@pytest.fixture
def public_key(signing_key):
    return signing_key.private_key.public_key()


def token(signing_key, issuer="g52-lambda-auth", audience="tech-challenge-api", ttl=3600, now=None):
    claims = {"sub": "1", "cpf": "55563271064", "roles": ["CLIENTE"]}
    return sign_token(claims, signing_key, issuer=issuer, audience=audience, ttl_seconds=ttl, now=now)


def authorize(authorization, public_key):
    event = {"type": "TOKEN", "authorizationToken": authorization, "methodArn": METHOD_ARN}
    return lambda_handler(event, None, public_key=public_key)


def test_token_valido_libera_todas_as_rotas_do_stage(signing_key, public_key):
    result = authorize(f"Bearer {token(signing_key)}", public_key)

    statement = result["policyDocument"]["Statement"][0]
    assert result["principalId"] == "1"
    assert statement["Effect"] == "Allow"
    assert statement["Resource"] == "arn:aws:execute-api:us-east-1:679084116705:uqjslc5lb8/dev/*/*"
    assert result["context"] == {"clienteId": "1", "cpf": "55563271064"}


def test_aceita_esquema_bearer_case_insensitive(signing_key, public_key):
    assert authorize(f"bearer {token(signing_key)}", public_key)["principalId"] == "1"


@pytest.mark.parametrize("authorization", [None, "", "Bearer", "Basic abc", "Bearer nao-e-jwt"])
def test_header_invalido_retorna_unauthorized(authorization, public_key):
    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize(authorization, public_key)


def test_token_expirado(signing_key, public_key):
    expired = token(signing_key, ttl=60, now=time.time() - 3600)
    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize(f"Bearer {expired}", public_key)


def test_issuer_errado(signing_key, public_key):
    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize(f"Bearer {token(signing_key, issuer='outro')}", public_key)


def test_audience_errada(signing_key, public_key):
    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize(f"Bearer {token(signing_key, audience='outra-api')}", public_key)


def test_assinatura_de_outra_chave(public_key):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    forged = token(load_signing_key(other))
    with pytest.raises(Exception, match="^Unauthorized$"):
        authorize(f"Bearer {forged}", public_key)
