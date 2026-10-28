"""Champion/Challenger och produktionsexport.

- production/champion.json: den strategi som appen kör (i dag den frysta "SwingEdge med guld", version 2.2).
  En ny champion skrivs bara med `approve()` och ett namngivet manuellt godkännande; tidigare versioner sparas
  i production/history/ så att ett byte kan återställas.
- En challenger från forskningsmotorn kan bara föreslås (`propose()`); den ändrar aldrig champion.json.
- `incumbent_targets()` uttrycker appens nuvarande strategi i motorns termer för jämförelser.
"""
import datetime as dt
import json
import os
import shutil

import numpy as np

from . import config
from . import strategies as S

INCUMBENT = {"name": "SwingEdge med guld (app 2.2)", "rules": [
    "Bitcoin Trend 20 %: Bitcoin Tracker One när BTC-USD stängt över SMA150 tre dagar i rad, sälj efter tre under.",
    "Lika vikt 40 %: XACT OMXS30, SXR8, Bitcoin Tracker One och Xetra-Gold, 10 % vardera, månadsvis ombalansering.",
    "S&P 500 Trend 40 %: SXR8 när S&P 500 > SMA200 på månadens sista handelsdag."]}


def incumbent_targets(ind):
    """Målvikter för appens strategi på en panel som innehåller bitcoin, omxs30, sp500 och gold."""
    p = ind.p
    ids = p.ids()
    j = {k: ids.index(k) for k in ("bitcoin", "omxs30", "sp500", "gold")}
    T, N = p.close.shape
    btc = S.holding_state({"entry": {"type": "ma_above", "n": 150, "ma": "sma"}, "exit": {"type": "default"}, "filter": None,
                           "confirm": 3}, _OneCol(ind, j["bitcoin"]))[:, 0]
    spc = p.close[:, j["sp500"]]
    m = p.cal.astype("datetime64[M]")
    month_end = np.concatenate([m[1:] != m[:-1], [True]])
    sma = ind.sma(200)[:, j["sp500"]]
    sp_on = np.zeros(T, bool); cur = False
    for t in range(T):
        if month_end[t] and not np.isnan(sma[t]):
            cur = spc[t] > sma[t]
        sp_on[t] = cur
    W = np.zeros((T, N))
    W[:, j["bitcoin"]] = 0.2 * btc + 0.1
    W[:, j["sp500"]] = 0.4 * sp_on + 0.1
    W[:, j["omxs30"]] = 0.1
    W[:, j["gold"]] = 0.1
    W[~p.avail] = 0.0
    change = np.concatenate([[True], btc[1:] != btc[:-1]]) | np.concatenate([[True], sp_on[1:] != sp_on[:-1]])
    D = month_end | change
    return W, D, "rebalance"


class _OneCol:
    """Indikator-vy för en kolumn (för tillståndsmaskinen)."""

    def __init__(self, ind, j):
        self.c = ind.c[:, [j]]
        self.p = type("P", (), {"ins": [ind.p.ins[j]]})()
        self._ind, self._j = ind, j

    def sma(self, n):
        return self._ind.sma(n)[:, [self._j]]

    def ema(self, n):
        return self._ind.ema(n)[:, [self._j]]

    def absdiff_mean(self, n):
        return self._ind.absdiff_mean(n)[:, [self._j]]


def _path(name):
    return os.path.join(config.PRODUCTION, name)


def current():
    p = _path("champion.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def propose(challenger, evidence, round_id):
    """Sparar en challenger för manuell granskning. Ändrar inte champion."""
    os.makedirs(_path("challengers"), exist_ok=True)
    rec = {"round_id": round_id, "proposed_at": dt.datetime.now().isoformat(timespec="seconds"), "spec": challenger,
           "description": S.describe(challenger) if challenger else None, "evidence": evidence,
           "status": "väntar på forward-test och manuellt godkännande",
           "requirements": ["oberoende validering godkänd", "holdout godkänd", "realistiska kostnader",
                            "minst 6 månaders paper trading med resultat i linje med valideringen",
                            "jämförelse med champion på samma perioder", "manuellt godkännande via approve()"]}
    p = _path(f"challengers/{round_id}.json")
    json.dump(rec, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    return p


def approve(round_id, approved_by, paper_trading_months):
    """Gör en challenger till champion. Kräver namngiven godkännare och minst sex månaders paper trading."""
    if not approved_by:
        raise PermissionError("Ett manuellt godkännande med namn krävs.")
    if paper_trading_months < 6:
        raise PermissionError("Minst sex månaders paper trading krävs innan en challenger kan bli champion.")
    ch = json.load(open(_path(f"challengers/{round_id}.json"), encoding="utf-8"))
    os.makedirs(_path("history"), exist_ok=True)
    cur = current()
    if cur:
        shutil.copy(_path("champion.json"), _path(f"history/champion_v{cur['version']}.json"))
    new = {"version": (cur["version"] + 1) if cur else 1, "name": ch["description"], "spec": ch["spec"], "round_id": round_id,
           "approved_by": approved_by, "approved_at": dt.datetime.now().isoformat(timespec="seconds"), "evidence": ch["evidence"]}
    json.dump(new, open(_path("champion.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    return new


def rollback(version):
    src = _path(f"history/champion_v{version}.json")
    shutil.copy(src, _path("champion.json"))
    return current()


def ensure_incumbent():
    """Första körningen: registrera appens nuvarande strategi som champion version 1."""
    os.makedirs(config.PRODUCTION, exist_ok=True)
    if current() is None:
        json.dump({"version": 1, "name": INCUMBENT["name"], "spec": "incumbent", "rules": INCUMBENT["rules"], "round_id": None,
                   "approved_by": "befintlig strategi i appen (fryst 28 okt 2026, tredagarsregel 29 okt 2026)",
                   "approved_at": "2026-10-29", "evidence": "research/archive/borslabbet (in-sample 2015–2026)"},
                  open(_path("champion.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return current()
