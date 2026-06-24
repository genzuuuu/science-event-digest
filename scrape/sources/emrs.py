import datetime
import re
from html import unescape

import requests

EMRS_DEADLINES_URL = "https://www.european-mrs.com/meetings/deadlines"
USER_AGENT = "science-event-digest/1.0 (+https://github.com/genzuuuu/science-event-digest)"

MEETING_URLS = {
    ("2026", "Spring"): "https://www.european-mrs.com/meetings/2026-spring-meeting-exhibit",
    ("2026", "Fall"): "https://www.european-mrs.com/meetings/2026-fall-meeting-exhibit",
    ("2027", "Spring"): "https://www.european-mrs.com/meetings/2027-spring-meeting-exhibit",
    ("2027", "Fall"): "https://www.european-mrs.com/meetings/2027-fall-meeting-exhibit",
}

MEETING_LOCATIONS = {
    ("2026", "Spring"): ("May 25–29, 2026", "Strasbourg, France"),
    ("2026", "Fall"): ("September 14–17, 2026", "Warsaw, Poland"),
    ("2027", "Spring"): ("May 17–21, 2027", "Strasbourg, France"),
}


def _parse_date(text: str) -> datetime.date | None:
    text = re.sub(r"(\d+)(st|nd|rd|th)", r"\1", text.strip())
    for fmt in ("%B %d, %Y", "%d %B %Y", "%b %d, %Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def fetch_emrs_meetings(horizon_start: datetime.date, horizon_end: datetime.date):
    from scrape.conferences import ConferenceEvent

    try:
        response = requests.get(
            EMRS_DEADLINES_URL,
            headers={"User-Agent": USER_AGENT},
            timeout=60,
        )
        response.raise_for_status()
        plain = unescape(re.sub(r"<[^>]+>", " ", response.text))
        plain = re.sub(r"\s+", " ", plain)
    except Exception as exc:
        print(f"E-MRS fetch failed: {exc}")
        return []

    results = []
    for match in re.finditer(
        r"E-MRS (\d{4}) - (Spring|Fall) Meeting & Exhibit\s+Deadline for abstract submission\s+"
        r"([A-Za-z]+ \d+(?:st|nd|rd|th)?, \d{4})",
        plain,
        re.I,
    ):
        year, season, deadline_text = match.group(1), match.group(2), match.group(3)
        deadline = _parse_date(deadline_text)
        if not deadline or not (horizon_start <= deadline <= horizon_end):
            continue

        when, where = MEETING_LOCATIONS.get((year, season), ("", ""))
        tail = plain[match.end() : match.end() + 220]
        location_match = re.search(
            r"([A-Za-z][\w\s,&'-]+(?:University|Centre|Poland|France|Germany)[^E]{0,80})",
            tail,
        )
        if location_match and not where:
            where = location_match.group(1).strip()

        label = f"E-MRS {year} {season} Meeting"
        url = MEETING_URLS.get((year, season), EMRS_DEADLINES_URL)
        results.append(
            ConferenceEvent(
                name=label,
                full_title=f"European Materials Research Society {year} {season} Meeting & Exhibit",
                when=when,
                where=where,
                deadline=deadline,
                url=url,
                source="E-MRS (european-mrs.com)",
                topics="materials science",
            )
        )
    return results
