"""
Verichains LeadHunter — Telegram Bot Helper
Sends formatted alerts to your personal Telegram chat.
"""

import requests
import config


def send_message(text: str) -> bool:
    """Send a plain text message to Telegram."""
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        print("[Telegram] ⚠️  Bot token or chat ID not configured. Printing to console:")
        print(text)
        return False

    url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"[Telegram] ❌ Failed to send message: {e}")
        return False


def alert_new_lead(lead: dict) -> bool:
    """Send a formatted NEW LEAD alert."""
    score = lead.get("score", 0)
    priority = "🔴 HOT" if score >= 80 else "🟡 WARM"

    text = (
        f"🔥 <b>NEW LEAD — Score: {score}/100 {priority}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{lead.get('name', 'Unknown')}</b>\n"
        f"🏷️ {lead.get('category', 'N/A')}\n"
        f"💰 {lead.get('funding', 'N/A')}\n"
        f"🛠️ {lead.get('tech', 'N/A')}\n"
        f"🔍 Audit: {lead.get('audit_status', 'Unknown')}\n"
        f"📡 Source: {lead.get('source', 'N/A')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 {lead.get('summary', '')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Action:</b> OSINT contact → outreach &lt;24h"
    )
    return send_message(text)


def alert_upgrade(upgrade: dict) -> bool:
    """Send a formatted UPGRADE DETECTED alert."""
    text = (
        f"⚠️ <b>UPGRADE — Score: {upgrade.get('score', 0)}/100</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{upgrade.get('name', 'Unknown')}</b>"
        f" {'(Khách cũ)' if upgrade.get('is_existing_client') else ''}\n"
        f"🔀 {upgrade.get('change_type', 'Update')}: {upgrade.get('change_detail', 'N/A')}\n"
        f"📊 Lines changed: {upgrade.get('lines_changed', 'N/A')}\n"
        f"🕐 Last audit: {upgrade.get('last_audit', 'Unknown')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 {upgrade.get('summary', '')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Action:</b> Reach out → upsell audit"
    )
    return send_message(text)


def alert_incident(incident: dict) -> bool:
    """Send a formatted HACK/INCIDENT alert."""
    targets = incident.get("targets", [])
    targets_text = "\n".join(
        [f"  {i+1}. {t}" for i, t in enumerate(targets[:5])]
    ) if targets else "  (Đang tìm...)"

    text = (
        f"🚨 <b>HACK ALERT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💥 <b>{incident.get('name', 'Unknown')}</b> — {incident.get('amount_lost', 'N/A')}\n"
        f"📌 Category: {incident.get('category', 'N/A')}\n"
        f"🔍 Root cause: {incident.get('root_cause', 'Unknown')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Contact ngay:</b>\n"
        f"{targets_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>Draft:</b> {incident.get('outreach_draft', '')}"
    )
    return send_message(text)


def alert_governance(proposal: dict) -> bool:
    """Send a formatted GOVERNANCE PROPOSAL alert."""
    text = (
        f"🗳️ <b>GOVERNANCE — Upgrade Signal</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📌 <b>{proposal.get('space', 'Unknown')}</b>\n"
        f"📋 Proposal: {proposal.get('title', 'N/A')}\n"
        f"📊 Status: {proposal.get('state', 'N/A')}\n"
        f"🕐 Ends: {proposal.get('end_date', 'N/A')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💡 {proposal.get('summary', '')}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎯 <b>Action:</b> Research + engage trước khi họ chốt auditor"
    )
    return send_message(text)


# ---- Quick test ----
if __name__ == "__main__":
    send_message("✅ LeadHunter Telegram Bot connected successfully!")
