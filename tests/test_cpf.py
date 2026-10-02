import pytest

from auth.cpf import is_valid_cpf, mask_cpf, normalize_cpf


@pytest.mark.parametrize("cpf", ["55563271064", "555.632.710-64", "84673421027", "93364249040"])
def test_cpf_valido(cpf):
    assert is_valid_cpf(cpf)


@pytest.mark.parametrize("cpf", [
    "55563271065",      # dígito verificador errado
    "11111111111",      # sequência repetida
    "123",              # tamanho inválido
    "72781890000127",   # CNPJ
    "",
    None,
    True,
    {"cpf": "55563271064"},
])
def test_cpf_invalido(cpf):
    assert not is_valid_cpf(cpf)


def test_normaliza_cpf_com_mascara():
    assert normalize_cpf("555.632.710-64") == "55563271064"


def test_mascara_cpf_para_logs():
    assert mask_cpf("55563271064") == "555.***.***-64"
