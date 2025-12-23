# utils/mission_validation.py

ALLOWED_DIFFICULTIES = {"basic", "elite"}
DIFFICULTY_LABELS = {"basic": "Basic", "elite": "Elite"}
DEFAULT_POINTS = {"basic": 10, "elite": 20}


def normalize_difficulty(raw: str) -> str:
    if raw is None:
        raise ValueError("difficulty is required")
    v = raw.strip().lower()
    if v not in ALLOWED_DIFFICULTIES:
        raise ValueError(f"Invalid difficulty: {raw}. Allowed: basic, elite")
    return v


def parse_tags(raw: str) -> list[str]:
    # raw может быть "-" или пусто
    if not raw:
        return []
    s = raw.strip()
    if s in {"-", "—"}:
        return []
    # "спорт, сон, вода" -> ["спорт","сон","вода"]
    parts = [p.strip() for p in s.split(",")]
    return [p for p in parts if p]
