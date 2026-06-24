import datetime
from dataclasses import dataclass

from scrape.sources.ai_deadlines import fetch_ai_deadlines
from scrape.sources.curated import fetch_curated_conferences
from scrape.sources.emrs import fetch_emrs_meetings
from scrape.sources.summer_schools import fetch_summer_schools
from scrape.sources.wikicfp import fetch_wikicfp

SOURCE_NAMES = [
    "ai-deadlines (mlciv.com) — top-tier AI/ML/CV/NLP/robotics",
    "curated — APS/MRS/NeurIPS/ICML/CVPR/ICLR/Elsevier materials (verified)",
    "curated summer schools — Les Houches, MLSS, Jülich, CECAM, ICTP, etc.",
    "TU Dresden SFB 1143 — external summer/winter schools (Europe-focused)",
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
    event_type: str = "conference"


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
        ("summer-schools", lambda: fetch_summer_schools(today, horizon_end)),
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
    conferences = [e for e in events if e.event_type != "summer_school"]
    summer_schools = [e for e in events if e.event_type == "summer_school"]

    lines = [
        f"Submission / application deadlines between {today.isoformat()} and "
        f"{(today + datetime.timedelta(days=horizon_days)).isoformat()}",
        "Topics: physics, materials science, AI / machine learning, summer schools",
        "Sources:",
    ]
    for source in SOURCE_NAMES:
        lines.append(f"- {source}")
    lines.append("")
    lines.append(
        "Prioritize major international academic venues (APS, MRS, E-MRS, IEEE, ACM, "
        "NeurIPS, ICML, ICLR, CVPR, AAAI, Les Houches, MLSS, CECAM, ICTP, etc.). "
        "Deprioritize regional aggregator conferences."
    )
    lines.append("")
    lines.append(
        "Include a dedicated Summer Schools section for PhD-level schools in physics, "
        "materials, and ML. Note if an application deadline may have just passed but "
        "the school session is still upcoming."
    )
    lines.append("")

    if conferences:
        lines.append("## Conferences")
        lines.append("")
        for i, event in enumerate(conferences, 1):
            lines.extend(_format_event_block(i, event))

    if summer_schools:
        lines.append("## Summer Schools")
        lines.append("")
        for i, event in enumerate(summer_schools, 1):
            lines.extend(_format_event_block(i, event, label="Summer School"))

    return "\n".join(lines)


def _format_event_block(index: int, event: ConferenceEvent, label: str = "Conference") -> list[str]:
    lines = [
        f"### {label} [{index}]",
        f"Name: {event.name}",
        f"Full title: {event.full_title}",
        f"URL: {event.url}",
        f"Dates: {event.when}",
        f"Location: {event.where}",
        f"Application deadline: {event.deadline.isoformat() if event.deadline else 'unknown'}",
        f"Data source: {event.source}",
    ]
    if event.topics:
        lines.append(f"Topics: {event.topics}")
    lines.append("")
    return lines
