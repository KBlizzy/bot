"""Wallet Tracker (copy-trade) tests.

Verifies:
1. POST /api/bot/tracker validation (empty addr with enabled=true -> 400).
2. Enable/disable persists in /api/bot/state.
3. In PAPER mode, when tracker is ON the bot does NOT open self-scanned
   positions (deterministic behavior). With tracker OFF, positions appear.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TRACKED = "suqh5sHtr8HyJ7q8scBimULPkPpA557prMG47xCHQfK"
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def s():
    ses = requests.Session()
    ses.headers.update({"Content-Type": "application/json"})
    return ses


@pytest.fixture(scope="module", autouse=True)
def cleanup(s):
    """Ensure test starts and ends in a known safe state (paper, tracker off)."""
    # Save original
    orig = s.get(f"{API}/bot/state", timeout=10).json()
    yield
    # cleanup: disable tracker, set mode back to original, pause
    try:
        s.post(f"{API}/bot/tracker", json={"enabled": False, "address": ""}, timeout=10)
        s.post(f"{API}/bot/mode", json={"mode": orig.get("mode", "real")}, timeout=10)
        st = s.get(f"{API}/bot/state", timeout=10).json()
        if st.get("running"):
            s.post(f"{API}/bot/toggle", timeout=10)
    except Exception as e:
        print("cleanup err:", e)


def _get_state(s):
    return s.get(f"{API}/bot/state", timeout=10).json()


def _set_running(s, want: bool):
    st = _get_state(s)
    if st["running"] != want:
        s.post(f"{API}/bot/toggle", timeout=10)


class TestTrackerValidation:
    def test_enable_without_address_returns_400(self, s):
        r = s.post(f"{API}/bot/tracker", json={"enabled": True, "address": ""}, timeout=10)
        assert r.status_code == 400
        body = r.json()
        assert "wallet address required" in (body.get("detail") or "").lower()

    def test_enable_with_address_persists(self, s):
        r = s.post(f"{API}/bot/tracker",
                   json={"enabled": True, "address": TRACKED}, timeout=10)
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["tracker_enabled"] is True
        assert data["tracked_wallet"] == TRACKED

        st = _get_state(s)
        assert st["tracker_enabled"] is True
        assert st["tracked_wallet"] == TRACKED

    def test_disable_clears(self, s):
        r = s.post(f"{API}/bot/tracker",
                   json={"enabled": False, "address": ""}, timeout=10)
        assert r.status_code == 200
        st = _get_state(s)
        assert st["tracker_enabled"] is False


class TestTrackerDisablesSelfScan:
    """Key safety test in PAPER MODE ONLY."""

    def test_paper_scan_off_when_tracker_on(self, s):
        # 1) Force paper mode
        r = s.post(f"{API}/bot/mode", json={"mode": "paper"}, timeout=10)
        assert r.status_code == 200

        # ensure tracker is OFF baseline
        s.post(f"{API}/bot/tracker",
               json={"enabled": False, "address": ""}, timeout=10)

        # 2) Restart (reset to $20, clears positions)
        r = s.post(f"{API}/bot/restart", timeout=10)
        assert r.status_code == 200

        # 3) Ensure running
        _set_running(s, True)
        st = _get_state(s)
        assert st["running"] is True
        assert st["mode"] == "paper"

        # 4) Baseline: tracker OFF, wait ~15s, expect positions > 0
        time.sleep(15)
        pos = s.get(f"{API}/positions", timeout=10).json()
        baseline_count = len(pos["positions"])
        print(f"baseline positions with tracker OFF: {baseline_count}")
        assert baseline_count > 0, (
            "expected paper bot to self-scan and open positions with tracker OFF")

        # 5) Restart, enable tracker, ensure running, wait ~15s
        r = s.post(f"{API}/bot/restart", timeout=10)
        assert r.status_code == 200
        r = s.post(f"{API}/bot/tracker",
                   json={"enabled": True, "address": TRACKED}, timeout=10)
        assert r.status_code == 200
        _set_running(s, True)

        st = _get_state(s)
        assert st["tracker_enabled"] is True
        assert st["running"] is True

        time.sleep(15)
        pos2 = s.get(f"{API}/positions", timeout=10).json()
        tracker_count = len(pos2["positions"])
        print(f"positions with tracker ON: {tracker_count}")
        assert tracker_count == 0, (
            f"tracker ON should disable self-scan; got {tracker_count} positions")

        # 6) Cleanup: disable tracker + pause
        s.post(f"{API}/bot/tracker",
               json={"enabled": False, "address": ""}, timeout=10)
        _set_running(s, False)
