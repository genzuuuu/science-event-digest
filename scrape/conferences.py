import datetime
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin

import requests

WIKICFP_BASE = "http://wikicfp.com"
USER_AGENT = "science-event-digest/1.0 (+https://github.com/genzuuuu/science-event-digest)"

SEARCH_QUERIES = [
    "materials science",
    "condensed matter physics",
    "machine learning",
    "artificial intelligence",
    "computational physics",
]


@dataclass
class ConferenceEvent:
    name: str
    full_title: str
    when: str
    where: str
    deadline: datetime.date | None
    url: str
    source_query: str


def _fetch_wikicfp(query: str) -> str:
    response = requests.get(
        f"{WIKICFP_BASE}/cfp/servlet/tool.search",
        params={"q": query, "year": "f"},
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    response.raise_for_status()
    return response.text


def _parse_deadline(text: str) -> datetime.date | None:
    text = text.strip()
    for fmt in ("%b %d, %Y", "%b %d,%Y", "%d %b %Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _parse_wikicfp_table(html: str, query: str) -> list[ConferenceEvent]:
    events = []
    rows = re.findall(
        r'<tr bgcolor="#(?:f6f6f6|e6e6e6)">(.*?)</tr>\s*<tr bgcolor="#(?:f6f6f6|e6e6e6)">(.*?)</tr>',
        html,
        flags=re.S,
    )
    for row1, row2 in rows:
        link_m = re.search(r'<a href="(/cfp/servlet/event\.[^"]+)">([^<]+)</a>', row1)
        title_m = re.search(r"<td[^>]*>([^<].*?)</td>", row1)
        when_m = re.search(r"<td align=\"left\">([^<]+)</td>", row2)
        where_m = re.search(r"<td align=\"left\">([^<]+)</td>", row2[row2.find("</td>") + 5 :])
        parts = re.findall(r"<td align=\"left\">([^<]+)</td>", row2)
        if not link_m or len(parts) < 3:
            continue
        when, where, deadline_text = parts[0], parts[1], parts[2]
        events.append(
            ConferenceEvent(
                name=unescape(link_m.group(2).strip()),
                full_title=unescape(title_m.group(1).strip()) if title_m else unescape(link_m.group(2).strip()),
                when=unescape(when.strip()),
                where=unescape(where.strip()),
                deadline=_parse_deadline(deadline_text),
                url=urljoin(WIKICFP_BASE, link_m.group(1)),
                source_query=query,
            )
        )
    return events


def fetch_upcoming_conferences(
    horizon_days: int = 45,
    reference: datetime.date | None = None,
) -> list[ConferenceEvent]:
    today = reference or datetime.date.today()
    horizon_end = today + datetime.timedelta(days=horizon_days)
    seen_urls: set[str] = set()
    results: list[ConferenceEvent] = []

    for query in SEARCH_QUERIES:
        try:
            html = _fetch_wikicfp(query)
            for event in _parse_wikicfp_table(html, query):
                if event.url in seen_urls:
                    continue
                if not event.deadline:
                    continue
                if today <= event.deadline <= horizon_end:
                    seen_urls.add(event.url)
                    results.append(event)
        except Exception as exc:
            print(f"WikiCFP query failed ({query}): {exc}")

    results.sort(key=lambda e: (e.deadline, e.name))
    return results


def format_conferences_for_llm(events: list[ConferenceEvent], today: datetime.date, horizon_days: int) -> str:
    lines = [
        f"Conference submission deadlines between {today.isoformat()} and "
        f"{(today + datetime.timedelta(days=horizon_days)).isoformat()}",
        "Topics: physics, materials science, AI / machine learning",
        "Source: WikiCFP (global listings)",
        "",
    ]
    for i, event in enumerate(events, 1):
        lines.append(f"### Conference [{i}]")
        lines.append(f"Name: {event.name}")
        lines.append(f"Full title: {event.full_title}")
        lines.append(f"URL: {event.url}")
        lines.append(f"Conference dates: {event.when}")
        lines.append(f"Location: {event.where}")
        lines.append(f"Submission deadline: {event.deadline.isoformat() if event.deadline else 'unknown'}")
        lines.append(f"Found via search: {event.source_query}")
        lines.append("")
    return "\n".join(lines)
