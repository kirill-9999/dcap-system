"""Unit-тесты CSV-утилит: защита от CSV injection (День 40.4)."""
import pytest

pytestmark = pytest.mark.unit

from manager.src.core.csv_utils import sanitize_csv_cell


def test_excel_formula_prefixed():
    assert sanitize_csv_cell("=cmd|' /C calc'!A0").startswith("'=")


def test_plus_prefixed():
    assert sanitize_csv_cell("+1234").startswith("'+")


def test_at_prefixed():
    assert sanitize_csv_cell("@SUM(1)").startswith("'@")


def test_hyphen_prefixed():
    assert sanitize_csv_cell("-1+2").startswith("'-")


def test_tab_prefixed():
    assert sanitize_csv_cell("\t=SUM(1)").startswith("'\t")


def test_normal_unchanged():
    assert sanitize_csv_cell("normal value") == "normal value"


def test_empty_unchanged():
    assert sanitize_csv_cell("") == ""