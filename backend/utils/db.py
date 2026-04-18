from __future__ import annotations

from typing import Any


def get_source_history(domains: list[str], db_dsn: str) -> dict[str, list[dict[str, Any]]]:
    return {domain: [] for domain in domains}
