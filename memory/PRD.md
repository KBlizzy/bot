# PumpScout — AI Paper Trading Terminal (PRD)

## Original Problem Statement
Scan Solana coins on pump.fun, have an AI bot decide which to pick, and paper-trade starting at $20. Show picks + progress, list of buys/sells up to 24h, mostly new coins, filter: must have a social link AND ≥0.5 Global Fees Paid. Copyable CA. Restart to $20. Real coins/real market cap, simulated real-time trading. Also a real-trading mode (send/withdraw real SOL, show wallet SOL balance). Trade 0.01 at a time, 25% slippage, .0001 priority, 0 bribe. Bot decides buy/sell off volume. Scout other wallets (copy-trade). Paper + Real modes. Scout all day until paused.

## Architecture
- **Backend** FastAPI + MongoDB (`/app/backend/server.py`, `engine.py`). Background async engine ticks every 4s: simulates market, runs bot, updates copy-trade feed. Ingests REAL new pump.fun coins via PumpPortal free websocket (`wss://pumpportal.fun/api/data`, subscribeNewToken) — real CA, name, market cap, socials. Simulator seeds ~30 coins so app is never empty.
- **Frontend** React + react-query polling (3-5s) + Tailwind, "Terminal Brutalism" dark theme (Azeret/JetBrains Mono). `/app/frontend/src/App.js`.
- **Data**: coins/positions/decisions/wallets in-memory; trades + bot wallet state persisted to MongoDB.

## User Persona
Solana degen trader who wants to test/observe an automated pump.fun sniping strategy risk-free before committing real funds.

## Core Requirements (static)
- Paper wallet starts $20, $0.01 SOL per trade, 24h trade history, one-click reset to $20.
- Filters: has social link + Global Fees Paid ≥ 0.5 SOL + new coins.
- Bot decides buy/sell autonomously off volume spikes, mcap growth, newness; TP +25% / SL -15% / time exit.
- Copyable contract address. Start/Pause scouting. Copy-trade wallet scout feed.
- Real mode: wallet SOL balance, deposit address, withdraw-to-any-address — **clearly-marked SIMULATION shell (no on-chain action)**.

## Implemented (2026-08-19)
- ✅ Live scanner of real + simulated pump.fun coins with mcap, volume, fees, age, socials, sparkline, copy CA.
- ✅ AI bot auto paper-trading from $20 with the exact filter/decision rules; decisions feed with reasons.
- ✅ Open positions + 24h trade history tabs with live P&L, win rate, realized P&L.
- ✅ Start/Pause, Reset $20, Paper/Real mode switch.
- ✅ Scouted smart-wallet copy-trade radar.
- ✅ Bot config strip (0.01 SOL / 25% slippage / .0001 priority / 0 bribe).

## REAL on-chain trading (2026-08-19) — LIVE
- ✅ Self-custody wallet (private key in backend/.env `SOLANA_PRIVATE_KEY_B58`, pubkey 7hEc6w6ptPDvbEmS6UA7nUNqWN6NR2JLFUJu2SBrfcuQ).
- ✅ RPC: Helius (`SOLANA_RPC_URL` in .env). Public RPC was too slow (BlockhashNotFound / timeouts) — Helius required.
- ✅ Real balance read from chain; real buy/sell via PumpPortal Local Transaction API (`real_trader.py`) signed with solders, submitted skip_preflight + confirmation polling (only records position after tx confirms).
- ✅ Withdraw real SOL to any address (SystemProgram transfer, validates destination on-chain).
- ✅ "Dev sold supply" filter — real on-chain check of creator's remaining token balance (getTokenAccountsByOwner). Only trades coins where dev is out of supply.
- ✅ Real exits use REAL prices from DexScreener (free); if a brand-new coin isn't on DexScreener yet, bot HOLDS (no fake-signal churn), 90-min safety exit.
- ✅ Real positions persisted to Mongo (survive restarts); LIVE banner + red UI; manual SELL buttons + Solscan links.
- ✅ Bot only auto-trades real funds when Real mode + Scouting are both ON. Currently PAUSED for safety.

## Known limitations / honesty
- Brand-new bonding-curve coins have NO external price feed (DexScreener/Jupiter list them only after volume/migration). So the bot can't do precise real-price TP/SL on the very newest coins — it holds until price data exists. True per-coin realtime exits need a PAID feed (PumpPortal subscribeTokenTrade) or on-chain bonding-curve decoding.
- 25% slippage on micro-caps is very permissive and round-trips lose value fast — this is the user's requested setting.
- Paper-mode per-coin price after listing is simulated (real starting mcap, then modeled).

## Backlog
- P1: Paid per-token realtime price (PumpPortal token-trade stream) for precise real exits on new coins.
- P1: Spend cap / daily loss limit control in UI; per-coin max hold config.
- P2: Real copy-trade following of scouted wallets; on-chain bonding-curve price decode.
