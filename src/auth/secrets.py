"""Leitura de segredos do Secrets Manager com cache entre invocações (container quente)."""
import json

import boto3

_client = None
_cache = {}


def get_secret_string(secret_id):
    global _client
    if secret_id not in _cache:
        _client = _client or boto3.client("secretsmanager")
        _cache[secret_id] = _client.get_secret_value(SecretId=secret_id)["SecretString"]
    return _cache[secret_id]


def get_secret_json(secret_id):
    return json.loads(get_secret_string(secret_id))
