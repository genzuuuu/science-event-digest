import argparse
import datetime
import os

from email_sender import send_digest_email, smtp_configured
from llm import summarize_bilingual
from scrape.conferences import fetch_upcoming_conferences, format_conferences_for_llm
from scrape.pks import fetch_pks_week, format_events_for_llm

REPO_URL = "https://github.com/genzuuuu/science-event-digest"

PKS_PROMPT_EN = """
You are curating a weekly digest for a condensed-matter / complex-systems researcher in Dresden.
From the PKS MPI event list, pick talks, colloquia, workshops, and seminars worth attending
in the coming week. Prioritize events with strong physics, materials, computation, or ML angles.
Group by day or category. For each item: date, time (if known), one-sentence why it matters,
and a markdown link. Skip routine admin events. Write in English.
"""

PKS_PROMPT_ZH = """
你正在为一位在德累斯顿的凝聚态/复杂系统研究者整理 PKS 每周活动导读。
从下方 MPI PKS 活动列表中，挑选接下来一周值得参加的讲座、研讨会和 workshop，
优先物理、材料、计算、机器学习相关。按日期或类别分组，每项注明时间、推荐理由，
并使用 markdown 链接。用中文撰写。
"""

CONF_PROMPT_EN = """
You are curating a monthly digest of international conferences in physics, materials science,
and AI / machine learning whose submission deadlines are approaching soon.
Prioritize major international academic venues (APS, MRS, E-MRS, IEEE, ACM, NeurIPS, ICML,
ICLR, CVPR, AAAI, ACL, RSS, CoRL, etc.). Deprioritize or omit regional aggregator
conferences and suspected predatory meetings, especially generic "International Conference on..."
events in low-signal locations.
For each selected item: conference name, location, conference dates, deadline, why it matters,
and a markdown link. Flag urgent deadlines (within 14 days). Write in English.
"""

CONF_PROMPT_ZH = """
你正在整理全球物理、材料、人工智能/机器学习方向的学术会议导读，重点是投稿截止日期临近的
国际性重要会议。优先 APS、MRS、E-MRS、IEEE、ACM、NeurIPS、ICML、ICLR、CVPR、AAAI、ACL、
RSS、CoRL 等知名会议；略过或少写区域性聚合会议和疑似掠夺性会议，尤其是地点信号较弱、
题目泛泛的 "International Conference on..." 类会议。
每项注明会议名称、地点、会期、截止日期、推荐理由和 markdown 链接。
特别标注 14 天内截止的紧急项。用中文撰写。
"""


def week_start_for_run(day: datetime.date) -> datetime.date:
    if day.weekday() == 6:
        return day + datetime.timedelta(days=1)
    return day - datetime.timedelta(days=day.weekday())


def is_last_sunday_of_month(day: datetime.date) -> bool:
    return day.weekday() == 6 and (day + datetime.timedelta(days=7)).month != day.month


def save_report(path: str, header: str, body_en: str, body_zh: str | None = None):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n\n## English\n\n")
        f.write(body_en)
        if body_zh:
            f.write("\n\n## 中文\n\n")
            f.write(body_zh)


def run_pks_weekly(api_key, base_url, model, send_email: bool):
    today = datetime.date.today()
    week_start = week_start_for_run(today)
    week_end = week_start + datetime.timedelta(days=6)
    events = fetch_pks_week(week_start)

    if not events:
        print("No PKS events found for the target week.")
        return False

    raw = format_events_for_llm(events, week_start)
    summary_en, summary_zh = summarize_bilingual(
        api_key, base_url, model, PKS_PROMPT_EN, PKS_PROMPT_ZH, raw
    )

    now = datetime.datetime.now()
    date_str = today.isoformat()
    header = (
        f"# PKS Weekly Event Digest\n\n"
        f"- **Week:** {week_start.isoformat()} – {week_end.isoformat()}\n"
        f"- **Generated:** {now.isoformat()}\n"
        f"- **Source:** [MPI PKS Dresden](https://www.pks.mpg.de/events)\n"
    )

    save_report(f"data/pks/{date_str}.md", header, summary_en, summary_zh)
    save_report("data/pks/README.md", header, summary_en, summary_zh)

    if send_email or smtp_configured():
        send_digest_email(
            subject=f"PKS Weekly Digest | 德累斯顿 PKS 每周活动 ({week_start.isoformat()})",
            summary_en=summary_en,
            summary_zh=summary_zh,
            meta={
                "title": "PKS Weekly Event Digest",
                "period": f"{week_start.isoformat()} – {week_end.isoformat()}",
                "generated_at": now.isoformat(),
                "repo_url": REPO_URL,
            },
        )
    return True


def run_conferences_monthly(api_key, base_url, model, send_email: bool, force: bool = False):
    today = datetime.date.today()
    if not force and not is_last_sunday_of_month(today):
        print(f"Today ({today}) is not the last Sunday of the month; skipping.")
        return False

    horizon = 60
    events = fetch_upcoming_conferences(horizon_days=horizon, reference=today)
    if not events:
        print("No upcoming conference deadlines found.")
        return False

    raw = format_conferences_for_llm(events, today, horizon)
    summary_en, summary_zh = summarize_bilingual(
        api_key, base_url, model, CONF_PROMPT_EN, CONF_PROMPT_ZH, raw
    )

    now = datetime.datetime.now()
    month_str = today.strftime("%Y-%m")
    header = (
        f"# Global Conference Deadline Digest\n\n"
        f"- **Month:** {month_str}\n"
        f"- **Deadline window:** next {horizon} days\n"
        f"- **Generated:** {now.isoformat()}\n"
        f"- **Sources:** ai-deadlines, curated, WikiCFP (filtered), E-MRS\n"
    )

    save_report(f"data/conferences/{month_str}.md", header, summary_en, summary_zh)
    save_report("data/conferences/README.md", header, summary_en, summary_zh)

    if send_email or smtp_configured():
        send_digest_email(
            subject=f"Conference Deadlines Digest | 全球会议截止提醒 ({month_str})",
            summary_en=summary_en,
            summary_zh=summary_zh,
            meta={
                "title": "Global Conference Deadline Digest",
                "period": f"{month_str}, next {horizon} days",
                "generated_at": now.isoformat(),
                "repo_url": REPO_URL,
            },
        )
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, choices=["pks-weekly", "conferences-monthly"])
    parser.add_argument("--api_key", default=os.environ.get("API_KEY", ""))
    parser.add_argument("--base_url", default=os.environ.get("BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--model", default=os.environ.get("MODEL", "deepseek-v4-flash"))
    parser.add_argument("--send_email", action="store_true")
    parser.add_argument("--force", action="store_true", help="Skip last-Sunday check for conferences")
    args = parser.parse_args()

    if args.task == "pks-weekly":
        ok = run_pks_weekly(args.api_key, args.base_url, args.model, args.send_email)
    else:
        ok = run_conferences_monthly(
            args.api_key, args.base_url, args.model, args.send_email, force=args.force
        )
    if not ok:
        raise SystemExit(0)


if __name__ == "__main__":
    main()
