from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel
from datetime import datetime, timezone, timedelta

from engine import Engine, SOL_USD, START_BALANCE_USD
import real_trader

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# Fall back to a local MongoDB + default DB name so the server can boot even
# before the operator has written backend/.env. Override both in your .env.
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
db_name = os.environ.get('DB_NAME', 'pumpscout')
client = AsyncIOMotorClient(mongo_url)
db = client[db_name]

app = FastAPI()
api_router = APIRouter(prefix="/api")

engine = Engine(db)


class ModeReq(BaseModel):
    mode: str


class WithdrawReq(BaseModel):
    address: str
    amount_sol: float


class TradeReq(BaseModel):
    mint: str


class StrategyReq(BaseModel):
    take_profit: float
    stop_loss: float
    trade_size_sol: float
    max_positions: int
    min_mcap_usd: float = 3000
    min_holders: int = 10
    flat_exit_min: float = 1
    min_volume_usd: float = 5000
    rebuy_cooldown_min: float = 5
    max_hold_min: float = 45
    min_score: float = 3.5


class GuardrailReq(BaseModel):
    enabled: bool
    daily_loss_limit_sol: float
    total_spend_cap_sol: float


class TrackerReq(BaseModel):
    enabled: bool
    address: str = ""


@api_router.get("/")
async def root():
    return {"message": "pump.fun bot online"}


@api_router.get("/coins")
async def get_coins(filter: str = "all"):
    coins = [engine.coin_view(c) for c in engine.coins.values()]
    if filter == "eligible":
        coins = [c for c in coins if c["eligible"]]
    elif filter == "new":
        coins = [c for c in coins if c["age_min"] <= 60]
    coins.sort(key=lambda c: c["vol_spike"], reverse=True)
    return {"coins": coins, "sol_usd": SOL_USD}


@api_router.get("/coins/{mint}")
async def get_coin(mint: str):
    c = engine.coins.get(mint)
    if not c:
        raise HTTPException(404, "coin not found")
    return engine.coin_view(c)


@api_router.get("/bot/state")
async def bot_state():
    real = engine.bot["mode"] == "real"
    positions = engine.real_positions_view() if real else engine.positions_view()
    pos_value = sum(p["value_usd"] for p in positions)
    equity = engine.bot["paper_balance_usd"] + sum(
        p["value_usd"] for p in engine.positions_view())
    configured = real_trader.is_configured()
    return {
        **engine.bot,
        "sol_usd": SOL_USD,
        "start_balance_usd": START_BALANCE_USD,
        "open_positions": len(positions),
        "positions_value_usd": pos_value,
        "equity_usd": equity,
        "total_pnl_usd": equity - START_BALANCE_USD,
        "total_pnl_pct": (equity - START_BALANCE_USD) / START_BALANCE_USD * 100,
        "real_configured": configured,
        "real_pubkey": real_trader.public_key(),
        "real_rpc": real_trader.rpc_url(),
        "real_open_positions": len(engine.real_positions),
        "guardrail_status": engine.guardrail_block(),
    }


@api_router.post("/bot/toggle")
async def bot_toggle():
    engine.bot["running"] = not engine.bot["running"]
    await engine.save()
    return {"running": engine.bot["running"]}


@api_router.post("/bot/mode")
async def bot_mode(req: ModeReq):
    if req.mode not in ("paper", "real"):
        raise HTTPException(400, "invalid mode")
    engine.bot["mode"] = req.mode
    await engine.save()
    return {"mode": engine.bot["mode"]}


@api_router.post("/bot/strategy")
async def set_strategy(req: StrategyReq):
    s = {
        "take_profit": max(0.02, min(req.take_profit, 10)),
        "stop_loss": -abs(req.stop_loss) if req.stop_loss > 0 else max(req.stop_loss, -0.95),
        "trade_size_sol": max(0.001, min(req.trade_size_sol, 100)),
        "max_positions": max(1, min(int(req.max_positions), 20)),
        "min_mcap_usd": max(0.0, req.min_mcap_usd),
        "min_holders": max(0, int(req.min_holders)),
        "flat_exit_min": max(0.1, req.flat_exit_min),
        "min_volume_usd": max(0.0, req.min_volume_usd),
        "rebuy_cooldown_min": max(0.0, req.rebuy_cooldown_min),
        "max_hold_min": max(0.5, req.max_hold_min),
        "min_score": max(0.0, req.min_score),
    }
    engine.bot["strategy"] = s
    engine.bot["settings"]["trade_size_sol"] = s["trade_size_sol"]
    await engine.save()
    logger.info("strategy updated: %s", s)
    return {"ok": True, "strategy": s}


@api_router.post("/bot/guardrails")
async def set_guardrails(req: GuardrailReq):
    g = {
        "enabled": req.enabled,
        "daily_loss_limit_sol": max(0.0, req.daily_loss_limit_sol),
        "total_spend_cap_sol": max(0.0, req.total_spend_cap_sol),
    }
    engine.bot["guardrails"] = g
    await engine.save()
    return {"ok": True, "guardrails": g}


@api_router.post("/bot/tracker")
async def set_tracker(req: TrackerReq):
    addr = req.address.strip()
    if req.enabled and not addr:
        raise HTTPException(400, "wallet address required to enable tracker")
    engine.bot["tracked_wallet"] = addr
    engine.bot["tracker_enabled"] = req.enabled
    await engine.save()
    return {"ok": True, "tracked_wallet": addr, "tracker_enabled": req.enabled}


@api_router.post("/bot/reset_spend")
async def reset_spend():
    engine.bot["spent_today_sol"] = 0.0
    engine.bot["loss_today_sol"] = 0.0
    engine.bot["total_spent_sol"] = 0.0
    await engine.save()
    return {"ok": True}


@api_router.post("/bot/restart")
async def bot_restart():
    await engine.restart()
    return {"ok": True, "paper_balance_usd": START_BALANCE_USD}


@api_router.get("/positions")
async def positions():
    if engine.bot["mode"] == "real":
        return {"positions": engine.real_positions_view(), "mode": "real"}
    return {"positions": engine.positions_view(), "mode": "paper"}


@api_router.post("/positions/close_all")
async def close_all_positions():
    return await engine.close_all()


@api_router.get("/trades")
async def trades(hours: int = 24):
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    docs = await db.trades.find(
        {"time": {"$gte": cutoff}, "mode": engine.bot["mode"]}, {"_id": 0}
    ).sort("time", -1).to_list(500)
    buys = sum(1 for d in docs if d["side"] == "BUY")
    sells = [d for d in docs if d["side"] == "SELL"]
    wins = sum(1 for d in sells if d.get("pnl_usd", 0) > 0)
    realized = sum(d.get("pnl_usd", 0) for d in sells)
    return {
        "trades": docs,
        "buys": buys,
        "sells": len(sells),
        "win_rate": round(wins / len(sells) * 100, 1) if sells else 0,
        "realized_pnl_usd": realized,
    }


@api_router.get("/decisions")
async def decisions():
    return {"decisions": engine.decisions}


@api_router.get("/wallets")
async def wallets():
    return {"wallets": sorted(engine.wallets, key=lambda w: w["pnl_sol"], reverse=True)}


@api_router.post("/wallet/withdraw")
async def withdraw(req: WithdrawReq):
    # amount_sol <= 0 means "send everything" (minus the on-chain fee reserve)
    send_all = req.amount_sol is None or req.amount_sol <= 0
    if real_trader.is_configured():
        try:
            amt = None if send_all else req.amount_sol
            sig, sent_sol = await real_trader.withdraw(req.address, amt)
        except Exception as e:
            raise HTTPException(400, str(e))
        bal = await real_trader.get_balance_sol()
        if bal is not None:
            engine.bot["real_balance_sol"] = bal
            await engine.save()
        return {"ok": True, "simulated": False, "signature": sig,
                "explorer": f"https://solscan.io/tx/{sig}",
                "message": f"Sent {sent_sol:.6f} SOL to {req.address}",
                "sent_sol": sent_sol,
                "real_balance_sol": engine.bot["real_balance_sol"]}
    # no key -> simulation shell
    amt = engine.bot["real_balance_sol"] if send_all else req.amount_sol
    if amt <= 0 or engine.bot["real_balance_sol"] < amt:
        raise HTTPException(400, "insufficient real balance")
    engine.bot["real_balance_sol"] -= amt
    await engine.save()
    return {"ok": True, "simulated": True, "sent_sol": amt,
            "message": f"[SIMULATION] Would send {amt:.6f} SOL to {req.address}",
            "real_balance_sol": engine.bot["real_balance_sol"]}


@api_router.post("/wallet/deposit_sim")
async def deposit_sim(req: WithdrawReq):
    if real_trader.is_configured():
        raise HTTPException(400, "wallet is live — deposit real SOL to the address instead")
    engine.bot["real_balance_sol"] += req.amount_sol
    await engine.save()
    return {"ok": True, "real_balance_sol": engine.bot["real_balance_sol"]}


@api_router.post("/real/buy")
async def real_buy(req: TradeReq):
    if not real_trader.is_configured():
        raise HTTPException(400, "real wallet not configured")
    c = engine.coins.get(req.mint)
    if not c:
        raise HTTPException(404, "coin not in scanner")
    await engine._real_buy(c, (c["market_cap_usd"] - c["mcap_start"]) / max(c["mcap_start"], 1))
    if req.mint not in engine.real_positions:
        raise HTTPException(502, "buy failed on-chain (see server logs)")
    return {"ok": True, "position": engine.real_positions[req.mint]}


@api_router.post("/real/sell")
async def real_sell(req: TradeReq):
    if not real_trader.is_configured():
        raise HTTPException(400, "real wallet not configured")
    if req.mint not in engine.real_positions:
        raise HTTPException(404, "no open real position for this mint")
    cur = await engine._real_price(req.mint)
    await engine._real_sell(req.mint, "manual sell", cur)
    return {"ok": True, "closed": req.mint not in engine.real_positions}


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _readiness_report():
    """Log a clear green/red checklist of what's configured before trading starts."""
    ok, warn = [], []

    # MongoDB
    mongo = os.environ.get('MONGO_URL')
    if mongo:
        ok.append("MONGO_URL set")
    else:
        warn.append("MONGO_URL not set -> using local fallback (mongodb://localhost:27017)")

    # RPC
    rpc = os.environ.get('SOLANA_RPC_URL', '')
    if not rpc:
        warn.append("SOLANA_RPC_URL not set -> falling back to PUBLIC RPC (rate-limited, real trades WILL fail)")
    elif 'api.mainnet-beta.solana.com' in rpc:
        warn.append("SOLANA_RPC_URL is the PUBLIC RPC (rate-limited, real trades WILL fail) -> use a Helius/Triton URL")
    else:
        ok.append("SOLANA_RPC_URL set (private RPC)")

    # Wallet key
    if real_trader.is_configured():
        ok.append(f"SOLANA_PRIVATE_KEY_B58 set -> bot wallet {real_trader.public_key()}")
    else:
        warn.append("SOLANA_PRIVATE_KEY_B58 not set -> REAL trading disabled (paper mode only). Run generate_wallet.py")

    logger.info("=== PumpScout readiness ===")
    for line in ok:
        logger.info("  [OK]   %s", line)
    for line in warn:
        logger.warning("  [WARN] %s", line)
    if not warn:
        logger.info("  All systems go: REAL trading is fully configured.")
    logger.info("===========================")


@app.on_event("startup")
async def startup():
    _readiness_report()
    await engine.load()
    engine.seed()
    if real_trader.is_configured():
        engine.bot["real_deposit_address"] = real_trader.public_key()
        bal = await real_trader.get_balance_sol()
        if bal is not None:
            engine.bot["real_balance_sol"] = bal
            logger.info("bot wallet balance: %.4f SOL", bal)
    engine.start()
    logger.info("engine started (real_configured=%s)", real_trader.is_configured())


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
