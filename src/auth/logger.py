import json
import os
import sys
from datetime import datetime, timezone


class JsonLogger:
    def __init__(self, **base_fields):
        self.base_fields = base_fields

    def _write(self, level, message, fields):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "service": os.environ.get("SERVICE_NAME", "g52-lambda-auth"),
            "message": message,
            **self.base_fields,
            **fields,
        }
        sys.stdout.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")

    def info(self, message, **fields):
        self._write("INFO", message, fields)

    def warning(self, message, **fields):
        self._write("WARN", message, fields)

    def error(self, message, **fields):
        self._write("ERROR", message, fields)
