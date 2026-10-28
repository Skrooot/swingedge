"""Forskningsvariant (inte Börslabbets original): Global trendföljning med fler tillgångsslag.
Tillägg är USA-noterade ETF:er/krypto i SEK (Yahoo, justerad stängning). De är forskningsproxyer;
för handel via Avanza krävs UCITS-motsvarigheter (se mapping i SwingEdge research). Skriver results_ext.json."""
import json, sys, time, datetime, urllib.request, os
sys.stdout.reconfigure(encoding="utf-8")
import gtf
from gtf import ASSETS, run, metrics, bootstrap_diff, months, ffill, rets

EXTRA = {
    "Råvaror": {"Silver": "SLV", "Koppar": "CPER", "Platina": "PPLT", "Olja": "USO", "Naturgas": "UNG", "Råvaruindex": "DBC"},
    "Räntor": {"USA stat 20+": "TLT", "USA stat 7-10": "IEF", "Företagsobl IG": "LQD", "High yield": "HYG", "Realränta USA": "TIP"},
    "Real": {"Fastigheter USA": "VNQ", "Infrastruktur": "IGF"},
    "Sektorer": {"Teknik": "XLK", "Finans": "XLF", "Hälsovård": "XLV", "Energi": "XLE", "Industri": "XLI", "Dagligvaror": "XLP",
                 "Sällanköp": "XLY", "Material": "XLB", "Kraft": "XLU"},
    "Krypto": {"Bitcoin": "BTC-USD", "Ether": "ETH-USD"},
}
CACHE = "data/ext.json"


def yahoo(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=0&period2={int(time.time())}&interval=1d"
    j = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SwingEdge-research/1.0"}), timeout=60))
    r = j["chart"]["result"][0]; c = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or r["indicators"]["quote"][0]["close"]
    m = {}
    for t, x in zip(r["timestamp"], c):
        if x: m[datetime.datetime.fromtimestamp(t, datetime.UTC).strftime("%Y-%m")] = x
    return m


data = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
for g in EXTRA.values():
    for n, s in g.items():
        if s not in data:
            data[s] = yahoo(s); print("hämtade", s, min(data[s])); time.sleep(0.4)
json.dump(data, open(CACHE, "w", encoding="utf-8"))

usdsek = gtf.Y["SEK=X"]
EXT = {}
for grp, g in EXTRA.items():
    for n, s in g.items():
        EXT[n] = rets(ffill(data[s], usdsek))
cost = dict(gtf.COST); cost.update({n: 0.004 for n in EXT})

START = "2013-01"  # koppar-ETF:n (CPER) har 12 månaders historik
END = gtf.LAST
U = {"Original (9 tillgångar)": dict(ASSETS)}
for grp, g in EXTRA.items():
    U[f"+ {grp}"] = {**ASSETS, **{n: EXT[n] for n in g}}
U["+ Allt"] = {**ASSETS, **EXT}
res = {"period": [START, END], "variants": {}}
base = run(U["Original (9 tillgångar)"], START, END, cost=cost)
for name, uni in U.items():
    for top in (3, max(3, round(len(uni) / 3))) if name == "+ Allt" else (3,):
        s = run(uni, START, END, top=top, cost=cost)
        key = name if top == 3 else f"{name}, topp {top} (en tredjedel)"
        m = metrics(s); p = bootstrap_diff(s, base) if name != "Original (9 tillgångar)" else None
        res["variants"][key] = {"n_assets": len(uni), "full": m, "since_2018": metrics(s, a="2018-01"),
                                "p_not_better_than_original": p[0] if p else None,
                                "exposure_added": sum(w for ww in s["w"] for a, w in ww.items() if a in EXT) / len(s["w"])}
        print(f"{key[:44]:44} n={len(uni):2} CAGR {m['cagr']*100:5.1f} vol {m['vol']*100:5.1f} Sharpe {m['sharpe']:.2f} MDD {m['maxdd']*100:4.0f} oms {m['turnover']*100:4.0f}"
              f" | 2018– {res['variants'][key]['since_2018']['sharpe']:.2f} | p(ej bättre) {p[0] if p else '–'} | andel tillägg {res['variants'][key]['exposure_added']:.2f}")
json.dump(res, open("results_ext.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
