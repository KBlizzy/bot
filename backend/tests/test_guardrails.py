"""Tests for guardrail_status, reset_spend, and set_guardrails endpoints."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL').rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    yield s
    # teardown: restore safe defaults and pause bot
    try:
        s.post(f"{API}/bot/reset_spend")
        s.post(f"{API}/bot/guardrails",
               json={"enabled": True, "daily_loss_limit_sol": 0.05,
                     "total_spend_cap_sol": 0.3})
        st = s.get(f"{API}/bot/state").json()
        if st.get("mode") == "real" and st.get("running"):
            s.post(f"{API}/bot/toggle")
    except Exception:
        pass


def _set_defaults(client):
    client.post(f"{API}/bot/reset_spend")
    r = client.post(f"{API}/bot/guardrails",
                    json={"enabled": True, "daily_loss_limit_sol": 0.05,
                          "total_spend_cap_sol": 0.3})
    assert r.status_code == 200


class TestGuardrailStatus:
    def test_state_has_guardrail_status_field(self, client):
        _set_defaults(client)
        r = client.get(f"{API}/bot/state")
        assert r.status_code == 200
        d = r.json()
        assert "guardrail_status" in d, "state must expose guardrail_status"
        assert d["guardrail_status"] is None, \
            f"expected null with defaults & spent=0, got {d['guardrail_status']!r}"

    def test_tripped_total_spend_cap(self, client):
        # First zero the spend so cap=0 with spent=0 -> total_spent (0) >= cap (0) -> tripped
        client.post(f"{API}/bot/reset_spend")
        r = client.post(f"{API}/bot/guardrails",
                        json={"enabled": True, "daily_loss_limit_sol": 0.05,
                              "total_spend_cap_sol": 0})
        assert r.status_code == 200
        body = r.json()
        assert body.get("ok") is True
        assert body["guardrails"]["total_spend_cap_sol"] == 0

        st = client.get(f"{API}/bot/state").json()
        gs = st.get("guardrail_status")
        assert gs is not None, "expected tripped guardrail, got null"
        assert "total spend cap hit" in gs.lower(), f"unexpected reason: {gs}"

    def test_reset_spend_zeros_counters(self, client):
        r = client.post(f"{API}/bot/reset_spend")
        assert r.status_code == 200
        assert r.json() == {"ok": True}
        st = client.get(f"{API}/bot/state").json()
        assert st["spent_today_sol"] == 0.0
        assert st["loss_today_sol"] == 0.0
        assert st["total_spent_sol"] == 0.0

    def test_restore_defaults_clears_status(self, client):
        _set_defaults(client)
        st = client.get(f"{API}/bot/state").json()
        assert st["guardrail_status"] is None
