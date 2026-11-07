"""Testa o envio de alertas ao webhook contra um receptor HTTP local (sem internet)."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests

from hospital_monitor.alerts import Alert, AlertCenter, Severity


def _server(status: int = 200):
    received: list[dict] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            size = int(self.headers["Content-Length"])
            received.append(json.loads(self.rfile.read(size)))
            self.send_response(status)
            self.end_headers()

        def log_message(self, *args):  # silencia o log do servidor de teste
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, received


def _center() -> AlertCenter:
    c = AlertCenter()
    c.add(Alert("Áudio", Severity.CRITICAL, "Termo crítico", "dor no peito", "00:05"))
    c.add(Alert("Vídeo", Severity.WARNING, "Fora de quadro", "sem paciente", "0-8s"))
    c.add(Alert("Áudio", Severity.INFO, "Voz", "monótona"))
    return c


def test_dispatch_webhook_sends_alerts_at_or_above_warning():
    srv, received = _server()
    try:
        n = _center().dispatch_webhook(f"http://127.0.0.1:{srv.server_port}/hook")
    finally:
        srv.shutdown()
    assert n == 2  # o INFO não é enviado
    body = received[0]
    assert len(body["alerts"]) == 2
    assert body["alerts"][0]["severity"] == "CRÍTICO"  # ordenado por severidade
    assert "dor no peito" in body["text"]


def test_dispatch_webhook_nothing_to_send_makes_no_request():
    srv, received = _server()
    try:
        c = AlertCenter()
        c.add(Alert("Áudio", Severity.INFO, "x", "y"))
        assert c.dispatch_webhook(f"http://127.0.0.1:{srv.server_port}/") == 0
    finally:
        srv.shutdown()
    assert received == []


def test_dispatch_webhook_raises_on_http_error():
    srv, _ = _server(status=500)
    try:
        with pytest.raises(requests.HTTPError):
            _center().dispatch_webhook(f"http://127.0.0.1:{srv.server_port}/")
    finally:
        srv.shutdown()
