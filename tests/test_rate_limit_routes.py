"""Rate limits must actually apply, and must key on the real client.

Until this fix, @limiter.limit sat ABOVE @app.post on 8 routes, so FastAPI registered the
undecorated handler and the limit never ran. Order matters: @app.<method> outermost,
@limiter.limit below it.
"""
import ast
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _decorator_names(fn):
    names = []
    for d in fn.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        names.append(ast.unparse(target))
    return names


def limited_route_order(source: str):
    """Return [(function name, line, ok)] for every function that carries @limiter.limit."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = _decorator_names(node)
            if "limiter.limit" in names:
                routes = [i for i, n in enumerate(names) if n.startswith("app.") and n.split(".")[1] in
                          ("get", "post", "put", "delete", "patch", "api_route")]
                ok = bool(routes) and routes[0] < names.index("limiter.limit")
                out.append((node.name, node.lineno, ok))
    return out


def test_every_limited_route_has_the_route_decorator_outermost():
    rows = limited_route_order((ROOT / "argentum.py").read_text())
    assert len(rows) >= 9, rows  # 8 fixed + /action/submit
    bad = [(n, l) for n, l, ok in rows if not ok]
    assert not bad, f"@limiter.limit above @app.<method> (limit never runs): {bad}"


def test_registered_endpoints_are_the_limited_wrappers(tmp_path):
    sys.modules.pop("argentum", None)
    import argentum
    limited = {k.split(".")[-1] for k in argentum.limiter._route_limits}
    assert len(limited) >= 9
    seen = set()
    for r in argentum.app.routes:
        ep = getattr(r, "endpoint", None)
        if ep is not None and ep.__name__ in limited and ep.__module__ == "argentum":
            seen.add(ep.__name__)
            assert hasattr(ep, "__wrapped__"), f"{r.path}: registered handler is not the rate-limited wrapper"
    assert seen == limited, limited - seen


def _request(peer, headers=None):
    from starlette.requests import Request
    scope = {"type": "http", "method": "POST", "path": "/", "query_string": b"",
             "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]}
    if peer is not None:
        scope["client"] = (peer, 5555)
    return Request(scope)


def check_key_func(key):
    assert key(_request("127.0.0.1", {"CF-Connecting-IP": "203.0.113.7"})) == "203.0.113.7"
    assert key(_request("::1", {"CF-Connecting-IP": "2001:db8::1"})) == "2001:db8::1"
    # from outside, the header is never believed
    assert key(_request("198.51.100.9", {"CF-Connecting-IP": "203.0.113.7"})) == "198.51.100.9"
    assert key(_request("127.0.0.2", {"CF-Connecting-IP": "203.0.113.7"})) == "127.0.0.2"
    # loopback without the header, or with junk, falls back to the socket peer
    assert key(_request("127.0.0.1")) == "127.0.0.1"
    assert key(_request("127.0.0.1", {"CF-Connecting-IP": "not-an-ip"})) == "127.0.0.1"
    assert key(_request(None)) == "unknown"


def test_rate_limit_key_trusts_cf_header_only_from_loopback():
    sys.modules.pop("argentum", None)
    import argentum
    check_key_func(argentum._rate_limit_key)
