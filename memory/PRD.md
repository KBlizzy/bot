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
- ✅ Real-wallet SIMULATION shell: balance, deposit address copy, simulate deposit, withdraw form.
- ✅ Scouted smart-wallet copy-trade radar.
- ✅ Bot config strip (0.01 SOL / 25% slippage / .0001 priority / 0 bribe).
- ✅ Backend 15/16 tests pass; all frontend flows verified; clipboard fallback added.

## MOCKED / Not real
- **Real on-chain trading is a SIMULATION shell** — `/api/wallet/withdraw` and `deposit_sim` do NOT move real SOL. No wallet keys, no blockchain transactions.
- Per-coin price evolution is simulated (real starting market cap from PumpPortal, then random-walk) since live per-token trade streaming requires a paid API key.

## Backlog
- P1: Enable genuine on-chain trading via PumpPortal Lightning/local transaction API + funded wallet (requires user key + explicit risk acceptance).
- P1: Persist open positions across backend restarts.
- P2: Live per-token trade/volume stream (paid PumpPortal key) for true real-time prices.
- P2: Configurable bot strategy params (TP/SL, trade size, min fees) from UI.
- P2: Real copy-trade following of scouted wallets.
