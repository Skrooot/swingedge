"""SwingEdges hinkar som månadsavkastningar i SEK (från qa/swing/study3.py)."""
import json, sys, os, io, contextlib
SW = "C:/Users/fredrik/android-build/qa/swing"


CONFIRM_SRC = """btc_state, _on, _st = {}, False, 0
for d, c, m in zip(btc.dates, btc.c, btc_sma):
    if m is None: btc_state[d] = None; continue
    _flip = (c <= m) if _on else (c > m)
    _st = _st + 1 if _flip else 0
    if _st >= %d: _on, _st = not _on, 0
    btc_state[d] = _on"""


def load_swingedge(confirm=1):
    """Kör study3.py:s simulering (utan att skriva om dess resultatfil) och returnerar månadsavkastningar i SEK.
    confirm > 1: Bitcoin-trenden byter läge först efter så många stängningar i rad på andra sidan SMA150
    (start i kontanter; exakt på medelvärdet räknas som under), som appens Rules.CRYPTO_CONFIRM."""
    cwd = os.getcwd(); os.chdir(SW); sys.path.insert(0, SW)
    ns = {"__name__": "study3_import", "__file__": f"{SW}/study3.py"}
    real = json.dump
    json.dump = lambda *a, **k: None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            src = open(f"{SW}/study3.py", encoding="utf-8").read()
            if confirm > 1:
                old = "btc_state = {d: (c > m if m else None) for d, c, m in zip(btc.dates, btc.c, btc_sma)}"
                assert old in src; src = src.replace(old, CONFIRM_SRC % confirm)
            exec(src, ns)
    finally:
        json.dump = real; os.chdir(cwd)
    def monthly(res):
        out = {}
        for d, r in zip(res["dates"], res["r"]):
            out.setdefault(d[:7], 1.0); out[d[:7]] *= 1 + r
        ks = sorted(out)
        return {k: v - 1 for k, v in out.items() if k != ks[0] and k != ks[-1]}  # bort med ofullständiga kantmånader
    s = ns["system"]
    return {"SwingEdge 20/40/40": monthly(ns["sys_res"]["SwingEdge 20/40/40 (nuvarande)"]),
            "SwingEdge med guld": monthly(ns["sys_res"]["SwingEdge med guld i lika vikt"]),
            "Bitcoin Trend (hink)": monthly(s(ns["BASE"], sleeves=(1.0, 0.0, 0.0))),
            "S&P 500 Trend (hink)": monthly(s(ns["BASE"], sleeves=(0.0, 0.0, 1.0))),
            "Lika vikt (hink)": monthly(ns["equal"](ns["BASE"]))}


