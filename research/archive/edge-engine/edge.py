"""SwingEdge Edge Discovery: forskningsmotor för hela universumet.

Nivå A: varje strategifamilj testas på den underliggande marknaden.
Nivå B: samma signal (från den underliggande marknaden) testas på Avanza-produktens egen kursserie.
Validering: träning till och med 2015, test 2016–2026, blockbootstrap, Benjamini–Hochberg (FDR),
Deflated Sharpe Ratio, Probability of Backtest Overfitting (CSCV), parametervarianter, stabilitet över
tre delperioder och kontroll av att urvalet håller utanför urvalsperioden.

Signal vid stängning t, affär vid stängning t+1 (samma tidsregel som appen). Kontanter ger 0 %.
Skriver edge.json och parity.json. Kör: python -E -s edge.py [--refetch]
"""
import bisect
import datetime as dt
import json
import math
import os
import random
import statistics
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import fetch as F  # noqa: E402

DATA = os.path.join(HERE, "data")
TRAIN_END, TEST_START = "2015-12-31", "2016-01-01"
SUBPERIODS = [("2016-01-01", "2019-12-31"), ("2020-01-01", "2022-12-31"), ("2023-01-01", "2026-12-31")]
COST = {"omxs30": 0.0015}
DEFAULT_COST = 0.0040


# ---------------- data ----------------
def series(sym, refetch=False):
    p = os.path.join(DATA, sym.replace("^", "_").replace("=", "_") + ".json")
    if refetch or not os.path.exists(p):
        d = F.fetch(sym)
        time.sleep(0.6)
        if not d or not d["rows"]:
            return None
        json.dump(d, open(p, "w"))
    d = json.load(open(p))
    rows = [r for r in d["rows"] if r[4] and r[4] > 0]
    # Yahoo-råvaruterminer har ibland noll/negativa eller orimliga dagar; ta bort dagsrörelser över 40 % som vänder direkt
    dates, closes = [], []
    for r in rows:
        if closes and dates and r[0] == dates[-1]:
            continue
        dates.append(r[0]); closes.append(r[4])
    clean_d, clean_c = [], []
    for i, (d0, c0) in enumerate(zip(dates, closes)):
        if 0 < i < len(closes) - 1:
            a, b = c0 / closes[i - 1], closes[i + 1] / c0
            if (a > 1.4 and b < 0.72) or (a < 0.72 and b > 1.4):
                continue
        clean_d.append(d0); clean_c.append(c0)
    return {"symbol": sym, "currency": d.get("currency"), "dates": clean_d, "closes": clean_c}


# ---------------- indikatorer ----------------
def sma(c, n):
    out, s = [None] * len(c), 0.0
    for i, v in enumerate(c):
        s += v
        if i >= n:
            s -= c[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def month_end(dates):
    """Sista handelsdagen i månaden enligt datan. Den sista stapeln räknas som månadsslut bara om månaden är slut."""
    today = dt.date.today().isoformat()[:7]
    return [(i + 1 < len(dates) and dates[i + 1][:7] != dates[i][:7]) or (i + 1 == len(dates) and dates[i][:7] < today)
            for i in range(len(dates))]


def rsi2(c):
    out, ag, al = [None] * len(c), 0.0, 0.0
    for i in range(1, len(c)):
        ch = c[i] - c[i - 1]
        g, lo = max(ch, 0.0), max(-ch, 0.0)
        if i <= 2:
            ag += g / 2; al += lo / 2
            if i < 2:
                continue
        else:
            ag = (ag + g) / 2; al = (al + lo) / 2
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def vol20(c):
    r = [0.0] + [c[i] / c[i - 1] - 1 for i in range(1, len(c))]
    out = [None] * len(c)
    for i in range(20, len(c)):
        w = r[i - 19:i + 1]
        m = sum(w) / 20
        out[i] = math.sqrt(sum((x - m) ** 2 for x in w) / 19 * 252)
    return out


# ---------------- strategifamiljer (frysta definitioner) ----------------
FAMILIES = {
    "sma150": {"name": "Trend SMA150, daglig", "kind": "befintlig", "horizon": "Veckor–månader"},
    "sma200m": {"name": "Trend SMA200, månadsvis", "kind": "befintlig", "horizon": "Månader"},
    "tsmom12": {"name": "Tidsseriemomentum 12 mån", "kind": "befintlig", "horizon": "Månader"},
    "donchian": {"name": "Donchian-utbrott 55/20", "kind": "befintlig", "horizon": "Veckor–månader"},
    "voltrend": {"name": "Volatilitetsstyrd trend", "kind": "befintlig", "horizon": "Veckor–månader"},
    "pullback": {"name": "Dipp i upptrend (RSI2)", "kind": "kandidat", "horizon": "Dagar"},
    "relmom": {"name": "Relativt momentum inom tillgångsslaget", "kind": "kandidat", "horizon": "Månader"},
}


def weights(fam, c, d, p, peers=None):
    n = len(c)
    w = [None] * n
    if fam in ("sma150", "smaN"):
        m = sma(c, p.get("n", 150))
        return [None if m[i] is None else (1.0 if c[i] > m[i] else 0.0) for i in range(n)]
    if fam == "sma200m":
        m, me, cur = sma(c, p.get("n", 200)), month_end(d), None
        for i in range(n):
            if m[i] is None:
                continue
            if me[i] or cur is None:
                cur = 1.0 if c[i] > m[i] else 0.0
            w[i] = cur
        return w
    if fam == "tsmom12":
        lb, me, cur = p.get("lookback", 252), month_end(d), None
        for i in range(lb, n):
            if me[i] or cur is None:
                cur = 1.0 if c[i] > c[i - lb] else 0.0
            w[i] = cur
        return w
    if fam == "donchian":
        a, b, pos = p.get("entry", 55), p.get("exit", 20), 0.0
        for i in range(a, n):
            hi, lo = max(c[i - a:i]), min(c[i - b:i])
            if pos == 0 and c[i] > hi:
                pos = 1.0
            elif pos and c[i] < lo:
                pos = 0.0
            w[i] = pos
        return w
    if fam == "voltrend":
        m, v, tv = sma(c, 200), vol20(c), p["target"]
        for i in range(n):
            if m[i] is None or v[i] is None:
                continue
            x = (min(1.0, tv / v[i]) if v[i] > 0 else 1.0) if c[i] > m[i] else 0.0
            w[i] = round(x * 4) / 4
        return w
    if fam == "pullback":
        m200, m5, r, pos, held = sma(c, 200), sma(c, 5), rsi2(c), 0.0, 0
        for i in range(n):
            if m200[i] is None or r[i] is None:
                continue
            if pos == 0 and c[i] > m200[i] and r[i] < 10:
                pos, held = 1.0, 0
            elif pos:
                held += 1
                if c[i] > m5[i] or held >= 10:
                    pos = 0.0
            w[i] = pos
        return w
    if fam == "relmom":
        # peers: dict sym -> (dates, closes) för tillgångsslaget; topp tredjedel på 12–1 mån och positiv
        me = month_end(d)
        idx = {s: {dd: k for k, dd in enumerate(pd)} for s, (pd, pc) in peers.items()}
        cur = None
        for i in range(n):
            if not me[i] and cur is not None:
                w[i] = cur
                continue
            if i < 252:
                continue
            scores = {}
            for s, (pd, pc) in peers.items():
                k = bisect.bisect_right(pd, d[i]) - 1
                if k >= 252:
                    scores[s] = pc[k - 21] / pc[k - 252] - 1
            mine = c[i - 21] / c[i - 252] - 1
            if len(scores) < 3:
                continue
            ranked = sorted(scores.values(), reverse=True)
            cut = ranked[max(0, len(ranked) // 3 - 1)]
            cur = 1.0 if (mine >= cut and mine > 0) else 0.0
            w[i] = cur
        return w
    raise KeyError(fam)


VARIANTS = {
    "sma150": [("smaN", {"n": 100}), ("smaN", {"n": 200}), ("smaN", {"n": 250})],
    "sma200m": [("sma200m", {"n": 150}), ("sma200m", {"n": 250})],
    "tsmom12": [("tsmom12", {"lookback": 126}), ("tsmom12", {"lookback": 189})],
    "donchian": [("donchian", {"entry": 20, "exit": 10}), ("donchian", {"entry": 100, "exit": 50})],
}


# ---------------- simulering och mått ----------------
def simulate(c, w, cost):
    n = len(c)
    r, ex, trades = [0.0] * n, [0.0] * n, 0
    pos = 0.0
    for t in range(1, n):
        eq = 1 + pos * (c[t] / c[t - 1] - 1)
        tgt = w[t - 1] if w[t - 1] is not None else 0.0
        if abs(tgt - pos) > 1e-9:
            eq *= 1 - abs(tgt - pos) * cost
            if pos == 0 and tgt > 0:
                trades += 1
            pos = tgt
        r[t] = eq - 1
        ex[t] = pos
    return r, ex


def stats(d, r, ex, a, b=None, ann=252):
    idx = [i for i, x in enumerate(d) if x >= a and (b is None or x <= b)]
    if len(idx) < 250:
        return None
    rs = [r[i] for i in idx]
    eq, peak, mdd = 1.0, 1.0, 0.0
    for x in rs:
        eq *= 1 + x; peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
    yrs = (dt.date.fromisoformat(d[idx[-1]]) - dt.date.fromisoformat(d[idx[0]])).days / 365.25
    m = sum(rs) / len(rs)
    sd = statistics.pstdev(rs)
    dn = math.sqrt(sum(min(x, 0) ** 2 for x in rs) / len(rs))
    entries = sum(1 for k in range(1, len(idx)) if ex[idx[k]] > 0 and ex[idx[k - 1]] == 0)
    cagr = eq ** (1 / yrs) - 1 if yrs > 0 and eq > 0 else -1
    return {"from": d[idx[0]], "to": d[idx[-1]], "years": round(yrs, 1), "cagr": cagr, "maxdd": mdd,
            "sharpe": m / sd * math.sqrt(ann) if sd else 0.0, "sortino": m / dn * math.sqrt(ann) if dn else 0.0,
            "calmar": cagr / abs(mdd) if mdd < 0 else 0.0, "exposure": sum(ex[i] for i in idx) / len(idx),
            "trades": entries, "vol": sd * math.sqrt(ann), "_idx": idx}


def sharpe(x, ann):
    sd = statistics.pstdev(x)
    return sum(x) / len(x) / sd * math.sqrt(ann) if sd else 0.0


def boot_p(ra, rb, ann, reps=250, block=20, seed=7):
    """Ensidigt p-värde: andel bootstrapdragningar där Sharpe(a) <= Sharpe(b)."""
    rnd = random.Random(seed)
    n = len(ra)
    worse = 0
    for _ in range(reps):
        xa, xb = [], []
        i = rnd.randrange(n)
        while len(xa) < n:
            xa.append(ra[i]); xb.append(rb[i])
            i = rnd.randrange(n) if rnd.random() < 1 / block else (i + 1) % n
        if sharpe(xa, ann) - sharpe(xb, ann) <= 0:
            worse += 1
    return (worse + 1) / (reps + 1)


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def norm_ppf(p):
    # Acklams approximation
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    dd = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    pl, ph = 0.02425, 1 - 0.02425
    if p < pl:
        q = math.sqrt(-2 * math.log(p)); return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    if p > ph:
        q = math.sqrt(-2 * math.log(1 - p)); return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((dd[0]*q+dd[1])*q+dd[2])*q+dd[3])*q+1)
    q = p - 0.5; r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def deflated_sharpe(active, n_trials, var_trial_sr):
    """Bailey & López de Prado (2014). active = dagliga aktiva avkastningar (strategi minus köp och behåll).
    SR mäts per dag; tröskeln SR0 är förväntad max-Sharpe bland n_trials oberoende försök."""
    T = len(active)
    m = sum(active) / T
    sd = statistics.pstdev(active)
    if sd == 0 or T < 30:
        return None
    sr = m / sd
    sk = sum(((x - m) / sd) ** 3 for x in active) / T
    ku = sum(((x - m) / sd) ** 4 for x in active) / T
    g = 0.5772156649
    sr0 = math.sqrt(max(var_trial_sr, 1e-12)) * ((1 - g) * norm_ppf(1 - 1 / n_trials) + g * norm_ppf(1 - 1 / (n_trials * math.e)))
    den = math.sqrt(max(1e-12, 1 - sk * sr + (ku - 1) / 4 * sr * sr))
    return norm_cdf((sr - sr0) * math.sqrt(T - 1) / den)


def bh_q(pvals):
    """Benjamini–Hochberg q-värden."""
    n = len(pvals)
    order = sorted(range(n), key=lambda i: pvals[i])
    q = [0.0] * n
    prev = 1.0
    for rank in range(n, 0, -1):
        i = order[rank - 1]
        prev = min(prev, pvals[i] * n / rank)
        q[i] = prev
    return q


def pbo_cscv(matrix, s=10):
    """Probability of Backtest Overfitting (Bailey m.fl. 2015). matrix: lista av kolumner (månadsavkastningar per försök)."""
    import itertools
    T = len(matrix[0])
    blocks = [list(range(k * T // s, (k + 1) * T // s)) for k in range(s)]
    lam = []
    for comb in itertools.combinations(range(s), s // 2):
        ins = [i for k in comb for i in blocks[k]]
        oos = [i for k in range(s) if k not in comb for i in blocks[k]]
        def sr(col, ix):
            x = [col[i] for i in ix]; sd = statistics.pstdev(x)
            return sum(x) / len(x) / sd if sd else 0.0
        is_sr = [sr(col, ins) for col in matrix]
        best = max(range(len(matrix)), key=lambda j: is_sr[j])
        oos_sr = [sr(col, oos) for col in matrix]
        rank = sum(1 for v in oos_sr if v <= oos_sr[best]) / (len(matrix) + 1)
        lam.append(math.log(rank / (1 - rank)))
    return sum(1 for x in lam if x <= 0) / len(lam)


def spearman(a, b):
    def ranks(x):
        o = sorted(range(len(x)), key=lambda i: x[i]); r = [0] * len(x)
        for k, i in enumerate(o):
            r[i] = k
        return r
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    return 1 - 6 * sum((ra[i] - rb[i]) ** 2 for i in range(n)) / (n * (n * n - 1))


def monthly(d, r):
    out = {}
    for x, v in zip(d, r):
        out.setdefault(x[:7], 1.0)
        out[x[:7]] *= 1 + v
    return {k: v - 1 for k, v in out.items()}


# ---------------- huvudflöde ----------------
def main():
    refetch = "--refetch" in sys.argv
    uni = json.load(open(os.path.join(HERE, "universe.json"), encoding="utf-8"))["markets"]
    mapping = json.load(open(os.path.join(HERE, "mapping.json"), encoding="utf-8"))
    markets, data, products = {}, {}, {}
    for m in uni:
        prods = [p for p in mapping["markets"].get(m["id"], []) if p.get("eligible") and p.get("yahoo")]
        under_sym = m["underlying"] or (prods[0]["yahoo"] if prods else None)
        s = series(under_sym, refetch) if under_sym else None
        if s is None or len(s["closes"]) < 300:
            markets[m["id"]] = dict(m, status="saknar data", products=prods)
            continue
        data[m["id"]] = s
        # produkt för forskningen = längst historik bland godkända listningar av samma produkt
        best = None
        for p in prods:
            ps = series(p["yahoo"], refetch)
            if ps and (best is None or ps["dates"][0] < best[1]["dates"][0]):
                best = (p, ps)
        if best:
            products[m["id"]] = best
        # handelslistning = köp- och säljbar, helst i SEK, annars mest omsatt
        trade = sorted(prods, key=lambda p: (p["currency"] != "SEK", -(p.get("valueTradedToday") or 0)))
        markets[m["id"]] = dict(m, status="ok", underlyingUsed=under_sym, products=prods,
                                tradeListing=trade[0] if trade else None,
                                researchProduct=best[0]["yahoo"] if best else None)
        print("data", m["id"], under_sym, s["dates"][0], len(s["closes"]), "produkt", best[0]["yahoo"] if best else None, flush=True)

    by_class = {}
    for mid, s in data.items():
        by_class.setdefault(markets[mid]["assetClass"], {})[mid] = (s["dates"], s["closes"])

    combos = []
    for mid, s in data.items():
        d, c = s["dates"], s["closes"]
        ann = 365 if markets[mid]["kind"] == "crypto" else 252
        cost = COST.get(mid, DEFAULT_COST)
        bh_r, bh_ex = simulate(c, [1.0] * len(c), cost)
        # volatilitetsmål för voltrend: median av 20-dagarsvolatilitet under träningsperioden (fryst)
        v = vol20(c)
        tv = [v[i] for i in range(len(c)) if v[i] and d[i] <= TRAIN_END]
        target = statistics.median(tv) if len(tv) > 200 else statistics.median([x for x in v if x])
        for fam in FAMILIES:
            if fam == "relmom" and len(by_class[markets[mid]["assetClass"]]) < 4:
                continue
            p = {"target": round(target, 4)} if fam == "voltrend" else {}
            w = weights(fam, c, d, p, peers=by_class[markets[mid]["assetClass"]] if fam == "relmom" else None)
            r, ex = simulate(c, w, cost)
            tr = stats(d, r, ex, "1900-01-01", TRAIN_END, ann=ann)
            te = stats(d, r, ex, TEST_START, ann=ann)
            bh_tr = stats(d, bh_r, bh_ex, "1900-01-01", TRAIN_END, ann=ann)
            bh_te = stats(d, bh_r, bh_ex, TEST_START, ann=ann)
            if te is None or bh_te is None:
                continue
            idx = te.pop("_idx"); bh_te.pop("_idx")
            if tr:
                tr.pop("_idx")
            if bh_tr:
                bh_tr.pop("_idx")
            active = [r[i] - bh_r[i] for i in idx]
            sub = []
            for a, b in SUBPERIODS:
                x, y = stats(d, r, ex, a, b, ann=ann), stats(d, bh_r, bh_ex, a, b, ann=ann)
                if x and y:
                    sub.append(round(x["sharpe"] - y["sharpe"], 3))
            var_res = []
            for vf, vp in VARIANTS.get(fam, []):
                vw = weights(vf, c, d, vp)
                vr, vex = simulate(c, vw, cost)
                vs = stats(d, vr, vex, TEST_START, ann=ann)
                if vs:
                    var_res.append(round(vs["sharpe"] - bh_te["sharpe"], 3))
            combos.append({
                "market": mid, "family": fam, "params": p, "ann": ann,
                "train": tr, "test": te, "bhTrain": bh_tr, "bhTest": bh_te,
                "excessTest": te["sharpe"] - bh_te["sharpe"],
                "excessTrain": (tr["sharpe"] - bh_tr["sharpe"]) if tr and bh_tr else None,
                "ddChange": te["maxdd"] - bh_te["maxdd"],
                "p": boot_p([r[i] for i in idx], [bh_r[i] for i in idx], ann),
                "irDaily": (sum(active) / len(active)) / statistics.pstdev(active) if statistics.pstdev(active) else 0.0,
                "_active": active,
                "subperiods": sub, "variants": var_res,
                "_w": w, "_d": d, "_c": c,
                "stateToday": w[-1], "stateDate": d[-1],
                "lastSwitch": next((d[i] for i in range(len(w) - 1, 0, -1) if w[i] is not None and w[i - 1] is not None and (w[i] > 0) != (w[i - 1] > 0)), None),
            })
        print("testat", mid, flush=True)

    # ---- multipeltest ----
    n = len(combos)
    qs = bh_q([x["p"] for x in combos])
    var_ir = statistics.pvariance([x["irDaily"] for x in combos])
    for x, q in zip(combos, qs):
        x["q"] = q
        x["dsr"] = deflated_sharpe(x.pop("_active"), n, var_ir)

    # ---- nivå B: produkten ----
    for x in combos:
        mid = x["market"]
        if mid not in products:
            x["product"] = None
            continue
        prod, ps = products[mid]
        ud, uw = x["_d"], x["_w"]
        pw = []
        for pd in ps["dates"]:
            k = bisect.bisect_left(ud, pd) - 1  # senaste underliggande stängning före produktdagen
            pw.append(uw[k] if k >= 0 else None)
        cost = COST.get(mid, DEFAULT_COST)
        r, ex = simulate(ps["closes"], pw, cost)
        br, bex = simulate(ps["closes"], [1.0] * len(pw), cost)
        start = max(TEST_START, ps["dates"][0])
        a, b = stats(ps["dates"], r, ex, start), stats(ps["dates"], br, bex, start)
        if a and b:
            a.pop("_idx"); b.pop("_idx")
        um = monthly(x["_d"], [0.0] + [x["_c"][i] / x["_c"][i - 1] - 1 for i in range(1, len(x["_c"]))])
        pm = monthly(ps["dates"], [0.0] + [ps["closes"][i] / ps["closes"][i - 1] - 1 for i in range(1, len(ps["closes"]))])
        keys = sorted(set(um) & set(pm))[1:-1]
        corr = None
        if len(keys) > 24:
            xa = [um[k] for k in keys]; xb = [pm[k] for k in keys]
            ma, mb = sum(xa) / len(xa), sum(xb) / len(xb)
            corr = sum((p - ma) * (q - mb) for p, q in zip(xa, xb)) / math.sqrt(sum((p - ma) ** 2 for p in xa) * sum((q - mb) ** 2 for q in xb))
            gu = math.prod(1 + um[k] for k in keys); gp = math.prod(1 + pm[k] for k in keys)
            yrs = len(keys) / 12
            drift = gp ** (1 / yrs) - gu ** (1 / yrs)
        else:
            drift = None
        x["product"] = {"yahoo": prod["yahoo"], "name": prod["name"], "currency": ps["currency"], "test": a, "bhTest": b,
                        "excess": (a["sharpe"] - b["sharpe"]) if a and b else None,
                        "trackingCorr": corr, "annualDriftVsUnderlying": drift}

    # ---- klassificering ----
    for x in combos:
        te = x["test"]
        robust = (sum(1 for v in x["variants"] if v > 0) >= max(1, math.ceil(len(x["variants"]) * 0.66))) if x["variants"] else None
        stable = sum(1 for v in x["subperiods"] if v > 0) >= 2
        enough = te["years"] >= 5 and te["trades"] >= 5
        pv = x["product"]
        prod_ok = bool(pv and pv["excess"] is not None and pv["excess"] > 0 and (pv["trackingCorr"] or 0) >= 0.8 and pv["test"]["years"] >= 4)
        risk_red = x["ddChange"] > 0.3 * abs(x["bhTest"]["maxdd"]) and x["excessTest"] > -0.05
        x["checks"] = {"enoughData": enough, "robustParams": robust, "stableSubperiods": stable, "productVerified": prod_ok,
                       "fdr10": x["q"] < 0.10, "dsr95": (x["dsr"] or 0) >= 0.95, "p10": x["p"] < 0.10}
        if x["excessTest"] > 0 and x["q"] < 0.10 and (x["dsr"] or 0) >= 0.95 and enough and stable and robust is not False and prod_ok:
            cls = "Validerad"
        elif x["excessTest"] > 0 and x["p"] < 0.10 and enough:
            cls = "Stark hypotes"
        elif x["excessTest"] > 0:
            cls = "Hypotes"
        else:
            cls = "Ingen edge"
        x["evidence"] = cls
        x["riskReduction"] = bool(risk_red)

    # ---- urvalet utanför urvalsperioden ----
    both = [x for x in combos if x["excessTrain"] is not None]
    sel = {}
    if len(both) > 20:
        rho = spearman([x["excessTrain"] for x in both], [x["excessTest"] for x in both])
        cut = sorted((x["excessTrain"] for x in both), reverse=True)[len(both) // 10]
        top = [x["excessTest"] for x in both if x["excessTrain"] >= cut]
        rest = [x["excessTest"] for x in both if x["excessTrain"] < cut]
        sel = {"n": len(both), "spearmanTrainTest": round(rho, 3), "topDecileTestExcess": round(statistics.mean(top), 3),
               "restTestExcess": round(statistics.mean(rest), 3)}

    # ---- PBO: välj bästa kombination på träning, mät rang på test (CSCV över gemensam period) ----
    cols = []
    for x in combos:
        mr = monthly(x["_d"], simulate(x["_c"], x["_w"], DEFAULT_COST)[0])
        cols.append(mr)
    common = sorted(set.intersection(*[set(k for k in col if "2006-01" <= k <= "2026-09") for col in cols if min(col) <= "2006-01"]))
    mat = [[col[k] for k in common] for col in cols if min(col) <= "2006-01"]
    pbo = pbo_cscv(mat) if len(mat) > 10 and len(common) > 100 else None

    # ---- portfölj av kombinationer valda på träningsdata ----
    picked = [x for x in combos if x["excessTrain"] is not None and x["excessTrain"] > 0.1 and x["train"]["trades"] >= 5]
    port = None
    if picked:
        months = sorted(set.intersection(*[set(monthly(x["_d"], simulate(x["_c"], x["_w"], DEFAULT_COST)[0])) for x in picked]))
        months = [k for k in months if k >= "2016-01"]
        if len(months) > 36:
            sr, br = [], []
            mrs = [monthly(x["_d"], simulate(x["_c"], x["_w"], DEFAULT_COST)[0]) for x in picked]
            mbs = [monthly(x["_d"], simulate(x["_c"], [1.0] * len(x["_c"]), DEFAULT_COST)[0]) for x in picked]
            vols = [max(1e-4, x["train"]["vol"]) for x in picked]
            iw = [1 / v for v in vols]; tot = sum(iw); iw = [v / tot for v in iw]
            for k in months:
                sr.append(sum(iw[j] * mrs[j][k] for j in range(len(picked))))
                br.append(sum(iw[j] * mbs[j][k] for j in range(len(picked))))
            def ms(x):
                eq, pk, dd = 1.0, 1.0, 0.0
                for v in x:
                    eq *= 1 + v; pk = max(pk, eq); dd = min(dd, eq / pk - 1)
                yrs = len(x) / 12
                return {"cagr": eq ** (1 / yrs) - 1, "sharpe": sharpe(x, 12), "maxdd": dd}
            port = {"n": len(picked), "from": months[0], "to": months[-1], "strategy": ms(sr), "buyHold": ms(br),
                    "members": [f"{x['market']}:{x['family']}" for x in picked][:60]}

    # ---- utdata ----
    clean = []
    for x in combos:
        y = {k: v for k, v in x.items() if not k.startswith("_")}
        clean.append(y)
    meta = {
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "method": {"train": f"till och med {TRAIN_END}", "test": f"{TEST_START} till senaste data", "execution": "signal vid stängning, affär vid nästa stängning",
                   "costPerSide": {"standard": DEFAULT_COST, **COST}, "families": FAMILIES,
                   "validatedRule": "positiv test-överavkastning i Sharpe, BH-q < 0,10, Deflated Sharpe >= 0,95, minst 5 års test och 5 affärer, positiv i minst 2 av 3 delperioder, parametervarianter håller, verifierad på Avanza-produkten (positiv överavkastning och korrelation >= 0,8)"},
        "nCombos": n, "pbo": pbo, "selectionOOS": sel, "trainSelectedPortfolio": port,
        "mappingVerified": mapping.get("verified"),
    }
    json.dump({"meta": meta, "markets": markets, "combos": clean}, open(os.path.join(HERE, "edge.json"), "w", encoding="utf-8"), ensure_ascii=False)
    # paritetsfixtur för appens Kotlin-motor: några serier med Pythons vikter
    par = {}
    for x in combos:
        if x["market"] in ("gold", "sp500", "bitcoin", "copper") and x["family"] != "relmom":
            par[f"{x['market']}:{x['family']}"] = {"dates": x["_d"][-1500:], "closes": x["_c"][-1500:], "params": x["params"],
                                                   "weights": x["_w"][-1500:], "warmup": 300}
    json.dump(par, open(os.path.join(HERE, "parity.json"), "w"))
    from collections import Counter
    print("\nkombinationer", n, Counter(x["evidence"] for x in combos))
    print("PBO", pbo, "urval", sel)
    print("portfölj", json.dumps(port, ensure_ascii=False)[:600] if port else None)
    for x in sorted(combos, key=lambda z: -z["excessTest"])[:25]:
        pv = x["product"]
        print(f"{x['evidence']:13s} {x['market']:13s} {x['family']:9s} ex {x['excessTest']:+.2f} p {x['p']:.3f} q {x['q']:.2f} dsr {x['dsr'] or 0:.2f} sub {x['subperiods']} var {x['variants']} prod {None if not pv else (round(pv['excess'],2) if pv['excess'] is not None else None, round(pv['trackingCorr'] or 0, 2))}")


if __name__ == "__main__":
    main()
