"""Trading engine: ingests real pump.fun coins (PumpPortal websocket), simulates
real-time price evolution, and runs an AI paper-trading bot."""
import asyncio
import json
import random
import string
import time
import uuid
from datetime import datetime, timezone, timedelta

import aiohttp

import real_trader

SOL_USD = 152.0  # reference SOL price for USD conversions

# ---- Bot trade parameters (as requested by user) ----
TRADE_SIZE_SOL = 0.01
SLIPPAGE_PCT = 25
PRIORITY_FEE = 0.0001
BRIBE_FEE = 0.0
START_BALANCE_USD = 20.0

# ---- Filter thresholds ----
MIN_GLOBAL_FEES_SOL = 0.5
NEW_COIN_MAX_AGE_MIN = 360  # prefer coins younger than 6h

# ---- Sell rules ----
TAKE_PROFIT = 0.25
STOP_LOSS = -0.15
MAX_HOLD_MIN = 45


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat()


class Engine:
    def __init__(self, db):
        self.db = db
        self.coins = {}          # mint -> coin dict
        self.positions = {}      # mint -> position dict (open, PAPER)
        self.real_positions = {} # mint -> position dict (open, REAL on-chain)
        self.decisions = []      # recent AI decisions
        self.wallets = []        # scouted smart wallets
        self._loop_count = 0
        self.bot = {
            "mode": "paper",
            "running": True,
            "paper_balance_usd": START_BALANCE_USD,
            "real_balance_sol": 0.0,
            "real_deposit_address": self._fake_addr(),
            "started_at": iso(now()),
            "settings": {
                "trade_size_sol": TRADE_SIZE_SOL,
                "slippage_pct": SLIPPAGE_PCT,
                "priority_fee": PRIORITY_FEE,
                "bribe_fee": BRIBE_FEE,
                "min_global_fees_sol": MIN_GLOBAL_FEES_SOL,
            },
        }
        self._tasks = []

    # ---------------- helpers ----------------
    def _fake_addr(self):
        chars = string.ascii_letters + string.digits
        return "".join(random.choice(chars) for _ in range(44))

    def _rand_name(self):
        first = ["Pepe", "Doge", "Moon", "Turbo", "Chad", "Wojak", "Bonk", "Sol",
                 "Giga", "Baby", "Mega", "Retard", "Ansem", "Degen", "Frog", "Cat",
                 "Shiba", "Elon", "Trump", "Silly", "Based", "Alpha", "Fartcoin", "Wif"]
        second = ["Inu", "Coin", "AI", "Cat", "Dog", "Lord", "King", "Master", "X",
                  "Money", "Cash", "Rocket", "Pump", "Fun", "Labs", "Protocol", "Hat"]
        return f"{random.choice(first)} {random.choice(second)}"

    def _symbol(self, name):
        return "".join([w[0] for w in name.split()][:4]).upper() + \
            random.choice(["", str(random.randint(1, 99))])

    def _make_coin(self, source="sim", real=None):
        mint = real.get("mint") if real else self._fake_addr()
        name = real.get("name") if real and real.get("name") else self._rand_name()
        symbol = real.get("symbol") if real and real.get("symbol") else self._symbol(name)
        mcap_sol = (real.get("marketCapSol") if real else None) or random.uniform(8, 120)
        mcap_usd = mcap_sol * SOL_USD
        socials = real.get("socials") if real else self._rand_socials()
        has_social = any(socials.values())
        price = mcap_usd / 1_000_000_000  # 1B supply convention
        # dev-sold status: sim coins get a heuristic; live coins verified on-chain
        if real:
            dev_sold, dev_checked = False, False
        else:
            dev_sold, dev_checked = random.random() < 0.55, True
        return {
            "mint": mint,
            "name": name,
            "symbol": symbol,
            "image": real.get("image") if real else "",
            "creator": real.get("creator") if real else "",
            "dev_sold": dev_sold,
            "dev_checked": dev_checked,
            "dev_attempts": 0,
            "socials": socials,
            "has_social": has_social,
            "created_at": iso(now()),
            "price": price,
            "price_prev": price,
            "market_cap_usd": mcap_usd,
            "mcap_start": mcap_usd,
            "volume_24h_usd": random.uniform(2000, 40000),
            "global_fees_paid_sol": random.uniform(0.05, 2.5),
            "vol_spike": random.uniform(0.8, 1.4),
            "source": source,
            "history": [round(price, 12)],
            "trades_count": random.randint(20, 400),
            "holders": random.randint(15, 800),
        }

    def _rand_socials(self):
        # ~70% of coins carry at least one social link
        s = {"twitter": "", "telegram": "", "website": ""}
        if random.random() < 0.75:
            slug = "".join(random.choice(string.ascii_lowercase) for _ in range(6))
            if random.random() < 0.8:
                s["twitter"] = f"https://x.com/{slug}"
            if random.random() < 0.4:
                s["telegram"] = f"https://t.me/{slug}"
            if random.random() < 0.3:
                s["website"] = f"https://{slug}.fun"
        return s

    # ---------------- coin universe ----------------
    def seed(self, n=28):
        for _ in range(n):
            c = self._make_coin("sim")
            # spread creation ages a bit
            age = random.uniform(0, 300)
            c["created_at"] = iso(now() - timedelta(minutes=age))
            self.coins[c["mint"]] = c
        self._seed_wallets()

    def _seed_wallets(self):
        handles = ["Ansem", "Cupsey", "Euris", "Frank", "Mitch", "Casino", "Waddles",
                   "Pow", "Kev", "Gorilla", "Assasin", "Cented"]
        for h in handles:
            self.wallets.append({
                "id": str(uuid.uuid4()),
                "handle": h,
                "address": self._fake_addr(),
                "win_rate": round(random.uniform(52, 88), 1),
                "pnl_sol": round(random.uniform(20, 900), 1),
                "last_buy": None,
                "followers": random.randint(200, 25000),
            })

    async def prune(self):
        cutoff = now() - timedelta(hours=6)
        for mint in list(self.coins.keys()):
            c = self.coins[mint]
            created = datetime.fromisoformat(c["created_at"])
            if created < cutoff and mint not in self.positions and len(self.coins) > 24:
                del self.coins[mint]
        # keep spawning fresh coins so "new coins" always exist
        while len(self.coins) < 30:
            c = self._make_coin("sim")
            self.coins[c["mint"]] = c

    # ---------------- market simulation ----------------
    def tick_market(self):
        for c in self.coins.values():
            c["price_prev"] = c["price"]
            # momentum + noise random walk; younger coins more volatile
            drift = random.gauss(0.005, 0.09)
            c["price"] = max(c["price"] * (1 + drift), 1e-12)
            c["market_cap_usd"] = c["price"] * 1_000_000_000
            vol_add = abs(random.gauss(0, 1)) * c["market_cap_usd"] * 0.02
            c["volume_24h_usd"] = c["volume_24h_usd"] * 0.985 + vol_add
            c["vol_spike"] = vol_add / max(c["volume_24h_usd"], 1) * 20
            c["global_fees_paid_sol"] += abs(drift) * random.uniform(0.02, 0.2)
            c["trades_count"] += random.randint(0, 12)
            c["holders"] = max(1, c["holders"] + random.randint(-3, 8))
            c["history"].append(round(c["price"], 12))
            if len(c["history"]) > 60:
                c["history"] = c["history"][-60:]

    def _age_min(self, c):
        return (now() - datetime.fromisoformat(c["created_at"])).total_seconds() / 60

    def _score(self, c):
        """Bot scoring: volume spike + mcap growth + newness, gated by filters."""
        growth = (c["market_cap_usd"] - c["mcap_start"]) / max(c["mcap_start"], 1)
        age = self._age_min(c)
        newness = max(0, 1 - age / NEW_COIN_MAX_AGE_MIN)
        score = c["vol_spike"] * 2 + growth * 3 + newness * 1.5
        return score, growth, age, newness

    def passes_filters(self, c):
        if not c["has_social"]:
            return False, "no social link"
        if c["global_fees_paid_sol"] < MIN_GLOBAL_FEES_SOL:
            return False, f"fees {c['global_fees_paid_sol']:.2f} < 0.5"
        if not c.get("dev_sold"):
            return False, ("dev still holds supply" if c.get("dev_checked")
                           else "dev holdings unverified")
        if self._age_min(c) > NEW_COIN_MAX_AGE_MIN:
            return False, "too old"
        return True, "ok"

    # ---------------- bot logic ----------------
    async def tick_bot(self):
        if not self.bot["running"]:
            return
        # --- manage open positions (sell decisions) ---
        for mint in list(self.positions.keys()):
            pos = self.positions[mint]
            c = self.coins.get(mint)
            if not c:
                await self._close(mint, "delisted")
                continue
            change = (c["price"] - pos["entry_price"]) / pos["entry_price"]
            held = (now() - datetime.fromisoformat(pos["entry_time"])).total_seconds() / 60
            reason = None
            if change >= TAKE_PROFIT:
                reason = "take profit"
            elif change <= STOP_LOSS:
                reason = "stop loss"
            elif held >= MAX_HOLD_MIN and change < 0.02:
                reason = "stagnant / time exit"
            elif c["vol_spike"] < 0.3 and change > 0.05:
                reason = "momentum fading"
            if reason:
                await self._close(mint, reason)

        # --- scan for buys ---
        if self.bot["mode"] != "paper":
            return  # real mode is a simulation shell; no auto real trades
        candidates = []
        for c in self.coins.values():
            if c["mint"] in self.positions:
                continue
            ok, why = self.passes_filters(c)
            if not ok:
                continue
            score, growth, age, newness = self._score(c)
            if score > 3.5:
                candidates.append((score, c, growth))
        candidates.sort(key=lambda x: x[0], reverse=True)
        cost_usd = TRADE_SIZE_SOL * SOL_USD
        for score, c, growth in candidates[:3]:
            if self.bot["paper_balance_usd"] < cost_usd:
                break
            if random.random() < 0.55:  # bot is selective
                await self._open(c, score, growth)

    async def _open(self, c, score, growth):
        cost_usd = TRADE_SIZE_SOL * SOL_USD
        self.bot["paper_balance_usd"] -= cost_usd
        qty = cost_usd / c["price"]
        pos = {
            "id": str(uuid.uuid4()),
            "mint": c["mint"],
            "name": c["name"],
            "symbol": c["symbol"],
            "entry_price": c["price"],
            "entry_time": iso(now()),
            "size_sol": TRADE_SIZE_SOL,
            "cost_usd": cost_usd,
            "qty": qty,
        }
        self.positions[c["mint"]] = pos
        reason = (f"vol spike {c['vol_spike']:.1f}x, mcap +{growth*100:.0f}%, "
                  f"fees {c['global_fees_paid_sol']:.2f} SOL, has social")
        await self._record_trade(c, "BUY", c["price"], cost_usd, reason, 0)
        self._log_decision(c, "BUY", reason)

    async def _close(self, mint, reason):
        pos = self.positions.pop(mint, None)
        if not pos:
            return
        c = self.coins.get(mint)
        exit_price = c["price"] if c else pos["entry_price"] * 0.5
        proceeds = pos["qty"] * exit_price
        pnl = proceeds - pos["cost_usd"]
        self.bot["paper_balance_usd"] += proceeds
        pnl_pct = (exit_price - pos["entry_price"]) / pos["entry_price"] * 100
        await self._record_trade(
            c or {"mint": mint, "name": pos["name"], "symbol": pos["symbol"]},
            "SELL", exit_price, proceeds, reason, pnl, pnl_pct, pos["entry_price"])
        self._log_decision(c or {"name": pos["name"], "symbol": pos["symbol"],
                                 "mint": mint}, "SELL", f"{reason} ({pnl_pct:+.0f}%)")

    async def _record_trade(self, c, side, price, usd, reason, pnl, pnl_pct=0, entry=None,
                            mode=None, sig=None):
        doc = {
            "id": str(uuid.uuid4()),
            "mint": c["mint"],
            "name": c.get("name", ""),
            "symbol": c.get("symbol", ""),
            "side": side,
            "price": price,
            "usd": usd,
            "sol": usd / SOL_USD,
            "reason": reason,
            "pnl_usd": pnl,
            "pnl_pct": pnl_pct,
            "entry_price": entry,
            "mode": mode or self.bot["mode"],
            "sig": sig,
            "explorer": f"https://solscan.io/tx/{sig}" if sig else None,
            "time": iso(now()),
        }
        await self.db.trades.insert_one(dict(doc))
        doc.pop("_id", None)

    def _log_decision(self, c, action, reason):
        self.decisions.insert(0, {
            "id": str(uuid.uuid4()),
            "mint": c.get("mint", ""),
            "name": c.get("name", ""),
            "symbol": c.get("symbol", ""),
            "action": action,
            "reason": reason,
            "time": iso(now()),
        })
        self.decisions = self.decisions[:40]

    # ---------------- REAL on-chain trading ----------------
    async def tick_real(self):
        if not self.bot["running"] or self.bot["mode"] != "real":
            return
        if not real_trader.is_configured():
            return
        # ---- manage open real positions using REAL prices ----
        for mint in list(self.real_positions.keys()):
            pos = self.real_positions[mint]
            cur_real = await real_trader.token_price_usd(mint)
            if cur_real is not None:
                pos["cur_real"] = cur_real  # cache for views
            held = (now() - datetime.fromisoformat(pos["entry_time"])).total_seconds() / 60
            entry_real = pos.get("entry_price_real")
            reason = None
            if entry_real and cur_real:
                change = (cur_real - entry_real) / entry_real
                if change >= TAKE_PROFIT:
                    reason = "take profit"
                elif change <= STOP_LOSS:
                    reason = "stop loss"
                elif held >= MAX_HOLD_MIN and change < 0.02:
                    reason = "time exit"
            else:
                # no real price feed yet -> hold; only a long safety exit
                if held >= 90:
                    reason = "safety exit (no live price)"
            if reason:
                await self._real_sell(mint, reason, cur_real)

        # ---- scan for real buys (ONLY genuine live coins) ----
        cost_sol = TRADE_SIZE_SOL + 0.0002  # trade + est. fees
        if self.bot["real_balance_sol"] < cost_sol:
            return
        candidates = []
        for c in self.coins.values():
            if c["source"] != "live":       # never trade simulated mints on-chain
                continue
            if c["mint"] in self.real_positions:
                continue
            ok, _ = self.passes_filters(c)
            if not ok:
                continue
            score, growth, _, _ = self._score(c)
            if score > 3.5:
                candidates.append((score, c, growth))
        candidates.sort(key=lambda x: x[0], reverse=True)
        for score, c, growth in candidates[:1]:  # conservative: one real buy per tick
            if len(self.real_positions) >= 5:
                break
            await self._real_buy(c, growth)

    async def _real_buy(self, c, growth):
        try:
            sig = await real_trader.execute_trade("buy", c["mint"], TRADE_SIZE_SOL, True)
        except Exception as e:
            self._log_decision(c, "SKIP", f"real buy failed: {str(e)[:80]}")
            print("real buy error:", e)
            return
        entry_real = await real_trader.token_price_usd(c["mint"])
        self.real_positions[c["mint"]] = {
            "id": str(uuid.uuid4()),
            "mint": c["mint"], "name": c["name"], "symbol": c["symbol"],
            "entry_price": c["price"], "entry_price_real": entry_real,
            "cur_real": entry_real, "entry_time": iso(now()),
            "size_sol": TRADE_SIZE_SOL, "cost_usd": TRADE_SIZE_SOL * SOL_USD,
            "qty": TRADE_SIZE_SOL * SOL_USD / c["price"], "sig": sig,
        }
        await self.db.real_positions.update_one(
            {"_id": c["mint"]}, {"$set": self.real_positions[c["mint"]]}, upsert=True)
        reason = (f"REAL buy {TRADE_SIZE_SOL}◎ · vol {c['vol_spike']:.1f}x, "
                  f"mcap +{growth*100:.0f}%, fees {c['global_fees_paid_sol']:.2f}◎, dev sold")
        await self._record_trade(c, "BUY", c["price"], TRADE_SIZE_SOL * SOL_USD,
                                 reason, 0, mode="real", sig=sig)
        self._log_decision(c, "BUY", reason)

    async def _real_sell(self, mint, reason, cur_real=None):
        pos = self.real_positions.get(mint)
        if not pos:
            return
        try:
            sig = await real_trader.execute_trade("sell", mint, "100%", False)
        except Exception as e:
            self._log_decision({"mint": mint, "symbol": pos["symbol"], "name": pos["name"]},
                               "SKIP", f"real sell failed: {str(e)[:80]}")
            print("real sell error:", e)
            return
        self.real_positions.pop(mint, None)
        await self.db.real_positions.delete_one({"_id": mint})
        c = self.coins.get(mint)
        entry_real = pos.get("entry_price_real")
        if entry_real and cur_real:
            pnl_pct = (cur_real - entry_real) / entry_real * 100
            proceeds = pos["cost_usd"] * (cur_real / entry_real)
        else:
            pnl_pct = 0.0
            proceeds = pos["cost_usd"]
        est_pnl = proceeds - pos["cost_usd"]
        await self._record_trade(c or {"mint": mint, "name": pos["name"], "symbol": pos["symbol"]},
                                 "SELL", cur_real or pos["entry_price"], proceeds,
                                 f"{reason} ({pnl_pct:+.0f}%)", est_pnl, pnl_pct,
                                 entry_real, mode="real", sig=sig)
        self._log_decision(c or {"mint": mint, "symbol": pos["symbol"], "name": pos["name"]},
                           "SELL", f"REAL {reason} ({pnl_pct:+.0f}%)")

    def real_positions_view(self):
        out = []
        for pos in self.real_positions.values():
            entry_real = pos.get("entry_price_real")
            cur_real = pos.get("cur_real") or entry_real
            has_price = bool(entry_real and cur_real)
            if has_price:
                value = pos["cost_usd"] * (cur_real / entry_real)
                pnl_pct = (cur_real - entry_real) / entry_real * 100
            else:
                value = pos["cost_usd"]
                pnl_pct = 0.0
            out.append({
                **{k: pos[k] for k in ("id", "mint", "name", "symbol", "entry_price",
                                       "entry_time", "size_sol", "cost_usd", "sig")},
                "entry_price": entry_real or pos["entry_price"],
                "current_price": cur_real or pos["entry_price"],
                "has_live_price": has_price,
                "value_usd": value,
                "pnl_usd": value - pos["cost_usd"],
                "pnl_pct": pnl_pct,
                "explorer": f"https://solscan.io/tx/{pos['sig']}",
                "history": [],
            })
        return sorted(out, key=lambda x: x["entry_time"], reverse=True)

    def tick_wallets(self):
        # smart wallets occasionally "buy" a live coin -> copy-trade feed
        if not self.coins:
            return
        for w in self.wallets:
            if random.random() < 0.25:
                c = random.choice(list(self.coins.values()))
                w["last_buy"] = {
                    "symbol": c["symbol"], "name": c["name"], "mint": c["mint"],
                    "time": iso(now()),
                }

    # ---------------- persistence ----------------
    async def load(self):
        st = await self.db.bot_state.find_one({"_id": "singleton"})
        if st:
            st.pop("_id", None)
            self.bot.update(st)
        async for doc in self.db.real_positions.find():
            doc.pop("_id", None)
            if doc.get("mint"):
                self.real_positions[doc["mint"]] = doc

    async def save(self):
        await self.db.bot_state.update_one(
            {"_id": "singleton"}, {"$set": dict(self.bot)}, upsert=True)

    async def restart(self):
        self.positions.clear()
        self.decisions.clear()
        self.bot["paper_balance_usd"] = START_BALANCE_USD
        self.bot["started_at"] = iso(now())
        await self.db.trades.delete_many({"mode": "paper"})
        await self.save()

    # ---------------- background loops ----------------
    async def sim_loop(self):
        while True:
            try:
                self._loop_count += 1
                self.tick_market()
                await self.tick_bot()
                self.tick_wallets()
                await self.prune()
                await self.save()
            except Exception as e:  # keep loop alive
                print("sim_loop error:", e)
            await asyncio.sleep(4)

    async def ingest_loop(self):
        """Connect to PumpPortal free websocket for REAL new pump.fun tokens."""
        import websockets
        url = "wss://pumpportal.fun/api/data"
        while True:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    await ws.send(json.dumps({"method": "subscribeNewToken"}))
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except Exception:
                            continue
                        if not msg.get("mint"):
                            continue
                        await self._ingest_real(msg)
            except Exception as e:
                print("ingest_loop reconnect:", e)
                await asyncio.sleep(10)

    async def _ingest_real(self, msg):
        if msg["mint"] in self.coins:
            return
        socials = {"twitter": "", "telegram": "", "website": ""}
        image = ""
        uri = msg.get("uri")
        if uri:
            try:
                timeout = aiohttp.ClientTimeout(total=5)
                async with aiohttp.ClientSession(timeout=timeout) as s:
                    async with s.get(uri) as r:
                        meta = await r.json(content_type=None)
                        socials["twitter"] = meta.get("twitter") or ""
                        socials["telegram"] = meta.get("telegram") or ""
                        socials["website"] = meta.get("website") or ""
                        image = meta.get("image") or ""
            except Exception:
                pass
        real = {
            "mint": msg["mint"],
            "name": msg.get("name"),
            "symbol": msg.get("symbol"),
            "marketCapSol": msg.get("marketCapSol"),
            "creator": msg.get("traderPublicKey"),
            "socials": socials,
            "image": image,
        }
        c = self._make_coin("live", real)
        self.coins[c["mint"]] = c

    async def real_loop(self):
        while True:
            try:
                await self.tick_real()
                if real_trader.is_configured():
                    bal = await real_trader.get_balance_sol()
                    if bal is not None:
                        self.bot["real_balance_sol"] = bal
                        await self.save()
            except Exception as e:
                print("real_loop error:", e)
            await asyncio.sleep(6)

    async def dev_check_loop(self):
        """Verify on-chain whether the dev/creator has sold their supply,
        for live coins with a known creator. Throttled to spare the RPC."""
        while True:
            try:
                pending = [c for c in self.coins.values()
                           if c["source"] == "live" and not c.get("dev_checked")
                           and c.get("creator")]
                for c in pending[:4]:
                    bal = await real_trader.creator_token_balance(c["creator"], c["mint"])
                    if bal is not None:
                        c["dev_sold"] = bal <= 1.0  # dev effectively out of supply
                        c["dev_checked"] = True
                    else:
                        c["dev_attempts"] = c.get("dev_attempts", 0) + 1
                        if c["dev_attempts"] >= 3:
                            c["dev_checked"] = True  # give up -> stays ineligible (safe)
                    await asyncio.sleep(1)
            except Exception as e:
                print("dev_check_loop error:", e)
            await asyncio.sleep(8)

    def start(self):
        loop = asyncio.get_event_loop()
        self._tasks.append(loop.create_task(self.sim_loop()))
        self._tasks.append(loop.create_task(self.ingest_loop()))
        self._tasks.append(loop.create_task(self.real_loop()))
        self._tasks.append(loop.create_task(self.dev_check_loop()))

    # ---------------- view builders ----------------
    def coin_view(self, c):
        return {
            "mint": c["mint"],
            "name": c["name"],
            "symbol": c["symbol"],
            "image": c["image"],
            "socials": c["socials"],
            "has_social": c["has_social"],
            "dev_sold": c.get("dev_sold", False),
            "dev_checked": c.get("dev_checked", False),
            "created_at": c["created_at"],
            "age_min": round(self._age_min(c), 1),
            "price": c["price"],
            "price_prev": c["price_prev"],
            "market_cap_usd": c["market_cap_usd"],
            "mcap_growth_pct": (c["market_cap_usd"] - c["mcap_start"]) / max(c["mcap_start"], 1) * 100,
            "volume_24h_usd": c["volume_24h_usd"],
            "global_fees_paid_sol": round(c["global_fees_paid_sol"], 3),
            "vol_spike": round(c["vol_spike"], 2),
            "source": c["source"],
            "history": c["history"][-40:],
            "holders": c["holders"],
            "trades_count": c["trades_count"],
            "eligible": self.passes_filters(c)[0],
            "held": c["mint"] in self.positions,
        }

    def positions_view(self):
        out = []
        for pos in self.positions.values():
            c = self.coins.get(pos["mint"])
            cur = c["price"] if c else pos["entry_price"]
            value = pos["qty"] * cur
            pnl = value - pos["cost_usd"]
            out.append({
                **{k: pos[k] for k in ("id", "mint", "name", "symbol", "entry_price",
                                       "entry_time", "size_sol", "cost_usd")},
                "current_price": cur,
                "value_usd": value,
                "pnl_usd": pnl,
                "pnl_pct": (cur - pos["entry_price"]) / pos["entry_price"] * 100,
                "history": (c["history"][-40:] if c else []),
            })
        return sorted(out, key=lambda x: x["entry_time"], reverse=True)
