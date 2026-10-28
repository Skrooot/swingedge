"""Dagliga signaler för den godkända produktionsstrategin och export till Android (api/production.json).

Appen räknar i dag själv sin strategi på telefonen. Filen här är kontraktet för en framtida champion: den
innehåller bara den godkända strategin, dagens målvikter, åtgärder och Avanza-länkar, inga forskningsdetaljer.
Kör: python -E -m quant.production [--end YYYY-MM-DD]
"""
import datetime as dt
import json
import os
import sys

import numpy as np

from . import champion, config
from . import strategies as S
from .data import build_panel
from .search import LRUIndicators, subpanel, universe_cols

API = os.path.join(config.ROOT, "api", "production.json")


def today_signals(end=None):
    ch = champion.ensure_incumbent()
    end = end or (dt.date.today() - dt.timedelta(days=1)).isoformat()   # senaste färdiga stängning
    panel = build_panel(end=end)
    if ch["spec"] == "incumbent":
        ids = panel.ids()
        cols = [ids.index(k) for k in ("bitcoin", "omxs30", "sp500", "gold")]
        sp = subpanel(panel, cols)
        W, D, mode = champion.incumbent_targets(LRUIndicators(sp))
    else:
        cols = universe_cols(panel, ch["spec"]["universe"])
        sp = subpanel(panel, cols)
        W, D, mode = S.targets(ch["spec"], LRUIndicators(sp), list(range(len(sp.ins))))
    t = len(sp.cal) - 1
    last_dec = int(np.nonzero(D[: t + 1])[0][-1])
    prev_dec = int(np.nonzero(D[:last_dec])[0][-1]) if D[:last_dec].any() else None
    rows = []
    for j, i in enumerate(sp.ins):
        w, w0 = float(W[last_dec, j]), float(W[prev_dec, j]) if prev_dec is not None else 0.0
        action = "KÖP" if w > 1e-9 and w0 <= 1e-9 else "SÄLJ" if w <= 1e-9 and w0 > 1e-9 else "BEHÅLL" if w > 1e-9 else "AVVAKTA"
        rows.append({"id": i.id, "name": i.avanza.get("name", i.name), "isin": i.avanza.get("isin"), "avanzaUrl": i.avanza.get("url"),
                     "targetWeight": round(w, 4), "action": action, "lastClose": float(sp.close[t, j])})
    out = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "asOf": str(sp.cal[t]), "decisionDate": str(sp.cal[last_dec]),
           "strategy": {"version": ch["version"], "name": ch["name"], "rules": ch.get("rules") or S.describe(ch["spec"]),
                        "approvedBy": ch["approved_by"], "approvedAt": ch["approved_at"]},
           "instruments": sorted(rows, key=lambda r: -r["targetWeight"]),
           "cash": round(1 - sum(r["targetWeight"] for r in rows), 4),
           "disclaimer": "Forskningsresultat, inte investeringsråd. Historiska resultat garanterar inget om framtiden."}
    os.makedirs(os.path.dirname(API), exist_ok=True)
    json.dump(out, open(API, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return out


if __name__ == "__main__":
    args = sys.argv[1:]
    r = today_signals(args[args.index("--end") + 1] if "--end" in args else None)
    print(json.dumps(r, ensure_ascii=False, indent=1))
