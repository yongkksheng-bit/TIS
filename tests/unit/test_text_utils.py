import pytest
from app.utils.text_utils import normalize_ocr_text

def test_fullwidth_numbers_to_ascii():
    assert normalize_ocr_text('１２３４５６７８９０') == '1234567890'

def test_fullwidth_uppercase_to_ascii():
    assert normalize_ocr_text('ＡＢＣＤＥＦ') == 'ABCDEF'

def test_fullwidth_lowercase_to_ascii():
    assert normalize_ocr_text('ａｂｃｄｅｆ') == 'abcdef'

def test_strip_whitespace():
    assert normalize_ocr_text('  hello  ') == 'hello'

def test_collapse_multiple_spaces():
    assert normalize_ocr_text('hello    world') == 'hello world'

def test_fullwidth_space_to_halfwidth():
    assert normalize_ocr_text('hello　world') == 'hello world'

def test_mixed_fullwidth():
    assert normalize_ocr_text('ＡＢＣ１２３') == 'ABC123'