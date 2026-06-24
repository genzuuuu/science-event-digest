import datetime
import re
from html import unescape
from urllib.parse import urljoin

import requests

WIKICFP_BASE = "http://wikicfp.com"
USER_AGENT = "science-event-digest/1.0 (+https://github.com/genzuuuu/science-event-digest)"

# Target established societies / venues rather than generic keyword spam
WIKICFP_QUERIES = [
    "APS",
    "American Physical Society",
    "MRS meeting",
    "materials research society",
    "condensed matter",
    "IEEE",
    "DPG",
    "IOP",
    "ACS meeting",
    "Gordon Research",
    "computational materials",
    "NeurIPS",
    "ICML",
    "CVPR",
]

# Generic aggregator conferences in these locations are usually low-signal
LOW_SIGNAL_LOCATIONS = (
    "china",
    "kunming",
    "nanjing",
    "chengdu",
    "harbin",
    "xiamen",
    "hangzhou",
    "guangzhou",
    "shenzhen",
    "chongqing",
    "wuhan",
    "changsha",
    "tianjin",
    "bangkok",
    "thailand",
    "vietnam",
    "indonesia",
    "malaysia",
    "philippines",
)

TRUSTED_NAME_MARKERS = (
    "ieee",
    "acm",
    "aps",
    "mrs",
    "acs",
    "dpg",
    "iop",
    "spie",
    "siam",
    "gordon research",
    "american physical society",
    "materials research society",
    "european materials",
    "e-mrs",
    "emrs",
    "avss",
    "sigma",
)


def _parse_deadline(text: str) -> datetime.date | None:
    text = text.strip()
    for fmt in ("%b %d, %Y", "%b %d,%Y", "%d %b %Y"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


HIGH_SIGNAL_REGIONS = (
    "usa",
    "united states",
    "u.s.",
    "canada",
    "uk",
    "united kingdom",
    "germany",
    "france",
    "netherlands",
    "switzerland",
    "austria",
    "italy",
    "spain",
    "portugal",
    "belgium",
    "denmark",
    "sweden",
    "norway",
    "finland",
    "ireland",
    "australia",
    "japan",
    "south korea",
    "singapore",
    "israel",
    "greece",
    "hungary",
    "poland",
    "czech",
    "montréal",
    "montreal",
    "boston",
    "denver",
    "california",
    "colorado",
    "hawaii",
    "strasbourg",
    "warsaw",
    "vienna",
    "munich",
    "london",
    "paris",
    "amsterdam",
    "zurich",
)


def _is_international_venue(where: str) -> bool:
    w = where.lower()
    return any(region in w for region in HIGH_SIGNAL_REGIONS)


def _has_trusted_marker(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in TRUSTED_NAME_MARKERS)


def _is_generic_spam(name: str, full_title: str, where: str) -> bool:
    if _has_trusted_marker(name):
        if any(loc in where.lower() for loc in LOW_SIGNAL_LOCATIONS):
            return True
        return False

    blob = f"{name} {full_title}".lower()
    if re.match(r"^ic[a-z]{2,}\b", name.lower()):
        return True
    if re.search(r"\bthe \d", full_title.lower()):
        return True
    if "international conference on" in full_title.lower():
        return True
    if re.search(r"\b\d{1,2}(st|nd|rd|th)\b", full_title.lower()):
        return True
    if "international conference" in full_title.lower() and any(
        loc in where.lower() for loc in LOW_SIGNAL_LOCATIONS
    ):
        return True
    if "society trends" in blob:
        return True
    return False


def _is_low_signal(name: str, full_title: str, where: str) -> bool:
    if _is_generic_spam(name, full_title, where):
        return True

    blob = f"{name} {full_title} {where}".lower()

    if any(marker in blob for marker in TRUSTED_NAME_MARKERS):
        return False

    if _is_international_venue(where):
        return False

    if any(loc in where.lower() for loc in LOW_SIGNAL_LOCATIONS):
        return True

    return True


def _fetch_html(query: str) -> str:
    response = requests.get(
        f"{WIKICFP_BASE}/cfp/servlet/tool.search",
        params={"q": query, "year": "f"},
        headers={"User-Agent": USER_AGENT},
        timeout=60,
    )
    response.raise_for_status()
    return response.text


def _parse_table(html: str, query: str):
    from scrape.conferences import ConferenceEvent

    events = []
    rows = re.findall(
        r'<tr bgcolor="#(?:f6f6f6|e6e6e6)">(.*?)</tr>\s*<tr bgcolor="#(?:f6f6f6|e6e6e6)">(.*?)</tr>',
        html,
        flags=re.S,
    )
    for row1, row2 in rows:
        link_m = re.search(r'<a href="(/cfp/servlet/event\.[^"]+)">([^<]+)</a>', row1)
        title_m = re.search(r"<td[^>]*>([^<].*?)</td>", row1)
        parts = re.findall(r'<td align="left">([^<]+)</td>', row2)
        if not link_m or len(parts) < 3:
            continue
        name = unescape(link_m.group(2).strip())
        full_title = unescape(title_m.group(1).strip()) if title_m else name
        when, where, deadline_text = parts[0], parts[1], parts[2]
        if _is_low_signal(name, full_title, where):
            continue
        events.append(
            ConferenceEvent(
                name=name,
                full_title=full_title,
                when=unescape(when.strip()),
                where=unescape(where.strip()),
                deadline=_parse_deadline(deadline_text),
                url=urljoin(WIKICFP_BASE, link_m.group(1)),
                source=f"WikiCFP ({query})",
                topics=query,
            )
        )
    return events


def fetch_wikicfp(horizon_start: datetime.date, horizon_end: datetime.date, max_events: int = 8):
    seen_urls: set[str] = set()
    results = []

    for query in WIKICFP_QUERIES:
        try:
            html = _fetch_html(query)
            for event in _parse_table(html, query):
                if event.url in seen_urls or not event.deadline:
                    continue
                if not (horizon_start <= event.deadline <= horizon_end):
                    continue
                seen_urls.add(event.url)
                results.append(event)
                if len(results) >= max_events:
                    return results
        except Exception as exc:
            print(f"WikiCFP query failed ({query}): {exc}")

    return results
