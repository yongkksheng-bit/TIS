import re
from datetime import date, datetime, timedelta
from typing import Optional

def parse_ocr_date(date_str: str) -> Optional[date]:
    """Parse various date formats from OCR text, with OCR error tolerance."""
    if not date_str:
        return None

    s = date_str.strip()

    # Handle "长期" / "永久"
    if '长期' in s or '永久' in s:
        return date(2099, 12, 31)

    # OCR corrections: 0<->O, 1<->I, 8<->B
    s = s.replace('O', '0').replace('o', '0')
    s = s.replace('I', '1').replace('l', '1')
    s = s.replace('B', '8')

    # Try standard formats first
    std_formats = ['%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d']
    for fmt in std_formats:
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue

    # Chinese format: YYYY年MM月DD日
    m = re.match(r'^(\d{4,5})年(\d{1,2})月(\d{1,2})日$', s)
    if m:
        year = int(m.group(1)[:4])
        month = int(m.group(2))
        day = int(m.group(3))
        try:
            return date(year, month, day)
        except ValueError:
            return None

    # Chinese format: YYYY年MM月 (year-month only, return last day of month)
    m = re.match(r'^(\d{4,5})年(\d{1,2})月$', s)
    if m:
        year = int(m.group(1)[:4])
        month = int(m.group(2))
        if month == 12:
            return date(year, 12, 31)
        # First day of next month, then subtract 1 day
        return date(year, month + 1, 1) - timedelta(days=1)

    # Chinese format: YYYY年 (year only, return last day of year)
    m = re.match(r'^(\d{4,5})年$', s)
    if m:
        year = int(m.group(1)[:4])
        return date(year, 12, 31)

    return None