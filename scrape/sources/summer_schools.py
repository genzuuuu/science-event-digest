import datetime
import json
import re
from html import unescape
from pathlib import Path
import requests

CURATED_PATH = Path(__file__).resolve().parents[2] / "data" / "curated_summer_schools.json"
DRESDEN_SCHOOLS_URL = (
    "https://tu-dresden.de/mn/physik/sfb1143/graduiertenkolleg/schulen?set_language=en"
)
USER_AGENT = "science-event-digest/1.0 (+https://github.com/genzuuuu/science-event-digest)"

LOW_SIGNAL_LOCATIONS = (
    "china",
    "chengdu",
    "kunming",
    "bangkok",
    "thailand",
    "vietnam",
    "indonesia",
    "malaysia",
)

SCHOOL_URLS = {
    "frontiers of condensed matter 2026": "https://frontiers-les-houches.org/",
    "correl26": "https://www.cond-mat.de/events/correl26/",
    "los alamos computational condensed matter summer school 2026": "https://laccmss.github.io/2026/",
}


def _parse_deadline(text: str) -> datetime.date | None:
    text = text.strip()
    if not text or text in {"\xa0", "-", "–"}:
        return None
    if "until all places" in text.lower():
        return None
    text = re.sub(r"(\d+)\.(\d+)\.(\d{4})", r"\3-\2-\1", text)
    text = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text)
    for fmt in ("%d.%m.%Y", "%Y-%m-%d", "%d %B %Y", "%B %d, %Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", text)
    if match:
        day, month, year = match.groups()
        return datetime.date(int(year), int(month), int(day))
    return None


def _parse_session_start(when: str) -> datetime.date | None:
    match = re.search(r"(\d{1,2})\.(\d{1,2})\.?-.*\.(\d{4})", when)
    if match:
        day, month, year = match.groups()
        return datetime.date(int(year), int(month), int(day))
    match = re.search(r"(\d{1,2})\s+(\w+)\s+-\s+(\d{1,2})\s+(\w+),?\s+(\d{4})", when)
    if match:
        day1, mon1, _, _, year = match.groups()
        try:
            return datetime.datetime.strptime(f"{day1} {mon1} {year}", "%d %B %Y").date()
        except ValueError:
            pass
    return None


def _is_international(where: str) -> bool:
    lowered = where.lower()
    return not any(loc in lowered for loc in LOW_SIGNAL_LOCATIONS)


def _event_from_item(item: dict, source: str):
    from scrape.conferences import ConferenceEvent

    deadline_raw = item.get("deadline")
    deadline = None
    if deadline_raw:
        try:
            deadline = datetime.date.fromisoformat(deadline_raw)
        except ValueError:
            deadline = _parse_deadline(deadline_raw)

    session_start = None
    if item.get("session_start"):
        try:
            session_start = datetime.date.fromisoformat(item["session_start"])
        except ValueError:
            session_start = _parse_session_start(item.get("when", ""))
    else:
        session_start = _parse_session_start(item.get("when", ""))

    return ConferenceEvent(
        name=item["name"],
        full_title=item.get("full_title") or item["name"],
        when=item.get("when", ""),
        where=item.get("where", ""),
        deadline=deadline,
        url=item["url"],
        source=source,
        topics=item.get("topics", "summer school"),
        event_type="summer_school",
    ), session_start


def _in_summer_school_window(
    deadline: datetime.date | None,
    session_start: datetime.date | None,
    horizon_start: datetime.date,
    horizon_end: datetime.date,
) -> bool:
    if deadline and horizon_start <= deadline <= horizon_end:
        return True
    session_horizon_end = horizon_end + datetime.timedelta(days=120)
    if session_start and horizon_start <= session_start <= session_horizon_end:
        if deadline is None:
            return True
        if deadline >= horizon_start - datetime.timedelta(days=60):
            return True
    return False


def fetch_curated_summer_schools(horizon_start: datetime.date, horizon_end: datetime.date):
    if not CURATED_PATH.exists():
        return []

    with CURATED_PATH.open(encoding="utf-8") as f:
        items = json.load(f)

    results = []
    for item in items:
        event, session_start = _event_from_item(item, item.get("source", "curated (summer schools)"))
        if _in_summer_school_window(event.deadline, session_start, horizon_start, horizon_end):
            results.append(event)
    return results


def fetch_dresden_external_schools(horizon_start: datetime.date, horizon_end: datetime.date):
    from scrape.conferences import ConferenceEvent

    try:
        response = requests.get(
            DRESDEN_SCHOOLS_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=60,
        )
        response.raise_for_status()
        html = response.text
    except Exception as exc:
        print(f"Dresden schools fetch failed: {exc}")
        return []

    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", html, flags=re.S)
    results = []
    for row in rows:
        cells = [
            unescape(re.sub(r"<[^>]+>", "", cell)).strip()
            for cell in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", row, flags=re.S)
        ]
        if len(cells) < 4 or cells[0].lower() == "school":
            continue

        name, when, where, deadline_text = cells[0], cells[1], cells[2], cells[3]
        if not _is_international(where):
            continue
        if re.search(r"cancelled|postponed|virtual\)|\(virtual", when + where, re.I):
            continue

        deadline = _parse_deadline(deadline_text)
        session_start = _parse_session_start(when)
        if not _in_summer_school_window(deadline, session_start, horizon_start, horizon_end):
            continue

        url = SCHOOL_URLS.get(name.lower(), DRESDEN_SCHOOLS_URL)
        results.append(
            ConferenceEvent(
                name=name,
                full_title=name,
                when=when,
                where=where.replace("\n", ", ").replace("  ", " "),
                deadline=deadline,
                url=url,
                source="TU Dresden SFB 1143 (external schools)",
                topics="physics, condensed matter, summer school",
                event_type="summer_school",
            )
        )
    return results


def fetch_summer_schools(horizon_start: datetime.date, horizon_end: datetime.date):
    school_horizon_end = horizon_start + datetime.timedelta(
        days=max((horizon_end - horizon_start).days, 90)
    )
    seen: set[str] = set()
    results = []

    for fetcher in (fetch_curated_summer_schools, fetch_dresden_external_schools):
        try:
            for event in fetcher(horizon_start, school_horizon_end):
                key = f"{event.name.lower()}|{event.deadline}|{event.event_type}"
                if key in seen:
                    continue
                seen.add(key)
                results.append(event)
        except Exception as exc:
            print(f"Summer school source failed: {exc}")

    results.sort(key=lambda e: (e.deadline or horizon_start, e.name))
    return results
