"""Tests of the REST API (skipped when FastAPI or httpx is not installed)."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

KEY = "cle-de-test"


@pytest.fixture()
def client(monkeypatch):
    monkeypatch.setenv("API_KEY", KEY)
    from td_arabic.api.app import app
    return TestClient(app)


def test_health_is_public(client):
    assert client.get("/health").json()["status"] == "ok"


def test_api_key_required(client):
    assert client.get("/translate", params={"q": "abad"}).status_code == 403
    r = client.get("/translate", params={"q": "abad"}, headers={"X-API-Key": "faux"})
    assert r.status_code == 403


def test_translate_word_keeps_v1_format(client):
    r = client.get("/translate", params={"q": "abad"}, headers={"X-API-Key": KEY}).json()
    assert r["status"] == "exact_match" and r["word"] == "abad"
    assert {"output", "pos", "sense_number", "forms"} <= set(r["translations"][0])
    r = client.get("/translate", params={"q": "oogid"}, headers={"X-API-Key": KEY}).json()
    assert r["status"] == "no_exact_match" and r["suggestions"]


def test_sentence_and_generation(client):
    h = {"X-API-Key": KEY}
    r = client.get("/translate/sentence", params={"text": "Ana nachri laham", "direction": "ar-fr"},
                   headers=h).json()
    assert r["coverage"] == 1.0
    themes = client.get("/generation/themes", headers=h).json()
    assert "marche" in themes
    r = client.get("/generation", params={"theme": "marche", "n": 3, "seed": 1}, headers=h).json()
    assert len(r) == 3 and all(s["theme"] == "marche" for s in r)
    assert client.get("/generation", params={"theme": "inconnu"}, headers=h).status_code == 404
