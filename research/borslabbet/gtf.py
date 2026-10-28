"""Global trendföljning (Börslabbets publika regler) och varianter på månadsdata i SEK.

Tillgångsserierna är NAV för fonder som går att köpa på Avanza (efter fondavgifter). Där en indexfond saknar
lång historik används en aktiv fond i samma kategori fram till att indexfonden startar (skarvning av
månadsavkastningar). Guld är Yahoo GC=F i SEK fram till 2009-11 och därefter Xetra-Gold (4GLD) i SEK.
"""
import json, math, random

D = json.load(open("data/funds.json", encoding="utf-8"))
F = D["funds"]; Y = D["yahoo"]
LAST = "2026-09"  # sista hela månaden


def months(a, b):
    y, m = int(a[:4]), int(a[5:]); out = []
    while f"{y:04d}-{m:02d}" <= b:
        out.append(f"{y:04d}-{m:02d}"); m += 1
        if m > 12: y, m = y + 1, 1
    return out


def rets(level):
    ks = sorted(k for k in level if k <= LAST)
    return {b: level[b] / level[a] - 1 for a, b in zip(ks, ks[1:]) if months(a, b)[1:] == [b]}


def splice(*parts):
    """parts: (serie-id, från-månad). Avkastning från den senaste delen som har startat."""
    out = {}
    for sid, start in parts:
        r = rets(F[str(sid)]["series"]) if isinstance(sid, int) else sid
        for k, v in r.items():
            if k >= start: out[k] = v
    return out


def ffill(a, b):
    """Produkt av två månadsserier; saknade månader i Yahoo fylls med föregående värde."""
    out, la, lb = {}, None, None
    for m in months(max(min(a), min(b)), LAST):
        la = a.get(m, la); lb = b.get(m, lb)
        out[m] = la * lb
    return out


def gold():
    usd = ffill(Y["GC=F"], Y["SEK=X"])
    eur = ffill(Y["4GLD.DE"], Y["EURSEK=X"])
    return splice((rets(usd), "0000"), (rets(eur), "2009-12"))


ASSETS = {
    "Sverige": splice((1983, "0000"), (159608, "2008-12")),
    "Europa": splice((581, "0000")),
    "USA": splice((1505, "0000")),
    "Japan": splice((1263, "0000")),
    "Tillväxtmarknader": splice((2155, "0000"), (487076, "2014-07")),
    "Svenska småbolag": splice((2008, "0000"), (789175, "2017-10")),
    "Svenska obligationer": splice((2098, "0000")),
    "Svenska korta räntor": splice((2028, "0000")),
    "Guld": gold(),
}
SHORT = "Svenska korta räntor"
WORLD = splice((2332, "0000"))
# Handelskostnad per sida: fonder handlas utan courtage på Avanza, guld (4GLD på Xetra) har courtage + växling
COST = {k: 0.0 for k in ASSETS}; COST["Guld"] = 0.004


def level(r, ms):
    p, out = 1.0, {}
    for m in ms:
        if m in r: p *= 1 + r[m]
        out[m] = p
    return out


def mom(lv, m, ms, look):
    i = ms.index(m)
    vals = []
    for n in look:
        if i - n < 0: return None
        vals.append(lv[ms[i]] / lv[ms[i - n]] - 1)
    return sum(vals) / len(vals)


def run(assets, start, end, top=3, thr=0.02, look=(3, 6, 12), filt=None, cost=None, delay=0, extra_cost=0.0,
        rebalance=True):
    """Månadsvis: signal vid månadsslut t, innehav under månad t+1 (+delay)."""
    cost = cost or COST
    ms = months("1984-12", end)
    lv = {a: level(r, ms) for a, r in assets.items()}
    have = {a: set(r) for a, r in assets.items()}
    hold, w = [], {}
    out = {"m": [], "r": [], "w": [], "turn": 0.0, "pos": []}
    ev = months(start, end)
    sigs = {}
    for m in months(ms[13], end):
        i = ms.index(m)
        elig = [a for a in assets if all(ms[j] in have[a] for j in range(i - max(look) + 1, i + 1))]
        sc = {a: mom(lv[a], m, ms, look) for a in elig}
        sc = {a: v for a, v in sc.items() if v is not None}
        sigs[m] = sc
    prev_w = {}
    open_pos = {}
    for k, m in enumerate(ev):
        i = ms.index(m)
        sm = ms[i - 1 - delay]  # signalmånad
        sc = sigs.get(sm, {})
        hold = [a for a in hold if a in sc]
        rank = sorted(sc, key=lambda a: -sc[a])
        if len(hold) < top:
            for a in rank:
                if len(hold) >= top: break
                if a not in hold: hold.append(a)
        # tröskel: byt bästa utomstående mot sämsta innehav så länge skillnaden är minst thr
        while True:
            outs = [a for a in rank if a not in hold]
            if not outs or not hold: break
            worst = min(hold, key=lambda a: sc[a]); best = outs[0]
            if sc[best] >= sc[worst] + thr and sc[best] > sc[worst]:
                hold[hold.index(worst)] = best
            else:
                break
        tw = {}
        for a in hold:
            on = True
            if filt == "ma12":
                lvl = lv[a]; ii = ms.index(sm)
                on = lvl[sm] > sum(lvl[ms[j]] for j in range(ii - 11, ii + 1)) / 12
            elif filt == "pos":
                on = sc[a] > 0
            elif filt == "abs":
                on = mom(lv[a], sm, ms, (12,)) > mom(lv[SHORT], sm, ms, (12,)) if SHORT in lv else True
            key = a if on else SHORT
            tw[key] = tw.get(key, 0) + 1 / top
        if not rebalance and prev_w:
            # behåll drivna vikter för innehav som ligger kvar
            kept = {a: prev_w[a] for a in tw if a in prev_w}
            s_k = sum(kept.values()); n_k = sum(tw[a] for a in kept)
            nw = {a: (kept[a] / s_k * n_k if a in kept else tw[a]) for a in tw}
            tw = nw
        tc = 0.0
        for a in set(tw) | set(prev_w):
            d = tw.get(a, 0) - prev_w.get(a, 0)
            tc += abs(d) * (cost.get(a, 0) + extra_cost)
            if d > 0: out["turn"] += d
        r = sum(wt * assets[a].get(m, 0.0) for a, wt in tw.items()) - tc
        # positionsloggning (inträde/utträde per tillgång)
        for a in tw:
            if a not in open_pos: open_pos[a] = [m, 1.0, 0]
        for a in list(open_pos):
            if a not in tw:
                st, g, n = open_pos.pop(a); out["pos"].append((st, m, g - 1, n))
        for a in tw:
            open_pos[a][1] *= 1 + assets[a].get(m, 0.0); open_pos[a][2] += 1
        out["m"].append(m); out["r"].append(r); out["w"].append(dict(tw))
        g = 1 + r
        prev_w = {a: wt * (1 + assets[a].get(m, 0.0)) / g for a, wt in tw.items()} if g > 0 else {}
    for a, (st, g, n) in open_pos.items():
        out["pos"].append((st, None, g - 1, n))
    return out


def fixed(weights, start, end, assets=None, cost=None):
    assets = assets or ASSETS; cost = cost or COST
    ev = months(start, end); out = {"m": [], "r": [], "w": [], "turn": 0.0, "pos": []}
    prev = {}
    for m in ev:
        tc = sum(abs(weights.get(a, 0) - prev.get(a, 0)) * cost.get(a, 0) for a in set(weights) | set(prev))
        out["turn"] += sum(max(weights.get(a, 0) - prev.get(a, 0), 0) for a in set(weights) | set(prev))
        r = sum(w * assets[a][m] for a, w in weights.items()) - tc
        out["m"].append(m); out["r"].append(r); out["w"].append(weights)
        prev = {a: w * (1 + assets[a][m]) / (1 + r) for a, w in weights.items()}
    return out


def series_bh(r, start, end):
    ev = months(start, end)
    return {"m": ev, "r": [r[m] for m in ev], "w": [], "turn": 0.0, "pos": []}


def metrics(res, rf=None, a=None, b=None):
    rf = rf or ASSETS[SHORT]
    idx = [i for i, m in enumerate(res["m"]) if (a is None or m >= a) and (b is None or m <= b)]
    r = [res["r"][i] for i in idx]; ms = [res["m"][i] for i in idx]
    if len(r) < 12: return None
    eq = peak = 1.0; mdd = 0.0
    for x in r:
        eq *= 1 + x; peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
    yrs = len(r) / 12
    cagr = eq ** (1 / yrs) - 1
    ex = [x - rf.get(m, 0.0) for x, m in zip(r, ms)]
    mu = sum(ex) / len(ex); sd = math.sqrt(sum((x - mu) ** 2 for x in ex) / (len(ex) - 1))
    dn = math.sqrt(sum(min(x, 0) ** 2 for x in ex) / len(ex))
    vol = math.sqrt(sum((x - sum(r) / len(r)) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(12)
    pos = [p for p in res["pos"] if p[0] >= ms[0] and (p[1] is None or p[1] <= ms[-1])]
    closed = [p for p in pos if p[1] is not None]
    return {"from": ms[0], "to": ms[-1], "years": round(yrs, 1), "cagr": cagr, "vol": vol,
            "sharpe": mu / sd * math.sqrt(12) if sd else 0.0, "sortino": mu / dn * math.sqrt(12) if dn else 0.0,
            "maxdd": mdd, "calmar": cagr / -mdd if mdd < 0 else None,
            "turnover": res["turn"] / (len(res["r"]) / 12) if res["r"] else 0.0,
            "winrate": (sum(1 for p in closed if p[2] > 0) / len(closed)) if closed else None,
            "hold_months": (sum(p[3] for p in closed) / len(closed)) if closed else None,
            "positions": len(closed)}


def sharpe_ex(r, ms, rf=None):
    rf = rf or ASSETS[SHORT]
    ex = [x - rf.get(m, 0.0) for x, m in zip(r, ms)]
    mu = sum(ex) / len(ex); sd = math.sqrt(sum((x - mu) ** 2 for x in ex) / (len(ex) - 1))
    return mu / sd * math.sqrt(12) if sd else 0.0


def bootstrap_diff(a, b, n=3000, block=12, seed=7):
    """Stationär blockbootstrap av Sharpe-skillnad a-b (samma månader). Returnerar P(diff<=0)."""
    rnd = random.Random(seed); ms = a["m"]; T = len(ms)
    ra, rb = a["r"], b["r"]; worse = 0; diffs = []
    for _ in range(n):
        idx = []
        while len(idx) < T:
            s = rnd.randrange(T); L = max(1, int(rnd.expovariate(1 / block)))
            idx += [(s + j) % T for j in range(L)]
        idx = idx[:T]
        d = sharpe_ex([ra[i] for i in idx], [ms[i] for i in idx]) - sharpe_ex([rb[i] for i in idx], [ms[i] for i in idx])
        diffs.append(d); worse += d <= 0
    diffs.sort()
    return worse / n, diffs[int(0.05 * n)], diffs[int(0.95 * n)]


def norm_cdf(x): return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def dsr(ex_returns, n_trials, sr_trials_var):
    """Deflated Sharpe (Bailey & López de Prado) på månadsdata."""
    r = ex_returns; T = len(r); mu = sum(r) / T
    sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (T - 1)); sr = mu / sd
    sk = sum((x - mu) ** 3 for x in r) / T / sd ** 3; ku = sum((x - mu) ** 4 for x in r) / T / sd ** 4
    g = 0.5772156649
    from statistics import NormalDist
    z = NormalDist().inv_cdf
    sr0 = math.sqrt(sr_trials_var) * ((1 - g) * z(1 - 1 / n_trials) + g * z(1 - 1 / (n_trials * math.e))) if n_trials > 1 else 0
    return norm_cdf((sr - sr0) * math.sqrt(T - 1) / math.sqrt(1 - sk * sr + (ku - 1) / 4 * sr ** 2))


def pbo(matrix, S=10):
    """CSCV: matrix = lista av avkastningsserier (samma längd). Andel kombinationer där IS-bästa hamnar under median OOS."""
    from itertools import combinations
    T = len(matrix[0]); blk = T // S
    parts = [list(range(i * blk, (i + 1) * blk)) for i in range(S)]
    def sr(r, idx):
        x = [r[i] for i in idx]; mu = sum(x) / len(x); sd = math.sqrt(sum((v - mu) ** 2 for v in x) / (len(x) - 1))
        return mu / sd if sd else 0
    bad = tot = 0
    for c in combinations(range(S), S // 2):
        IS = [i for p in c for i in parts[p]]; OS = [i for p in range(S) if p not in c for i in parts[p]]
        is_sr = [sr(r, IS) for r in matrix]; best = max(range(len(matrix)), key=lambda k: is_sr[k])
        os_sr = [sr(r, OS) for r in matrix]
        rank = sum(1 for v in os_sr if v < os_sr[best]) / (len(matrix) - 1)
        bad += rank < 0.5; tot += 1
    return bad / tot
