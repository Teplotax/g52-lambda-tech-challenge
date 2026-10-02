import base64
import hashlib
import json
import time
from dataclasses import dataclass

import jwt
from cryptography.hazmat.primitives.serialization import load_pem_private_key, load_pem_public_key
from jwt.algorithms import RSAAlgorithm


@dataclass(frozen=True)
class SigningKey:
    private_key: object
    kid: str
    jwk: dict


def _thumbprint(jwk):
    # kid = thumbprint da chave (rfc 7638)
    canonical = json.dumps({"e": jwk["e"], "kty": jwk["kty"], "n": jwk["n"]}, separators=(",", ":"), sort_keys=True)
    digest = hashlib.sha256(canonical.encode()).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def load_signing_key(private_key_pem):
    private_key = load_pem_private_key(private_key_pem.encode(), password=None)
    public_jwk = RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    kid = _thumbprint(public_jwk)
    return SigningKey(
        private_key=private_key,
        kid=kid,
        jwk={**public_jwk, "kid": kid, "use": "sig", "alg": "RS256"},
    )


def sign_token(claims, signing_key, *, issuer, audience, ttl_seconds, now=None):
    iat = int(now if now is not None else time.time())
    payload = {**claims, "iss": issuer, "aud": audience, "iat": iat, "nbf": iat, "exp": iat + ttl_seconds}
    return jwt.encode(payload, signing_key.private_key, algorithm="RS256", headers={"kid": signing_key.kid})


def to_jwks(signing_key):
    return {"keys": [signing_key.jwk]}


def load_public_key(public_key_pem):
    return load_pem_public_key(public_key_pem.encode())


def verify_token(token, public_key, *, issuer, audience):
    return jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        issuer=issuer,
        audience=audience,
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
