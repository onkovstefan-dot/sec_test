from __future__ import annotations

import importlib

import pytest


def _m():
    return importlib.import_module("utils.populate_daily_values")


@pytest.mark.parametrize(
    "scheme,value,expected",
    [
        ("gleif_lei", "5493001KJTIIGC8Y1R12", "5493001KJTIIGC8Y1R12"),
        ("gleif_lei", "5493001kjtiigc8y1r12", "5493001KJTIIGC8Y1R12"),
        ("isin", "us0378331005", "US0378331005"),
        ("gb_companies_house", "1234567", "01234567"),
        ("gb_companies_house", "00001234", "00001234"),
        ("fr_siren", "552 100 554", "552100554"),
        ("eu_vat", "de 123 456 789", "DE123456789"),
        ("ticker_exchange", "aapl:xnas", "AAPL:XNAS"),
        ("ticker_exchange", " AAPL : XNAS ", "AAPL:XNAS"),
    ],
)
def test_normalize_identifier_value_valid(
    scheme: str, value: str, expected: str
) -> None:
    m = _m()
    assert m._normalize_identifier_value(scheme, value) == expected


@pytest.mark.parametrize(
    "scheme,value",
    [
        ("gleif_lei", "SHORT"),
        ("gleif_lei", "!" * 20),
        ("isin", "TOO-SHORT"),
        ("gb_companies_house", "123456789"),
        ("fr_siren", "123"),
        ("eu_vat", "   "),
        ("ticker_exchange", "AAPL"),
        ("ticker_exchange", ":XNAS"),
        ("ticker_exchange", "AAPL:"),
    ],
)
def test_normalize_identifier_value_invalid_raises(scheme: str, value: str) -> None:
    m = _m()
    with pytest.raises(ValueError):
        m._normalize_identifier_value(scheme, value)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("sec", "sec_cik"),
        ("CIK", "sec_cik"),
        ("gleif", "gleif_lei"),
        ("companies_house", "gb_companies_house"),
        ("siren", "fr_siren"),
        ("vat", "eu_vat"),
        ("ticker", "ticker_exchange"),
    ],
)
def test_scheme_alias(raw: str, expected: str) -> None:
    m = _m()
    assert m._scheme_alias(raw) == expected
