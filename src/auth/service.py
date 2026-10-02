import hashlib
import hmac
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

        if not cliente.ativo:
            log.warning("Cliente inativo", event="auth.cliente_inativo", clienteId=cliente.id)
            return _error(403, "Forbidden", "Cliente inativo")

        # cnpj não autentica por cpf
        if (cliente.tipo_documento or "").upper() != "CPF":
            log.warning("Cliente sem permissão para autenticar por CPF", event="auth.cliente_forbidden",
                        clienteId=cliente.id, tipoDocumento=cliente.tipo_documento)
            return _error(403, "Forbidden", "Cliente não habilitado para autenticação por CPF")

        log.info("Token emitido", event="auth.token_issued", clienteId=cliente.id)
        return self._token({
            "sub": str(cliente.id),
            "cpf": cpf,
            "name": cliente.nome_social or cliente.nome,
            "email": cliente.email,
            "roles": ["CLIENTE"],
        })

    # token administrativo (equipe da oficina / sistemas), grant client_credentials
    def authenticate_client(self, client_id, client_secret, correlation_id):
        log = self.logger_factory(correlationId=correlation_id)
        expected_id = self.settings.admin_client_id
        expected_hash = self.settings.admin_client_secret_sha256

        secret_hash = hashlib.sha256((client_secret or "").encode()).hexdigest()
        valid = (bool(expected_id) and bool(expected_hash)
                 and hmac.compare_digest(client_id or "", expected_id)
                 and hmac.compare_digest(secret_hash, expected_hash))

        if not valid:
            log.warning("Credenciais de client inválidas", event="auth.invalid_client", clientId=client_id)
            return _error(401, "Unauthorized", "client_id ou client_secret inválido")

        log.info("Token emitido", event="auth.client_token_issued", clientId=client_id)
        return self._token({"sub": client_id, "roles": ["ADMIN"]})

    def _token(self, claims):
        token = sign_token(
            claims,
            self.signing_key_provider(),
            issuer=self.settings.jwt_issuer,
            audience=self.settings.jwt_audience,
            ttl_seconds=self.settings.jwt_ttl_seconds,
            now=self.clock() if self.clock else None,
        )
        return AuthResult(200, {
            "access_token": token,
            "token_type": "Bearer",
            "expires_in": self.settings.jwt_ttl_seconds,
        })

    def jwks(self):
        return AuthResult(200, to_jwks(self.signing_key_provider()))


def _error(status_code, exception_type, message):
    return AuthResult(status_code, error_body(exception_type, message))
