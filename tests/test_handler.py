import json

import jwt
from jwt import PyJWK

from auth.repository import DatabaseUnavailable
from handler import lambda_handler


def rest_event(method, path, body=None, headers=None):
    return {
        "httpMethod": method,
        "path": path,
        "headers": headers or {},
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


def call(service, event):
    res = lambda_handler(event, None, service=service)
    return res["statusCode"], json.loads(res["body"]), res["headers"]


def test_emite_token_valido_verificavel_pelo_jwks(service):
    status, body, _ = call(service, rest_event("POST", "/auth", {"cpf": "555.632.710-64"}))

    assert status == 200
    assert body["token_type"] == "Bearer"
    assert body["expires_in"] == 3600

    _, jwks, _ = call(service, rest_event("GET", "/.well-known/jwks.json"))
    header = jwt.get_unverified_header(body["access_token"])
    jwk = next(k for k in jwks["keys"] if k["kid"] == header["kid"])

    claims = jwt.decode(body["access_token"], PyJWK(jwk).key, algorithms=["RS256"],
                        audience="tech-challenge-api", issuer="g52-lambda-auth")
    assert claims["sub"] == "1"
    assert claims["cpf"] == "55563271064"
    assert claims["name"] == "Maria Oliveira"
    assert claims["roles"] == ["CLIENTE"]
    assert claims["exp"] - claims["iat"] == 3600


def test_cpf_invalido_retorna_400(service):
    status, body, _ = call(service, rest_event("POST", "/auth", {"cpf": "11111111111"}))
    assert status == 400
    assert body == {"message": "CPF inválido", "exceptionType": "BadRequest"}


def test_corpo_sem_cpf_retorna_400(service):
    status, _, _ = call(service, rest_event("POST", "/auth", {"documento": "55563271064"}))
    assert status == 400


def test_corpo_invalido_retorna_400(service):
    event = rest_event("POST", "/auth")
    event["body"] = "nao-e-json"
    status, _, _ = call(service, event)
    assert status == 400


def test_cliente_inexistente_retorna_401(service):
    status, body, _ = call(service, rest_event("POST", "/auth", {"cpf": "93364249040"}))
    assert status == 401
    assert body["exceptionType"] == "Unauthorized"


def test_cliente_nao_habilitado_retorna_403(service):
    status, body, _ = call(service, rest_event("POST", "/auth", {"cpf": "84673421027"}))
    assert status == 403
    assert body["exceptionType"] == "Forbidden"


def test_cliente_inativo_retorna_403(service):
    status, body, _ = call(service, rest_event("POST", "/auth", {"cpf": "529.982.247-25"}))
    assert status == 403
    assert body == {"message": "Cliente inativo", "exceptionType": "Forbidden"}


def test_propaga_correlation_id(service):
    event = rest_event("POST", "/auth", {"cpf": "55563271064"}, headers={"X-CorrelationId": "abc-123"})
    _, _, headers = call(service, event)
    assert headers["x-correlationid"] == "abc-123"


def test_gera_correlation_id_quando_ausente(service):
    _, _, headers = call(service, rest_event("POST", "/auth", {"cpf": "55563271064"}))
    assert headers["x-correlationid"]


def test_aceita_payload_http_api_v2(service):
    event = {
        "rawPath": "/auth",
        "requestContext": {"http": {"method": "POST"}},
        "headers": {},
        "body": json.dumps({"cpf": "55563271064"}),
    }
    status, _, _ = call(service, event)
    assert status == 200


def test_metodo_nao_permitido(service):
    status, _, _ = call(service, rest_event("GET", "/auth"))
    assert status == 405


def test_rota_inexistente(service):
    status, _, _ = call(service, rest_event("GET", "/outra"))
    assert status == 404


def test_banco_indisponivel_retorna_503(service):
    class Broken:
        def find_by_cpf(self, cpf):
            raise DatabaseUnavailable("timeout")

    service.repository = Broken()
    status, body, _ = call(service, rest_event("POST", "/auth", {"cpf": "55563271064"}))
    assert status == 503
    assert body["exceptionType"] == "ServiceUnavailable"
