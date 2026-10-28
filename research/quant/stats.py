"""Statistisk validering. Antaganden redovisas i varje funktion.

- stationary_bootstrap: Politis–Romano, geometriska blocklängder (bevarar autokorrelation och volatilitetskluster).
- deflated_sharpe: Bailey & López de Prado (2014). Antar att försökens Sharpe är ungefär normalfördelade och att
  antalet försök N är det effektiva antalet oberoende försök (vi använder antalet unika strategier, konservativt).
- pbo_cscv: Bailey m.fl. (2017), Combinatorially Symmetric Cross-Validation på månadsavkastningar.
- spa_test: Hansen (2005) med stationär bootstrap; även Whites Reality Check (ej omcentrerad).
- bh_fdr: Benjamini–Hochberg; giltig under oberoende eller positivt beroende test (PRDS).
"""
import itertools
import math

import numpy as np

EULER = 0.5772156649


def norm_cdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def norm_ppf(p):
    """Acklams rationella approximation (fel < 1e-9)."""
    if p <= 0 or p >= 1:
        raise ValueError(p)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    lo, hi = 0.02425, 1 - 0.02425
    if p < lo:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > hi:
        return -norm_ppf(1 - p)
    q = p - 0.5; r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


def stationary_indices(n, mean_block, rng):
    p = 1.0 / mean_block
    idx = np.empty(n, dtype=np.int64)
    idx[0] = rng.integers(n)
    jumps = rng.random(n) < p
    starts = rng.integers(n, size=n)
    for t in range(1, n):
        idx[t] = starts[t] if jumps[t] else (idx[t - 1] + 1) % n
    return idx


def sharpe(r):
    sd = r.std(ddof=1)
    return r.mean() / sd * math.sqrt(252) if sd > 0 else 0.0


def bootstrap_sharpe_diff(a, b, reps=2000, mean_block=21, seed=1):
    """P(Sharpe(a) - Sharpe(b) <= 0) under stationär bootstrap av parade dagsavkastningar, plus 90 %-intervall."""
    rng = np.random.default_rng(seed)
    n = len(a); out = np.empty(reps)
    for k in range(reps):
        i = stationary_indices(n, mean_block, rng)
        out[k] = sharpe(a[i]) - sharpe(b[i])
    return float((out <= 0).mean()), float(np.quantile(out, 0.05)), float(np.quantile(out, 0.95))


def monte_carlo(r, reps=2000, mean_block=21, seed=2):
    """Fördelning av CAGR och största nedgång om historiken spelats upp i en annan ordning (blockvis)."""
    rng = np.random.default_rng(seed)
    n = len(r); cagr = np.empty(reps); mdd = np.empty(reps)
    for k in range(reps):
        x = r[stationary_indices(n, mean_block, rng)]
        e = np.cumprod(1 + x)
        cagr[k] = e[-1] ** (252 / n) - 1
        mdd[k] = (e / np.maximum.accumulate(e) - 1).min()
    q = lambda v, p: float(np.quantile(v, p))
    return {"cagr_p05": q(cagr, 0.05), "cagr_p50": q(cagr, 0.5), "maxdd_p05": q(mdd, 0.05), "maxdd_p50": q(mdd, 0.5)}


def deflated_sharpe(r, trial_sharpes, n_trials=None):
    """Sannolikheten att den sanna Sharpe är > 0 efter justering för antal försök, skevhet och kurtosis.
    r: dagsavkastning för den valda strategin; trial_sharpes: årliga Sharpe för alla försök i samma sökning."""
    r = np.asarray(r, float)
    n = len(r)
    sr = r.mean() / r.std(ddof=1)                          # per dag
    ts = np.asarray(trial_sharpes, float) / math.sqrt(252)
    N = n_trials or len(ts)
    var = float(np.var(ts, ddof=1)) if len(ts) > 1 else 0.0
    sr0 = math.sqrt(var) * ((1 - EULER) * norm_ppf(1 - 1 / N) + EULER * norm_ppf(1 - 1 / (N * math.e))) if N > 1 else 0.0
    sk = float(np.mean(((r - r.mean()) / r.std()) ** 3)); ku = float(np.mean(((r - r.mean()) / r.std()) ** 4))
    den = math.sqrt(max(1e-12, 1 - sk * sr + (ku - 1) / 4 * sr * sr))
    return {"dsr": norm_cdf((sr - sr0) * math.sqrt(n - 1) / den), "sr0_annual": sr0 * math.sqrt(252), "n_trials": N,
            "psr": norm_cdf(sr * math.sqrt(n - 1) / den)}


def pbo_cscv(M, S=10):
    """M: (perioder x strategier) avkastningsmatris. Returnerar PBO och logit-fördelningens median."""
    M = np.asarray(M, float)
    T, K = M.shape
    blocks = np.array_split(np.arange(T), S)
    logits = []
    for comb in itertools.combinations(range(S), S // 2):
        is_idx = np.concatenate([blocks[i] for i in comb])
        oos_idx = np.concatenate([blocks[i] for i in range(S) if i not in comb])
        def sh(x):
            sd = x.std(axis=0, ddof=1)
            return np.where(sd > 0, x.mean(axis=0) / sd, -np.inf)
        best = int(np.argmax(sh(M[is_idx])))
        oos = sh(M[oos_idx])
        rank = (oos < oos[best]).sum() + 0.5 * ((oos == oos[best]).sum() - 1)
        w = (rank + 0.5) / K
        logits.append(math.log(w / (1 - w)))
    logits = np.array(logits)
    return {"pbo": float((logits <= 0).mean()), "logit_median": float(np.median(logits)), "combinations": len(logits)}


def spa_test(D, reps=2000, mean_block=21, seed=3):
    """D: (dagar x modeller) differensavkastning mot referensen. H0: ingen modell är bättre än referensen.
    Returnerar Hansens SPA-p (consistent) och Whites Reality Check-p."""
    D = np.asarray(D, float)
    n, K = D.shape
    rng = np.random.default_rng(seed)
    mu = D.mean(axis=0)
    boot_means = np.empty((reps, K))
    for b in range(reps):
        boot_means[b] = D[stationary_indices(n, mean_block, rng)].mean(axis=0)
    # långsiktig standardavvikelse med Newey–West (Bartlett, lag = medelblocklängden). En bootstrap-skattning
    # ger brus som max-statistiken plockar upp (modellen med lägst skattad varians ser bäst ut).
    X = D - mu
    lrv = (X * X).mean(axis=0)
    for L in range(1, mean_block + 1):
        lrv += 2 * (1 - L / (mean_block + 1)) * (X[L:] * X[:-L]).mean(axis=0)
    omega = np.sqrt(np.maximum(lrv, 1e-24))
    stat = max(0.0, float(np.max(math.sqrt(n) * mu / omega)))
    thr = -math.sqrt(2 * math.log(math.log(n)))
    mu_c = np.where(math.sqrt(n) * mu / omega >= thr, mu, 0.0)
    # Hansen: Z* = d̄* − g(d̄); modeller med t ≥ tröskeln centreras i noll, klart sämre modeller behåller sitt negativa medel
    spa = np.maximum(0, np.max(math.sqrt(n) * (boot_means - mu_c) / omega, axis=1))
    rc = np.max(math.sqrt(n) * (boot_means - mu), axis=1)
    rc_stat = float(np.max(math.sqrt(n) * mu))
    return {"spa_p": float((spa >= stat).mean()), "rc_p": float((rc >= rc_stat).mean()), "stat": stat, "models": K}


def bh_fdr(pvals, q=0.10):
    """Benjamini–Hochberg: returnerar justerade q-värden och vilka som passerar nivån q."""
    p = np.asarray(pvals, float); m = len(p)
    order = np.argsort(p)
    adj = np.empty(m)
    run = 1.0
    for rank, i in reversed(list(enumerate(order, start=1))):
        run = min(run, p[i] * m / rank)
        adj[i] = run
    return adj.tolist(), (adj <= q).tolist()
