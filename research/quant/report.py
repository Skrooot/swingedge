"""Skriver en läsbar rapport (Markdown) från en omgångs report.json. Kör: python -E -m quant.report R1"""
import json
import os
import sys

from . import config


def pct(x, d=1):
    return "–" if x is None else f"{x * 100:.{d}f} %".replace(".", ",")


def num(x, d=2):
    return "–" if x is None else f"{x:.{d}f}".replace(".", ",")


def main(rid):
    r = json.load(open(os.path.join(config.RESULTS_DIR, f"{rid}_report.json"), encoding="utf-8"))
    L = [f"# Forskningsomgång {rid}", "", f"Dataversion `{r['data_version']}`. Perioder: utveckling {r['periods']['dev'][0]} – {r['periods']['dev'][1]}, "
         f"validering {r['periods']['validation'][0]} – {r['periods']['validation'][1]}, holdout {r['periods']['holdout'][0]} – {r['periods']['holdout'][1]}.", ""]
    c = r["champion"]
    L += [f"## Resultat: **{c['verdict']}**", ""]
    if c.get("note"):
        L += [c["note"], ""]
    if c.get("description"):
        h = c["holdout"]; hb = c["holdout_benchmark"]
        L += [f"Kandidat: {c['description']}", "", f"Holdout: {pct(h['cagr'])} per år, Sharpe {num(h['sharpe'])}, största nedgång {pct(h['maxdd'], 0)} "
              f"(jämförelse {pct(hb['cagr'])}, {num(hb['sharpe'])}, {pct(hb['maxdd'], 0)}). Krav som inte uppfylldes: {', '.join(c['holdout_failures']) or 'inga'}.", ""]
    s = r["search"]; inv = r["inventory"]
    L += ["## Sökning", "", f"- Instrument: {inv['instruments']} ({inv['tradable']} köpbara via Avanza), per grupp {inv['by_group']}. Registrerade datafel: {inv['data_issues']}.",
          f"- Unika strategier testade: **{s['unique_strategies_tested']}** (screening {s['screened']}, varav giltiga {s['valid_screen']}; fördjupning {s['dev_evaluated']}; förfiningspool {s['refined_pool']}).",
          f"- Utvecklingsperioden har cirka {s['dev_months']} månader. Antalet testade hypoteser är alltså mångdubbelt fler än antalet oberoende observationer; därför används Deflated Sharpe, PBO, SPA och FDR.",
          f"- PBO (CSCV) för de 50 bästa på utvecklingsdata: **{num(r['pbo_top50']['pbo'])}**.",
          f"- SPA-test över finalisterna i valideringen mot respektive jämförelseindex: p = {num(r['validation_spa']['spa_p'], 3)} (Whites Reality Check p = {num(r['validation_spa']['rc_p'], 3)}).", ""]
    L += ["## Finalister (låsta före validering)", "",
          "| Strategi | Utv. Sharpe | WF Sharpe | DSR | Grannar | Val. Sharpe | Jämf. | Val. nedgång | Underkänd på |", "|---|---|---|---|---|---|---|---|---|"]
    for f in r["finalists"]:
        wf = (f["walk_forward"].get("summary") or {})
        L.append(f"| {f['description']} | {num(f['dev']['sharpe'])} | {num(wf.get('sharpe'))} | {num(f['dsr']['dsr'])} | {pct(f['stability']['share_ok'], 0)} | "
                 f"{num(f['validation']['sharpe'])} | {num(f['validation_benchmark']['sharpe'])} | {pct(f['validation']['maxdd'], 0)} | {'; '.join(f['failures']) or 'godkänd'} |")
    inc = r.get("incumbent")
    if inc:
        L += ["", f"## Jämförelse: {inc['name']}", "", f"({inc['note']})", "", "| Period | Avkastning/år | Sharpe | Största nedgång |", "|---|---|---|---|"]
        for k, lab in (("dev", "Utveckling"), ("validation", "Validering"), ("holdout", "Holdout")):
            x = inc.get(k)
            if x:
                L.append(f"| {lab} | {pct(x['cagr'])} | {num(x['sharpe'])} | {pct(x['maxdd'], 0)} |")
    L += ["", f"Körtid {r['minutes']:.0f} minuter. Alla siffror kommer från registret `experiments/registry.sqlite` och filen `{rid}_report.json`.", ""]
    path = os.path.join(config.RESULTS_DIR, f"{rid}_report.md")
    open(path, "w", encoding="utf-8").write("\n".join(L))
    return path


if __name__ == "__main__":
    print(main(sys.argv[1] if len(sys.argv) > 1 else "R1"))
