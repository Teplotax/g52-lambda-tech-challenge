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


# rotas que o token de cliente (cpf) pode chamar; o resto é só admin
CLIENTE_ROUTES = [
    "GET/ordensDeServico",
    "GET/ordensDeServico/*",
    "POST/ordensDeServico/*/aprovar",
]


def _stage_arn(method_arn):
    # arn:aws:execute-api:{region}:{account}:{apiId}/{stage}/{method}/{path}
    prefix, _, path = method_arn.partition("/")
    return f"{prefix}/{path.split('/', 1)[0]}"


# a policy cobre todas as rotas da role, senão o cache do authorizer quebra em outras rotas
def _allowed_resources(method_arn, roles):
    stage = _stage_arn(method_arn)
    if "ADMIN" in roles:
        return [f"{stage}/*/*"]
    if "CLIENTE" in roles:
        return [f"{stage}/{route}" for route in CLIENTE_ROUTES]
    return []


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

    roles = claims.get("roles") or []
    resources = _allowed_resources(method_arn, roles)
    context = {"sub": claims["sub"], "roles": ",".join(roles), "cpf": claims.get("cpf", "")}

    if not resources:
        # token válido mas sem role conhecida: gateway responde 403
        log.warning("Token sem role", event="authorizer.no_role", sub=claims["sub"], methodArn=method_arn)
        return _policy(claims["sub"], "Deny", f"{_stage_arn(method_arn)}/*/*", context)

    log.info("Token válido", event="authorizer.allowed", sub=claims["sub"], roles=roles, methodArn=method_arn)
    return _policy(claims["sub"], "Allow", resources, context)
