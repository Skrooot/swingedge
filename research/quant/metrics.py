"""Riskstatistik på dagliga avkastningar (252 handelsdagar per år, riskfri ränta 0 som i appens studier)."""
import math

import numpy as np

DAYS = 252


def equity(r):
    return np.cumprod(1.0 + np.asarray(r, float))


def max_drawdown(r):
    e = equity(r)
    if len(e) == 0:
        return 0.0
    peak = np.maximum.accumulate(np.concatenate([[1.0], e]))[1:]
    return float(min(0.0, (e / peak - 1).min()))


def summary(r, trades=None, turnover=None):
    r = np.asarray(r, float)
    n = len(r)
    if n < 20:
        return None
    yrs = n / DAYS
    e = float(np.prod(1 + r))
    cagr = e ** (1 / yrs) - 1 if e > 0 else -1.0
    sd = float(r.std(ddof=1))
    mu = float(r.mean())
    down = math.sqrt(float(np.mean(np.minimum(r, 0) ** 2)))
    mdd = max_drawdown(r)
    out = {"cagr": cagr, "vol": sd * math.sqrt(DAYS), "sharpe": mu / sd * math.sqrt(DAYS) if sd > 0 else 0.0,
           "sortino": mu / down * math.sqrt(DAYS) if down > 0 else 0.0, "maxdd": mdd,
           "calmar": cagr / -mdd if mdd < 0 else 0.0, "years": yrs, "skew": _moment(r, 3), "kurt": _moment(r, 4)}
    if trades is not None:
        out["trades"] = int(trades); out["trades_per_year"] = trades / yrs
    if turnover is not None:
        out["turnover_per_year"] = turnover / yrs
    return out


def _moment(r, k):
    sd = r.std()
    return float(np.mean(((r - r.mean()) / sd) ** k)) if sd > 0 else 0.0


def monthly(r, dates):
    """Sammansätter dagsavkastning till månader (för PBO, bootstrap och rapporter)."""
    m = np.asarray(dates).astype("datetime64[M]")
    keys, idx = np.unique(m, return_index=True)
    out = np.add.reduceat(np.log1p(np.asarray(r, float)), idx)
    return keys, np.expm1(out)
