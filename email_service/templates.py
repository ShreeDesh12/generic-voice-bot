import json
from datetime import datetime


def format_transcript_email(
    bot_name: str,
    transcript_rows: list[dict],
    summary: dict | None = None,
    contact_info: dict | None = None,
) -> str:
    """Build an HTML email body from transcript rows and an optional summary."""
    # Visitor contact info section
    contact_html = ""
    if contact_info and any(contact_info.values()):
        rows = []
        if contact_info.get("name"):
            rows.append(f'<tr><td style="padding:6px 12px;font-weight:600;color:#555;">Name</td><td style="padding:6px 12px;">{contact_info["name"]}</td></tr>')
        if contact_info.get("email"):
            rows.append(f'<tr><td style="padding:6px 12px;font-weight:600;color:#555;">Email</td><td style="padding:6px 12px;"><a href="mailto:{contact_info["email"]}">{contact_info["email"]}</a></td></tr>')
        if contact_info.get("phone"):
            rows.append(f'<tr><td style="padding:6px 12px;font-weight:600;color:#555;">Phone</td><td style="padding:6px 12px;">{contact_info["phone"]}</td></tr>')
        if rows:
            contact_html = (
                '<h2 style="color:#333;margin-top:24px;">Visitor Contact Info</h2>'
                '<table style="background:#e8f4fd;border-radius:8px;width:100%;border-collapse:collapse;">'
                + "".join(rows) + '</table>'
            )

    messages_html = ""
    for row in transcript_rows:
        role = row["role"].capitalize()
        content = row["content"].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        ts = row.get("created_at", "")
        if isinstance(ts, datetime):
            ts = ts.strftime("%H:%M:%S")
        elif isinstance(ts, str) and "T" in ts:
            ts = ts.split("T")[1][:8]
        bg = "#e8f4fd" if row["role"] == "user" else "#f0f0f0"
        messages_html += (
            f'<div style="background:{bg};padding:10px 14px;border-radius:8px;margin-bottom:8px;">'
            f'<strong>{role}</strong> <span style="color:#888;font-size:0.85em;">{ts}</span>'
            f'<br/><span style="white-space:pre-wrap;">{content}</span>'
            f"</div>"
        )

    summary_html = ""
    if summary:
        # Handle raw_summary fallback
        if "raw_summary" in summary:
            raw = summary["raw_summary"]
            summary_html = (
                '<h2 style="color:#333;margin-top:24px;">Summary</h2>'
                f'<p style="background:#f8f8f8;padding:14px;border-radius:8px;'
                f'white-space:pre-wrap;">{raw}</p>'
            )
        else:
            parts = []
            if summary.get("visitor_intent"):
                intent = summary["visitor_intent"]
                parts.append(
                    f'<tr><td style="padding:8px 12px;font-weight:600;color:#555;vertical-align:top;">Visitor Intent</td>'
                    f'<td style="padding:8px 12px;">{intent}</td></tr>'
                )
            if summary.get("key_topics"):
                topics = ", ".join(summary["key_topics"])
                parts.append(
                    f'<tr><td style="padding:8px 12px;font-weight:600;color:#555;vertical-align:top;">Key Topics</td>'
                    f'<td style="padding:8px 12px;">{topics}</td></tr>'
                )
            if summary.get("action_items"):
                items = "".join(f"<li>{item}</li>" for item in summary["action_items"])
                parts.append(
                    f'<tr><td style="padding:8px 12px;font-weight:600;color:#555;vertical-align:top;">Action Items</td>'
                    f'<td style="padding:8px 12px;"><ul style="margin:0;padding-left:18px;">{items}</ul></td></tr>'
                )
            if summary.get("overall_sentiment"):
                sentiment = summary["overall_sentiment"]
                parts.append(
                    f'<tr><td style="padding:8px 12px;font-weight:600;color:#555;vertical-align:top;">Sentiment</td>'
                    f'<td style="padding:8px 12px;">{sentiment.capitalize()}</td></tr>'
                )
            rows_html = "".join(parts)
            summary_html = (
                '<h2 style="color:#333;margin-top:24px;">Summary</h2>'
                f'<table style="background:#f8f8f8;border-radius:8px;width:100%;border-collapse:collapse;">'
                f'{rows_html}</table>'
            )

    return f"""
    <html>
    <body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
                 max-width:640px;margin:0 auto;padding:20px;color:#222;">
        <h1 style="color:#333;">Chat Transcript &mdash; {bot_name}</h1>
        <p style="color:#666;">A conversation session with your portfolio bot has ended.</p>
        {contact_html}
        {summary_html}
        <h2 style="color:#333;margin-top:24px;">Full Transcript</h2>
        {messages_html}
        <hr style="margin-top:32px;border:none;border-top:1px solid #ddd;"/>
        <p style="color:#999;font-size:0.85em;">Sent by My Voice</p>
    </body>
    </html>
    """
