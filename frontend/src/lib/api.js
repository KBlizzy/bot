import axios from "axios";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export const api = {
  coins: (filter = "all") => axios.get(`${API}/coins`, { params: { filter } }).then((r) => r.data),
  botState: () => axios.get(`${API}/bot/state`).then((r) => r.data),
  positions: () => axios.get(`${API}/positions`).then((r) => r.data),
  trades: (hours = 24) => axios.get(`${API}/trades`, { params: { hours } }).then((r) => r.data),
  decisions: () => axios.get(`${API}/decisions`).then((r) => r.data),
  wallets: () => axios.get(`${API}/wallets`).then((r) => r.data),
  toggle: () => axios.post(`${API}/bot/toggle`).then((r) => r.data),
  setMode: (mode) => axios.post(`${API}/bot/mode`, { mode }).then((r) => r.data),
  restart: () => axios.post(`${API}/bot/restart`).then((r) => r.data),
  withdraw: (address, amount_sol) => axios.post(`${API}/wallet/withdraw`, { address, amount_sol }).then((r) => r.data),
  depositSim: (amount_sol) => axios.post(`${API}/wallet/deposit_sim`, { address: "self", amount_sol }).then((r) => r.data),
  realBuy: (mint) => axios.post(`${API}/real/buy`, { mint }).then((r) => r.data),
  realSell: (mint) => axios.post(`${API}/real/sell`, { mint }).then((r) => r.data),
  setStrategy: (s) => axios.post(`${API}/bot/strategy`, s).then((r) => r.data),
  setGuardrails: (g) => axios.post(`${API}/bot/guardrails`, g).then((r) => r.data),
};

export const fmtUsd = (n) =>
  n == null ? "—" : "$" + Number(n).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const fmtMcap = (n) => {
  if (n == null) return "—";
  if (n >= 1e6) return "$" + (n / 1e6).toFixed(2) + "M";
  if (n >= 1e3) return "$" + (n / 1e3).toFixed(1) + "K";
  return "$" + n.toFixed(0);
};

export const fmtPct = (n) => (n == null ? "—" : (n >= 0 ? "+" : "") + n.toFixed(1) + "%");
export const fmtSol = (n) => (n == null ? "—" : Number(n).toFixed(4) + " ◎");
export const shortCa = (a) => (a ? a.slice(0, 4) + "…" + a.slice(-4) : "");
