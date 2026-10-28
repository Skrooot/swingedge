"""Oberoende referens för appens Backtests.btcOnProduct och sp500OnIndex: egen implementation från reglerna
(inte appens kod och inte engine.py). Skriver fixturen app/src/test/resources/backtest_ref.json."""
import json, math, sys
sys.stdout.reconfigure(encoding="utf-8")
D = "C:/Users/fredrik/android-build/qa/swing/data/"
def load(f): return [(r[0], r[4]) for r in json.load(open(D + f, encoding="utf-8"))["rows"] if r[4]]
btc, xbt, sp = load("BTC-USD.json"), load("BITCOIN-XBT.ST.json"), load("_GSPC.json")
sp = [x for x in sp if x[0] >= "1990-01-01"]

def sim(closes, w, cost):
    r = [0.0] * len(closes); pos = 0.0; trades = 0
    for t in range(1, len(closes)):
        eq = 1 + pos * (closes[t] / closes[t - 1] - 1)
        tgt = w[t - 1] if w[t - 1] is not None else 0.0
        if abs(tgt - pos) > 1e-9:
            eq *= 1 - abs(tgt - pos) * cost; trades += pos == 0; pos = tgt
        r[t] = eq - 1
    return r, trades

def metrics(dates, r):
    eq = peak = 1.0; mdd = 0.0
    for x in r: eq *= 1 + x; peak = max(peak, eq); mdd = min(mdd, eq / peak - 1)
    from datetime import date
    yrs = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 365.25
    mu = sum(r) / len(r); sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1))
    return {"cagr": eq ** (1 / yrs) - 1, "maxdd": mdd, "sharpe": mu / sd * math.sqrt(252)}

# Bitcoin: SMA150 på BTC-USD med tredagarsregeln (från 2.2): läget byter först efter tre stängningar i rad på
# andra sidan medelvärdet (över = close > SMA, exakt lika räknas som under), start i kontanter. Läget från
# BTC-dagar före produktdagen.
CONFIRM = 3
bd = [d for d, _ in btc]; bc = [c for _, c in btc]
state, on, streak = {}, False, 0
for i in range(149, len(bc)):
    above = bc[i] > sum(bc[i - 149:i + 1]) / 150
    streak = streak + 1 if above != on else 0
    if streak >= CONFIRM: on, streak = above, 0
    state[bd[i]] = on
# w[i] = läget som är känt före nästa produktdags öppning; sim handlar på stängningen den dagen,
# dvs. stängningen på första handelsdagen efter att BTC-stapeln blev klar (00:00 UTC)
from datetime import date, timedelta
w, k, cur = [], 0, None
for i, (d, _) in enumerate(xbt):
    nxt = xbt[i + 1][0] if i + 1 < len(xbt) else (date.fromisoformat(d) + timedelta(days=1)).isoformat()
    while k < len(bd) and bd[k] < nxt:
        if bd[k] in state: cur = state[bd[k]]
        k += 1
    w.append(None if cur is None else (1.0 if cur else 0.0))
xc = [c for _, c in xbt]; xd = [d for d, _ in xbt]
r, n = sim(xc, w, 0.004)
ref = {"btc": {"metrics": metrics(xd, r), "entries": n}}
# S&P 500: SMA200 på index, beslut på månadens sista stapel
sd_, sc = [d for d, _ in sp], [c for _, c in sp]
w, cur = [], None
for i in range(len(sc)):
    if i >= 199 and i + 1 < len(sc) and sd_[i + 1][:7] != sd_[i][:7]:
        cur = 1.0 if sc[i] > sum(sc[i - 199:i + 1]) / 200 else 0.0
    w.append(cur)
r2, n2 = sim(sc, w, 0.004)
ref["sp"] = {"metrics": metrics(sd_, r2), "entries": n2}
json.dump({"btc": {"dates": bd, "closes": bc}, "xbt": {"dates": xd, "closes": xc}, "sp": {"dates": sd_, "closes": sc}, "ref": ref},
          open("C:/Users/fredrik/android-build/swingedge/app/src/test/resources/backtest_ref.json", "w", encoding="utf-8"))
print(json.dumps(ref, indent=1))
