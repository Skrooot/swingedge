"""Strategibyggstenar: indikatorer (cachade), entry, exit, filter, rangordning, positionsstorlek och schema.

En strategi är en specifikation (dict, se SPACE) som översätts till målvikter på beslutsdagar. All logik använder
bara data till och med beslutsdagens stängning; exekveringen sker i motorerna, tidigast nästa färska dag.
"""
import hashlib
import json

import numpy as np

UNIVERSES = {
    # köpbara via Avanza (verifierad produkt eller direkt handel)
    "etp_all": lambda i: i.group == "etp" and i.tradable,
    "etp_equity": lambda i: i.group == "etp" and i.tradable and i.asset_class in ("Aktieindex", "Sektorer och teman"),
    "etp_real": lambda i: i.group == "etp" and i.tradable and i.asset_class in ("Ädelmetaller", "Industrimetaller", "Energi",
                                                                                 "Jordbruksråvaror", "Fastigheter och infrastruktur",
                                                                                 "Räntor och obligationer"),
    "etp_core": lambda i: i.id in ("sp500", "nasdaq100", "omxs30", "em", "japan", "stoxx600", "gold", "silver", "ust_long",
                                   "ust_mid", "tips", "reit_world", "bitcoin", "ether"),
    "crypto": lambda i: i.group == "etp" and i.tradable and i.asset_class == "Kryptovalutor",
    "se_stocks": lambda i: i.group == "se_stock",
    "us_stocks": lambda i: i.group == "us_stock",
    # bara forskning (korsmarknadsvalidering)
    "research_all_etp": lambda i: i.group == "etp",
    "research_crypto_x": lambda i: i.group == "crypto_x" or (i.group == "etp" and i.asset_class == "Kryptovalutor"),
    "research_fx": lambda i: i.group == "fx",
}
MARKET = {"etp": "world", "se_stock": "omxs30", "us_stock": "sp500", "crypto_x": "btc", "fx": "world"}

# Sökutrymmet: varje nyckel listar tillåtna värden; generatorn drar kombinationer härifrån.
SPACE = {
    "universe": ["etp_all", "etp_equity", "etp_real", "etp_core", "crypto", "se_stocks", "us_stocks"],
    "entry": [
        {"type": "ma_above", "n": [50, 100, 150, 200, 250], "ma": ["sma", "ema"]},
        {"type": "ma_cross", "f": [10, 20, 50], "s": [100, 150, 200]},
        {"type": "donchian", "n": [20, 55, 100, 200]},
        {"type": "mom", "L": [21, 63, 126, 252]},
        {"type": "rsi_pullback", "n": [2, 3, 14], "thr": [10, 20, 30]},
        {"type": "boll_revert", "n": [20], "z": [-1.5, -2.0, -2.5]},
        {"type": "vol_breakout", "n": [20, 50], "k": [1.0, 2.0, 3.0]},
        {"type": "high52", "prox": [0.02, 0.05, 0.10]},
        {"type": "always"},
    ],
    "exit": [
        {"type": "default"},
        {"type": "ma_below", "n": [20, 50, 100, 200]},
        {"type": "atr_trail", "k": [2.0, 3.0, 4.0, 6.0]},
        {"type": "time", "days": [5, 10, 21, 63]},
        {"type": "donchian_low", "n": [10, 20, 55]},
        {"type": "mom_neg", "L": [63, 126]},
    ],
    "filter": [
        None,
        {"type": "market_trend", "n": [150, 200]},
        {"type": "vol_below", "q": [0.5, 0.8]},
        {"type": "er_above", "L": [50, 100], "thr": [0.1, 0.2]},
    ],
    "confirm": [1, 2, 3],
    "rank": ["mom126", "mom252", "lowvol", "none"],
    "max_pos": [1, 3, 5, 10, 0],
    "sizing": ["slot", "invvol"],
    "schedule": ["daily", "weekly", "monthly"],
}
EVENT_ENTRIES = {"donchian", "rsi_pullback", "boll_revert", "vol_breakout", "high52"}


def spec_id(spec):
    return hashlib.sha1(json.dumps(spec, sort_keys=True).encode()).hexdigest()[:12]


def complexity(spec):
    """Antal regler utöver den enklaste (en entry med invers exit, ingen filter)."""
    c = 0
    c += spec["exit"]["type"] != "default"
    c += spec["filter"] is not None
    c += spec["confirm"] > 1
    c += spec["rank"] != "none" and spec["max_pos"] != 0
    c += spec["sizing"] != "slot"
    return c


def describe(spec):
    e, x, f = spec["entry"], spec["exit"], spec["filter"]
    p = lambda d: ", ".join(f"{k}={v}" for k, v in d.items() if k != "type")
    s = f"{spec['universe']}: entry {e['type']}({p(e)})"
    if x["type"] != "default":
        s += f"; exit {x['type']}({p(x)})"
    if f:
        s += f"; filter {f['type']}({p(f)})"
    if spec["confirm"] > 1:
        s += f"; bekräftelse {spec['confirm']} dagar"
    s += f"; {'alla' if spec['max_pos'] == 0 else 'max ' + str(spec['max_pos'])} positioner"
    if spec["max_pos"] != 0:
        s += f" rangordnat {spec['rank']}"
    s += f"; {spec['sizing']}; beslut {spec['schedule']}"
    return s


# ---------------- indikatorer ----------------
class Indicators:
    """Indikatorer över alla kolumner i en panel, beräknade en gång och återanvända mellan strategier."""

    def __init__(self, panel):
        self.p = panel
        self.c = panel.close
        self.cache = {}

    def get(self, key, fn):
        if key not in self.cache:
            self.cache[key] = fn()
        return self.cache[key]

    def sma(self, n):
        def f():
            c = self.c
            x = np.nan_to_num(c)
            cs = np.cumsum(x, axis=0)
            cnt = np.cumsum(~np.isnan(c), axis=0)
            out = np.full_like(c, np.nan)
            out[n - 1:] = cs[n - 1:] - np.vstack([np.zeros((1, c.shape[1])), cs[:-n]])
            k = cnt.copy(); k[n:] = cnt[n:] - cnt[:-n]
            out = np.where(k == n, out / n, np.nan)
            return out
        return self.get(("sma", n), f)

    def ema(self, n):
        def f():
            c = self.c; a = 2 / (n + 1)
            out = np.full_like(c, np.nan); e = np.full(c.shape[1], np.nan); cnt = np.zeros(c.shape[1])
            for t in range(len(c)):
                x = c[t]; ok = ~np.isnan(x)
                e = np.where(ok, np.where(np.isnan(e), x, e + a * (x - e)), e)
                cnt += ok
                out[t] = np.where(cnt >= n, e, np.nan)
            return out
        return self.get(("ema", n), f)

    def roll(self, n, how):
        """Högsta/lägsta stängning de n föregående dagarna (exklusive i dag)."""
        def f():
            c = self.c
            out = np.full_like(c, np.nan)
            from numpy.lib.stride_tricks import sliding_window_view
            for j in range(c.shape[1]):
                col = c[:, j]
                if len(col) <= n:
                    continue
                w = sliding_window_view(col[:-1], n)
                v = np.max(w, axis=1) if how == "max" else np.min(w, axis=1)
                out[n:, j] = v
            return out
        return self.get(("roll", n, how), f)

    def mom(self, L, skip=0):
        def f():
            c = self.c
            out = np.full_like(c, np.nan)
            out[L:] = c[L - skip:len(c) - skip] / c[:-L] - 1 if skip else c[L:] / c[:-L] - 1
            return out
        return self.get(("mom", L, skip), f)

    def absdiff_mean(self, n):
        def f():
            c = self.c
            d = np.abs(np.diff(c, axis=0, prepend=np.nan))
            x = np.nan_to_num(d); cs = np.cumsum(x, axis=0); cnt = np.cumsum(~np.isnan(d), axis=0)
            out = np.full_like(c, np.nan)
            s = cs.copy(); s[n:] = cs[n:] - cs[:-n]
            k = cnt.copy(); k[n:] = cnt[n:] - cnt[:-n]
            return np.where(k == n, s / n, np.nan)
        return self.get(("atrc", n), f)

    def vol(self, n):
        def f():
            c = self.c
            r = np.diff(np.log(c), axis=0, prepend=np.nan)
            x = np.nan_to_num(r); x2 = x * x
            cs, cs2 = np.cumsum(x, axis=0), np.cumsum(x2, axis=0)
            cnt = np.cumsum(~np.isnan(r), axis=0)
            s, s2, k = cs.copy(), cs2.copy(), cnt.copy()
            s[n:] -= cs[:-n]; s2[n:] -= cs2[:-n]; k[n:] -= cnt[:-n]
            var = (s2 - s * s / n) / (n - 1)
            return np.where(k == n, np.sqrt(np.maximum(var, 0)) * np.sqrt(252), np.nan)
        return self.get(("vol", n), f)

    def rsi(self, n):
        def f():
            c = self.c
            d = np.diff(c, axis=0, prepend=np.nan)
            up, dn = np.full(c.shape[1], np.nan), np.full(c.shape[1], np.nan)
            out = np.full_like(c, np.nan); cnt = np.zeros(c.shape[1])
            for t in range(len(c)):
                x = d[t]; ok = ~np.isnan(x)
                g, l_ = np.where(ok, np.maximum(x, 0), 0), np.where(ok, np.maximum(-x, 0), 0)
                up = np.where(ok, np.where(np.isnan(up), g, (up * (n - 1) + g) / n), up)
                dn = np.where(ok, np.where(np.isnan(dn), l_, (dn * (n - 1) + l_) / n), dn)
                cnt += ok
                rs = np.divide(up, dn, out=np.full_like(up, np.inf), where=dn > 0)
                out[t] = np.where(cnt >= n, 100 - 100 / (1 + rs), np.nan)
            return out
        return self.get(("rsi", n), f)

    def er(self, L):
        def f():
            c = self.c
            net = np.full_like(c, np.nan); net[L:] = np.abs(c[L:] - c[:-L])
            path = self.absdiff_mean(L) * L
            return np.where(path > 0, net / path, np.nan)
        return self.get(("er", L), f)

    def market(self, group, n):
        """Marknadstrend för gruppens referens (känd vid stängning): True om över SMA(n)."""
        def f():
            key = MARKET.get(group, "world")
            if key == "btc":
                ids = self.p.ids()
                col = self.c[:, ids.index("bitcoin")] if "bitcoin" in ids else None
            else:
                col = self.p.bench.get(key)
                if key == "world" and col is not None:
                    sp = self.p.bench.get("sp500")
                    col = np.where(np.isnan(col), sp, col)    # URTH saknas före 2012: S&P 500 som ersättning
            if col is None:
                return np.ones(len(self.c), bool)
            s = np.full(len(col), np.nan)
            ok = ~np.isnan(col)
            x = np.nan_to_num(col); cs = np.cumsum(x); cnt = np.cumsum(ok)
            s[n - 1:] = cs[n - 1:] - np.concatenate([[0], cs[:-n]])
            k = cnt.copy(); k[n:] = cnt[n:] - cnt[:-n]
            s = np.where(k == n, s / n, np.nan)
            return np.where(np.isnan(s), True, col > s)
        return self.get(("market", group, n), f)


# ---------------- signaler ----------------
def _ma(ind, kind, n):
    return ind.sma(n) if kind == "sma" else ind.ema(n)


def entry_exit(spec, ind):
    """(entry_cond, exit_cond) som bool-matriser. NaN-jämförelser blir False."""
    e, c = spec["entry"], ind.c
    with np.errstate(invalid="ignore"):
        t = e["type"]
        if t == "ma_above":
            m = _ma(ind, e["ma"], e["n"]); en = c > m; ex = c <= m
        elif t == "ma_cross":
            a, b = ind.sma(e["f"]), ind.sma(e["s"]); en = a > b; ex = a <= b
        elif t == "donchian":
            en = c > ind.roll(e["n"], "max"); ex = c < ind.roll(max(5, e["n"] // 2), "min")
        elif t == "mom":
            m = ind.mom(e["L"]); en = m > 0; ex = m <= 0
        elif t == "rsi_pullback":
            r = ind.rsi(e["n"]); up = c > ind.sma(200); en = (r < e["thr"]) & up; ex = r > 100 - e["thr"]
        elif t == "boll_revert":
            z = (c - ind.sma(e["n"])) / (ind.absdiff_mean(e["n"]) * np.sqrt(e["n"])); up = c > ind.sma(200)
            en = (z < e["z"]) & up; ex = z > 0
        elif t == "vol_breakout":
            m = ind.sma(e["n"]); a = ind.absdiff_mean(e["n"]); en = c > m + e["k"] * a; ex = c < m
        elif t == "high52":
            h = ind.roll(252, "max"); en = c >= (1 - e["prox"]) * h; ex = c < (1 - 3 * e["prox"]) * h
        elif t == "always":
            en = ~np.isnan(c); ex = np.zeros_like(en)
        else:
            raise ValueError(t)
        x = spec["exit"]
        if x["type"] == "ma_below":
            ex = c < ind.sma(x["n"])
        elif x["type"] == "donchian_low":
            ex = c < ind.roll(x["n"], "min")
        elif x["type"] == "mom_neg":
            ex = ind.mom(x["L"]) <= 0
    return en, ex


def holding_state(spec, ind):
    """Tillståndsmaskin per instrument: in/ur position efter entry, exit, bekräftelse, stopp och filter."""
    en, ex = entry_exit(spec, ind)
    c = ind.c
    T, N = c.shape
    k = spec["confirm"] if spec["entry"]["type"] not in EVENT_ENTRIES else 1
    x = spec["exit"]
    f = spec["filter"]
    with np.errstate(invalid="ignore"):
        gate_hold = np.ones((T, N), bool)
        gate_entry = np.ones((T, N), bool)
        if f:
            if f["type"] == "market_trend":
                groups = [i.group for i in ind.p.ins]
                cols = {g: ind.market(g, f["n"]) for g in set(groups)}
                gate_hold = np.stack([cols[g] for g in groups], axis=1)
            elif f["type"] == "vol_below":
                v = ind.vol(63)
                q = np.nanquantile(np.where(np.isnan(v), np.nan, v), f["q"], axis=1, keepdims=True) if N > 1 else v
                gate_entry = v <= q
            elif f["type"] == "er_above":
                gate_hold = ind.er(f["L"]) > f["thr"]
    atr = ind.absdiff_mean(20) if x["type"] == "atr_trail" else None
    on = np.zeros(N, bool); s_en = np.zeros(N); s_ex = np.zeros(N); held = np.zeros(N); peak = np.full(N, -np.inf)
    out = np.zeros((T, N), bool)
    for t in range(T):
        s_en = np.where(en[t] & ~on, s_en + 1, 0)
        s_ex = np.where(ex[t] & on, s_ex + 1, 0)
        stop = np.zeros(N, bool)
        if atr is not None:
            peak = np.where(on, np.maximum(peak, np.nan_to_num(c[t], nan=-np.inf)), -np.inf)
            with np.errstate(invalid="ignore"):
                stop = on & (c[t] < peak - x["k"] * atr[t])
        if x["type"] == "time":
            stop = on & (held >= x["days"])
        leave = on & ((s_ex >= k) | stop | ~gate_hold[t])
        enter = ~on & (s_en >= k) & gate_entry[t] & gate_hold[t]
        on = (on & ~leave) | enter
        held = np.where(on, held + 1, 0)
        if atr is not None:
            peak = np.where(enter, np.nan_to_num(c[t], nan=-np.inf), peak)
        s_en = np.where(enter, 0, s_en); s_ex = np.where(leave, 0, s_ex)
        out[t] = on
    return out


def decision_days(cal, schedule):
    if schedule == "daily":
        return np.ones(len(cal), bool)
    if schedule == "weekly":
        w = (cal.astype("datetime64[D]").view("int64") - 4) // 7      # vecka som slutar på fredag
        return np.concatenate([w[1:] != w[:-1], [True]])
    m = cal.astype("datetime64[M]")
    return np.concatenate([m[1:] != m[:-1], [True]])


def targets(spec, ind, cols):
    """Målvikter (T x N) på beslutsdagar för instrumenten i `cols` (index i panelen); övriga 0.

    Returnerar (W, D, mode). mode 'changes' = handla bara instrument vars urval ändras,
    'rebalance' = handla till målvikt på varje beslutsdag (tolerans hanteras i motorn).
    """
    p = ind.p
    T, N = p.close.shape
    state = holding_state(spec, ind)
    avail = p.avail & ~np.isnan(p.close)
    mask = np.zeros(N, bool); mask[cols] = True
    elig = state & avail & mask
    D = decision_days(p.cal, spec["schedule"])
    W = np.zeros((T, N))
    mp = spec["max_pos"]
    if spec["rank"] == "mom126":
        score = ind.mom(126)
    elif spec["rank"] == "mom252":
        score = ind.mom(252, skip=21)
    elif spec["rank"] == "lowvol":
        score = -ind.vol(63)
    else:
        score = ind.mom(126)          # neutral regel behöver ändå en deterministisk ordning när fler kvalificerar
    score = np.nan_to_num(score, nan=-1e9)
    inv = 1.0 / np.maximum(ind.vol(63), 0.05) if spec["sizing"] == "invvol" else None
    n_univ = np.maximum((avail & mask).sum(axis=1), 1)
    for t in np.nonzero(D)[0]:
        e = elig[t]
        if not e.any():
            continue
        idx = np.nonzero(e)[0]
        if mp and len(idx) > mp:
            idx = idx[np.argsort(-score[t, idx], kind="stable")[:mp]]
        slots = mp if mp else n_univ[t]
        if inv is None:
            W[t, idx] = 1.0 / slots
        else:
            v = np.nan_to_num(inv[t, idx], nan=1.0)
            W[t, idx] = v / v.sum() * len(idx) / slots
    mode = "changes" if spec["schedule"] == "daily" else "rebalance"
    return W, D, mode


def sample(rng, space=SPACE):
    """Drar en slumpad specifikation ur sökutrymmet."""
    def pick(block):
        if block is None:
            return None
        return {k: (v[rng.integers(len(v))] if isinstance(v, list) else v) for k, v in block.items()}
    s = {"universe": space["universe"][rng.integers(len(space["universe"]))],
         "entry": pick(space["entry"][rng.integers(len(space["entry"]))]),
         "exit": pick(space["exit"][rng.integers(len(space["exit"]))]),
         "filter": pick(space["filter"][rng.integers(len(space["filter"]))]),
         "confirm": int(space["confirm"][rng.integers(len(space["confirm"]))]),
         "rank": space["rank"][rng.integers(len(space["rank"]))],
         "max_pos": int(space["max_pos"][rng.integers(len(space["max_pos"]))]),
         "sizing": space["sizing"][rng.integers(len(space["sizing"]))],
         "schedule": space["schedule"][rng.integers(len(space["schedule"]))]}
    return normalize(s)


def normalize(s):
    """Tar bort meningslösa kombinationer så att samma strategi inte testas under flera namn."""
    s = json.loads(json.dumps(s))
    if s["entry"]["type"] == "ma_cross" and s["entry"]["f"] >= s["entry"]["s"]:
        s["entry"]["f"] = 20
    if s["entry"]["type"] in EVENT_ENTRIES:
        s["confirm"] = 1
    if s["entry"]["type"] == "always":
        s["confirm"] = 1
        if s["exit"]["type"] == "default" and s["filter"] is None:
            s["exit"] = {"type": "default"}
    if s["max_pos"] == 0:
        s["rank"] = "none"
    if s["universe"] == "crypto" and s["max_pos"] and s["max_pos"] > 3:
        s["max_pos"] = 0
    return s


def neighbors(spec, space=SPACE):
    """Alla specifikationer som skiljer sig i exakt en numerisk parameter med ett steg."""
    out = []
    for part in ("entry", "exit", "filter"):
        blk = spec[part]
        if not blk:
            continue
        tmpl = next(b for b in space[part] if b and b["type"] == blk["type"])
        for k, vals in tmpl.items():
            if k == "type" or not isinstance(vals, list) or not all(isinstance(v, (int, float)) for v in vals):
                continue
            i = vals.index(blk[k])
            for j in (i - 1, i + 1):
                if 0 <= j < len(vals):
                    s = json.loads(json.dumps(spec)); s[part][k] = vals[j]; out.append(normalize(s))
    for k in ("confirm", "max_pos"):
        vals = space[k]; i = vals.index(spec[k])
        for j in (i - 1, i + 1):
            if 0 <= j < len(vals) and not (k == "max_pos" and vals[j] == 0):
                s = json.loads(json.dumps(spec)); s[k] = vals[j]; out.append(normalize(s))
    uniq = {spec_id(s): s for s in out if spec_id(s) != spec_id(spec)}
    return list(uniq.values())
