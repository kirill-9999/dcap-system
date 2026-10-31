"""Форматтер hex-дампа (День 40.4)."""


def format_hex_dump(data: bytes, base_offset: int = 0, width: int = 16) -> str:
    """
    Классический hex-дамп:

    00000000  48 65 6c 6c 6f 20 57 6f  72 6c 64 21 0a 00 00 00  |Hello World!....|
    """
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i + width]
        offset_str = f"{base_offset + i:08x}"
        hex_str = " ".join(f"{b:02x}" for b in chunk).ljust(width * 3 - 1)
        ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{offset_str}  {hex_str}  |{ascii_str}|")
    return "\n".join(lines)