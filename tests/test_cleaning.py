import pytest

from ocr_labels.cleaning import (
    clean_code,
    is_valid_code,
    is_valid_sscc,
    sscc_check_digit,
)


def test_clean_code_preserves_the_prefix():
    assert clean_code("4260OI2345678901Z5") == "426001234567890125"


def test_clean_code_does_not_change_a_correct_code():
    code = "426001234567890125"
    assert clean_code(code) == code


@pytest.mark.parametrize(
    "code,expected",
    [
        ("426001234567890125", True),
        ("42600123456789012", False),  # insufficient length
        ("42600123456789012A", False),  # non-numeric character
    ],
)
def test_is_valid_code(code, expected):
    assert is_valid_code(code) is expected


def test_check_digit_matches_the_gs1_algorithm():
    base = "42600123456789012"
    assert is_valid_sscc(base + str(sscc_check_digit(base)))


def test_a_misread_digit_invalidates_the_sscc():
    base = "42600123456789012"
    correct = base + str(sscc_check_digit(base))
    altered = correct[:5] + str((int(correct[5]) + 1) % 10) + correct[6:]
    assert not is_valid_sscc(altered)


def test_check_digit_requires_17_digits():
    with pytest.raises(ValueError):
        sscc_check_digit("123")
