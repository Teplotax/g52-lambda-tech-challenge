"""Consulta de clientes no PostgreSQL gerenciado (tabela `clientes` da aplicação principal)."""
import os
import ssl
from dataclasses import dataclass

import pg8000.native

from .secrets import get_secret_json

RDS_CA_BUNDLE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "rds-ca-bundle.pem")

_FIND_BY_DOCUMENTO = """
    SELECT id, nome, nome_social, email, tipo_documento
      FROM clientes
     WHERE documento = :documento
"""


@dataclass(frozen=True)
class Cliente:
    id: int
    nome: str
    nome_social: str
    email: str
    tipo_documento: str


class DatabaseUnavailable(Exception):
    pass


class ClienteRepository:
    def __init__(self, settings):
        self.settings = settings
        self._conn = None

    def _connect(self):
        if not self.settings.db_host or not self.settings.db_secret_arn:
            raise DatabaseUnavailable("Banco de dados não configurado (DB_HOST/DB_SECRET_ARN)")

        # Formato do segredo gerenciado pelo RDS: {"username": "...", "password": "..."}
        credentials = get_secret_json(self.settings.db_secret_arn)

        ssl_context = None
        if self.settings.db_ssl:
            ssl_context = ssl.create_default_context(cafile=RDS_CA_BUNDLE if os.path.exists(RDS_CA_BUNDLE) else None)

        return pg8000.native.Connection(
            user=credentials["username"],
            password=credentials["password"],
            host=self.settings.db_host,
            port=self.settings.db_port,
            database=self.settings.db_name,
            ssl_context=ssl_context,
            timeout=5,
        )

    def _run(self, sql, **params):
        # A conexão é reaproveitada entre invocações; se caiu, reconecta uma vez
        for attempt in range(2):
            try:
                if self._conn is None:
                    self._conn = self._connect()
                return self._conn.run(sql, **params)
            except DatabaseUnavailable:
                raise
            except Exception as exc:
                self._close()
                if attempt == 1:
                    raise DatabaseUnavailable(str(exc)) from exc

    def _close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

    def find_by_cpf(self, cpf):
        rows = self._run(_FIND_BY_DOCUMENTO, documento=cpf)
        return Cliente(*rows[0]) if rows else None
