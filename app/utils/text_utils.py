import re

def normalize_ocr_text(text: str) -> str:
    """Normalize OCR text: fullwidth→halfwidth, whitespace cleaning."""
    if not text:
        return ''

    result = text

    # Fullwidth to halfwidth (ASCII range)
    # Numbers: \uff10-\uff19 (０-９) → \x30-\x39 (0-9)
    for i in range(0xFF10, 0xFF1A):
        result = result.replace(chr(i), chr(i - 0xFF10 + 0x30))
    # Uppercase: \uff21-\uff2a (Ａ-Ｚ) → \x41-\x5a (A-Z)
    for i in range(0xFF21, 0xFF3A):
        result = result.replace(chr(i), chr(i - 0xFF21 + 0x41))
    # Lowercase: \uff41-\uff5a (ａ-ｚ) → \x61-\x7a (a-z)
    for i in range(0xFF41, 0xFF5B):
        result = result.replace(chr(i), chr(i - 0xFF41 + 0x61))

    # Fullwidth space \u3000 → halfwidth space
    result = result.replace('\u3000', ' ')

    # Strip and collapse whitespace
    result = result.strip()
    result = re.sub(r' +', ' ', result)

    return result