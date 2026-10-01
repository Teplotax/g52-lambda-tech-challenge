"""Regras de autenticação por CPF: validar CPF, verificar cliente na base e emitir o JWT."""
from dataclasses import dataclass

from .cpf import is_valid_cpf, mask_cpf, normalize_cpf
from .http import error_body
from .tokens import sign_token, to_jwks


@dataclass(frozen=True)
class AuthResult:
    status_code: int
    body: dict


class AuthService:
    def __init__(self, settings, repository, signing_key_provider, logger_factory, clock=None):
        self.settings = settings
        self.repository = repository
        self.signing_key_provider = signing_key_provider
        self.logger_factory = logger_factory
        self.clock = clock

    def authenticate(self, cpf_input, correlation_id):
        log = self.logger_factory(correlationId=correlation_id)

        if not is_valid_cpf(cpf_input):
            log.warning("CPF inválido", event="auth.invalid_cpf")
            return _error(400, "BadRequest", "CPF inválido")

        cpf = normalize_cpf(cpf_input)
        cliente = self.repository.find_by_cpf(cpf)

        if cliente is None:
            log.warning("Cliente não encontrado", event="auth.cliente_not_found", cpf=mask_cpf(cpf))
            return _error(401, "Unauthorized", "Cliente não encontrado")

        # Status do cliente: só clientes pessoa física (documento CPF) podem se autenticar por CPF
        if (cliente.tipo_documento or "").upper() != "CPF":
            log.warning("Cliente sem permissão para autenticar por CPF", event="auth.cliente_forbidden",
                        clienteId=cliente.id, tipoDocumento=cliente.tipo_documento)
            return _error(403, "Forbidden", "Cliente não habilitado para autenticação por CPF")

        token = sign_token(
            {
                "sub": str(cliente.id),
                "cpf": cpf,
                "name": cliente.nome_social or cliente.nome,
                "email": cliente.email,
                "roles": ["CLIENTE"],
            },
            self.signing_key_provider(),
            issuer=self.settings.jwt_issuer,
            audience=self.settings.jwt_audience,
            ttl_seconds=self.settings.jwt_ttl_seconds,
            now=self.clock() if self.clock else None,
        )

        log.info("Token emitido", event="auth.token_issued", clienteId=cliente.id)
        return AuthResult(200, {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self.settings.jwt_ttl_seconds,
        })

    def jwks(self):
        return AuthResult(200, to_jwks(self.signing_key_provider()))


def _error(status_code, exception_type, message):
    return AuthResult(status_code, error_body(exception_type, message))
