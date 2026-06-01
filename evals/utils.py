def keyword_in_text(keyword: str, text: str) -> bool:
    """Case-insensitive keyword matching."""
    return keyword.lower() in text.lower()


def cost_within_bounds(value: int, bounds: dict) -> bool:
    """Check if value is within min/max bounds."""
    min_val = bounds.get("min", float("-inf"))
    max_val = bounds.get("max", float("inf"))
    return min_val <= value <= max_val
