"""Real on-chain Solana trading via PumpPortal Local Transaction API.

Self-custody: the wallet private key is read from env, backend signs and submits
transactions to a Solana RPC. Trades pump.fun / PumpSwap tokens.
Requested policy: 0.01 SOL/trade, 25% slippage, 0.0001 priority fee, 0 jito tip.
"""
import asyncio
import os

import httpx
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.transaction import VersionedTransaction
from solders.message import MessageV0
from solders.system_program import transfer, TransferParams
from solana.rpc.async_api import AsyncClient
from solana.rpc.models import TxOpts, TokenAccountOpts

LAMPORTS = 1_000_000_000
FEE_RESERVE = 10_000  # lamports kept for network fee on withdraw

SLIPPAGE = 25
PRIORITY_FEE = 0.0001
POOL = "auto"


def rpc_url():
    return os.environ.get("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com"


def get_keypair():
    k = (os.environ.get("SOLANA_PRIVATE_KEY_B58") or "").strip()
    if not k:
        return None
    try:
        return Keypair.from_base58_string(k)
    except Exception:
        return None


def is_configured():
    return get_keypair() is not None


def public_key():
    kp = get_keypair()
    return str(kp.pubkey()) if kp else None


async def get_balance_sol():
    kp = get_keypair()
    if not kp:
        return None
    try:
        async with AsyncClient(rpc_url()) as rpc:
            r = await rpc.get_balance(kp.pubkey())
            return r.value / LAMPORTS
    except Exception as e:
        print("balance error:", e)
        return None


async def token_price_usd(mint):
    """Real USD price for a token from DexScreener (free). None if not listed yet."""
    if not mint:
        return None
    try:
        async with httpx.AsyncClient(timeout=8) as c:
            r = await c.get(f"https://api.dexscreener.com/latest/dex/tokens/{mint}")
            pairs = (r.json() or {}).get("pairs") or []
            if not pairs:
                return None
            pairs.sort(key=lambda p: ((p.get("liquidity") or {}).get("usd") or 0),
                       reverse=True)
            pr = pairs[0].get("priceUsd")
            return float(pr) if pr else None
    except Exception as e:
        print("price error:", str(e)[:100])
        return None


async def creator_token_balance(creator, mint):
    """Remaining amount of `mint` still held by the dev/creator wallet.
    Returns float amount, or None if it can't be determined."""
    if not creator or not mint:
        return None
    try:
        async with AsyncClient(rpc_url()) as rpc:
            resp = await rpc.get_token_accounts_by_owner_json_parsed(
                Pubkey.from_string(creator),
                TokenAccountOpts(mint=Pubkey.from_string(mint)))
            total = 0.0
            for acc in resp.value:
                info = acc.account.data.parsed["info"]
                amt = info["tokenAmount"].get("uiAmount") or 0
                total += float(amt)
            return total
    except Exception as e:
        print("dev-check error:", str(e)[:120])
        return None


async def execute_trade(action, mint, amount, denominated_in_sol):
    """action: 'buy'|'sell'. Returns tx signature string."""
    kp = get_keypair()
    if not kp:
        raise RuntimeError("wallet not configured")
    body = {
        "publicKey": str(kp.pubkey()),
        "action": action,
        "mint": mint,
        "amount": amount,
        "denominatedInSol": "true" if denominated_in_sol else "false",
        "slippage": SLIPPAGE,
        "priorityFee": PRIORITY_FEE,
        "pool": POOL,
    }
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post("https://pumpportal.fun/api/trade-local", json=body)
    if r.status_code != 200:
        raise RuntimeError(f"pumpportal {r.status_code}: {r.text[:200]}")
    tx = VersionedTransaction.from_bytes(r.content)
    signed = VersionedTransaction(tx.message, [kp])
    async with AsyncClient(rpc_url()) as rpc:
        sent = await rpc.send_raw_transaction(
            bytes(signed),
            opts=TxOpts(skip_preflight=True, preflight_commitment="confirmed",
                        max_retries=5))
        sig = sent.value
        # confirm the tx actually landed before we treat it as a real fill
        for _ in range(16):
            await asyncio.sleep(2)
            try:
                st = await rpc.get_signature_statuses([sig])
                v = st.value[0]
            except Exception:
                continue
            if v is None:
                continue
            if v.err is not None:
                raise RuntimeError(f"tx failed on-chain: {v.err}")
            if v.confirmation_status is not None:
                return str(sig)
        raise RuntimeError("tx not confirmed (RPC too slow / blockhash expired)")


async def withdraw(destination, sol):
    kp = get_keypair()
    if not kp:
        raise RuntimeError("wallet not configured")
    try:
        to = Pubkey.from_string(destination)
    except Exception:
        raise RuntimeError("invalid destination address")
    lamports = int(sol * LAMPORTS)
    async with AsyncClient(rpc_url()) as rpc:
        bal = (await rpc.get_balance(kp.pubkey())).value
        if lamports <= 0 or lamports + FEE_RESERVE > bal:
            raise RuntimeError("insufficient balance plus fee reserve")
        bh = (await rpc.get_latest_blockhash()).value.blockhash
        ix = transfer(TransferParams(
            from_pubkey=kp.pubkey(), to_pubkey=to, lamports=lamports))
        msg = MessageV0.try_compile(kp.pubkey(), [ix], [], bh)
        tx = VersionedTransaction(msg, [kp])
        sent = await rpc.send_raw_transaction(bytes(tx))
    return str(sent.value)
