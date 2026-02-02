import re

PHONE_RE = re.compile(r"^\+?\d{7,15}$")

def valid_phone(phone: str) -> bool:
    return bool(PHONE_RE.match(phone))


def format_rating(avg: float, cnt: int) -> str:
    """Return a formatted rating string or empty string when no reviews.

    Examples:
        format_rating(4.72, 23) -> '⭐ 4.7 (23)'
        format_rating(0.0, 0) -> ''
    """
    try:
        if not cnt or cnt <= 0:
            return ''
        return f"⭐ {avg:.1f} ({cnt})"
    except Exception:
        return ''
