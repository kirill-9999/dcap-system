"""CSV-утилиты (День 40.4)."""

_CSV_DANGEROUS = ("=", "+", "-", "@", "\t", "\r")


def sanitize_csv_cell(value: str) -> str:
    """
    Защита от CSV injection (формулы в Excel/LibreOffice).

    Если значение начинается с =, +, -, @, TAB, CR — префиксуем апострофом.
    """
    if value and value[0] in _CSV_DANGEROUS:
        return "'" + value
    return value