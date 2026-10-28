"""Snabb forskningsmotor: målvikter -> dagliga portföljavkastningar i SEK efter Avanza-kostnader.

Tidsregel: beslut vid stängning dag t (data till och med t), exekvering vid stängningen på instrumentets nästa
färska dag efter t. Mellan besluten driver vikterna med kurserna. Avkastning dag t använder innehavet efter
exekveringarna vid stängningen dag t-1. Kostnaden dras från kapitalet samma dag som affären.
"""
import numpy as np

from . import config
from . import metrics as M


def cost_vectors(panel):
    """Per instrument: proportionell kostnad per sida (valuta, halv spread, slippage), courtage-andel och minimum i SEK."""
    prop, rate, minfee = [], [], []
    for i in panel.ins:
        r, mn = config.COURTAGE[i.exchange]
        cur = i.currency
        prop.append((config.FX_FEE if cur != "SEK" else 0.0) + i.half_spread + config.SLIPPAGE)
        rate.append(r)
        minfee.append((mn, cur))
    return np.array(prop), np.array(rate), minfee


def run(panel, W, D, mode, start, end, stress=1.0, capital=config.CAPITAL_SEK, tol=0.02, init=None):
    """Kör målvikterna mellan start och end (datumsträngar). Returnerar dict med dagsavkastning, datum m.m."""
    t0 = int(np.searchsorted(panel.cal, np.datetime64(start)))
    t1 = int(np.searchsorted(panel.cal, np.datetime64(end), side="right")) - 1
    N = W.shape[1]
    prop, rate, minfee = cost_vectors(panel)
    # minimicourtage i SEK med växelkursen vid periodens start (förenkling i den snabba motorn)
    fx_min = np.array([mn * (1.0 if cur == "SEK" else panel.fx[cur][t0]) for (mn, cur) in minfee])
    R, F = panel.ret, panel.fresh
    w = np.zeros(N); cash = 1.0; eq = 1.0
    pend = np.full(N, np.nan) if init is None else np.where(init > 0, init, np.nan)   # init: köp vid första färska dag
    rets = np.zeros(t1 - t0 + 1); trades = 0; turnover = 0.0
    hold_days = np.zeros(N); holds = []
    for k, t in enumerate(range(t0, t1 + 1)):
        if k > 0:
            g = w * (1 + R[t])
            tot = g.sum() + cash
            r = tot - 1.0
            w = g / tot; cash = cash / tot
        else:
            r = 0.0
        cost = 0.0
        ex = ~np.isnan(pend) & F[t]
        if ex.any():
            dw = pend[ex] - w[ex]
            a = np.abs(dw)
            traded = a > 1e-9
            if traded.any():
                cap = max(capital * eq * (1 + r), 1e-6)
                fee = np.maximum(rate[ex] * a, fx_min[ex] / cap) * traded + prop[ex] * a
                cost = float(fee.sum()) * stress
                newpos = traded & (w[ex] < 1e-9) & (pend[ex] > 1e-9)
                trades += int(newpos.sum())
                closed = traded & (pend[ex] < 1e-9) & (w[ex] > 1e-9)
                if closed.any():
                    holds.extend(hold_days[ex][closed].tolist())
                turnover += float(a.sum())
                w_ex = w[ex]; w_ex[traded] = pend[ex][traded]; w[ex] = w_ex
                cash -= float(dw[traded].sum())
            pend[ex] = np.nan
        if cost:
            cash -= cost
            cost = min(cost, 1.0)                 # avgifterna kan inte överstiga kapitalet
            r = (1 + r) * (1 - cost) - 1          # kostnaden är en andel av kapitalet efter dagens avkastning
            tot = w.sum() + cash
            if tot <= 1e-12:                      # kapitalet är slut: inga fler affärer
                rets[k:] = 0.0; rets[k] = -1.0 if eq > 0 else 0.0
                break
            w = w / tot; cash = cash / tot
        rets[k] = r
        eq *= 1 + r
        hold_days = np.where(w > 1e-9, hold_days + 1, 0)
        if D[t] and t < t1:
            tw = W[t]
            if mode == "changes":
                chg = (tw > 1e-12) != (w > 1e-9)
                pend = np.where(chg, tw, pend)
            else:
                drift = np.abs(tw - w)
                need = (drift > tol) | ((tw > 1e-12) != (w > 1e-9))
                pend = np.where(need, tw, np.nan)
    dates = panel.cal[t0:t1 + 1]
    return {"r": rets, "dates": dates, "trades": trades, "turnover": turnover,
            "avg_hold_days": float(np.mean(holds)) if holds else None,
            "summary": M.summary(rets, trades, turnover)}


def benchmark(panel, cols, start, end):
    """Likaviktat köp och behåll av universumet (köp vid periodens första dag, månadsvis ombalansering)."""
    T, N = panel.close.shape
    mask = np.zeros(N, bool); mask[cols] = True
    m = panel.cal.astype("datetime64[M]")
    D = np.concatenate([m[1:] != m[:-1], [True]])
    W = np.zeros((T, N))
    for t in np.nonzero(D)[0]:
        idx = np.nonzero(panel.avail[t] & mask)[0]
        if len(idx):
            W[t, idx] = 1.0 / len(idx)
    t0 = int(np.searchsorted(panel.cal, np.datetime64(start)))
    idx = np.nonzero(panel.avail[t0] & mask)[0]
    init = np.zeros(N)
    if len(idx):
        init[idx] = 1.0 / len(idx)
    return run(panel, W, D, "rebalance", start, end, init=init)
