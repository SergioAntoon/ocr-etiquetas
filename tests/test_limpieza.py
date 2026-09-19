import pytest

from ocr_etiquetas.limpieza import (
    digito_control_sscc,
    es_codigo_valido,
    es_sscc_valido,
    limpiar_codigo,
)


def test_limpiar_codigo_respeta_el_prefijo():
    assert limpiar_codigo("4260OI2345678901Z5") == "426001234567890125"


def test_limpiar_codigo_no_altera_un_codigo_correcto():
    codigo = "426001234567890125"
    assert limpiar_codigo(codigo) == codigo


@pytest.mark.parametrize(
    "codigo,esperado",
    [
        ("426001234567890125", True),
        ("42600123456789012", False),   # longitud insuficiente
        ("42600123456789012A", False),  # carácter no numérico
    ],
)
def test_es_codigo_valido(codigo, esperado):
    assert es_codigo_valido(codigo) is esperado


def test_digito_control_coincide_con_el_algoritmo_gs1():
    base = "42600123456789012"
    assert es_sscc_valido(base + str(digito_control_sscc(base)))


def test_un_digito_mal_leido_invalida_el_sscc():
    base = "42600123456789012"
    correcto = base + str(digito_control_sscc(base))
    alterado = correcto[:5] + str((int(correcto[5]) + 1) % 10) + correcto[6:]
    assert not es_sscc_valido(alterado)


def test_digito_control_requiere_17_digitos():
    with pytest.raises(ValueError):
        digito_control_sscc("123")
