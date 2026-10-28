"""Bitcoin Trend: färre affärer? Jämför appens dagliga SMA150-regel med varianter som filtrerar bort snabba byten.
BTC-USD dagsstängning (Yahoo), signal på dagens stängning, position från nästa dag. 0,40 % kostnad per sida,
kontanter ger 0 %. Period 2015-06-01 – sista dagen i datat, plus delperioder. Avkastning i USD."""
import json, math, sys
sys.stdout.reconfigure(encoding="utf-8")

rows = [(r[0], r[4]) for r in json.load(open("C:/Users/fredrik/android-build/qa/swing/data/BTC-USD.json", encoding="utf-8"))["rows"] if r[4]]
D = [d for d, _ in rows]; C = [c for _, c in rows]
COST = 0.004

def sma(n):
    out, s = [None] * len(C), 0.0
    for i, c in enumerate(C):
        s += c
        if i >= n: s -= C[i - n]
        if i >= n - 1: out[i] = s / n
    return out

def month_end(i): return i + 1 < len(D) and D[i + 1][:7] != D[i][:7]
def week_end(i):  # söndag
    import datetime
    return datetime.date.fromisoformat(D[i]).weekday() == 6

def rule(n=150, band=0.0, confirm=1, check=None):
    m = sma(n); state = []; on = False; streak = 0
    for i, c in enumerate(C):
        if m[i] is None: state.append(False); continue
        want_on = c > m[i] * (1 + band); want_off = c < m[i] * (1 - band)
        flip = (want_off if on else want_on)
        streak = streak + 1 if flip else 0
        if (check is None or check(i)) and streak >= confirm:
            on = not on; streak = 0
        state.append(on)
    return state

def run(state, a, b):
    eq, peak, dd, rets, trades, inv, was = 1.0, 1.0, 0.0, [], 0, 0, None
    for i in range(1, len(C)):
        if not (a <= D[i] <= b): continue
        pos = state[i - 1]                       # beslut i går, gäller i dag
        r = (C[i] / C[i - 1] - 1) if pos else 0.0
        if was is not None and pos != was: r -= COST; trades += 1
        was = pos; inv += pos
        eq *= 1 + r; peak = max(peak, eq); dd = min(dd, eq / peak - 1); rets.append(r)
    n = len(rets); yrs = n / 365.25
    mu = sum(rets) / n; sd = math.sqrt(sum((x - mu) ** 2 for x in rets) / (n - 1))
    return {"cagr": eq ** (1 / yrs) - 1, "sharpe": mu / sd * math.sqrt(365), "maxdd": dd, "trades_yr": trades / yrs, "inv": inv / n}

V = {
    "App: daglig SMA150": rule(),
    "SMA150 + 3 % band": rule(band=0.03),
    "SMA150 + 5 % band": rule(band=0.05),
    "SMA150, 3 dagar i rad": rule(confirm=3),
    "SMA150, kontroll varje söndag": rule(check=week_end),
    "SMA150, kontroll vid månadsslut": rule(check=month_end),
    "SMA200, kontroll vid månadsslut": rule(n=200, check=month_end),
    "Köp och behåll": [True] * len(C),
}
P = [("2015-06-01", D[-1], "2015–2026"), ("2015-06-01", "2019-12-31", "2015–2019"), ("2020-01-01", D[-1], "2020–2026")]
print(f"{'Variant':34} | " + " | ".join(f"{lab:^31}" for _, _, lab in P))
print(f"{'':34} | " + " | ".join(f"{'år%':>6} {'Sh':>4} {'maxDD':>6} {'aff/år':>6} {'inv':>4}" for _ in P))
for k, st in V.items():
    print(f"{k:34} | " + " | ".join(
        (lambda r: f"{r['cagr']*100:6.1f} {r['sharpe']:4.2f} {r['maxdd']*100:6.0f} {r['trades_yr']:6.1f} {r['inv']*100:4.0f}")(run(st, a, b)) for a, b, _ in P))
