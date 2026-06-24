import datetime
import re

import requests

AI_DEADLINES_URL = "https://mlciv.com/ai-deadlines/conferences.json"
USER_AGENT = "science-event-digest/1.0 (+https://github.com/genzuuuu/science-event-digest)"

# Subjects relevant to physics-adjacent AI / robotics / materials informatics
RELEVANT_SUBJECTS = {"ML", "CV", "NLP", "RO", "DM", "AP", "SP", "CG", "HCI"}


def _parse_deadline(value: str) -> datetime.date | None:
    if not value or "TBA" in value.upper():
        return None
    cleaned = value.strip().replace(" ", "T")
    cleaned = re.sub(r"[^\d\-:T]", "", cleaned)[:19]
    try:
        return datetime.datetime.fromisoformat(cleaned).date()
    except ValueError:
        for fmt in ("%Y-%m-%d",):
            try:
                return datetime.datetime.strptime(value[:10], fmt).date()
            except ValueError:
                continue
    return None


def fetch_ai_deadlines(horizon_start: datetime.date, horizon_end: datetime.date):
    from scrape.conferences import ConferenceEvent

    response = requests.get(
        AI_DEADLINES_URL,
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    results = []
    for item in data:
        subs = set(item.get("sub") or [])
        if not subs & RELEVANT_SUBJECTS:
            continue
        deadline = _parse_deadline(item.get("deadline", ""))
        if not deadline or not (horizon_start <= deadline <= horizon_end):
            continue
        place = item.get("place") or "TBA"
        results.append(
            ConferenceEvent(
                name=item.get("title", "Unknown"),
                full_title=item.get("full_name") or item.get("title", ""),
                when=item.get("date") or item.get("start", ""),
                where=place,
                deadline=deadline,
                url=item.get("link", AI_DEADLINES_URL),
                source="ai-deadlines (mlciv.com)",
                topics=", ".join(sorted(subs)),
            )
        )
    return results
