"""Forskningsomgång: inventering -> screening -> fördjupning -> förfining -> robusthet -> validering -> holdout.

Kör: python -E -m quant.run_research [--round R1] [--screen N] [--workers K]
Omgången kan avbrytas och återupptas: redan registrerade experiment körs inte om. Holdout körs högst en gång
per omgång och bara för en kandidat som klarat alla valideringskrav (annars förblir holdout orörd).
"""
import argparse
import json
import math
import os
import sys
import time

import numpy as np

from . import champion, config, exact, fast, stats, validate
from . import metrics as M
from . import strategies as S
from .data import build_panel, inventory
from .registry import Registry
from .search import Evaluator, evaluate_many, generate, mutate, score

DEV_A = (config.DEV[0], "2007-12-31")


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def stage(reg, rid, name, specs, period, method, seed, n_comb, workers):
    """Kör de specifikationer som saknas i registret och returnerar alla resultat för steget."""
    todo = [s for s in specs if not reg.done(rid, name, S.spec_id(s))]
    if todo:
        log(f"{name}: kör {len(todo)} av {len(specs)}")
        for k, (sid, spec, out, sc, why) in enumerate(evaluate_many(todo, *period, workers=workers, seed=seed)):
            reg.log(rid, name, sid, spec, S.describe(spec), method, seed, n_comb, period, out,
                    None if sc == -math.inf else sc, "förkastad" if why else "kandidat", why)
            if k % 200 == 0:
                reg.commit()
        reg.commit()
    want = {S.spec_id(s) for s in specs}
    return [r for r in reg.results(rid, name) if r["spec_id"] in want]


def ranked(rows):
    ok = [r for r in rows if r["score"] is not None and r["status"] == "kandidat"]
    return sorted(ok, key=lambda r: -r["score"])


def diverse(rows, n, per_family=2, per_universe=None):
    """Högst `per_family` kandidater per (universum, entry-typ) och högst `per_universe` per universum, så att
    finalisterna inte är varianter av samma idé eller domineras av ett universum."""
    out, cnt, cu = [], {}, {}
    for r in rows:
        k = (r["spec"]["universe"], r["spec"]["entry"]["type"]); u = r["spec"]["universe"]
        if cnt.get(k, 0) < per_family and (per_universe is None or cu.get(u, 0) < per_universe):
            out.append(r); cnt[k] = cnt.get(k, 0) + 1; cu[u] = cu.get(u, 0) + 1
        if len(out) == n:
            break
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default="R1")
    ap.add_argument("--screen", type=int, default=config.N_SCREEN)
    ap.add_argument("--workers", type=int, default=config.MAX_WORKERS)
    a = ap.parse_args(argv)
    t_start = time.time()
    rid = a.round
    out_dir = config.RESULTS_DIR; os.makedirs(out_dir, exist_ok=True)
    log("bygger panel")
    panel = build_panel()
    ev = Evaluator(panel)
    reg = Registry()
    cfg = {k: getattr(config, k) for k in ("DEV", "VALIDATION", "HOLDOUT", "WF_FOLDS", "COURTAGE", "FX_FEE", "SLIPPAGE", "GATES",
                                          "SEED", "N_SCREEN", "HALVING_KEEP", "N_REFINE", "REFINE_GENERATIONS", "REFINE_CHILDREN",
                                          "N_FINALISTS", "CAPITAL_SEK")}
    cfg["N_SCREEN"] = a.screen
    reg.new_round(rid, cfg, panel.version, config.SEED, "Forskningsomgång 1: bred screening på hela universumet")
    report = {"round": rid, "data_version": panel.version, "periods": {"dev": config.DEV, "validation": config.VALIDATION,
              "holdout": config.HOLDOUT}, "gates": config.GATES}

    # 1. inventering
    inv = inventory(panel)
    json.dump(inv, open(os.path.join(out_dir, f"{rid}_inventory.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    report["inventory"] = {"instruments": len(inv), "tradable": sum(r["tradable"] for r in inv),
                           "by_group": {g: sum(r["group"] == g for r in inv) for g in sorted({r["group"] for r in inv})},
                           "data_issues": sum(r["issues"] for r in inv)}

    # 2. bred screening på första halvan av utvecklingsdata
    specs = generate(a.screen, config.SEED)
    rows = stage(reg, rid, "screen", specs, DEV_A, "random", config.SEED, a.screen, a.workers)
    r1 = ranked(rows)
    keep1 = r1[: int(len(specs) * config.HALVING_KEEP[0])]
    log(f"screen: {len(r1)} giltiga av {len(rows)}, {len(keep1)} vidare")

    # 3. fördjupning: hela utvecklingsperioden
    rows2 = stage(reg, rid, "dev", [r["spec"] for r in keep1], config.DEV, "successive_halving", config.SEED, a.screen, a.workers)
    r2 = ranked(rows2)
    keep2 = r2[: max(config.N_REFINE, int(len(specs) * config.HALVING_KEEP[1]))]
    log(f"dev: {len(r2)} giltiga, {len(keep2)} vidare")

    # 4. förfining: evolutionär lokal sökning på utvecklingsdata
    rng = np.random.default_rng(config.SEED + 1)
    pool = {r["spec_id"]: r for r in keep2}
    parents = diverse(r2, config.N_REFINE, per_family=3)
    for g in range(config.REFINE_GENERATIONS):
        kids = []
        for p_ in parents:
            kids += list(mutate(p_["spec"], rng, config.REFINE_CHILDREN))
        kids = [k for k in {S.spec_id(k): k for k in kids}.values() if S.spec_id(k) not in pool]
        rows3 = stage(reg, rid, "refine", kids, config.DEV, "evolutionary", config.SEED + 1 + g, len(kids), a.workers)
        for r in ranked(rows3):
            pool[r["spec_id"]] = r
        parents = diverse(sorted(pool.values(), key=lambda r: -r["score"]), config.N_REFINE, per_family=3)
        log(f"förfining {g + 1}: {len(kids)} barn, bästa poäng {parents[0]['score']:.2f}")
    devpool = sorted([r for r in pool.values() if r["score"] is not None], key=lambda r: -r["score"])
    finalists = diverse(devpool, config.N_FINALISTS, per_family=1, per_universe=3)
    n_trials = reg.trials(rid)
    report["search"] = {"screened": len(rows), "valid_screen": len(r1), "dev_evaluated": len(rows2), "refined_pool": len(pool),
                        "unique_strategies_tested": n_trials, "dev_months": int((np.datetime64(config.DEV[1]) - np.datetime64(config.DEV[0])).astype(int) / 30.4)}
    log(f"{n_trials} unika strategier testade; {len(finalists)} finalister")

    # 5. robusthet på utvecklingsdata (urvalet är låst innan valideringen öppnas)
    trial_sharpes = [r["result"]["summary"]["sharpe"] for r in reg.results(rid, "dev") + reg.results(rid, "refine")
                     if r["result"].get("summary")]
    top = devpool[:50]
    mats = []
    for r in top:
        res = ev.run(r["spec"], *config.DEV)
        keys, mr = M.monthly(res["r"], res["dates"]); mats.append(mr)
    L = min(len(x) for x in mats)
    pbo = stats.pbo_cscv(np.stack([x[-L:] for x in mats], axis=1), S=10)
    report["pbo_top50"] = pbo
    log(f"PBO för de 50 bästa: {pbo['pbo']:.2f}")
    recs = []
    for r in finalists:
        spec = r["spec"]
        dev = ev.run(spec, *config.DEV)
        ins = ev.sub(spec["universe"])[0].ins
        rec = {"spec_id": r["spec_id"], "spec": spec, "description": S.describe(spec), "dev": dev["summary"],
               "avg_hold_days": dev.get("avg_hold_days"),
               "dsr": stats.deflated_sharpe(dev["r"], trial_sharpes, n_trials),
               "walk_forward": validate.walk_forward(ev, spec), "stability": validate.stability(ev, spec),
               "cost_stress": validate.cost_stress(ev, spec), "subperiods": validate.subperiods(ev, spec),
               "concentration_dev": validate.concentration(dev), "cross_market": validate.cross_market(ev, spec),
               "pbo": pbo, "survivorship_biased": any(i.survivorship_biased for i in ins),
               "tradable": all(i.tradable for i in ins),
               "proxy_share_dev": float(ev.sub(spec["universe"])[0].proxy[panel.index(config.DEV[0]):panel.index(config.DEV[1])].mean())}
        rec["dev_benchmark"] = ev.benchmark(spec["universe"], *config.DEV)["summary"]
        rec["mc_dev"] = stats.monte_carlo(dev["r"])
        recs.append(rec)
        reg.log(rid, "robust", r["spec_id"], spec, rec["description"], "robusthet", config.SEED, n_trials, config.DEV,
                {k: v for k, v in rec.items() if k not in ("spec",)}, r["score"], "finalist")
        log(f"robust: {rec['description'][:80]} | WF {(rec['walk_forward']['summary'] or {}).get('sharpe', float('nan')):.2f} "
            f"DSR {rec['dsr']['dsr']:.2f} grannar {rec['stability']['share_ok']:.0%}")
    reg.commit()

    # 6. validering (första gången perioden används i omgången)
    diffs, pvals = [], []
    for rec in recs:
        v = ev.run(rec["spec"], *config.VALIDATION); b = ev.benchmark(rec["spec"]["universe"], *config.VALIDATION)
        rec["validation"] = v["summary"]; rec["validation_benchmark"] = b["summary"]
        p, lo, hi = stats.bootstrap_sharpe_diff(v["r"], b["r"], reps=1000)
        rec["validation_vs_benchmark"] = {"p": p, "diff_lo": lo, "diff_hi": hi}
        rec["regimes_validation"] = validate.regimes(ev, v, b)
        rec["concentration_validation"] = validate.concentration(v)
        n = min(len(v["r"]), len(b["r"]))
        diffs.append(v["r"][-n:] - b["r"][-n:]); pvals.append(p)
        ex = exact.run_panel(ev.sub(rec["spec"]["universe"])[0], *S.targets(rec["spec"], ev.sub(rec["spec"]["universe"])[1],
                             list(range(len(ev.sub(rec["spec"]["universe"])[0].ins)))), config.DEV[0], config.VALIDATION[1])
        fa = fast.run(ev.sub(rec["spec"]["universe"])[0], *S.targets(rec["spec"], ev.sub(rec["spec"]["universe"])[1],
                      list(range(len(ev.sub(rec["spec"]["universe"])[0].ins)))), config.DEV[0], config.VALIDATION[1])
        rec["exact"] = ex["summary"]; rec["exact_gap"] = abs(ex["summary"]["cagr"] - fa["summary"]["cagr"])
    q, ok = stats.bh_fdr(pvals, config.GATES["max_fdr_q"])
    n = min(len(d) for d in diffs)
    spa = stats.spa_test(np.stack([d[-n:] for d in diffs], axis=1), reps=1000)
    report["validation_spa"] = spa
    for rec, qq, kk in zip(recs, q, ok):
        rec["fdr_q"], rec["fdr_pass"] = qq, kk
        rec["failures"] = validate.gates(rec)
        reg.log(rid, "validation", rec["spec_id"], rec["spec"], rec["description"], "validering", config.SEED, n_trials,
                config.VALIDATION, {k: v for k, v in rec.items() if k != "spec"}, rec["validation"]["sharpe"],
                "godkänd" if not rec["failures"] else "förkastad", "; ".join(rec["failures"]) or None)
        log(f"validering: {rec['description'][:70]} | Sharpe {rec['validation']['sharpe']:.2f} vs {rec['validation_benchmark']['sharpe']:.2f} "
            f"| {'GODKÄND' if not rec['failures'] else 'underkänd: ' + rec['failures'][0]}")
    reg.commit()

    # jämförelse: appens nuvarande strategi (designad med data 2015–2026, alltså inte oberoende)
    inc = incumbent(panel)
    report["incumbent"] = inc

    # 7. champion och holdout
    passed = sorted([r for r in recs if not r["failures"]], key=lambda r: -r["validation"]["sharpe"])
    report["finalists"] = [{k: v for k, v in r.items() if k not in ("spec",)} | {"spec": r["spec"]} for r in recs]
    if passed:
        ch = passed[0]
        reg.freeze(rid, ch["spec_id"], ch["spec"], {"rule": "högst validerings-Sharpe bland godkända", "candidates": [r["spec_id"] for r in passed]})
        h = ev.run(ch["spec"], *config.HOLDOUT); hb = ev.benchmark(ch["spec"]["universe"], *config.HOLDOUT)
        hx = exact.run_panel(ev.sub(ch["spec"]["universe"])[0], *S.targets(ch["spec"], ev.sub(ch["spec"]["universe"])[1],
                             list(range(len(ev.sub(ch["spec"]["universe"])[0].ins)))), *config.HOLDOUT)
        ch["holdout"] = h["summary"]; ch["holdout_benchmark"] = hb["summary"]; ch["holdout_exact"] = hx["summary"]
        ch["holdout_failures"] = validate.gates(ch, holdout=True)
        reg.record_holdout(rid, ch["spec_id"], {"fast": h["summary"], "exact": hx["summary"], "benchmark": hb["summary"],
                                                "failures": ch["holdout_failures"]})
        verdict = "CHAMPION CANDIDATE" if not ch["holdout_failures"] else "HOLDOUT FAILED"
        report["champion"] = {"spec": ch["spec"], "description": ch["description"], "verdict": verdict,
                              "holdout": ch["holdout"], "holdout_exact": ch["holdout_exact"], "holdout_benchmark": ch["holdout_benchmark"],
                              "holdout_failures": ch["holdout_failures"]}
        if verdict == "CHAMPION CANDIDATE":
            champion.propose(ch["spec"], {k: v for k, v in ch.items() if k != "spec"}, rid)
    else:
        report["champion"] = {"verdict": "NO VERIFIED EDGE FOUND",
                              "note": "Ingen finalist klarade valideringskraven. Holdout-perioden har inte använts och sparas till en senare omgång."}
    report["minutes"] = (time.time() - t_start) / 60
    champion.ensure_incumbent()
    json.dump(report, open(os.path.join(out_dir, f"{rid}_report.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=float)
    log(f"klar: {report['champion']['verdict']} ({report['minutes']:.0f} min)")
    return report


def incumbent(panel):
    """Appens strategi i samma motor och perioder. Obs: valdes med data 2015–2026, så validering/holdout är in-sample."""
    from .search import LRUIndicators, subpanel
    ids = panel.ids()
    cols = [ids.index(k) for k in ("bitcoin", "omxs30", "sp500", "gold")]
    sp = subpanel(panel, cols)
    W, D, mode = champion.incumbent_targets(LRUIndicators(sp))
    out = {"name": champion.INCUMBENT["name"], "note": "in-sample: strategin valdes med data 2015–2026"}
    for k, per in (("dev", config.DEV), ("validation", config.VALIDATION), ("holdout", config.HOLDOUT)):
        r = fast.run(sp, W, D, mode, *per)
        out[k] = r["summary"]
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
