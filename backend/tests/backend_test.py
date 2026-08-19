"""Backend tests for pump.fun bot API."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://pump-scout-ai.preview.emergentagent.com').rstrip('/')
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# --- coins ---
class TestCoins:
    def test_get_coins_all(self, client):
        r = client.get(f"{API}/coins")
        assert r.status_code == 200
        data = r.json()
        assert "coins" in data and "sol_usd" in data
        assert len(data["coins"]) > 0
        c = data["coins"][0]
        for f in ["mint", "name", "symbol", "socials", "has_social",
                  "market_cap_usd", "mcap_growth_pct", "volume_24h_usd",
                  "global_fees_paid_sol", "age_min", "history", "eligible", "held"]:
            assert f in c, f"missing field {f}"

    def test_filter_eligible(self, client):
        r = client.get(f"{API}/coins?filter=eligible")
        assert r.status_code == 200
        for c in r.json()["coins"]:
            assert c["eligible"] is True
            assert c["has_social"] is True
            assert c["global_fees_paid_sol"] >= 0.5

    def test_filter_new(self, client):
        r = client.get(f"{API}/coins?filter=new")
        assert r.status_code == 200
        for c in r.json()["coins"]:
            assert c["age_min"] <= 60


# --- bot state ---
class TestBotState:
    def test_state_shape(self, client):
        r = client.get(f"{API}/bot/state")
        assert r.status_code == 200
        d = r.json()
        for f in ["mode", "running", "paper_balance_usd", "equity_usd",
                  "total_pnl_usd", "open_positions", "settings",
                  "real_balance_sol", "real_deposit_address"]:
            assert f in d
        s = d["settings"]
        assert s["trade_size_sol"] == 0.01
        assert s["slippage_pct"] == 25
        assert s["priority_fee"] == 0.0001
        assert s["bribe_fee"] == 0
        assert s["min_global_fees_sol"] == 0.5


# --- toggle / mode / restart ---
class TestBotControls:
    def test_toggle(self, client):
        s0 = client.get(f"{API}/bot/state").json()["running"]
        r = client.post(f"{API}/bot/toggle")
        assert r.status_code == 200
        assert r.json()["running"] != s0
        # toggle back
        r2 = client.post(f"{API}/bot/toggle")
        assert r2.json()["running"] == s0

    def test_mode_switch(self, client):
        r = client.post(f"{API}/bot/mode", json={"mode": "real"})
        assert r.status_code == 200 and r.json()["mode"] == "real"
        r = client.post(f"{API}/bot/mode", json={"mode": "paper"})
        assert r.json()["mode"] == "paper"

    def test_mode_invalid(self, client):
        r = client.post(f"{API}/bot/mode", json={"mode": "bogus"})
        assert r.status_code == 400

    def test_restart(self, client):
        r = client.post(f"{API}/bot/restart")
        assert r.status_code == 200
        assert r.json()["paper_balance_usd"] == 20.0
        st = client.get(f"{API}/bot/state").json()
        # equity should be ~20 immediately post-restart (positions cleared)
        assert st["open_positions"] == 0
        assert abs(st["paper_balance_usd"] - 20.0) < 0.01


# --- auto-trading ---
class TestAutoTrading:
    def test_bot_generates_trades(self, client):
        # ensure running + paper mode
        st = client.get(f"{API}/bot/state").json()
        if not st["running"]:
            client.post(f"{API}/bot/toggle")
        client.post(f"{API}/bot/mode", json={"mode": "paper"})
        # wait for bot cycles
        got_trade = False
        for _ in range(10):
            time.sleep(4)
            t = client.get(f"{API}/trades?hours=24").json()
            if len(t["trades"]) > 0:
                got_trade = True
                break
        assert got_trade, "no trades recorded after ~40s"
        for tr in t["trades"]:
            assert tr["side"] in ("BUY", "SELL")

    def test_positions(self, client):
        r = client.get(f"{API}/positions")
        assert r.status_code == 200
        assert "positions" in r.json()

    def test_decisions_only_eligible_buys(self, client):
        d = client.get(f"{API}/decisions").json()["decisions"]
        buys = [x for x in d if x["action"] == "BUY"]
        for b in buys:
            assert "fees" in b["reason"].lower() and "social" in b["reason"].lower()


# --- real wallet sim ---
class TestRealWallet:
    def test_deposit_sim(self, client):
        b0 = client.get(f"{API}/bot/state").json()["real_balance_sol"]
        r = client.post(f"{API}/wallet/deposit_sim", json={"address": "x", "amount_sol": 1.0})
        assert r.status_code == 200
        assert abs(r.json()["real_balance_sol"] - (b0 + 1.0)) < 1e-6

    def test_withdraw_ok(self, client):
        # ensure some balance
        client.post(f"{API}/wallet/deposit_sim", json={"address": "x", "amount_sol": 2.0})
        b0 = client.get(f"{API}/bot/state").json()["real_balance_sol"]
        r = client.post(f"{API}/wallet/withdraw",
                        json={"address": "SoLDestAddr123", "amount_sol": 0.5})
        assert r.status_code == 200
        d = r.json()
        assert d["simulated"] is True
        assert abs(d["real_balance_sol"] - (b0 - 0.5)) < 1e-6

    def test_withdraw_insufficient(self, client):
        r = client.post(f"{API}/wallet/withdraw",
                        json={"address": "x", "amount_sol": 999999.0})
        assert r.status_code == 400


# --- feeds ---
class TestFeeds:
    def test_decisions(self, client):
        r = client.get(f"{API}/decisions")
        assert r.status_code == 200 and "decisions" in r.json()

    def test_wallets(self, client):
        r = client.get(f"{API}/wallets")
        assert r.status_code == 200
        assert len(r.json()["wallets"]) > 0
