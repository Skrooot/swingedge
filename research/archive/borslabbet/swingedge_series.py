"""SwingEdges hinkar som månadsavkastningar i SEK (från qa/swing/study3.py)."""
import json, sys, os, io, contextlib
SW = "C:/Users/fredrik/android-build/qa/swing"


def load_swingedge():
    """Kör study3.py:s simulering (utan att skriva om dess resultatfil) och returnerar månadsavkastningar i SEK."""
    cwd = os.getcwd(); os.chdir(SW); sys.path.insert(0, SW)
    ns = {"__name__": "study3_import", "__file__": f"{SW}/study3.py"}
    real = json.dump
    json.dump = lambda *a, **k: None
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            exec(open(f"{SW}/study3.py", encoding="utf-8").read(), ns)
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


