import datetime
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin

import requests

PKS_BASE = "https://www.pks.mpg.de"
WORKSHOPS_URL = f"{PKS_BASE}/events/workshops-seminars"
EVENTS_URL = f"{PKS_BASE}/events"
USER_AGENT = "science-event-digest/1.0 (+https://github.com/genzuuuu/science-event-digest)"


@dataclass
class PksEvent:
    kind: str
    title: str
    start: datetime.date
    end: datetime.date | None
    time: str
    speaker: str
    category: str
    url: str
    details: str


def _fetch(url: str) -> str:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
    response.raise_for_status()
    return response.text


def _parse_date(value: str) -> datetime.date | None:
    value = value.strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d %b %Y", "%d  %b %Y"):
        try:
            return datetime.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _in_range(event_date: datetime.date, start: datetime.date, end: datetime.date) -> bool:
    return start <= event_date <= end


def fetch_talks(week_start: datetime.date) -> list[PksEvent]:
    html = _fetch(EVENTS_URL)
    match = re.search(r'class="xm_mpipks_xrbs__calendar-ajax--url" value="([^"]+)"', html)
    if not match:
        raise ValueError("Could not find PKS talks calendar AJAX URL")

    ajax_path = unescape(match.group(1))
    ajax_url = urljoin(PKS_BASE, ajax_path)
    ts = int(datetime.datetime.combine(week_start, datetime.time.min).timestamp())
    response = requests.post(
        ajax_url,
        data={"dateFromTS": ts},
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    response.raise_for_status()
    fragment = response.text

    week_end = week_start + datetime.timedelta(days=6)
    events = []
    blocks = re.findall(
        r'<div class="col-md-3 col-sm-6".*?</div>\s*</div>',
        fragment,
        flags=re.S,
    )
    for block in blocks:
        title_m = re.search(r"<h3>(.*?)</h3>", block, re.S)
        link_m = re.search(r'<a href="([^"]+)"', block)
        date_m = re.search(r"icon-calendar.*?(\d{1,2}\s+\w+\s+\d{4})", block, re.S)
        time_m = re.search(r"icon-time.*?(\d{1,2}:\d{2}\s*(?:AM|PM))", block, re.S)
        speaker_m = re.search(r"<i>\s*(.*?)\s*</i>", block, re.S)
        if not title_m or not date_m:
            continue
        title = re.sub(r"<[^>]+>", "", title_m.group(1))
        title = unescape(title.strip())
        start = _parse_date(date_m.group(1))
        if not start or not _in_range(start, week_start, week_end):
            continue
        url = link_m.group(1) if link_m else f"{PKS_BASE}/events/talks"
        speaker = unescape(re.sub(r"<[^>]+>", "", speaker_m.group(1)).strip()) if speaker_m else ""
        events.append(
            PksEvent(
                kind="talk",
                title=title,
                start=start,
                end=None,
                time=time_m.group(1).strip() if time_m else "",
                speaker=speaker,
                category="Talk / Colloquium",
                url=url,
                details=speaker,
            )
        )
    return events


def fetch_workshops(week_start: datetime.date) -> list[PksEvent]:
    html = _fetch(WORKSHOPS_URL)
    week_end = week_start + datetime.timedelta(days=6)
    events = []

    panels = re.findall(
        r'<div class="panel article.*?</div>\s*</div>\s*</div>',
        html,
        flags=re.S,
    )
    for panel in panels:
        start_m = re.search(r'<time datetime="(\d{4}-\d{2}-\d{2})">', panel)
        end_m = re.search(r'<meta itemprop="datePublished" content="(\d{4}-\d{2}-\d{2})".*?'
                          r'<time datetime="(\d{4}-\d{2}-\d{2})">', panel, re.S)
        # end date: second time tag after datePublished
        end_dates = re.findall(r'<time datetime="(\d{4}-\d{2}-\d{2})">', panel)
        category_m = re.search(r'<span class="oblique">([^<]+)</span>', panel)
        title_m = re.search(r"<h3>(.*?)</h3>", panel, re.S)
        link_m = re.search(r'href="(/[^"]+)"[^>]*><span class="sr-only">Read more', panel)
        body_m = re.search(r'<div class="media-body">(.*?)</div>', panel, re.S)
        if not start_m or not title_m:
            continue
        start = _parse_date(start_m.group(1))
        end = _parse_date(end_dates[1]) if len(end_dates) > 1 else None
        if not start:
            continue
        # include if workshop overlaps the week
        effective_end = end or start
        if effective_end < week_start or start > week_end:
            continue
        title = unescape(re.sub(r"<[^>]+>", "", title_m.group(1)).strip())
        path = link_m.group(1) if link_m else ""
        url = urljoin(PKS_BASE, path) if path else WORKSHOPS_URL
        details = unescape(re.sub(r"<[^>]+>", "", body_m.group(1)).strip()) if body_m else ""
        events.append(
            PksEvent(
                kind="workshop",
                title=title,
                start=start,
                end=end,
                time="",
                speaker="",
                category=unescape(category_m.group(1).strip()) if category_m else "Workshop",
                url=url,
                details=details,
            )
        )
    return events


def fetch_pks_week(week_start: datetime.date | None = None) -> list[PksEvent]:
    if week_start is None:
        today = datetime.date.today()
        week_start = today + datetime.timedelta(days=(7 - today.weekday()) % 7)
        if today.weekday() == 6:
            week_start = today

    talks = fetch_talks(week_start)
    workshops = fetch_workshops(week_start)
    merged = talks + workshops
    merged.sort(key=lambda e: (e.start, e.kind, e.title))
    return merged


def format_events_for_llm(events: list[PksEvent], week_start: datetime.date) -> str:
    week_end = week_start + datetime.timedelta(days=6)
    lines = [
        f"PKS MPI Dresden events for {week_start.isoformat()} to {week_end.isoformat()}",
        f"Source: {PKS_BASE}",
        "",
    ]
    for i, event in enumerate(events, 1):
        end = f" to {event.end.isoformat()}" if event.end else ""
        lines.append(f"### Event [{i}]")
        lines.append(f"Type: {event.category} ({event.kind})")
        lines.append(f"Title: {event.title}")
        lines.append(f"URL: {event.url}")
        lines.append(f"Date: {event.start.isoformat()}{end}")
        if event.time:
            lines.append(f"Time: {event.time}")
        if event.speaker:
            lines.append(f"Speaker: {event.speaker}")
        if event.details:
            lines.append(f"Details: {event.details}")
        lines.append("")
    return "\n".join(lines)
