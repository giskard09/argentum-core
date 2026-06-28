"""
billing_report.py — Reporte mensual de billing por Telegram.

Ejecutar el día 1 de cada mes (cron o systemd timer).
Reporta el mes anterior: cantidad de trails, monto total, período, por cuenta.

Env vars requeridas:
  TRAILS_DB        — path al trails.db (default: ./trails.db)
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID
"""

import datetime
import os
import sys

import mycelium_trails

TRAILS_DB = os.environ.get("TRAILS_DB", os.path.join(os.path.dirname(__file__), "trails.db"))
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def previous_month_key() -> str:
    today = datetime.date.today()
    first = today.replace(day=1)
    last_month = first - datetime.timedelta(days=1)
    return last_month.strftime("%Y-%m")


def send_telegram(text: str) -> None:
    import urllib.request, json as _json
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = _json.dumps({"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        if r.status != 200:
            raise RuntimeError(f"Telegram API {r.status}")


def build_message(month_key: str, summary: list[dict]) -> str:
    if not summary:
        return (
            f"<b>Billing report — {month_key}</b>\n\n"
            "Sin trails facturables en el período."
        )

    total_trails = sum(r["trail_count"] for r in summary)
    total_usd = sum(r["total_usd"] for r in summary)

    lines = [f"<b>Billing report — {month_key}</b>\n"]
    for r in summary:
        lines.append(
            f"• <code>{r['agent_id']}</code>: {r['trail_count']} trails — ${r['total_usd']:.3f} USD"
        )
    lines.append(f"\n<b>Total: {total_trails} trails — ${total_usd:.3f} USD</b>")
    lines.append("\nCobro: factura tipo E + transferencia USDC manual.")
    return "\n".join(lines)


def main() -> None:
    if not BOT_TOKEN or not CHAT_ID:
        print("ERROR: TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID requeridos", file=sys.stderr)
        sys.exit(1)

    month_key = sys.argv[1] if len(sys.argv) > 1 else previous_month_key()
    summary = mycelium_trails.get_billing_summary(TRAILS_DB, month_key)
    message = build_message(month_key, summary)

    print(f"Enviando reporte {month_key}...")
    print(message)
    send_telegram(message)
    print("OK")


if __name__ == "__main__":
    main()
