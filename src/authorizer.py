# authorizer TOKEN do api gateway, valida o jwt emitido pelo handler.py
import os

import jwt

from auth.logger import JsonLogger
from auth.tokens import load_public_key, verify_token

_public_key = None


def _get_public_key():
    global _public_key
    _public_key = _public_key or load_public_key(os.environ["JWT_PUBLIC_KEY_PEM"])
    return _public_key


def _extract_token(authorization):
    scheme, _, token = (authorization or "").strip().partition(" ")
    return token.strip() if scheme.lower() == "bearer" and token.strip() else None


def _api_wildcard_arn(method_arn):
    # libera o stage inteiro, senão o cache do authorizer quebra em outras rotas
    prefix, _, path = method_arn.partition("/")
    stage = path.split("/", 1)[0]
    return f"{prefix}/{stage}/*/*"


def _policy(principal_id, effect, resource, context=None):
    policy = {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [{"Action": "execute-api:Invoke", "Effect": effect, "Resource": resource}],
        },
    }
    if context:
        policy["context"] = context
    return policy


def lambda_handler(event, context, public_key=None):
    log = JsonLogger(requestId=getattr(context, "aws_request_id", None))
    method_arn = event.get("methodArn", "")

    token = _extract_token(event.get("authorizationToken"))
    if not token:
        log.warning("Header Authorization ausente ou fora do padrão Bearer", event="authorizer.missing_token",
                    methodArn=method_arn)
        # o gateway só devolve 401 com essa mensagem exata
        raise Exception("Unauthorized")

    try:
        claims = verify_token(
            token,
            public_key or _get_public_key(),
            issuer=os.environ.get("JWT_ISSUER", "g52-lambda-auth"),
            audience=os.environ.get("JWT_AUDIENCE", "tech-challenge-api"),
        )
    except jwt.InvalidTokenError as exc:
        log.warning("Token inválido", event="authorizer.invalid_token", reason=str(exc),
                    errorType=type(exc).__name__, methodArn=method_arn)
        raise Exception("Unauthorized")

    log.info("Token válido", event="authorizer.allowed", clienteId=claims["sub"], methodArn=method_arn)
    return _policy(
        claims["sub"],
        "Allow",
        _api_wildcard_arn(method_arn),
        {"clienteId": claims["sub"], "cpf": claims.get("cpf", "")},
    )
