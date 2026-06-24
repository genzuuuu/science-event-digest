import datetime
import json
from pathlib import Path

CURATED_PATH = Path(__file__).resolve().parents[2] / "data" / "curated_conferences.json"


def fetch_curated_conferences(horizon_start: datetime.date, horizon_end: datetime.date):
    from scrape.conferences import ConferenceEvent

    if not CURATED_PATH.exists():
        return []

    with CURATED_PATH.open(encoding="utf-8") as f:
        items = json.load(f)

    results = []
    for item in items:
        deadline_raw = item.get("deadline")
        if not deadline_raw:
            continue
        try:
            deadline = datetime.date.fromisoformat(deadline_raw)
        except ValueError:
            continue
        if not (horizon_start <= deadline <= horizon_end):
            continue
        results.append(
            ConferenceEvent(
                name=item["name"],
                full_title=item.get("full_title") or item["name"],
                when=item.get("when", ""),
                where=item.get("where", ""),
                deadline=deadline,
                url=item["url"],
                source=item.get("source", "curated"),
                topics=item.get("topics", ""),
            )
        )
    return results
