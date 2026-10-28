"""Filter mot falska signaler från tradingkurser/litteratur, mot SMA150 med tredagarsregeln, på samma 436 instrument
som study_sma3d_many.py (data från dess cache). Varje familj körs med flera inställningar; vi redovisar mediantal över
instrumenten för familjens mittinställning och hur ofta familjen slår tredagarsregeln.
ATR approximeras med medelvärdet av |dagsförändring| (bara stängningskurser finns för alla instrument).
Kostnad 0,2 % per byte (kryptor 0,4 %), kontanter 0 %, signal på stängning, position nästa dag, från 2000."""
import json, math, os, sys, glob, statistics, datetime, collections
getattr(sys.stdout, "reconfigure", lambda **k: None)(encoding="utf-8")
SW = "C:/Users/fredrik/android-build/qa/swing/data"; MANY = "C:/Users/fredrik/android-build/qa/bl/data/many"; CR = "C:/Users/fredrik/android-build/qa/bl/data/crypto"
CATS = {"Index": "_", "Råvaror": "=F", "Valutor": "=X"}

U = []
for f in glob.glob(f"{SW}/*.ST.json"):
    U.append(("Svenska aktier", [(r[0], r[4]) for r in json.load(open(f, encoding="utf-8"))["rows"] if r[4]]))
for f in glob.glob(f"{MANY}/*.json"):
    b = os.path.basename(f)[:-5]
    if b in ("XACT-OMXS30.ST",): continue
    cat = "Index" if b.startswith("_") or b == "000001.SS" else "Råvaror" if b.endswith("_F") else "Valutor" if b.endswith("_X") else \
          "Räntor/ETF" if b in "TLT IEF LQD HYG GLD SLV VNQ EEM EFA EWJ EWG EWU EWZ EWC EWA FXI EWY EWT EWW EWS EWH EWL EWP EWI EWQ EWD XLB XLE XLF XLI XLK XLP XLU XLV XLY SPY QQQ IWM DIA".split() else "USA-aktier"
    U.append((cat, json.load(open(f))))
for f in glob.glob(f"{CR}/*.json"): U.append(("Kryptor", json.load(open(f))))

# ---- signalfamiljer: varje funktion ger tillstånd (True = investerad) per stapel ----
def sma(C, n):
    out, s = [None] * len(C), 0.0
    for i, c in enumerate(C):
        s += c
        if i >= n: s -= C[i - n]
        if i >= n - 1: out[i] = s / n
    return out
def atr(C, n=20):
    out, s, q = [None] * len(C), 0.0, []
    for i in range(1, len(C)):
        x = abs(C[i] - C[i - 1]); q.append(x); s += x
        if len(q) > n: s -= q.pop(0)
        if len(q) == n: out[i] = s / n
    return out

def f_confirm(D, C, k=3, n=150):
    m = sma(C, n); on, st, out = False, 0, []
    for i, c in enumerate(C):
        if m[i] is None: out.append(False); continue
        flip = c < m[i] if on else c > m[i]; st = st + 1 if flip else 0
        if st >= k: on, st = not on, 0
        out.append(on)
    return out

def f_atrband(D, C, k=1.0, n=150):
    """Köp när stängning > SMA + k·ATR, sälj när < SMA − k·ATR."""
    m, a = sma(C, n), atr(C); on, out = False, []
    for i, c in enumerate(C):
        if m[i] is None or a[i] is None: out.append(False); continue
        if not on and c > m[i] + k * a[i]: on = True
        elif on and c < m[i] - k * a[i]: on = False
        out.append(on)
    return out

def f_weekly(D, C, n=30):
    """Weinstein: veckostängning mot 30-veckors medelvärde, kontroll vid veckans sista stapel."""
    wk = [datetime.date.fromisoformat(d).isocalendar()[:2] for d in D]
    ends = [i for i in range(len(D)) if i + 1 == len(D) or wk[i + 1] != wk[i]]
    wc = [C[i] for i in ends]; wm = sma(wc, n); out = [False] * len(C); on = False; j = 0
    for idx, i in enumerate(ends):
        if wm[idx] is not None: on = wc[idx] > wm[idx]
        nxt = ends[idx + 1] if idx + 1 < len(ends) else len(C) - 1
        for t in range(i, nxt): out[t] = on
    out[-1] = on
    return out

def f_monthly(D, C, n=10, band=0.0):
    """Faber: månadsstängning mot 10-månaders medelvärde (± band)."""
    ends = [i for i in range(len(D)) if i + 1 == len(D) or D[i + 1][:7] != D[i][:7]]
    mc = [C[i] for i in ends]; mm = sma(mc, n); out = [False] * len(C); on = False
    for idx, i in enumerate(ends):
        if mm[idx] is not None:
            if not on and mc[idx] > mm[idx] * (1 + band): on = True
            elif on and mc[idx] < mm[idx] * (1 - band): on = False
        nxt = ends[idx + 1] if idx + 1 < len(ends) else len(C) - 1
        for t in range(i, nxt): out[t] = on
    out[-1] = on
    return out

def f_supertrend(D, C, n=10, k=3.0):
    """Supertrend på stängningar: följande stopp k·ATR under/över kursen."""
    a = atr(C, n); on, stop, out = False, None, []
    for i, c in enumerate(C):
        if a[i] is None: out.append(False); continue
        if on:
            stop = max(stop, c - k * a[i])
            if c < stop: on, stop = False, c + k * a[i]
        else:
            stop = c + k * a[i] if stop is None else min(stop, c + k * a[i])
            if c > stop: on, stop = True, c - k * a[i]
        out.append(on)
    return out

def f_chandelier(D, C, k=3.0, look=22, n=150):
    """Köp med tredagarsregeln över SMA150; sälj på tredagarsregeln eller när kursen faller k·ATR från högsta på 22 dagar."""
    base, a = f_confirm(D, C, 3, n), atr(C, 22); on, out = False, []
    for i, c in enumerate(C):
        if not on and base[i] and (i == 0 or not base[i - 1] or not out or True):
            if base[i] and (i == 0 or not base[i - 1]): on = True
        if on and (not base[i] or (a[i] and c < max(C[max(0, i - look + 1):i + 1]) - k * a[i])): on = False
        out.append(on)
    return out

def f_adx_like(D, C, n=150, eff=0.25, look=50):
    """Tredagarsregeln, men nya köp bara när trenden är tydlig (Kaufmans effektivitetskvot över 50 dagar > eff)."""
    base = f_confirm(D, C, 3, n); on, out = False, []
    for i, c in enumerate(C):
        if i >= look:
            path = sum(abs(C[t] - C[t - 1]) for t in range(i - look + 1, i + 1)); er = abs(C[i] - C[i - look]) / path if path else 0
        else: er = 0
        if not on and base[i] and (i == 0 or not base[i - 1] or er > eff) and er > eff: on = True
        if on and not base[i]: on = False
        out.append(on)
    return out

FAM = {
    "SMA150 + 3 dagar (referens)":        [lambda D, C: f_confirm(D, C, 3)],
    "SMA150 + 2/4/5 dagar":               [lambda D, C, k=k: f_confirm(D, C, k) for k in (2, 4, 5)],
    "SMA150 + ATR-band (0,5/1/2 ATR)":    [lambda D, C, k=k: f_atrband(D, C, k) for k in (0.5, 1.0, 2.0)],
    "Weinstein 30 v (26/30/40 v)":        [lambda D, C, n=n: f_weekly(D, C, n) for n in (26, 30, 40)],
    "Faber 10 mån (8/10/12)":             [lambda D, C, n=n: f_monthly(D, C, n) for n in (8, 10, 12)],
    "Faber 10 mån ± 2/5 % band":          [lambda D, C, b=b: f_monthly(D, C, 10, b) for b in (0.02, 0.05)],
    "Supertrend (10,3)/(20,3)/(10,4)":    [lambda D, C, n=n, k=k: f_supertrend(D, C, n, k) for n, k in ((10, 3), (20, 3), (10, 4))],
    "3 dagar + chandelier-exit (3/4/5)":  [lambda D, C, k=k: f_chandelier(D, C, k) for k in (3.0, 4.0, 5.0)],
    "3 dagar + effektivitetsfilter":      [lambda D, C, e=e: f_adx_like(D, C, 150, e) for e in (0.15, 0.25, 0.35)],
}

def bt(D, C, st, cost, start="2000-01-01", n0=200):
    eq, peak, dd, rets, tr, d0 = 1.0, 1.0, 0.0, [], 0, None
    for i in range(max(1, n0), len(C)):
        if D[i] < start: continue
        d0 = d0 or D[i]; pos = st[i - 1]
        r = (C[i] / C[i - 1] - 1) if pos else 0.0
        if i - 1 >= 1 and st[i - 1] != st[i - 2]: r -= cost; tr += 1
        eq *= 1 + r; peak = max(peak, eq); dd = min(dd, eq / peak - 1); rets.append(r)
    if len(rets) < 500: return None
    yrs = (datetime.date.fromisoformat(D[-1]) - datetime.date.fromisoformat(d0)).days / 365.25
    sd = statistics.pstdev(rets)
    return {"cagr": eq ** (1 / yrs) - 1 if eq > 0 else -1, "sh": statistics.mean(rets) / sd * math.sqrt(len(rets) / yrs) if sd else 0, "dd": dd, "tr": tr / yrs}

R = collections.defaultdict(lambda: collections.defaultdict(list))   # fam -> variant -> [(cat, res)]
for cat, rows in U:
    rows = [r for r in rows if r[1] and r[1] > 0]
    if len(rows) < 800: continue
    D, C = [r[0] for r in rows], [r[1] for r in rows]; cost = 0.004 if cat == "Kryptor" else 0.002
    ok = True; tmp = {}
    for fam, vs in FAM.items():
        for vi, f in enumerate(vs):
            r = bt(D, C, f(D, C), cost)
            if r is None: ok = False; break
            tmp[(fam, vi)] = r
        if not ok: break
    if ok:
        for (fam, vi), r in tmp.items(): R[fam][vi].append((cat, r))

med = statistics.median
ref = [r for _, r in R["SMA150 + 3 dagar (referens)"][0]]
cats = sorted({c for c, _ in R["SMA150 + 3 dagar (referens)"][0]})
print(f"{len(ref)} instrument. Kolumner: median Sharpe / största fall / byten per år, andel instrument där Sharpe > tredagarsregeln,")
print("Sharpe-skillnad mot tredagarsregeln (medel ±SE), sämsta inställningen i familjen, och antal kategorier (av 7) där familjen slår referensen i median.\n")
for fam, vs in FAM.items():
    rows = []
    for vi in range(len(vs)):
        L = [r for _, r in R[fam][vi]]
        d = [a["sh"] - b["sh"] for a, b in zip(L, ref)]
        rows.append((vi, L, d))
    vi, L, d = rows[len(rows) // 2]
    worst = min(statistics.mean(x[2]) for x in rows)
    catwin = 0
    for c in cats:
        idx = [i for i, (cc, _) in enumerate(R[fam][vi]) if cc == c]
        if med([d[i] for i in idx]) > 0: catwin += 1
    print(f"{fam:34} Sh {med(x['sh'] for x in L):.2f}  DD {med(x['dd'] for x in L)*100:4.0f} %  byten {med(x['tr'] for x in L):4.1f}  "
          f"slår ref {sum(x > 0 for x in d)/len(d)*100:3.0f} %  diff {statistics.mean(d):+.3f}±{statistics.stdev(d)/math.sqrt(len(d)) if len(d)>1 else 0:.3f}  "
          f"sämsta {worst:+.3f}  kategorier {catwin}/{len(cats)}")
