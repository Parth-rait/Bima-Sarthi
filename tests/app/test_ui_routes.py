"""Serving the React build at "/" with the old page kept at /legacy as the rollback."""
import pytest
from fastapi.testclient import TestClient

from sarthi.app.main import app

LEGACY_MARK = "Bima Sarthi"


@pytest.fixture
def dist(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text('<!doctype html><html><body><div id="root">REACT-SHELL</div></body></html>')
    (tmp_path / "assets" / "app.js").write_text("console.log('x')")
    (tmp_path / "secret.txt").write_text("nope")
    monkeypatch.setenv("SARTHI_FRONTEND_DIST", str(tmp_path))
    return tmp_path


def test_react_served_at_root_when_built(dist, monkeypatch):
    monkeypatch.setenv("SARTHI_UI", "react")
    c = TestClient(app)
    assert "REACT-SHELL" in c.get("/").text
    assert LEGACY_MARK in c.get("/legacy").text and "REACT-SHELL" not in c.get("/legacy").text


def test_auto_mode_uses_react_when_dist_exists(dist, monkeypatch):
    monkeypatch.delenv("SARTHI_UI", raising=False)
    assert "REACT-SHELL" in TestClient(app).get("/").text


def test_legacy_env_forces_old_page(dist, monkeypatch):
    monkeypatch.setenv("SARTHI_UI", "legacy")
    assert "REACT-SHELL" not in TestClient(app).get("/").text


def test_falls_back_to_legacy_when_no_build(tmp_path, monkeypatch):
    monkeypatch.setenv("SARTHI_FRONTEND_DIST", str(tmp_path / "missing"))
    monkeypatch.delenv("SARTHI_UI", raising=False)
    r = TestClient(app).get("/")
    assert r.status_code == 200 and "REACT-SHELL" not in r.text


def test_assets_served_and_traversal_blocked(dist, monkeypatch):
    monkeypatch.setenv("SARTHI_UI", "react")
    c = TestClient(app)
    assert c.get("/assets/app.js").status_code == 200
    assert c.get("/assets/../secret.txt").status_code == 404
    assert c.get("/assets/%2e%2e/secret.txt").status_code == 404
    assert c.get("/assets/missing.js").status_code == 404


def test_api_routes_unaffected(dist, monkeypatch):
    monkeypatch.setenv("SARTHI_UI", "react")
    assert TestClient(app).get("/health").json() == {"status": "ok"}


CLIENT_ROUTES = ["/about", "/how-it-works", "/check-claim", "/action-plan", "/cases",
                 "/privacy", "/help", "/results/abc-123", "/dev/components"]


@pytest.mark.parametrize("path", CLIENT_ROUTES)
def test_client_routes_return_react_shell_on_refresh(dist, monkeypatch, path):
    monkeypatch.setenv("SARTHI_UI", "react")
    r = TestClient(app).get(path)
    assert r.status_code == 200 and "REACT-SHELL" in r.text


def test_client_routes_in_legacy_mode_serve_old_page(dist, monkeypatch):
    monkeypatch.setenv("SARTHI_UI", "legacy")
    r = TestClient(app).get("/about")
    assert r.status_code == 200 and "REACT-SHELL" not in r.text


def test_unknown_paths_still_404_and_api_unshadowed(dist, monkeypatch):
    monkeypatch.setenv("SARTHI_UI", "react")
    c = TestClient(app)
    assert c.get("/definitely-not-a-page").status_code == 404
    assert c.get("/session/none/policy").status_code == 404
    assert c.get("/gallery").status_code == 200
