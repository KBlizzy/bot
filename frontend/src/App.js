import { useEffect, useRef, useState } from "react";
import "@/App.css";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Toaster, toast } from "sonner";
import {
  Activity, Play, Pause, RotateCcw, Copy, Check, Twitter, Send, Globe,
  TrendingUp, TrendingDown, Zap, Radio, Wallet, ArrowUpRight, Bot, Crosshair,
  AlertTriangle, Flame, Sliders,
} from "lucide-react";
import { api, fmtUsd, fmtMcap, fmtPct, fmtSol, shortCa } from "@/lib/api";
import { Sparkline } from "@/components/Sparkline";

const P = "#14F195";
const L = "#FF3B30";

function useCopy() {
  const [copied, setCopied] = useState(null);
  const copy = (text, label = "Contract address") => {
    const done = () => {
      setCopied(text);
      toast.success(`${label} copied`, { description: shortCa(text) });
      setTimeout(() => setCopied(null), 1200);
    };
    try {
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done).catch(() => fallbackCopy(text, done));
      } else {
        fallbackCopy(text, done);
      }
    } catch {
      fallbackCopy(text, done);
    }
  };
  return { copied, copy };
}

function fallbackCopy(text, done) {
  try {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    document.execCommand("copy");
    document.body.removeChild(ta);
    done();
  } catch {
    toast.error("Copy failed", { description: text });
  }
}

/* ---------- flashing number ---------- */
const Flash = ({ value, format, className = "" }) => {
  const prev = useRef(value);
  const [cls, setCls] = useState("");
  useEffect(() => {
    if (prev.current !== value && prev.current !== undefined) {
      setCls(value > prev.current ? "flash-up" : "flash-dn");
      const t = setTimeout(() => setCls(""), 600);
      prev.current = value;
      return () => clearTimeout(t);
    }
    prev.current = value;
  }, [value]);
  return <span className={`font-num ${cls} ${className}`}>{format(value)}</span>;
};

/* ================= HEADER ================= */
const Header = ({ state, onToggle, onMode, onRestart }) => {
  const paper = state?.mode === "paper";
  return (
    <header className="sticky top-0 z-30 bg-[#0B0C0E] border-b border-[#232528]">
      <div className="px-4 lg:px-6 py-3 flex flex-wrap items-center gap-3 lg:gap-6">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 grid place-items-center bg-[#9945FF] rounded-sm">
            <Crosshair size={18} strokeWidth={2.5} />
          </div>
          <div>
            <div className="font-head text-lg leading-none">PUMPSCOUT</div>
            <div className="font-num text-[10px] text-[#8A8F98] leading-none mt-1">
              pump.fun ai terminal
            </div>
          </div>
        </div>

        {/* mode switch */}
        <div className="flex items-center border border-[#232528] rounded-sm overflow-hidden" data-testid="mode-switch">
          <button
            data-testid="paper-mode-btn"
            onClick={() => onMode("paper")}
            className={`px-4 py-2 text-xs font-num font-semibold transition-colors ${
              paper ? "bg-[#14F195] text-black" : "text-[#8A8F98] hover:text-white"
            }`}
          >
            PAPER
          </button>
          <button
            data-testid="real-mode-btn"
            onClick={() => onMode("real")}
            className={`px-4 py-2 text-xs font-num font-semibold transition-colors ${
              !paper ? "bg-[#FF3B30] text-white" : "text-[#8A8F98] hover:text-white"
            }`}
          >
            REAL
          </button>
        </div>

        <div className="flex items-center gap-3 ml-auto">
          {/* running status */}
          <div className="flex items-center gap-2 px-3 py-2 border border-[#232528] rounded-sm">
            <span className={`w-2 h-2 rounded-full ${state?.running ? "bg-[#14F195] live-dot" : "bg-[#8A8F98]"}`} />
            <span className="font-num text-xs text-[#8A8F98]">
              {state?.running ? "SCOUTING" : "PAUSED"}
            </span>
          </div>
          <button
            data-testid="toggle-bot-btn"
            onClick={onToggle}
            className="flex items-center gap-2 px-3.5 py-2 border border-[#232528] rounded-sm text-xs font-num font-semibold hover:border-[#14F195] hover:text-[#14F195] transition-colors"
          >
            {state?.running ? <Pause size={14} /> : <Play size={14} />}
            {state?.running ? "PAUSE" : "SCOUT"}
          </button>
          <button
            data-testid="restart-btn"
            onClick={onRestart}
            className="flex items-center gap-2 px-3.5 py-2 border border-[#232528] rounded-sm text-xs font-num font-semibold hover:border-[#FF3B30] hover:text-[#FF3B30] transition-colors"
          >
            <RotateCcw size={14} /> RESET $20
          </button>
        </div>
      </div>
    </header>
  );
};

/* ================= STAT TILE ================= */
const Stat = ({ label, children, testid, accent }) => (
  <div className="panel px-4 py-3 rounded-sm" data-testid={testid}>
    <div className="font-num text-[10px] uppercase tracking-widest text-[#8A8F98]">{label}</div>
    <div className={`font-num text-xl mt-1.5 ${accent || ""}`}>{children}</div>
  </div>
);

/* ================= WALLET / STATS ROW ================= */
const StatsRow = ({ state, trades }) => {
  const pnl = state?.total_pnl_usd ?? 0;
  const up = pnl >= 0;
  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2 lg:gap-3">
      <Stat label="Paper Equity" testid="stat-equity">
        <Flash value={state?.equity_usd ?? 0} format={fmtUsd} />
      </Stat>
      <Stat label="Cash" testid="stat-cash">
        <Flash value={state?.paper_balance_usd ?? 0} format={fmtUsd} className="text-[#8A8F98]" />
      </Stat>
      <Stat label="Total P&L" testid="stat-pnl" accent={up ? "text-[#14F195]" : "text-[#FF3B30]"}>
        {fmtUsd(pnl)} <span className="text-sm">({fmtPct(state?.total_pnl_pct)})</span>
      </Stat>
      <Stat label="Open Positions" testid="stat-open">{state?.open_positions ?? 0}</Stat>
      <Stat label="Win Rate" testid="stat-winrate" accent="text-[#14F195]">
        {trades?.win_rate ?? 0}%
      </Stat>
      <Stat label="Realized (24h)" testid="stat-realized"
        accent={(trades?.realized_pnl_usd ?? 0) >= 0 ? "text-[#14F195]" : "text-[#FF3B30]"}>
        {fmtUsd(trades?.realized_pnl_usd ?? 0)}
      </Stat>
    </div>
  );
};

/* ================= SOCIAL ICONS ================= */
const Socials = ({ s }) => (
  <div className="flex items-center gap-1.5">
    {s.twitter && <a href={s.twitter} target="_blank" rel="noreferrer" className="text-[#8A8F98] hover:text-white"><Twitter size={13} /></a>}
    {s.telegram && <a href={s.telegram} target="_blank" rel="noreferrer" className="text-[#8A8F98] hover:text-white"><Send size={13} /></a>}
    {s.website && <a href={s.website} target="_blank" rel="noreferrer" className="text-[#8A8F98] hover:text-white"><Globe size={13} /></a>}
    {!s.twitter && !s.telegram && !s.website && <span className="text-[#4a4e54] font-num text-[10px]">none</span>}
  </div>
);

/* ================= SCANNER ================= */
const Scanner = ({ coins, copy, copied }) => {
  const [filter, setFilter] = useState("all");
  const shown = coins.filter((c) => {
    if (filter === "eligible") return c.eligible;
    if (filter === "new") return c.age_min <= 60;
    return true;
  });
  const tabs = [["all", "ALL"], ["eligible", "BOT ELIGIBLE"], ["new", "NEW <1H"]];
  return (
    <div className="panel rounded-sm flex flex-col h-full" data-testid="scanner-panel">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#232528]">
        <div className="flex items-center gap-2">
          <Radio size={15} className="text-[#14F195]" />
          <span className="font-head text-sm">LIVE SCANNER</span>
          <span className="font-num text-[10px] text-[#8A8F98]">{shown.length} coins</span>
        </div>
        <div className="flex gap-1">
          {tabs.map(([k, lbl]) => (
            <button key={k} data-testid={`scanner-tab-${k}`} onClick={() => setFilter(k)}
              className={`px-2.5 py-1 font-num text-[10px] rounded-sm border transition-colors ${
                filter === k ? "border-[#14F195] text-[#14F195]" : "border-[#232528] text-[#8A8F98] hover:text-white"
              }`}>{lbl}</button>
          ))}
        </div>
      </div>
      <div className="overflow-auto flex-1" style={{ maxHeight: "560px" }}>
        <table className="w-full border-collapse">
          <thead className="sticky top-0 bg-[#111316] z-10">
            <tr className="font-num text-[10px] uppercase text-[#8A8F98] text-left">
              <th className="px-4 py-2 font-medium">Coin</th>
              <th className="px-2 py-2 font-medium">CA</th>
              <th className="px-2 py-2 font-medium">Social</th>
              <th className="px-2 py-2 font-medium">Dev</th>
              <th className="px-2 py-2 font-medium text-right">Mcap</th>
              <th className="px-2 py-2 font-medium text-right">Chg</th>
              <th className="px-2 py-2 font-medium text-right">Vol</th>
              <th className="px-2 py-2 font-medium text-right">Fees ◎</th>
              <th className="px-2 py-2 font-medium text-right">Hldrs</th>
              <th className="px-2 py-2 font-medium text-right">Age</th>
              <th className="px-3 py-2 font-medium text-right">Trend</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((c) => (
              <tr key={c.mint} data-testid={`coin-row-${c.mint}`}
                className={`border-t border-[#1c1e21] hover:bg-white/[0.02] ${c.held ? "bg-[#14F195]/[0.04]" : ""}`}>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2">
                    {c.eligible && <span title="bot eligible" className="w-1.5 h-1.5 rounded-full bg-[#14F195]" />}
                    <div>
                      <div className="font-num text-xs font-semibold flex items-center gap-1.5">
                        {c.symbol}
                        {c.source === "live" && <span className="text-[8px] px-1 py-0.5 bg-[#9945FF]/20 text-[#b98bff] rounded-sm">LIVE</span>}
                        {c.held && <span className="text-[8px] px-1 py-0.5 bg-[#14F195]/20 text-[#14F195] rounded-sm">HOLDING</span>}
                      </div>
                      <div className="text-[10px] text-[#8A8F98] truncate max-w-[110px]">{c.name}</div>
                    </div>
                  </div>
                </td>
                <td className="px-2 py-2.5">
                  <button data-testid={`copy-ca-${c.mint}`} onClick={() => copy(c.mint)}
                    className="flex items-center gap-1 font-num text-[10px] text-[#8A8F98] hover:text-white">
                    {shortCa(c.mint)}
                    {copied === c.mint ? <Check size={11} className="text-[#14F195]" /> : <Copy size={11} />}
                  </button>
                </td>
                <td className="px-2 py-2.5"><Socials s={c.socials} /></td>
                <td className="px-2 py-2.5">
                  {!c.dev_checked ? (
                    <span className="font-num text-[9px] px-1.5 py-0.5 rounded-sm bg-white/5 text-[#8A8F98]">?</span>
                  ) : c.dev_sold ? (
                    <span data-testid={`dev-sold-${c.mint}`} className="font-num text-[9px] px-1.5 py-0.5 rounded-sm bg-[#14F195]/15 text-[#14F195]">SOLD</span>
                  ) : (
                    <span className="font-num text-[9px] px-1.5 py-0.5 rounded-sm bg-[#FF3B30]/15 text-[#FF3B30]">HOLD</span>
                  )}
                </td>
                <td className="px-2 py-2.5 text-right font-num text-xs">{fmtMcap(c.market_cap_usd)}</td>
                <td className={`px-2 py-2.5 text-right font-num text-xs ${c.mcap_growth_pct >= 0 ? "text-[#14F195]" : "text-[#FF3B30]"}`}>
                  {fmtPct(c.mcap_growth_pct)}
                </td>
                <td className="px-2 py-2.5 text-right font-num text-xs text-[#8A8F98]">{fmtMcap(c.volume_24h_usd)}</td>
                <td className={`px-2 py-2.5 text-right font-num text-xs ${c.global_fees_paid_sol >= 0.5 ? "text-white" : "text-[#4a4e54]"}`}>
                  {c.global_fees_paid_sol.toFixed(2)}
                </td>
                <td className={`px-2 py-2.5 text-right font-num text-xs ${c.holders >= 10 ? "text-white" : "text-[#4a4e54]"}`}>
                  {c.holders}
                </td>
                <td className="px-2 py-2.5 text-right font-num text-[10px] text-[#8A8F98]">
                  {c.age_min < 60 ? `${c.age_min.toFixed(0)}m` : `${(c.age_min / 60).toFixed(1)}h`}
                </td>
                <td className="px-3 py-2.5 text-right">
                  <div className="inline-block"><Sparkline data={c.history} color="auto" /></div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};

/* ================= AI DECISIONS ================= */
const Decisions = ({ decisions }) => (
  <div className="panel rounded-sm flex flex-col" data-testid="decisions-panel">
    <div className="flex items-center gap-2 px-4 py-3 border-b border-[#232528]">
      <Bot size={15} className="text-[#9945FF]" />
      <span className="font-head text-sm">AI DECISIONS</span>
    </div>
    <div className="overflow-auto" style={{ maxHeight: "300px" }}>
      {decisions.length === 0 && (
        <div className="px-4 py-6 font-num text-[11px] text-[#8A8F98]">Scanning market for signals…</div>
      )}
      {decisions.map((d) => (
        <div key={d.id} className="row-in px-4 py-2.5 border-t border-[#1c1e21]">
          <div className="flex items-center gap-2">
            <span className={`font-num text-[10px] px-1.5 py-0.5 rounded-sm font-semibold ${
              d.action === "BUY" ? "bg-[#14F195]/15 text-[#14F195]" : "bg-[#FF3B30]/15 text-[#FF3B30]"
            }`}>{d.action}</span>
            <span className="font-num text-xs font-semibold">{d.symbol}</span>
            <span className="font-num text-[10px] text-[#8A8F98] ml-auto">
              {new Date(d.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
            </span>
          </div>
          <div className="font-num text-[10px] text-[#8A8F98] mt-1">{d.reason}</div>
        </div>
      ))}
    </div>
  </div>
);

/* ================= SCOUTED WALLETS ================= */
const Wallets = ({ wallets, copy }) => (
  <div className="panel rounded-sm flex flex-col" data-testid="wallets-panel">
    <div className="flex items-center gap-2 px-4 py-3 border-b border-[#232528]">
      <Crosshair size={15} className="text-[#14F195]" />
      <span className="font-head text-sm">SCOUTED WALLETS</span>
      <span className="font-num text-[10px] text-[#8A8F98]">copy-trade radar</span>
    </div>
    <div className="overflow-auto" style={{ maxHeight: "300px" }}>
      {wallets.map((w) => (
        <div key={w.id} className="px-4 py-2.5 border-t border-[#1c1e21] flex items-center gap-3">
          <div className="w-7 h-7 rounded-sm bg-[#9945FF]/20 grid place-items-center font-num text-[10px] text-[#b98bff]">
            {w.handle.slice(0, 2).toUpperCase()}
          </div>
          <div className="min-w-0">
            <div className="font-num text-xs font-semibold flex items-center gap-2">
              {w.handle}
              <button onClick={() => copy(w.address, "Wallet address")} className="text-[#8A8F98] hover:text-white">
                <Copy size={10} />
              </button>
            </div>
            <div className="font-num text-[10px] text-[#8A8F98]">
              WR {w.win_rate}% · +{w.pnl_sol}◎
            </div>
          </div>
          <div className="ml-auto text-right">
            {w.last_buy ? (
              <div className="font-num text-[10px] text-[#14F195] flex items-center gap-1 justify-end">
                <ArrowUpRight size={11} /> aped {w.last_buy.symbol}
              </div>
            ) : (
              <span className="font-num text-[10px] text-[#4a4e54]">idle</span>
            )}
          </div>
        </div>
      ))}
    </div>
  </div>
);

/* ================= POSITIONS + TRADES ================= */
const PositionsAndTrades = ({ positions, trades, copy, isReal, onSell }) => {
  const [tab, setTab] = useState("positions");
  return (
    <div className="panel rounded-sm" data-testid="ledger-panel">
      <div className="flex items-center gap-5 px-4 py-3 border-b border-[#232528]">
        <button data-testid="tab-positions" onClick={() => setTab("positions")}
          className={`font-head text-sm pb-1 ${tab === "positions" ? "tab-active" : "text-[#8A8F98]"}`}>
          OPEN POSITIONS ({positions.length})
        </button>
        <button data-testid="tab-history" onClick={() => setTab("history")}
          className={`font-head text-sm pb-1 ${tab === "history" ? "tab-active" : "text-[#8A8F98]"}`}>
          TRADE HISTORY 24H ({trades.length})
        </button>
      </div>
      <div className="overflow-auto" style={{ maxHeight: "340px" }}>
        {tab === "positions" ? (
          <table className="w-full">
            <thead className="sticky top-0 bg-[#111316]">
              <tr className="font-num text-[10px] uppercase text-[#8A8F98] text-left">
                <th className="px-4 py-2 font-medium">Coin</th>
                <th className="px-2 py-2 font-medium text-right">Entry</th>
                <th className="px-2 py-2 font-medium text-right">Now</th>
                <th className="px-2 py-2 font-medium text-right">Size</th>
                <th className="px-2 py-2 font-medium text-right">Value</th>
                <th className="px-4 py-2 font-medium text-right">P&L</th>
                {isReal && <th className="px-3 py-2 font-medium text-right">Action</th>}
              </tr>
            </thead>
            <tbody>
              {positions.length === 0 && (
                <tr><td colSpan={isReal ? 7 : 6} className="px-4 py-6 font-num text-[11px] text-[#8A8F98]">No open positions. Bot is scouting…</td></tr>
              )}
              {positions.map((p) => (
                <tr key={p.id} data-testid={`position-${p.mint}`} className="border-t border-[#1c1e21]">
                  <td className="px-4 py-2.5">
                    <div className="font-num text-xs font-semibold flex items-center gap-1.5">
                      {p.symbol}
                      {p.explorer && <a href={p.explorer} target="_blank" rel="noreferrer" className="text-[#9945FF]"><ArrowUpRight size={11} /></a>}
                    </div>
                    <div className="text-[10px] text-[#8A8F98] truncate max-w-[120px]">{p.name}</div>
                  </td>
                  <td className="px-2 py-2.5 text-right font-num text-[10px] text-[#8A8F98]">${p.entry_price.toExponential(2)}</td>
                  <td className="px-2 py-2.5 text-right font-num text-[10px]">${p.current_price.toExponential(2)}</td>
                  <td className="px-2 py-2.5 text-right font-num text-[10px]">{fmtSol(p.size_sol)}</td>
                  <td className="px-2 py-2.5 text-right font-num text-xs">{fmtUsd(p.value_usd)}</td>
                  <td className={`px-4 py-2.5 text-right font-num text-xs ${p.pnl_usd >= 0 ? "text-[#14F195]" : "text-[#FF3B30]"}`}>
                    {fmtUsd(p.pnl_usd)} <span className="text-[10px]">({fmtPct(p.pnl_pct)})</span>
                  </td>
                  {isReal && (
                    <td className="px-3 py-2.5 text-right">
                      <button data-testid={`sell-${p.mint}`} onClick={() => onSell(p.mint)}
                        className="font-num text-[10px] px-2.5 py-1 rounded-sm bg-[#FF3B30]/15 text-[#FF3B30] hover:bg-[#FF3B30] hover:text-white transition-colors">
                        SELL
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <table className="w-full">
            <thead className="sticky top-0 bg-[#111316]">
              <tr className="font-num text-[10px] uppercase text-[#8A8F98] text-left">
                <th className="px-4 py-2 font-medium">Time</th>
                <th className="px-2 py-2 font-medium">Side</th>
                <th className="px-2 py-2 font-medium">Coin</th>
                <th className="px-2 py-2 font-medium">CA</th>
                <th className="px-2 py-2 font-medium text-right">Amount</th>
                <th className="px-4 py-2 font-medium text-right">P&L</th>
              </tr>
            </thead>
            <tbody>
              {trades.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-6 font-num text-[11px] text-[#8A8F98]">No trades yet.</td></tr>
              )}
              {trades.map((t) => (
                <tr key={t.id} data-testid={`trade-${t.id}`} className="border-t border-[#1c1e21]">
                  <td className="px-4 py-2.5 font-num text-[10px] text-[#8A8F98]">
                    {new Date(t.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
                  </td>
                  <td className="px-2 py-2.5">
                    <span className={`font-num text-[10px] px-1.5 py-0.5 rounded-sm font-semibold ${
                      t.side === "BUY" ? "bg-[#14F195]/15 text-[#14F195]" : "bg-[#FF3B30]/15 text-[#FF3B30]"
                    }`}>{t.side}</span>
                  </td>
                  <td className="px-2 py-2.5 font-num text-xs font-semibold">
                    <span className="flex items-center gap-1">
                      {t.symbol}
                      {t.explorer && <a href={t.explorer} target="_blank" rel="noreferrer" className="text-[#9945FF]"><ArrowUpRight size={11} /></a>}
                    </span>
                  </td>
                  <td className="px-2 py-2.5">
                    <button onClick={() => copy(t.mint)} className="flex items-center gap-1 font-num text-[10px] text-[#8A8F98] hover:text-white">
                      {shortCa(t.mint)} <Copy size={10} />
                    </button>
                  </td>
                  <td className="px-2 py-2.5 text-right font-num text-[10px]">{fmtUsd(t.usd)}</td>
                  <td className={`px-4 py-2.5 text-right font-num text-xs ${
                    t.side === "SELL" ? (t.pnl_usd >= 0 ? "text-[#14F195]" : "text-[#FF3B30]") : "text-[#8A8F98]"
                  }`}>
                    {t.side === "SELL" ? `${fmtUsd(t.pnl_usd)} (${fmtPct(t.pnl_pct)})` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

/* ================= REAL WALLET PANEL ================= */
const RealWallet = ({ state, copy, refetch }) => {
  const [addr, setAddr] = useState("");
  const [amt, setAmt] = useState("");
  const configured = state?.real_configured;
  const doWithdraw = async () => {
    if (!addr || !amt) return toast.error("Enter address and amount");
    try {
      const r = await api.withdraw(addr, parseFloat(amt));
      if (r.simulated) toast.success("Withdrawal (simulated)", { description: r.message });
      else toast.success("SOL sent on-chain", { description: `tx ${shortCa(r.signature)}` });
      setAddr(""); setAmt(""); refetch();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Withdraw failed");
    }
  };
  const doDeposit = async () => {
    try { await api.depositSim(0.5); toast.success("Simulated 0.5 ◎ deposit"); refetch(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Not available on live wallet"); }
  };
  return (
    <div className="panel rounded-sm border-[#FF3B30]/40" data-testid="real-wallet-panel">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#FF3B30]/30 bg-[#FF3B30]/[0.05]">
        <AlertTriangle size={15} className="text-[#FF3B30]" />
        <span className="font-head text-sm text-[#FF3B30]">
          {configured ? "REAL WALLET — LIVE" : "REAL WALLET — SIMULATION SHELL"}
        </span>
        {configured && <span className="live-dot w-2 h-2 rounded-full bg-[#FF3B30] ml-auto" />}
      </div>
      <div className="p-4 space-y-4">
        <div className="font-num text-[10px] text-[#8A8F98] leading-relaxed border border-[#FF3B30]/20 bg-[#FF3B30]/[0.04] p-3 rounded-sm">
          {configured
            ? "⚠ LIVE trading is enabled. Real SOL moves on Solana mainnet. When Real mode + Scouting are ON the bot auto-buys/sells 0.01 ◎ at a time on verified coins."
            : "⚠ Real on-chain trading is NOT enabled. No real SOL moves — this demonstrates the flows safely as a simulation."}
        </div>
        <div>
          <div className="font-num text-[10px] uppercase tracking-widest text-[#8A8F98]">Real Balance {configured && <span className="text-[#14F195]">· on-chain</span>}</div>
          <div className="font-num text-3xl mt-1">{fmtSol(state?.real_balance_sol)}</div>
          <div className="font-num text-xs text-[#8A8F98]">≈ {fmtUsd((state?.real_balance_sol || 0) * (state?.sol_usd || 0))}</div>
        </div>
        <div>
          <div className="font-num text-[10px] uppercase tracking-widest text-[#8A8F98] mb-1">
            {configured ? "Wallet Address (send SOL here to fund)" : "Deposit Address"}
          </div>
          <button data-testid="copy-deposit-addr" onClick={() => copy(state?.real_deposit_address, "Wallet address")}
            className="w-full flex items-center justify-between gap-2 border border-[#232528] rounded-sm px-3 py-2 font-num text-[11px] text-left hover:border-[#9945FF]">
            <span className="truncate">{state?.real_deposit_address}</span>
            <Copy size={13} className="shrink-0 text-[#8A8F98]" />
          </button>
          {configured ? (
            <a href={`https://solscan.io/account/${state?.real_deposit_address}`} target="_blank" rel="noreferrer"
              className="mt-2 inline-block font-num text-[10px] text-[#9945FF] hover:underline">view on solscan ↗</a>
          ) : (
            <button data-testid="sim-deposit-btn" onClick={doDeposit}
              className="mt-2 font-num text-[10px] text-[#9945FF] hover:underline">+ simulate 0.5 ◎ deposit</button>
          )}
        </div>
        <div className="space-y-2">
          <div className="font-num text-[10px] uppercase tracking-widest text-[#8A8F98]">Withdraw To Any Wallet</div>
          <input data-testid="withdraw-address" value={addr} onChange={(e) => setAddr(e.target.value)}
            placeholder="destination wallet address"
            className="w-full bg-[#0B0C0E] border border-[#232528] rounded-sm px-3 py-2 font-num text-xs outline-none focus:border-[#FF3B30]" />
          <div className="flex gap-2">
            <input data-testid="withdraw-amount" value={amt} onChange={(e) => setAmt(e.target.value)}
              type="number" step="0.01" placeholder="amount ◎"
              className="flex-1 bg-[#0B0C0E] border border-[#232528] rounded-sm px-3 py-2 font-num text-xs outline-none focus:border-[#FF3B30]" />
            <button data-testid="withdraw-btn" onClick={doWithdraw}
              className="px-4 py-2 bg-[#FF3B30] text-white font-num text-xs font-semibold rounded-sm hover:bg-[#ff5147]">
              SEND
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

/* ================= STRATEGY TUNER + GUARDRAILS ================= */
const NumField = ({ label, value, onChange, step = "1", suffix, testid }) => (
  <div>
    <div className="font-num text-[9px] uppercase tracking-wider text-[#8A8F98] mb-1">{label}</div>
    <div className="flex items-center border border-[#232528] rounded-sm bg-[#0B0C0E] focus-within:border-[#9945FF]">
      <input data-testid={testid} type="number" step={step} value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full bg-transparent px-2.5 py-1.5 font-num text-xs outline-none" />
      {suffix && <span className="px-2 font-num text-[10px] text-[#8A8F98]">{suffix}</span>}
    </div>
  </div>
);

const StrategyPanel = ({ state, refetch }) => {
  const s = state?.strategy;
  const g = state?.guardrails;
  const [tp, setTp] = useState(25);
  const [sl, setSl] = useState(15);
  const [size, setSize] = useState(0.01);
  const [maxPos, setMaxPos] = useState(5);
  const [minMcap, setMinMcap] = useState(3000);
  const [minHolders, setMinHolders] = useState(10);
  const [gEnabled, setGEnabled] = useState(true);
  const [dayLimit, setDayLimit] = useState(0.05);
  const [cap, setCap] = useState(0.3);
  const seeded = useRef(false);

  useEffect(() => {
    if (s && g && !seeded.current) {
      setTp((s.take_profit * 100).toFixed(0));
      setSl((Math.abs(s.stop_loss) * 100).toFixed(0));
      setSize(s.trade_size_sol);
      setMaxPos(s.max_positions);
      setMinMcap(s.min_mcap_usd ?? 3000);
      setMinHolders(s.min_holders ?? 10);
      setGEnabled(g.enabled);
      setDayLimit(g.daily_loss_limit_sol);
      setCap(g.total_spend_cap_sol);
      seeded.current = true;
    }
  }, [s, g]);

  const save = async () => {
    try {
      await api.setStrategy({
        take_profit: parseFloat(tp) / 100,
        stop_loss: parseFloat(sl) / 100,
        trade_size_sol: parseFloat(size),
        max_positions: parseInt(maxPos, 10),
        min_mcap_usd: parseFloat(minMcap),
        min_holders: parseInt(minHolders, 10),
      });
      await api.setGuardrails({
        enabled: gEnabled,
        daily_loss_limit_sol: parseFloat(dayLimit),
        total_spend_cap_sol: parseFloat(cap),
      });
      toast.success("Strategy & limits saved");
      refetch();
    } catch (e) {
      toast.error("Save failed");
    }
  };

  const spent = state?.total_spent_sol || 0;
  const lossToday = state?.loss_today_sol || 0;
  const capPct = cap > 0 ? Math.min(100, (spent / cap) * 100) : 0;

  return (
    <div className="panel rounded-sm" data-testid="strategy-panel">
      <div className="flex items-center gap-2 px-4 py-3 border-b border-[#232528]">
        <Sliders size={15} className="text-[#9945FF]" />
        <span className="font-head text-sm">STRATEGY & LIMITS</span>
      </div>
      <div className="p-4 space-y-4">
        <div className="grid grid-cols-2 gap-2.5">
          <NumField label="Take Profit" value={tp} onChange={setTp} suffix="%" testid="tune-tp" />
          <NumField label="Stop Loss" value={sl} onChange={setSl} suffix="%" testid="tune-sl" />
          <NumField label="Trade Size" value={size} onChange={setSize} step="0.001" suffix="◎" testid="tune-size" />
          <NumField label="Max Positions" value={maxPos} onChange={setMaxPos} testid="tune-maxpos" />
          <NumField label="Min Market Cap" value={minMcap} onChange={setMinMcap} step="500" suffix="$" testid="tune-minmcap" />
          <NumField label="Min Holders" value={minHolders} onChange={setMinHolders} testid="tune-minholders" />
        </div>

        <div className="border-t border-[#232528] pt-3 space-y-2.5">
          <label className="flex items-center justify-between cursor-pointer">
            <span className="font-num text-[10px] uppercase tracking-wider text-[#8A8F98]">Spend Guardrails</span>
            <button data-testid="toggle-guardrails" onClick={() => setGEnabled(!gEnabled)}
              className={`w-9 h-5 rounded-full transition-colors relative ${gEnabled ? "bg-[#14F195]" : "bg-[#232528]"}`}>
              <span className={`absolute top-0.5 w-4 h-4 bg-black rounded-full transition-all ${gEnabled ? "left-[18px]" : "left-0.5"}`} />
            </button>
          </label>
          <div className="grid grid-cols-2 gap-2.5">
            <NumField label="Daily Loss Limit" value={dayLimit} onChange={setDayLimit} step="0.01" suffix="◎" testid="tune-dayloss" />
            <NumField label="Total Spend Cap" value={cap} onChange={setCap} step="0.01" suffix="◎" testid="tune-cap" />
          </div>
          <div>
            <div className="flex items-center justify-between font-num text-[10px] text-[#8A8F98]">
              <span>Spent {spent.toFixed(3)}◎ / {Number(cap).toFixed(2)}◎</span>
              <span className={lossToday > 0 ? "text-[#FF3B30]" : ""}>loss today {lossToday.toFixed(3)}◎</span>
            </div>
            <div className="h-1.5 bg-[#232528] rounded-full mt-1 overflow-hidden">
              <div className="h-full bg-[#9945FF]" style={{ width: `${capPct}%`, transition: "width 0.4s ease" }} />
            </div>
          </div>
        </div>

        <button data-testid="save-strategy-btn" onClick={save}
          className="w-full py-2 bg-[#9945FF] text-white font-num text-xs font-semibold rounded-sm hover:bg-[#a95cff] transition-colors">
          SAVE STRATEGY
        </button>

        <div className="grid grid-cols-3 gap-2 border-t border-[#232528] pt-3 font-num text-[10px]">
          <div><span className="text-[#8A8F98] block">Slippage</span>{state?.settings?.slippage_pct}%</div>
          <div><span className="text-[#8A8F98] block">Priority</span>{state?.settings?.priority_fee}</div>
          <div><span className="text-[#8A8F98] block">Bribe</span>{state?.settings?.bribe_fee}</div>
        </div>
      </div>
    </div>
  );
};

/* ================= APP ================= */
function App() {
  const qc = useQueryClient();
  const { copied, copy } = useCopy();

  const state = useQuery({ queryKey: ["state"], queryFn: api.botState, refetchInterval: 3000 });
  const coins = useQuery({ queryKey: ["coins"], queryFn: () => api.coins(), refetchInterval: 3000 });
  const positions = useQuery({ queryKey: ["positions"], queryFn: api.positions, refetchInterval: 3000 });
  const trades = useQuery({ queryKey: ["trades"], queryFn: () => api.trades(24), refetchInterval: 4000 });
  const decisions = useQuery({ queryKey: ["decisions"], queryFn: api.decisions, refetchInterval: 3000 });
  const wallets = useQuery({ queryKey: ["wallets"], queryFn: api.wallets, refetchInterval: 5000 });

  const refetchAll = () => ["state", "coins", "positions", "trades", "decisions", "wallets"]
    .forEach((k) => qc.invalidateQueries({ queryKey: [k] }));

  const onToggle = async () => {
    const r = await api.toggle();
    toast[r.running ? "success" : "message"](r.running ? "Bot scouting" : "Bot paused");
    refetchAll();
  };
  const onMode = async (m) => {
    await api.setMode(m);
    const live = st?.real_configured;
    toast[m === "real" ? "error" : "success"](`Switched to ${m.toUpperCase()} mode`,
      m === "real"
        ? { description: live ? "LIVE — real SOL will move when scouting" : "Simulation shell — no real funds move" }
        : undefined);
    refetchAll();
  };
  const onRestart = async () => {
    await api.restart();
    toast.success("Reset to $20.00", { description: "Positions & history cleared" });
    refetchAll();
  };
  const onRealSell = async (mint) => {
    toast.message("Submitting on-chain sell…");
    try {
      await api.realSell(mint);
      toast.success("Sell submitted", { description: "Confirming on-chain" });
      refetchAll();
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Sell failed");
    }
  };

  const st = state.data;
  const isReal = st?.mode === "real";

  return (
    <div className="App scanlines min-h-screen bg-[#0B0C0E] relative">
      <Toaster theme="dark" position="top-right" toastOptions={{ style: { fontFamily: "JetBrains Mono, monospace", background: "#111316", border: "1px solid #232528", color: "#fff" } }} />
      <Header state={st} onToggle={onToggle} onMode={onMode} onRestart={onRestart} />

      <main className="px-4 lg:px-6 py-4 space-y-3 relative z-10 max-w-[1600px]">
        {isReal && st?.real_configured && (
          <div className="panel rounded-sm border-[#FF3B30]/50 bg-[#FF3B30]/[0.06] px-4 py-2.5 flex items-center gap-3" data-testid="live-banner">
            <AlertTriangle size={15} className="text-[#FF3B30]" />
            <span className="font-num text-xs text-[#FF3B30]">
              LIVE TRADING — real SOL on Solana mainnet. Bot {st?.running ? "is auto-trading now" : "is PAUSED (hit SCOUT to start)"}. Balance {fmtSol(st?.real_balance_sol)}.
            </span>
          </div>
        )}
        <StatsRow state={st} trades={trades.data} />

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
          <div className="lg:col-span-8">
            <Scanner coins={coins.data?.coins || []} copy={copy} copied={copied} />
          </div>
          <div className="lg:col-span-4 space-y-3">
            {isReal && <RealWallet state={st} copy={copy} refetch={refetchAll} />}
            <StrategyPanel state={st} refetch={refetchAll} />
            <Decisions decisions={decisions.data?.decisions || []} />
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
          <div className="lg:col-span-8">
            <PositionsAndTrades
              positions={positions.data?.positions || []}
              trades={trades.data?.trades || []}
              copy={copy}
              isReal={isReal}
              onSell={onRealSell}
            />
          </div>
          <div className="lg:col-span-4">
            <Wallets wallets={wallets.data?.wallets || []} copy={copy} />
          </div>
        </div>

        <footer className="font-num text-[10px] text-[#4a4e54] py-4 flex items-center gap-2">
          <Flame size={11} /> PumpScout — paper trading simulation on real pump.fun coin data · educational use only
        </footer>
      </main>
    </div>
  );
}

export default App;
