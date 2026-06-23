"""Notificación por webhook al integrador cuando un trail se ancla on-chain.

El integrador declara su `notify_webhook` en la cuenta PAYG. Cuando un trail suyo
confirma anchor on-chain, el VPS hace POST {trail_id, tx_hash, anchored_at} a esa URL.
Sistema-a-sistema: no requiere humano en el loop (a diferencia del email).

SEGURIDAD (SSRF): el daemon corre en el VPS junto a servicios internos
(argentum-core:8017, memory, marks, RPC, metadata 169.254.169.254). La URL la declara
un externo, así que ANTES de hacer el POST se resuelve el host y se rechaza si apunta a
loopback / rangos privados / link-local / reservados. Sin esto, un integrador podría
usar el webhook para alcanzar la red interna del VPS.
"""
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import requests

_log = logging.getLogger(__name__)

_TIMEOUT = 5  # segundos — best-effort, no bloquea el daemon de anchor


def _host_is_public(host: str) -> bool:
    """True solo si TODAS las IPs resueltas del host son públicas y ruteables."""
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False
    if not infos:
        return False
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        # Bloquea loopback, privadas (10/8, 172.16/12, 192.168/16), link-local
        # (169.254/16 — incluye metadata 169.254.169.254), reservadas, multicast,
        # unspecified (0.0.0.0).
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return False
    return True


def is_safe_webhook_url(url: str) -> bool:
    """Valida que la URL sea http(s), con host, y que no apunte a red interna."""
    if not url:
        return False
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https"):
        return False
    if not p.hostname:
        return False
    return _host_is_public(p.hostname)


def notify_anchor(url: str, trail_id: str, tx_hash: str, anchored_at: str) -> bool:
    """POST {trail_id, tx_hash, anchored_at} al webhook del integrador.

    Best-effort: revalida SSRF en el momento del envío (no solo al registrar la URL,
    para acotar DNS rebinding), traga cualquier excepción y nunca propaga al daemon.
    Retorna True si el endpoint respondió 2xx.
    """
    if not is_safe_webhook_url(url):
        _log.warning("webhook bloqueado por SSRF guard: %s", url)
        return False
    payload = {"trail_id": trail_id, "tx_hash": tx_hash, "anchored_at": anchored_at}
    try:
        r = requests.post(url, json=payload, timeout=_TIMEOUT,
                          headers={"User-Agent": "mycelium-anchor-webhook/1"})
        ok = 200 <= r.status_code < 300
        if not ok:
            _log.warning("webhook %s respondió %s", url, r.status_code)
        return ok
    except Exception as exc:
        _log.warning("webhook POST falló (%s): %s", url, exc)
        return False
