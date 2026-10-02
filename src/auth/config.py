import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_secret_arn: str
    db_ssl: bool
    jwt_secret_arn: str
    jwt_issuer: str
    jwt_audience: str
    jwt_ttl_seconds: int

    @classmethod
    def from_env(cls):
        env = os.environ.get
        return cls(
            db_host=env("DB_HOST", ""),
            db_port=int(env("DB_PORT", "5432")),
            db_name=env("DB_NAME", "techchallenge"),
            db_secret_arn=env("DB_SECRET_ARN", ""),
            db_ssl=env("DB_SSL", "true").lower() == "true",
            jwt_secret_arn=env("JWT_SECRET_ARN", ""),
            jwt_issuer=env("JWT_ISSUER", "g52-lambda-auth"),
            jwt_audience=env("JWT_AUDIENCE", "tech-challenge-api"),
            jwt_ttl_seconds=int(env("JWT_TTL_SECONDS", "3600")),
        )
