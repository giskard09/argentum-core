"""Notificación por webhook al integrador cuando un trail se ancla on-chain.

El integrador declara su `notify_webhook` en la cuenta PAYG. Cuando un trail suyo
confirma anchor on-chain, el VPS hace POST {trail_id, tx_hash, anchored_at} a esa URL.
Sistema-a-sistema: no requiere humano en el loop (a diferencia del email).

SEGURIDAD (SSRF): el daemon corre en el VPS junto a servicios internos
(argentum-core:8017, memory, marks, RPC, metadata 169.254.169.254). La URL la declara
un externo. Defensas:

  1. Validación de destino: se resuelve el host y se rechaza si CUALQUIER IP resuelta
     es loopback / privada / link-local (incl. metadata) / reservada / multicast.
  2. IP pinning: se conecta a la IP validada exacta (no se vuelve a resolver), lo que
     cierra el DNS rebinding / TOCTOU entre la validación y el POST. Se preserva el
     Host header y la validación de cert TLS contra el hostname real.
  3. Sin redirects: allow_redirects=False — un 3xx hacia un destino interno no se sigue;
     se trata como entrega fallida.
"""
import ipaddress
import logging
import socket
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool

_log = logging.getLogger(__name__)

_TIMEOUT = 5  # segundos — best-effort, no bloquea el daemon de anchor


def _resolve_safe_ip(host: str):
    """Resuelve el host y retorna UNA IP segura para pinnear, o None.

    Devuelve None si la resolución falla o si CUALQUIER IP resuelta no es pública y
    ruteable (loopback/privada/link-local/reservada/multicast/unspecified). Devolver
    la IP validada permite conectarse a ella directamente sin re-resolver.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return None
    if not infos:
        return None
    safe_ip = None
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return None
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return None
        if safe_ip is None:
            safe_ip = ip_str
    return safe_ip


def is_safe_webhook_url(url: str) -> bool:
    """Valida que la URL sea http(s), con host, y que no resuelva a red interna.

    Usada al registrar el webhook (feedback rápido). El envío revalida + pinnea.
    """
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
    return _resolve_safe_ip(p.hostname) is not None


class _PinnedIPAdapter(HTTPAdapter):
    """Pinnea la conexión a una IP pre-validada, evitando DNS rebinding entre la
    validación SSRF y la request. Preserva el Host header (lo setea requests desde la
    URL) y, en https, el SNI + la validación de cert contra el hostname real."""

    def __init__(self, hostname: str, pinned_ip: str, **kwargs):
        self._hostname = hostname
        self._pinned_ip = pinned_ip
        super().__init__(**kwargs)

    def get_connection(self, url, proxies=None):
        parsed = urlparse(url)
        if parsed.scheme == "https":
            return HTTPSConnectionPool(
                self._pinned_ip,
                port=parsed.port or 443,
                timeout=_TIMEOUT,
                server_hostname=self._hostname,
                assert_hostname=self._hostname,
                cert_reqs="CERT_REQUIRED",
            )
        return HTTPConnectionPool(
            self._pinned_ip,
            port=parsed.port or 80,
            timeout=_TIMEOUT,
        )


def notify_anchor(url: str, trail_id: str, tx_hash: str, anchored_at: str) -> bool:
    """POST {trail_id, tx_hash, anchored_at} al webhook del integrador.

    Best-effort: valida + pinnea la IP en el momento del envío, no sigue redirects,
    traga cualquier excepción y nunca propaga al daemon. Retorna True solo con 2xx.
    """
    if not url:
        return False
    try:
        p = urlparse(url)
    except Exception:
        return False
    if p.scheme not in ("http", "https") or not p.hostname:
        _log.warning("webhook url inválida: %s", url)
        return False

    pinned_ip = _resolve_safe_ip(p.hostname)
    if pinned_ip is None:
        _log.warning("webhook bloqueado por SSRF guard: %s", url)
        return False

    payload = {"trail_id": trail_id, "tx_hash": tx_hash, "anchored_at": anchored_at}
    prefix = f"{p.scheme}://{p.hostname}" + (f":{p.port}" if p.port else "")
    session = requests.Session()
    session.mount(prefix, _PinnedIPAdapter(p.hostname, pinned_ip))
    try:
        r = session.post(
            url, json=payload, timeout=_TIMEOUT,
            allow_redirects=False,
            headers={"User-Agent": "mycelium-anchor-webhook/1"},
        )
        ok = 200 <= r.status_code < 300
        if not ok:
            _log.warning("webhook %s respondió %s", url, r.status_code)
        return ok
    except Exception as exc:
        _log.warning("webhook POST falló (%s): %s", url, exc)
        return False
    finally:
        session.close()
