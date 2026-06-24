import datetime
from dataclasses import dataclass

from scrape.sources.ai_deadlines import fetch_ai_deadlines
from scrape.sources.curated import fetch_curated_conferences
from scrape.sources.emrs import fetch_emrs_meetings
from scrape.sources.wikicfp import fetch_wikicfp

SOURCE_NAMES = [
    "ai-deadlines (mlciv.com) — top-tier AI/ML/CV/NLP/robotics",
    "curated — APS/MRS/NeurIPS/ICML/CVPR/ICLR/Elsevier materials (verified)",
    "WikiCFP — APS/MRS/IEEE/condensed matter (international filter)",
    "E-MRS (european-mrs.com) — European materials meetings",
]


@dataclass
class ConferenceEvent:
    name: str
    full_title: str
    when: str
    where: str
    deadline: datetime.date | None
    url: str
    source: str
    topics: str = ""


def _dedupe_key(event: ConferenceEvent) -> str:
    return f"{event.name.lower()}|{event.deadline}"


def fetch_upcoming_conferences(
    horizon_days: int = 60,
    reference: datetime.date | None = None,
) -> list[ConferenceEvent]:
    today = reference or datetime.date.today()
    horizon_end = today + datetime.timedelta(days=horizon_days)
    seen: set[str] = set()
    results: list[ConferenceEvent] = []

    fetchers = [
        ("ai-deadlines", lambda: fetch_ai_deadlines(today, horizon_end)),
        ("curated", lambda: fetch_curated_conferences(today, horizon_end)),
        ("wikicfp", lambda: fetch_wikicfp(today, horizon_end)),
        ("emrs", lambda: fetch_emrs_meetings(today, horizon_end)),
    ]

    for source_name, fetcher in fetchers:
        try:
            events = fetcher()
            print(f"[{source_name}] fetched {len(events)} events")
            for event in events:
                key = _dedupe_key(event)
                if key in seen:
                    continue
                seen.add(key)
                results.append(event)
        except Exception as exc:
            print(f"[{source_name}] failed: {exc}")

    results.sort(key=lambda e: (e.deadline or today, e.name))
    return results


def format_conferences_for_llm(events: list[ConferenceEvent], today: datetime.date, horizon_days: int) -> str:
    lines = [
        f"Conference submission deadlines between {today.isoformat()} and "
        f"{(today + datetime.timedelta(days=horizon_days)).isoformat()}",
        "Topics: physics, materials science, AI / machine learning",
        "Sources:",
    ]
    for source in SOURCE_NAMES:
        lines.append(f"- {source}")
    lines.append("")
    lines.append(
        "Prioritize major international academic venues (APS, MRS, E-MRS, IEEE, ACM, "
        "NeurIPS, ICML, ICLR, CVPR, AAAI, etc.). Deprioritize regional aggregator conferences."
    )
    lines.append("")

    for i, event in enumerate(events, 1):
        lines.append(f"### Conference [{i}]")
        lines.append(f"Name: {event.name}")
        lines.append(f"Full title: {event.full_title}")
        lines.append(f"URL: {event.url}")
        lines.append(f"Conference dates: {event.when}")
        lines.append(f"Location: {event.where}")
        lines.append(f"Submission deadline: {event.deadline.isoformat() if event.deadline else 'unknown'}")
        lines.append(f"Data source: {event.source}")
        if event.topics:
            lines.append(f"Topics: {event.topics}")
        lines.append("")
    return "\n".join(lines)
