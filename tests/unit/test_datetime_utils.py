import pytest
from datetime import date
from app.utils.datetime_utils import parse_ocr_date

def test_parse_standard_format():
    assert parse_ocr_date('2025-03-15') == date(2025, 3, 15)

def test_parse_dot_separator():
    assert parse_ocr_date('2025.03.15') == date(2025, 3, 15)

def test_parse_slash_separator():
    assert parse_ocr_date('2025/03/15') == date(2025, 3, 15)

def test_parse_chinese_format():
    assert parse_ocr_date('2025年3月15日') == date(2025, 3, 15)

def test_parse_chinese_year_month():
    assert parse_ocr_date('2025年3月') == date(2025, 3, 31)

def test_parse_chinese_year_only():
    assert parse_ocr_date('2025年') == date(2025, 12, 31)

def test_ocr_zero_to_o():
    # OCR might misread '0' as 'O'
    assert parse_ocr_date('2025O年3月15日') == date(2025, 3, 15)

def test_ocr_8_to_b():
    assert parse_ocr_date('2025年3月B日') == date(2025, 3, 15)

def test_permanent_returns_2099():
    assert parse_ocr_date('长期') == date(2099, 12, 31)
    assert parse_ocr_date('有效期永久') == date(2099, 12, 31)

def test_invalid_returns_none():
    assert parse_ocr_date('这不是日期') is None
    assert parse_ocr_date('') is None