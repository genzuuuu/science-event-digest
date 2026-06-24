import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import markdown


def smtp_configured() -> bool:
    return bool(
        os.environ.get("SMTP_HOST")
        and os.environ.get("SMTP_USER")
        and os.environ.get("SMTP_PASSWORD")
        and os.environ.get("EMAIL_TO")
    )


def send_digest_email(subject: str, summary_en: str, summary_zh: str, meta: dict) -> None:
    if not smtp_configured():
        print("SMTP not configured; skipping email.")
        return

    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ["SMTP_USER"]
    password = os.environ["SMTP_PASSWORD"]
    to_addrs = [addr.strip() for addr in os.environ["EMAIL_TO"].split(",") if addr.strip()]
    from_addr = os.environ.get("SMTP_FROM", user)

    meta_html = (
        f"<p><b>{meta.get('title', 'Science Event Digest')}</b></p>"
        f"<p><b>Period:</b> {meta.get('period', '')}</p>"
        f"<p><b>Generated:</b> {meta['generated_at']}</p>"
        f"<p><a href=\"{meta['repo_url']}\">View on GitHub</a></p>"
    )

    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; line-height: 1.6; color: #222; max-width: 800px; margin: 0 auto; padding: 20px;">
{meta_html}
<hr>
<h2>English</h2>
{markdown.markdown(summary_en, extensions=["extra", "sane_lists"])}
<hr>
<h2>中文</h2>
{markdown.markdown(summary_zh, extensions=["extra", "sane_lists"])}
</body>
</html>"""

    text_body = (
        f"{meta.get('title', 'Science Event Digest')}\n"
        f"Period: {meta.get('period', '')}\n"
        f"Generated: {meta['generated_at']}\n\n"
        f"=== English ===\n\n{summary_en}\n\n"
        f"=== 中文 ===\n\n{summary_zh}\n"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(host, port, timeout=60) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(from_addr, to_addrs, msg.as_string())

    print(f"Email sent to {', '.join(to_addrs)}")
