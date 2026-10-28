"""Strategigenerator och sökning: slumpad bred screening, successive halving och evolutionär lokal förfining.

Valet av metod: sökutrymmet är diskret och blandat (kategoriska byggstenar + få numeriska parametrar per
byggsten), så slumpsökning med tidig gallring ger bred täckning billigt, och lokal sökning över grannparametrar
förfinar de bästa. Bayesiansk optimering (Optuna) tillför lite i ett sådant rum och används inte.
All utvärdering här sker på utvecklingsdata; validerings- och holdoutperioderna nås inte från den här modulen.
"""
import math
import multiprocessing as mp
import os
from collections import OrderedDict

import numpy as np

from . import config
from . import fast
from . import strategies as S
from .data import build_panel

_W = {}


class LRUIndicators(S.Indicators):
    def __init__(self, panel, size=24):
        super().__init__(panel)
        self.cache = OrderedDict(); self.size = size

    def get(self, key, fn):
        if key in self.cache:
            self.cache.move_to_end(key); return self.cache[key]
        v = fn(); self.cache[key] = v
        if len(self.cache) > self.size:
            self.cache.popitem(last=False)
        return v


def subpanel(panel, cols):
    """Panel med bara kolumnerna `cols` (så indikatorer per universum blir små)."""
    from .data import Panel
    c = np.asarray(cols, dtype=np.int64)
    return Panel(panel.cal, [panel.ins[j] for j in c], panel.close[:, c], panel.high[:, c], panel.low[:, c], panel.volume[:, c],
                 panel.ret[:, c], panel.avail[:, c], panel.fresh[:, c], panel.proxy[:, c], panel.price_sek[:, c], panel.fx,
                 panel.bench, panel.version, {i.id: panel.issues.get(i.id, []) for i in (panel.ins[j] for j in c)})


def universe_cols(panel, name):
    pred = S.UNIVERSES[name]
    return [j for j, i in enumerate(panel.ins) if pred(i)]


class Evaluator:
    """Håller panel, delpaneler och indikatorer per universum i en process."""

    def __init__(self, panel=None):
        self.panel = panel or build_panel()
        self.subs = {}

    def sub(self, universe):
        if universe not in self.subs:
            cols = universe_cols(self.panel, universe)
            sp = subpanel(self.panel, cols)
            if len(self.subs) >= 3:                       # högst tre universum i minnet per process
                self.subs.pop(next(iter(self.subs)))
            self.subs[universe] = (sp, LRUIndicators(sp))
        return self.subs[universe]

    def run(self, spec, start, end, stress=1.0, engine="fast"):
        sp, ind = self.sub(spec["universe"])
        if len(sp.ins) == 0:
            return None
        W, D, mode = S.targets(spec, ind, list(range(len(sp.ins))))
        if engine == "fast":
            return fast.run(sp, W, D, mode, start, end, stress)
        from . import exact
        return exact.run_panel(sp, W, D, mode, start, end, stress)

    def benchmark(self, universe, start, end):
        sp, _ = self.sub(universe)
        return fast.benchmark(sp, list(range(len(sp.ins))), start, end)


def score(summary, spec, min_years=3.0):
    """Förregistrerad målfunktion: Sharpe efter kostnad, straff för nedgång bortom −30 % och för komplexitet.
    Returnerar (poäng, skäl att förkasta eller None)."""
    if summary is None:
        return -math.inf, "för kort historik"
    if summary["years"] < min_years:
        return -math.inf, "för kort historik"
    if summary["cagr"] <= 0:
        return -math.inf, "ingen nettoavkastning"
    need = config.GATES["min_trades_per_year"][spec["schedule"]] * 0.5
    if summary.get("trades_per_year", 0) < need and spec["entry"]["type"] != "always":
        return -math.inf, "för få affärer"
    s = summary["sharpe"] - 2.0 * max(0.0, -summary["maxdd"] - 0.30) - 0.03 * S.complexity(spec)
    return s, None


def _init(seed):
    _W["ev"] = Evaluator()
    np.random.seed(seed)


def _task(args):
    spec, start, end, stress = args
    try:
        res = _W["ev"].run(spec, start, end, stress)
        summ = res["summary"] if res else None
        sc, why = score(summ, spec)
        out = {"summary": summ, "avg_hold_days": res.get("avg_hold_days") if res else None}
        return S.spec_id(spec), spec, out, sc, why
    except Exception as e:  # en trasig kandidat ska inte stoppa omgången, men felet registreras
        return S.spec_id(spec), spec, {"error": repr(e)}, -math.inf, "fel: " + repr(e)[:120]


def evaluate_many(specs, start, end, stress=1.0, workers=config.MAX_WORKERS, seed=config.SEED):
    """Kör specifikationer parallellt. Grupperas per universum så att indikatorcachen återanvänds."""
    specs = sorted(specs, key=lambda s: s["universe"])
    args = [(s, start, end, stress) for s in specs]
    if workers <= 1:
        _init(seed)
        return [_task(a) for a in args]
    ctx = mp.get_context("spawn")
    with ctx.Pool(workers, initializer=_init, initargs=(seed,)) as pool:
        chunk = max(1, len(args) // (workers * 8))
        return list(pool.imap(_task, args, chunksize=chunk))


def generate(n, seed=config.SEED, exclude=()):
    rng = np.random.default_rng(seed)
    seen = set(exclude); out = []
    tries = 0
    while len(out) < n and tries < n * 50:
        tries += 1
        s = S.sample(rng)
        k = S.spec_id(s)
        if k not in seen:
            seen.add(k); out.append(s)
    return out


def mutate(spec, rng, k):
    """k barn: grannparametrar plus enstaka byte av exit, filter eller schema (en ändring per barn)."""
    nb = S.neighbors(spec)
    kids = []
    for _ in range(k):
        if nb and rng.random() < 0.7:
            kids.append(nb[rng.integers(len(nb))])
        else:
            s = dict(spec)
            part = ["exit", "filter", "schedule", "sizing", "rank"][rng.integers(5)]
            sample = S.sample(rng)
            s[part] = sample[part]
            kids.append(S.normalize(s))
    return {S.spec_id(x): x for x in kids}.values()
