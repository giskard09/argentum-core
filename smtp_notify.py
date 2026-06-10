"""Notificaciones via Brevo API HTTP — hello@rgiskard.xyz.

Uso:
    from smtp_notify import send_email, notify_trail_limit, notify_payg_topup, notify_rsa_activation
"""
import os
import requests

BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")
FROM_ADDR     = {"name": "Giskard Reventlov", "email": "hello@rgiskard.xyz"}
ADMIN_ADDR    = os.environ.get("ADMIN_EMAIL", "playplay2736@gmail.com")

_API_URL = "https://api.brevo.com/v3/smtp/email"


def send_email(to: str, subject: str, body_text: str, body_html: str = "") -> bool:
    """Envía un email via Brevo API HTTP. Retorna True si fue exitoso."""
    if not BREVO_API_KEY:
        return False
    payload = {
        "sender":      FROM_ADDR,
        "to":          [{"email": to}],
        "subject":     subject,
        "textContent": body_text,
    }
    if body_html:
        payload["htmlContent"] = body_html
    try:
        r = requests.post(
            _API_URL,
            json=payload,
            headers={"api-key": BREVO_API_KEY},
            timeout=10,
        )
        return r.status_code in (200, 201)
    except Exception:
        return False


def notify_trail_limit(agent_id: str, used: int, limit: int, to: str = "") -> bool:
    """Notifica al agente que alcanzó el límite mensual de trails (Free tier)."""
    recipient = to or ADMIN_ADDR
    subject = f"[Mycelium] Límite mensual de trails alcanzado — {agent_id}"
    text = (
        f"El agente {agent_id} alcanzó su límite mensual de trails.\n\n"
        f"Usados: {used}/{limit}\n\n"
        f"Para continuar sin límite, activá PAYG:\n"
        f"https://argentum-api.rgiskard.xyz/docs#payg\n\n"
        f"— Giskard / Rama"
    )
    html = (
        f"<p>El agente <code>{agent_id}</code> alcanzó su límite mensual de trails.</p>"
        f"<p><strong>Usados:</strong> {used}/{limit}</p>"
        f"<p>Para continuar sin límite, activá <a href='https://argentum-api.rgiskard.xyz/docs#payg'>PAYG</a>.</p>"
        f"<p>— Giskard / Rama</p>"
    )
    return send_email(recipient, subject, text, html)


def notify_payg_topup(agent_id: str, trails_added: int, trails_total: int, to: str = "") -> bool:
    """Confirma un topup PAYG al agente."""
    recipient = to or ADMIN_ADDR
    subject = f"[Mycelium] Topup confirmado — {trails_added} trails acreditados"
    text = (
        f"Topup PAYG confirmado para {agent_id}.\n\n"
        f"Trails acreditados: +{trails_added}\n"
        f"Balance total: {trails_total}\n\n"
        f"Verificá tu balance:\n"
        f"https://argentum-api.rgiskard.xyz/payg/balance\n\n"
        f"— Giskard / Rama"
    )
    return send_email(recipient, subject, text)


def notify_rsa_activation(trail_id: str, signer_email: str, negotiation_ref: str,
                           action_ref: str, to: str = "") -> bool:
    """Notifica al equipo que el trail de activación RSA fue committed."""
    recipient = to or ADMIN_ADDR
    subject = "[Mycelium] RSA activation trail committed — SafeAgent"
    neg_display = negotiation_ref[:16] + "..." if negotiation_ref else "N/A"
    text = (
        f"Trail de activación RSA committed en mainnet.\n\n"
        f"Firmante: {signer_email}\n"
        f"trail_id: {trail_id}\n"
        f"action_ref: {action_ref[:16]}...\n"
        f"negotiation_ref (SHA-256 PDF): {neg_display}\n\n"
        f"Verificar:\n"
        f"https://argentum-api.rgiskard.xyz/trails/agents/pioneer-agent-001\n\n"
        f"— Giskard / Rama"
    )
    return send_email(recipient, subject, text)
