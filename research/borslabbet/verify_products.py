"""Kontrollerar appens produkter mot Avanzas publika API: namn, ISIN, handelsplats, valuta, köpbarhet, avgift."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
import av
P = [("XBT", "certificate", 563966, "SE0007126024"), ("XACT", "etf", 5510, "SE0000693293"), ("SXR8", "etf", 1063851, "IE00B5BMR087"),
     ("GOLD", "certificate", 1077331, "DE000A0S9GB0"), ("AVWC", "etf", 1858742, "IE000RJECXS5"), ("AVWS", "etf", 1858741, "IE0003R87OG3"),
     ("AVEM", "etf", 1918246, "IE000K975W13")]
F = [("SE", 159608, "SE0002656611"), ("EU", 581, "SE0000810772"), ("US", 1505, "SE0000594111"), ("JP", 1263, "SE0000810764"),
     ("EM", 487076, "SE0005796331"), ("SMB", 789175, "SE0010323642"), ("BOND", 2098, "SE0000709313"), ("SHORT", 2028, "SE0000356305")]
out = []
for k, kind, i, isin in P:
    url = f"https://www.avanza.se/_api/market-guide/certificate/{i}" if kind == "certificate" else f"https://www.avanza.se/_api/market-etf/{i}"
    try: g = av.get(url)
    except Exception as e: out.append((k, "FEL", str(e))); continue
    lst = g.get("listing", {}); ki = g.get("keyIndicators", {})
    fee = ki.get("managementFee") or ki.get("productFee") or g.get("fee")
    out.append((k, g.get("name"), g.get("isin"), "ISIN OK" if g.get("isin") == isin else "ISIN AVVIKER", g.get("tradable"),
                lst.get("marketPlaceName"), lst.get("currency"), {kk: ki.get(kk) for kk in ("leverage", "managementFee", "spread") if kk in ki}, fee))
for k, i, isin in F:
    g = av.get(f"https://www.avanza.se/_api/fund-guide/guide/{i}")
    out.append((k, g.get("name"), g.get("isin"), "ISIN OK" if g.get("isin") == isin else "ISIN AVVIKER", "fond", g.get("currency"), "avgift", g.get("productFee"), "navDate", g.get("navDate")))
for o in out: print(" | ".join(map(str, o)))
