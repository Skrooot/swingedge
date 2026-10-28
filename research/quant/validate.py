"""Validering: walk-forward, parameterstabilitet, kostnadskänslighet, delperioder, regimer, koncentration,
korsmarknad och godkännandekrav. Funktionerna tar emot perioden de får använda; validerings- och
holdoutperioderna skickas bara in av run_research i rätt steg."""
import math

import numpy as np

from . import config
from . import metrics as M
from . import stats
from . import strategies as S
from .search import score

CRISES = [("Finanskrisen", "2007-10-09", "2009-03-09"), ("Eurokrisen", "2011-07-01", "2011-10-04"),
          ("Kina/olja", "2015-08-01", "2016-02-11"), ("Krypto-vintern 2018", "2018-01-01", "2018-12-15"),
          ("Coronakraschen", "2020-02-19", "2020-03-23"), ("Räntechocken", "2022-01-01", "2022-10-12"),
          ("Krypto-vintern 2022", "2021-11-10", "2022-11-21")]


def walk_forward(ev, spec):
    """Välj bästa variant av familjen (spec + grannparametrar) på varje träningsfönster, testa på nästa fönster."""
    fam = [spec] + S.neighbors(spec)
    rets, folds = [], []
    for a, b, c, d in config.WF_FOLDS:
        best, bs = None, -math.inf
        for s in fam:
            r = ev.run(s, a, b)
            sc, _ = score(r["summary"] if r else None, s, min_years=2.0)
            if sc > bs:
                best, bs = s, sc
        if best is None:
            folds.append({"train": (a, b), "test": (c, d), "chosen": None}); continue
        r = ev.run(best, c, d)
        if r:
            rets.append(r["r"])
        folds.append({"train": (a, b), "test": (c, d), "chosen": S.spec_id(best), "same_as_base": S.spec_id(best) == S.spec_id(spec),
                      "test_summary": r["summary"] if r else None})
    allr = np.concatenate(rets) if rets else np.array([])
    return {"summary": M.summary(allr) if len(allr) else None, "folds": folds,
            "stable_choice": sum(f.get("same_as_base", False) for f in folds) / len(folds)}


def stability(ev, spec, period=config.DEV):
    base = ev.run(spec, *period)["summary"]["sharpe"]
    out = []
    for s in S.neighbors(spec):
        r = ev.run(s, *period)
        out.append({"spec_id": S.spec_id(s), "sharpe": r["summary"]["sharpe"] if r and r["summary"] else None})
    ok = [x for x in out if x["sharpe"] is not None and x["sharpe"] >= 0.5 * base and x["sharpe"] > 0]
    return {"base_sharpe": base, "neighbors": out, "share_ok": len(ok) / len(out) if out else 0.0}


def cost_stress(ev, spec, period=config.DEV):
    out = {}
    for m in config.COST_STRESS:
        s = ev.run(spec, *period, stress=m)["summary"]
        out[str(m)] = {"cagr": s["cagr"], "sharpe": s["sharpe"]}
    return out


def subperiods(ev, spec, parts=(("2000-01-03", "2005-12-31"), ("2006-01-01", "2010-12-31"), ("2011-01-01", "2015-12-31"))):
    out = []
    for a, b in parts:
        r = ev.run(spec, a, b)
        s = r["summary"] if r else None
        out.append({"from": a, "to": b, "sharpe": s["sharpe"] if s else None, "cagr": s["cagr"] if s else None})
    return out


def regimes(ev, result, bench):
    """Avkastning i kriser (rapport) och i förhandsbestämda regimer från världsindex (kända vid varje dag)."""
    d = result["dates"]; r = result["r"]; br = bench["r"]
    out = {"crises": [], "regimes": {}}
    for name, a, b in CRISES:
        m = (d >= np.datetime64(a)) & (d <= np.datetime64(b))
        if m.sum() > 5:
            out["crises"].append({"name": name, "strategy": float(np.prod(1 + r[m]) - 1), "benchmark": float(np.prod(1 + br[m]) - 1)})
    w = ev.panel.bench.get("world"); sp = ev.panel.bench.get("sp500")
    idx = np.where(np.isnan(w), sp, w) if w is not None else sp
    t0 = int(np.searchsorted(ev.panel.cal, d[0]))
    x = idx[: t0 + len(d)]
    lr = np.diff(np.log(x), prepend=np.nan)
    vol = np.array([np.nanstd(lr[max(0, t - 62):t + 1]) for t in range(len(x))]) * math.sqrt(252)
    med = np.array([np.nanmedian(vol[max(0, t - 1260):t + 1]) for t in range(len(x))])
    sma = np.array([np.nanmean(x[max(0, t - 199):t + 1]) for t in range(len(x))])
    lab_vol = np.where(vol > med, "hög volatilitet", "låg volatilitet")[t0 - 1: t0 - 1 + len(d)]
    trend = np.where(x > sma * 1.02, "uppåttrend", np.where(x < sma * 0.98, "nedåttrend", "sidled"))[t0 - 1: t0 - 1 + len(d)]
    for lab in (lab_vol, trend):
        for k in np.unique(lab):
            m = lab == k
            if m.sum() > 20:
                out["regimes"][str(k)] = {"days": int(m.sum()), "strategy_ann": float(np.mean(r[m]) * 252), "benchmark_ann": float(np.mean(br[m]) * 252)}
    return out


def concentration(result):
    keys, mr = M.monthly(result["r"], result["dates"])
    lr = np.log1p(mr)
    tot = lr.sum()
    best = np.sort(lr)[::-1]
    k = max(1, int(round(len(lr) * 0.05)))
    without3 = math.exp(tot - best[:3].sum()) ** (12 / len(lr)) - 1 if len(lr) > 12 else None
    return {"months": len(lr), "share_from_best_5pct_months": float(best[:k].sum() / tot) if tot > 0 else None,
            "cagr_without_best_3_months": without3}


def cross_market(ev, spec, period=config.DEV):
    """Samma regler på andra universum (även icke köpbara, bara för forskning)."""
    out = {}
    for u in ("research_all_etp", "research_crypto_x", "research_fx", "etp_all", "etp_equity", "etp_real", "se_stocks", "us_stocks"):
        if u == spec["universe"]:
            continue
        s = dict(spec); s["universe"] = u
        s = S.normalize(s)
        try:
            r = ev.run(s, *period); b = ev.benchmark(u, *period)
            if r and r["summary"] and b["summary"]:
                out[u] = {"sharpe": r["summary"]["sharpe"], "benchmark_sharpe": b["summary"]["sharpe"], "cagr": r["summary"]["cagr"]}
        except Exception as e:
            out[u] = {"error": repr(e)[:100]}
    beats = [v for v in out.values() if "sharpe" in v and v["sharpe"] > v["benchmark_sharpe"]]
    return {"universes": out, "share_beating_benchmark": len(beats) / max(1, len([v for v in out.values() if "sharpe" in v]))}


def gates(rec, holdout=False):
    """Lista över krav som inte är uppfyllda (tom lista = godkänd)."""
    G = config.GATES; f = []
    v = rec.get("validation", {}); dv = rec.get("dev", {})
    if not holdout:
        if dv.get("years", 0) < G["min_years"]:
            f.append("för kort historik")
        if v.get("sharpe", -9) < G["min_validation_sharpe"]:
            f.append(f"validerings-Sharpe {v.get('sharpe', float('nan')):.2f} < {G['min_validation_sharpe']}")
        if v.get("maxdd", -1) < G["max_drawdown"]:
            f.append(f"största nedgång i validering {v.get('maxdd', 0):.0%} sämre än {G['max_drawdown']:.0%}")
        if G["beat_benchmark_sharpe"] and v.get("sharpe", -9) <= rec.get("validation_benchmark", {}).get("sharpe", 9):
            f.append("slår inte likaviktat köp och behåll på Sharpe i validering")
        wf = rec.get("walk_forward", {}).get("summary") or {}
        if wf.get("sharpe", -9) < G["min_wf_sharpe"]:
            f.append(f"walk-forward-Sharpe {wf.get('sharpe', float('nan')):.2f} < {G['min_wf_sharpe']}")
        if rec.get("dsr", {}).get("dsr", 0) < G["min_dsr"]:
            f.append(f"Deflated Sharpe {rec.get('dsr', {}).get('dsr', 0):.2f} < {G['min_dsr']}")
        if rec.get("pbo", {}).get("pbo", 1) > G["max_pbo"]:
            f.append(f"PBO {rec.get('pbo', {}).get('pbo', 1):.2f} > {G['max_pbo']}")
        if rec.get("stability", {}).get("share_ok", 0) < G["min_neighbor_share"]:
            f.append(f"parameterkänslig: {rec.get('stability', {}).get('share_ok', 0):.0%} av grannarna håller")
        cs = rec.get("cost_stress", {}).get(str(G["cost_stress_positive"]))
        if cs and cs["cagr"] <= 0:
            f.append("ingen avkastning vid dubbla kostnader")
        if rec.get("fdr_pass") is False:
            f.append(f"klarar inte FDR (q {rec.get('fdr_q', float('nan')):.2f})")
        tpy = dv.get("trades_per_year", 0)
        if rec["spec"]["entry"]["type"] != "always" and tpy < G["min_trades_per_year"][rec["spec"]["schedule"]]:
            f.append(f"för få affärer ({tpy:.1f}/år)")
        if dv.get("trades", 0) < G["min_total_trades"] and rec["spec"]["entry"]["type"] != "always":
            f.append(f"för få affärer totalt ({dv.get('trades', 0)})")
        if rec.get("exact_gap") is not None and rec["exact_gap"] > G["max_exact_gap_cagr"]:
            f.append(f"snabb och exakt motor skiljer {rec['exact_gap']:.1%} i CAGR")
        if rec.get("survivorship_biased"):
            f.append("universumet har överlevnadsbias (dagens bolag); kan inte verifieras")
        if not rec.get("tradable", True):
            f.append("kräver produkter som inte går att handla via Avanza")
    else:
        h = rec.get("holdout", {})
        if h.get("sharpe", -9) < G["holdout_min_sharpe"]:
            f.append(f"holdout-Sharpe {h.get('sharpe', float('nan')):.2f} < {G['holdout_min_sharpe']}")
        if h.get("maxdd", -1) < G["holdout_max_drawdown"]:
            f.append(f"holdout-nedgång {h.get('maxdd', 0):.0%}")
    return f
