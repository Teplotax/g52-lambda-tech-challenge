# POST /auth e GET /.well-known/jwks.json
import uuid

from auth.config import Settings
from auth.http import error, get_header, get_json_body, get_method, get_path, response
from auth.logger import JsonLogger
from auth.repository import ClienteRepository, DatabaseUnavailable
from auth.secrets import get_secret_string
from auth.service import AuthService
from auth.tokens import load_signing_key

_service = None


def _build_service():
    settings = Settings.from_env()
    signing_key = None

    def signing_key_provider():
        nonlocal signing_key
        if signing_key is None:
            signing_key = load_signing_key(get_secret_string(settings.jwt_secret_arn))
        return signing_key

    return AuthService(settings, ClienteRepository(settings), signing_key_provider, JsonLogger)


def _get_service():
    global _service
    _service = _service or _build_service()
    return _service


def lambda_handler(event, context, service=None):
    service = service or _get_service()
    correlation_id = get_header(event, "x-correlationid") or str(uuid.uuid4())
    log = JsonLogger(correlationId=correlation_id,
                     requestId=getattr(context, "aws_request_id", None))

    method, path = get_method(event), get_path(event).rstrip("/")
    log.info("Requisição recebida", event="http.request", method=method, path=path)

    try:
        if path.endswith("/.well-known/jwks.json") and method == "GET":
            result = service.jwks()
            return response(result.status_code, result.body, correlation_id,
                            {"Cache-Control": "public, max-age=300"})

        if path.endswith("/auth"):
            if method != "POST":
                return error(405, "MethodNotAllowed", "Método não permitido", correlation_id)
            body = get_json_body(event)
            if body is None or "cpf" not in body:
                return error(400, "BadRequest", "Informe o CPF no corpo da requisição: {\"cpf\": \"...\"}",
                             correlation_id)
            result = service.authenticate(body["cpf"], correlation_id)
            return response(result.status_code, result.body, correlation_id)

        return error(404, "NotFound", "Recurso não encontrado", correlation_id)

    except DatabaseUnavailable as exc:
        log.error("Banco de dados indisponível", event="auth.db_unavailable", error=str(exc))
        return error(503, "ServiceUnavailable", "Serviço temporariamente indisponível", correlation_id)
    except Exception as exc:
        log.error("Erro inesperado", event="auth.unexpected_error", error=str(exc), errorType=type(exc).__name__)
        return error(500, "InternalServerError", "Erro interno", correlation_id)
