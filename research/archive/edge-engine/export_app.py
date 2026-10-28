"""Gör edge.json till den mindre edge-app.json som appen hämtar. Kör efter edge.py."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "edge-app.json")


def met(m):
    if not m:
        return None
    return {k: (round(m[k], 4) if isinstance(m.get(k), float) else m.get(k)) for k in ("cagr", "sharpe", "maxdd", "trades", "years", "exposure", "vol") if k in m}


def main():
    e = json.load(open(os.path.join(HERE, "edge.json"), encoding="utf-8"))
    markets = []
    for mid, m in e["markets"].items():
        t = m.get("tradeListing")
        under = m.get("underlyingUsed") or m.get("underlying")
        markets.append({
            "id": mid, "name": m["name"], "assetClass": m["assetClass"], "kind": m["kind"], "underlying": under,
            "status": m.get("status", "ok"), "productCount": len(m.get("products") or []),
            "trade": None if not t else {k: t.get(k) for k in ("name", "ticker", "isin", "marketPlace", "currency", "avanzaUrl", "spread", "owners", "type")},
        })
    combos = []
    for x in e["combos"]:
        pv = x.get("product")
        combos.append({
            "market": x["market"], "family": x["family"], "params": x.get("params") or {},
            "evidence": x["evidence"], "riskReduction": x["riskReduction"],
            "excess": round(x["excessTest"], 4), "p": round(x["p"], 4), "q": round(x["q"], 4),
            "dsr": None if x.get("dsr") is None else round(x["dsr"], 4),
            "test": met(x["test"]), "bh": met(x["bhTest"]),
            "product": None if not pv else {"yahoo": pv["yahoo"], "name": pv["name"],
                                            "excess": None if pv.get("excess") is None else round(pv["excess"], 4),
                                            "corr": None if pv.get("trackingCorr") is None else round(pv["trackingCorr"], 3),
                                            "drift": None if pv.get("annualDriftVsUnderlying") is None else round(pv["annualDriftVsUnderlying"], 4),
                                            "years": (pv.get("test") or {}).get("years")},
            "checks": x["checks"], "subperiods": x["subperiods"], "variants": x["variants"],
            "excessTrain": None if x.get("excessTrain") is None else round(x["excessTrain"], 4),
        })
    meta = e["meta"]
    sel = meta.get("selectionOOS") or {}
    out = {
        "generated": meta["generated"], "mappingVerified": meta.get("mappingVerified"), "nCombos": meta["nCombos"],
        "pbo": meta.get("pbo"), "selection": {k: v for k, v in sel.items() if isinstance(v, (int, float))},
        "portfolio": meta.get("trainSelectedPortfolio"),
        "method": {k: (v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)) for k, v in meta["method"].items() if k != "families"},
        "families": meta["method"]["families"], "markets": markets, "combos": combos,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print("skrev", OUT, os.path.getsize(OUT), "byte,", len(combos), "kombinationer")


if __name__ == "__main__":
    main()
