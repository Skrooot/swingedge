"""Hämtar månadsserier (NAV i SEK, efter fondavgifter) för Global trendföljning från Avanzas publika fond-API
samt guld (Yahoo) som månadsslut i SEK. Sparar data/funds.json."""
import json, time, datetime, urllib.request
import av
FUNDS = {  # nyckel: orderbookId, namn
    1983: "SEB Sverigefond A", 159608: "Länsförsäkringar Sverige Index",
    581: "Skandia Europa Exponering", 1505: "Storebrand USA A SEK", 1263: "Skandia Japan Exponering",
    2155: "Handelsbanken Tillväxtmarknad A1", 487076: "Länsförsäkringar Tillväxtmarknad Index A",
    2008: "Swedbank Robur Småbolagsfond Sverige A", 789175: "PLUS Småbolag Sverige Index",
    2098: "Carnegie Obligationsfond A", 2122: "SEB Obligationsfond SEK A", 2028: "Handelsbanken Kortränta Defensiv A1",
    2063: "SEB Likviditetsfond SEK A", 2332: "Storebrand Global All Countries A SEK",
}
def month(ms): return datetime.datetime.fromtimestamp(ms/1000, datetime.UTC).strftime("%Y-%m")
out = {"funds": {}, "yahoo": {}, "fetched": datetime.date.today().isoformat()}
for i, n in FUNDS.items():
    d = av.get(f"https://www.avanza.se/_api/fund-guide/chart/{i}/infinity?raw=true")["dataSerie"]
    g = av.get(f"https://www.avanza.se/_api/fund-guide/guide/{i}")
    s = {}
    for p in d:
        if p["y"] is not None:
            # punkten har tidsstämpeln midnatt svensk tid den 1:a i månaden men värdet är månadens sista NAV (kontrollerat mot SPY i SEK); +12 h ger rätt månad
            s[month(p["x"] + 12*3600*1000)] = p["y"]
    out["funds"][str(i)] = {"name": n, "isin": g.get("isin"), "fee": g.get("productFee"), "index": g.get("indexFund"),
                            "start": g.get("startDate"), "currency": g.get("currency"), "series": s}
    print(i, n, len(s), min(s), max(s)); time.sleep(0.5)
def yahoo(sym):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?period1=0&period2={int(time.time())}&interval=1d"
    j = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "SwingEdge-research/1.0"}), timeout=60))
    r = j["chart"]["result"][0]; ts = r["timestamp"]; c = r["indicators"]["quote"][0]["close"]
    ac = r["indicators"].get("adjclose", [{}])[0].get("adjclose") or c
    m = {}
    for t, x in zip(ts, ac):
        if x: m[datetime.datetime.fromtimestamp(t, datetime.UTC).strftime("%Y-%m")] = x  # sista handelsdagen i månaden vinner
    return m
for sym in ["GC=F", "SEK=X", "4GLD.DE", "EURSEK=X"]:
    out["yahoo"][sym] = yahoo(sym); print(sym, len(out["yahoo"][sym]), min(out["yahoo"][sym]))
json.dump(out, open("data/funds.json", "w", encoding="utf-8"), ensure_ascii=False)
