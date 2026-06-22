"""Helpers for communication app."""


def mysql_text_safe(value):
    """
    Encode characters outside the MySQL utf8mb3 range as HTML entities.

    Legacy utf8 columns reject 4-byte UTF-8 (e.g. emojis). utf8mb4 columns
    accept the original string unchanged.
    """
    if value is None:
        return value
    if not isinstance(value, str):
        value = str(value)
    parts = []
    for char in value:
        if ord(char) <= 0xFFFF:
            parts.append(char)
        else:
            parts.append('&#{};'.format(ord(char)))
    return ''.join(parts)
