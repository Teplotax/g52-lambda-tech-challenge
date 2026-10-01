"""Validação de CPF (formato + dígitos verificadores)."""
import re


def normalize_cpf(value):
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    digits = re.sub(r"\D", "", str(value))
    return digits if len(digits) == 11 else None


def _check_digit(digits, length):
    total = sum(int(digits[i]) * (length + 1 - i) for i in range(length))
    rest = (total * 10) % 11
    return 0 if rest == 10 else rest


def is_valid_cpf(value):
    cpf = normalize_cpf(value)
    if not cpf:
        return False
    # Sequências repetidas (000.000.000-00, 111...) passam no cálculo mas são inválidas
    if cpf == cpf[0] * 11:
        return False
    return _check_digit(cpf, 9) == int(cpf[9]) and _check_digit(cpf, 10) == int(cpf[10])


def mask_cpf(cpf):
    return f"{cpf[:3]}.***.***-{cpf[9:]}" if cpf else None
