# aceita evento do api gateway rest (v1) e http api (v2)
import base64
import json
from urllib.parse import parse_qsl


def get_method(event):
    return (event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method") or "").upper()


def get_path(event):
    return event.get("path") or event.get("rawPath") or "/"


def get_header(event, name):
    headers = event.get("headers") or {}
    name = name.lower()
    return next((v for k, v in headers.items() if k.lower() == name), None)


def _raw_body(event):
    body = event.get("body")
    if body and event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode()
    return body


def get_json_body(event):
    body = _raw_body(event)
    if not body:
        return None
    try:
        parsed = json.loads(body)
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


# client_credentials manda form-urlencoded, mas aceita json também
def get_form_body(event):
    body = _raw_body(event)
    if not body:
        return {}
    if "json" in (get_header(event, "content-type") or ""):
        return get_json_body(event) or {}
    return dict(parse_qsl(body))


# client_secret_basic (rfc 6749): Authorization: Basic base64(client_id:client_secret)
def get_basic_credentials(event):
    scheme, _, value = (get_header(event, "authorization") or "").partition(" ")
    if scheme.lower() != "basic" or not value:
        return None, None
    try:
        client_id, _, client_secret = base64.b64decode(value).decode().partition(":")
    except (ValueError, UnicodeDecodeError):
        return None, None
    return client_id, client_secret


def response(status_code, body, correlation_id, extra_headers=None):
    headers = {"Content-Type": "application/json", "x-correlationid": correlation_id}
    headers.update(extra_headers or {})
    return {"statusCode": status_code, "headers": headers, "body": json.dumps(body, ensure_ascii=False)}


def error(status_code, exception_type, message, correlation_id):
    # mesmo formato do ErrorMessage do contrato
    return response(status_code, error_body(exception_type, message), correlation_id)


def error_body(exception_type, message):
    return {"message": message, "exceptionType": exception_type}
