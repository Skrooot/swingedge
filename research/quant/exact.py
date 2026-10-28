"""Exakt, händelsestyrd verifieringsmotor: ordrar, fyllnader, hela andelar, kontantkonto i SEK och Avanza-avgifter.

Dagens ordning: (1) bolagshändelser (bara i rå-läge: utdelning till kontot, split ändrar antalet), (2) fyllnad av
väntande ordrar på färska dagar, säljordrar före köpordrar, (3) värdering vid stängning, (4) beslut vid stängning
som blir ordrar till nästa färska dag. Köp begränsas av tillgängliga kontanter; kontot kan inte bli negativt.
"""
import math
from dataclasses import dataclass, field

import numpy as np

from . import config
from . import metrics as M


@dataclass
class Fill:
    t: int
    j: int
    qty: int
    price: float        # i handelsvalutan, inklusive spread och slippage
    fee_sek: float


@dataclass
class Book:
    cash: float
    shares: np.ndarray
    fills: list = field(default_factory=list)


def courtage(notional_cur, exchange, stress=1.0):
    r, mn = config.COURTAGE[exchange]
    return max(r * notional_cur, mn) * stress


def simulate(price, fxr, fresh, W, D, mode, exchanges, currencies, half_spread, t0, t1, capital=config.CAPITAL_SEK,
             stress=1.0, tol=0.02, events=None):
    """price: (T, N) pris i handelsvalutan (NaN = ingen kurs); fxr: (T, N) SEK per valutaenhet.
    events: {t: [(j, "div", belopp per andel i handelsvalutan) | (j, "split", kvot)]} för rå-läge."""
    T, N = price.shape
    book = Book(capital, np.zeros(N, dtype=np.int64))
    pend = {}
    eq = np.zeros(t1 - t0 + 1)
    last = np.full(N, np.nan)
    trades = 0
    for k, t in enumerate(range(t0, t1 + 1)):
        last = np.where(np.isnan(price[t]), last, price[t])
        for (j, kind, x) in (events or {}).get(t, []):
            if kind == "div" and book.shares[j]:
                book.cash += book.shares[j] * x * fxr[t, j]
            elif kind == "split":
                book.shares[j] = int(round(book.shares[j] * x))
        # fyllnader
        ready = [j for j in pend if fresh[t, j] and not np.isnan(price[t, j])]
        value = book.cash + np.nansum(book.shares * np.nan_to_num(last) * fxr[t])
        orders = []
        for j in ready:
            tw = pend.pop(j)
            target = int(math.floor(tw * value / (price[t, j] * fxr[t, j]))) if tw > 0 else 0
            q = target - int(book.shares[j])
            if q:
                orders.append((j, q))
        for j, q in sorted(orders, key=lambda o: o[1]):          # sälj först
            slip = (half_spread[j] + config.SLIPPAGE) * stress
            px = price[t, j] * (1 + slip if q > 0 else 1 - slip)
            notional = abs(q) * px
            fee = courtage(notional, exchanges[j], stress) * fxr[t, j]
            if currencies[j] != "SEK":
                fee += notional * fxr[t, j] * config.FX_FEE * stress
            if q > 0:
                afford = book.cash - fee
                if afford < q * px * fxr[t, j]:
                    q = int(max(0, math.floor((book.cash - fee) / (px * fxr[t, j]))))
                    if q <= 0:
                        continue
                    notional = q * px
                    fee = courtage(notional, exchanges[j], stress) * fxr[t, j] + (notional * fxr[t, j] * config.FX_FEE * stress if currencies[j] != "SEK" else 0)
                    if q * px * fxr[t, j] + fee > book.cash:
                        continue
                if book.shares[j] == 0:
                    trades += 1
            book.cash -= q * px * fxr[t, j] + fee
            book.shares[j] += q
            book.fills.append(Fill(t, j, q, px, fee))
        eq[k] = book.cash + np.nansum(book.shares * np.nan_to_num(last) * fxr[t])
        if D[t] and t < t1:
            value = eq[k]
            wnow = np.where(np.isnan(last), 0, book.shares * np.nan_to_num(last) * fxr[t]) / value
            tw = W[t]
            if mode == "changes":
                for j in np.nonzero((tw > 1e-12) != (wnow > 1e-9))[0]:
                    pend[int(j)] = float(tw[j])
            else:
                pend = {}
                for j in np.nonzero((np.abs(tw - wnow) > tol) | ((tw > 1e-12) != (wnow > 1e-9)))[0]:
                    pend[int(j)] = float(tw[j])
    r = np.zeros(len(eq))
    r[0] = eq[0] / capital - 1
    r[1:] = eq[1:] / eq[:-1] - 1
    return {"r": r, "equity": eq, "book": book, "trades": trades, "summary": M.summary(r, trades)}


def run_panel(panel, W, D, mode, start, end, stress=1.0, capital=config.CAPITAL_SEK):
    """Kör den exakta motorn på panelens produktpriser (justerade, så utdelningar ingår i kursen)."""
    t0 = int(np.searchsorted(panel.cal, np.datetime64(start)))
    t1 = int(np.searchsorted(panel.cal, np.datetime64(end), side="right")) - 1
    T, N = panel.close.shape
    fxr = np.ones((T, N))
    for j, i in enumerate(panel.ins):
        if i.currency != "SEK":
            fxr[:, j] = panel.fx[i.currency]
    price = np.where(panel.avail, panel.price_sek / fxr, np.nan)
    res = simulate(price, fxr, panel.fresh, W, D, mode, [i.exchange for i in panel.ins], [i.currency for i in panel.ins],
                   np.array([i.half_spread for i in panel.ins]), t0, t1, capital, stress)
    res["dates"] = panel.cal[t0:t1 + 1]
    return res
