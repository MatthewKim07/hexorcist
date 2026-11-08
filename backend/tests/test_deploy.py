"""Deploy kit tests that need no VM. A fake inference server stands in for Vultr."""
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
FAKE_KEY = "fake-key-do-not-print-0123456789"


def load_script():
    spec = importlib.util.spec_from_file_location("list_models", ROOT / "deploy" / "list_models.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Fake(BaseHTTPRequestHandler):
    seen_auth = ""
    status = 200
    body = b""

    def do_GET(self):  # noqa: N802 - http.server's naming
        Fake.seen_auth = self.headers.get("Authorization", "")
        self.send_response(Fake.status)
        self.end_headers()
        self.wfile.write(Fake.body)

    def log_message(self, *args):
        pass


@pytest.fixture
def server():
    httpd = HTTPServer(("127.0.0.1", 0), Fake)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}/v1"
    httpd.shutdown()


def write_env(directory: Path, base: str, key: str = FAKE_KEY, model: str = "") -> None:
    (directory / ".env").write_text(f"# a comment\nLLM_BASE_URL={base}\nLLM_API_KEY={key}\nLLM_MODEL={model}\n")


def test_lists_models_and_never_prints_the_key(server, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write_env(tmp_path, server, model="model-b")
    Fake.status, Fake.body = 200, json.dumps({"data": [{"id": "model-b"}, {"id": "model-a"}]}).encode()
    assert load_script().main() == 0
    out = capsys.readouterr()
    assert "model-a" in out.out and "model-b  <- LLM_MODEL" in out.out
    assert Fake.seen_auth == f"Bearer {FAKE_KEY}"
    assert FAKE_KEY not in out.out + out.err


def test_an_error_that_echoes_the_key_is_scrubbed(server, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write_env(tmp_path, server)
    Fake.status, Fake.body = 401, f"bad key {FAKE_KEY}".encode()
    assert load_script().main() == 1
    out = capsys.readouterr()
    assert "HTTP 401" in out.err
    assert FAKE_KEY not in out.out + out.err


def test_a_model_id_that_echoes_the_key_is_scrubbed(server, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write_env(tmp_path, server)
    Fake.status, Fake.body = 200, json.dumps({"data": [{"id": f"x-{FAKE_KEY}"}]}).encode()
    assert load_script().main() == 0
    out = capsys.readouterr()
    assert FAKE_KEY not in out.out + out.err


def test_missing_env_or_key_is_explained(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert load_script().main() == 1
    assert "No .env" in capsys.readouterr().err
    write_env(tmp_path, "http://unused/v1", key="")
    assert load_script().main() == 1
    assert "LLM_API_KEY" in capsys.readouterr().err


def test_unreachable_endpoint_is_explained(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    write_env(tmp_path, "http://127.0.0.1:9/v1")
    assert load_script().main() == 1
    out = capsys.readouterr()
    assert "Could not list models" in out.err
    assert FAKE_KEY not in out.out + out.err


def test_production_compose_publishes_only_caddy_and_keeps_the_socket_on_the_backend():
    prod = (ROOT / "deploy" / "docker-compose.prod.yml").read_text()
    base = (ROOT / "docker-compose.yml").read_text()
    assert "docker.sock" not in prod
    assert sum("docker.sock" in line for line in base.splitlines()) == 1
    assert "/var/run/docker.sock:/var/run/docker.sock" in base.split("frontend:")[0].split("backend:")[1]
    assert '"80:80"' in prod and '"443:443"' in prod
    assert "ports: !reset []" in prod
    assert prod.count("ports:") == 2
    for required in ("DEMO_PASSCODE: ${DEMO_PASSCODE:?", "ACME_EMAIL: ${ACME_EMAIL:?", 'REQUIRE_DEMO_PASSCODE: "1"'):
        assert required in prod


def test_tunnel_compose_binds_loopback_only_and_requires_a_passcode():
    tunnel = (ROOT / "deploy" / "docker-compose.tunnel.yml").read_text()
    script = (ROOT / "deploy" / "tunnel.sh").read_text()
    assert '"127.0.0.1:${HEXORCIST_PORT:-8080}:80"' in tunnel
    assert "docker.sock" not in tunnel
    for required in ("DEMO_PASSCODE: ${DEMO_PASSCODE:?", 'REQUIRE_DEMO_PASSCODE: "1"', 'TRUST_CLOUDFLARE: "1"'):
        assert required in tunnel
    # The script must never read .env, and must keep its generated passcode out of git.
    assert not any(("cat .env" in line or "source .env" in line or ". .env" in line) for line in script.splitlines())
    assert "deploy/.tunnel-passcode" in (ROOT / ".gitignore").read_text()
