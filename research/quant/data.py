"""Instrumentuniversum, datakontroll och paneler på en gemensam kalender i SEK.

Varje instrument har en signalserie (underliggande marknad, native valuta) och en avkastningsserie: den köpbara
Avanza-produkten omräknad till SEK. Före produktens start används den underliggande serien i SEK minus en
uppskattad förvaltningsavgift (markeras som proxy). Bara instrument med verifierad Avanza-produkt eller direkt
handel på Avanza (svenska och amerikanska aktier) räknas som köpbara.

Kalender: alla vardagar från config.START. Saknad kurs en vardag (helgdag på den börsen) framåtfylls och markeras
som ej färsk; den snabba motorn och den exakta motorn handlar bara på färska dagar.
"""
import glob
import hashlib
import json
import os
from dataclasses import dataclass, field

import numpy as np

from . import config

PRODUCT_FEE = {"etf": 0.003, "certificate": 0.005, "crypto_tracker": 0.025, "stock": 0.0}
US_STOCKS = ["AAPL", "MSFT", "AMZN", "GOOGL", "META", "NVDA", "TSLA", "JPM", "JNJ", "XOM", "WMT", "PG", "KO", "PEP",
             "INTC", "CSCO", "ORCL", "IBM", "GE", "BA", "CAT", "MMM", "DIS", "MCD", "NKE", "HD", "UNH", "PFE", "MRK",
             "CVX", "BAC", "C", "WFC", "T", "VZ", "AMD", "QCOM", "TXN", "ADBE", "CRM", "NFLX", "COST", "LLY", "ABT",
             "MO", "F", "GM", "HON", "UPS", "LMT"]
CRYPTO_EXTRA = ["ADA-USD", "AVAX-USD", "BCH-USD", "BNB-USD", "DOGE-USD", "DOT-USD", "ETC-USD", "LINK-USD", "LTC-USD",
                "TRX-USD", "XLM-USD", "HBAR-USD", "FET-USD", "ICP-USD", "NEAR-USD"]
FX = {"EUR": "EURSEK=X", "USD": "USDSEK=X"}
BENCH = {"world": "URTH", "sp500": "^GSPC", "omxs30": "^OMX"}
SWING_DIR = "C:/Users/fredrik/android-build/qa/swing/data"
NOT_STOCKS = {"BITCOIN-XBT.ST", "XACT-OMXS30.ST", "ETHEREUM-XBT.ST"}


@dataclass
class Instrument:
    id: str
    name: str
    group: str                  # etp, se_stock, us_stock, crypto_x (forskning), fx (forskning)
    asset_class: str
    signal: str                 # Yahoo-symbol för signalen
    product: str | None         # Yahoo-symbol för den köpbara produkten
    currency: str               # produktens valuta
    exchange: str               # XSTO, XETRA, US
    kind: str                   # etf, certificate, crypto_tracker, stock
    tradable: bool
    survivorship_biased: bool = False
    avanza: dict = field(default_factory=dict)

    @property
    def half_spread(self):
        s = self.avanza.get("spread_pct")
        return s / 2 if s else config.HALF_SPREAD_DEFAULT["crypto_tracker" if self.kind == "crypto_tracker" else self.kind]


def _mapping():
    m = json.load(open(config.MAPPING, encoding="utf-8"))["markets"]
    u = {x["id"]: x for x in json.load(open(config.UNIVERSE, encoding="utf-8"))["markets"]}
    return m, u


def instruments():
    """Hela universumet i en bestämd ordning."""
    m, u = _mapping()
    out = []
    for mid, meta in u.items():
        prods = [p for p in m.get(mid, []) if p.get("eligible") and p.get("yahoo") and (p.get("leverage") or 1) == 1]
        prods.sort(key=lambda p: (p.get("yahooFirstTrade") or 9e12))
        p = prods[0] if prods else None
        if meta["kind"] == "fx" or (p is None and meta.get("underlying") is None):
            if meta["kind"] == "fx":
                out.append(Instrument(mid, meta["name"], "fx", meta["assetClass"], meta["underlying"], None, "SEK", "XSTO", "etf", False))
            continue
        kind = "crypto_tracker" if meta["kind"] == "crypto" else ("certificate" if p and p["type"] == "CERTIFICATE" else "etf")
        exch = "XSTO" if p and p["currency"] == "SEK" else "XETRA"
        av = {}
        if p:
            last = p.get("avanzaLast") or 0
            av = {"orderbookId": p["orderbookId"], "isin": p["isin"], "name": p["name"], "ticker": p["ticker"], "url": p["avanzaUrl"],
                  "marketPlace": p["marketPlace"], "spread_pct": (p["spread"] / last) if p.get("spread") and last else None}
        out.append(Instrument(mid, meta["name"], "etp", meta["assetClass"], meta["underlying"] or p["yahoo"], p["yahoo"] if p else None,
                              p["currency"] if p else "SEK", exch, kind, p is not None, False, av))
    for f in sorted(glob.glob(os.path.join(SWING_DIR, "*.ST.json"))):
        s = os.path.basename(f)[:-5]
        if s in NOT_STOCKS:
            continue
        out.append(Instrument("se:" + s, s, "se_stock", "Aktier Sverige", s, s, "SEK", "XSTO", "stock", True, True))
    for s in US_STOCKS:
        out.append(Instrument("us:" + s, s, "us_stock", "Aktier USA", s, s, "USD", "US", "stock", True, True))
    for s in CRYPTO_EXTRA:
        out.append(Instrument("cx:" + s, s, "crypto_x", "Krypto", s, None, "USD", "XSTO", "crypto_tracker", False))
    return out


def all_symbols():
    syms = set(FX.values()) | set(BENCH.values())
    for i in instruments():
        syms.add(i.signal)
        if i.product:
            syms.add(i.product)
    return sorted(s for s in syms if s)


# ---------------- inläsning och kontroll ----------------
@dataclass
class Series:
    symbol: str
    currency: str | None
    dates: np.ndarray           # datetime64[D]
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray           # justerad för utdelning och split
    volume: np.ndarray
    raw_close: np.ndarray
    dividends: list
    splits: list
    issues: list


def load(sym):
    p = os.path.join(config.DATA_DIR, "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in sym) + ".json")
    if not os.path.exists(p):
        return None
    d = json.load(open(p))
    rows = d.get("rows") or []
    if len(rows) < 30:
        return None
    return clean(sym, d.get("currency"), rows, d.get("dividends", []), d.get("splits", []))


def clean(sym, currency, rows, dividends=(), splits=()):
    """Datakontroll: dubbletter, icke-positiva kurser, vändande spikar och långa platta perioder."""
    issues = []
    seen = {}
    for r in rows:
        if r[4] is None or r[4] <= 0:
            issues.append(("icke-positiv", r[0])); continue
        seen[r[0]] = r
    rows = [seen[k] for k in sorted(seen)]
    keep = []
    c = [r[4] for r in rows]
    for i, r in enumerate(rows):
        if 0 < i < len(rows) - 1:
            a, b = c[i] / c[i - 1], c[i + 1] / c[i]
            if (a > 1.4 and b < 0.72) or (a < 0.72 and b > 1.4):
                issues.append(("spik", r[0])); continue
        keep.append(r)
    arr = np.array([[r[1] or r[4], r[2] or r[4], r[3] or r[4], r[4], r[5] or 0, r[6] if len(r) > 6 else r[4]] for r in keep], dtype=float)
    flat = 0
    for i in range(1, len(arr)):
        flat = flat + 1 if arr[i, 3] == arr[i - 1, 3] else 0
        if flat == 10:
            issues.append(("platt 10 dagar", keep[i][0]))
    return Series(sym, currency, np.array([r[0] for r in keep], dtype="datetime64[D]"), arr[:, 0], arr[:, 1], arr[:, 2], arr[:, 3],
                  arr[:, 4], arr[:, 5], list(dividends), list(splits), issues)


def calendar(start=config.START, end=config.HOLDOUT[1]):
    d = np.arange(np.datetime64(start), np.datetime64(end) + 1, dtype="datetime64[D]")
    return d[np.is_busday(d)]


def align(s, cal):
    """Framåtfyllda kolumner på kalendern + färsk-mask. Före seriens start: NaN."""
    idx = np.searchsorted(s.dates, cal, side="right") - 1
    ok = idx >= 0
    out = {}
    for k in ("open", "high", "low", "close", "volume"):
        v = np.full(len(cal), np.nan)
        v[ok] = getattr(s, k)[idx[ok]]
        out[k] = v
    fresh = np.zeros(len(cal), bool)
    pos = np.searchsorted(cal, s.dates)
    m = (pos < len(cal)) & (cal[np.minimum(pos, len(cal) - 1)] == s.dates)
    fresh[pos[m]] = True
    out["fresh"] = fresh
    return out


@dataclass
class Panel:
    cal: np.ndarray
    ins: list
    close: np.ndarray           # signal (native valuta), framåtfylld
    high: np.ndarray
    low: np.ndarray
    volume: np.ndarray
    ret: np.ndarray             # produktens dagsavkastning i SEK (0 före start / ej färsk)
    avail: np.ndarray           # produkten (eller proxyn) har kurs och kan ägas
    fresh: np.ndarray           # färsk kurs denna dag (handel kan ske)
    proxy: np.ndarray           # avkastningen kommer från underliggande proxy
    price_sek: np.ndarray       # produktens pris i SEK (framåtfyllt), för den exakta motorn
    fx: dict
    bench: dict
    version: str
    issues: dict

    def index(self, date):
        return int(np.searchsorted(self.cal, np.datetime64(date)))

    def ids(self):
        return [i.id for i in self.ins]


def _fx_series(cal):
    out = {"SEK": np.ones(len(cal))}
    for cur, sym in FX.items():
        s = load(sym)
        a = align(s, cal)["close"]
        first = np.nanargmax(~np.isnan(a)) if np.any(~np.isnan(a)) else 0
        a[:first] = a[first]
        out[cur] = a
    return out


def build_panel(groups=None, end=None):
    """Bygger panelen för valda grupper (None = alla) på kalendern till och med `end` (standard: holdoutens slut)."""
    cal = calendar(end=end or config.HOLDOUT[1])
    ins_all = [i for i in instruments() if groups is None or i.group in groups]
    h = hashlib.sha256()
    loaded = {}
    for i in ins_all:
        for sym in {i.signal, i.product} - {None}:
            if sym not in loaded:
                s = load(sym)
                loaded[sym] = s
                if s is not None:
                    h.update(sym.encode()); h.update(s.close.tobytes()); h.update(s.dates.astype("int64").tobytes())
    for sym in list(FX.values()) + list(BENCH.values()):
        if sym not in loaded:
            loaded[sym] = load(sym)
            if loaded[sym] is not None:
                h.update(sym.encode()); h.update(loaded[sym].close.tobytes())
    version = h.hexdigest()[:16]
    fx = _fx_series(cal)
    ins = [i for i in ins_all if loaded.get(i.signal) is not None and (i.product is None or loaded.get(i.product) is not None)]
    n, T = len(ins), len(cal)
    C, H, L, V = (np.full((T, n), np.nan) for _ in range(4))
    R = np.zeros((T, n)); A = np.zeros((T, n), bool); F = np.zeros((T, n), bool); P = np.zeros((T, n), bool); PS = np.full((T, n), np.nan)
    issues = {}
    for j, i in enumerate(ins):
        sig = align(loaded[i.signal], cal)
        C[:, j], H[:, j], L[:, j], V[:, j] = sig["close"], sig["high"], sig["low"], sig["volume"]
        issues[i.id] = loaded[i.signal].issues + (loaded[i.product].issues if i.product and i.product != i.signal else [])
        # proxy-avkastning från signalserien i SEK
        scur = loaded[i.signal].currency or i.currency
        sfx = fx.get(scur, fx["USD"] if scur not in fx else fx[scur])
        sc = sig["close"] * sfx
        pr = np.zeros(T)
        okp = ~np.isnan(sc)
        pr[1:] = np.where(okp[1:] & okp[:-1], sc[1:] / np.where(okp[:-1], sc[:-1], 1) - 1, 0.0)
        pr -= PRODUCT_FEE[i.kind] / 252 * okp
        avail = okp.copy(); fresh = sig["fresh"] & okp; prox = okp.copy()
        price = np.where(okp, sc, np.nan)
        if i.product:
            pp = align(loaded[i.product], cal)
            pc = pp["close"] * fx[i.currency]
            okq = ~np.isnan(pc)
            qr = np.zeros(T)
            qr[1:] = np.where(okq[1:] & okq[:-1], pc[1:] / np.where(okq[:-1], pc[:-1], 1) - 1, 0.0)
            use = okq & np.concatenate([[False], okq[:-1]])
            pr = np.where(use, qr, pr if i.signal != i.product else 0.0)
            prox = np.where(okq, False, prox if i.signal != i.product else False)
            avail = okq | (avail if i.signal != i.product else False)
            fresh = np.where(okq, pp["fresh"], fresh if i.signal != i.product else False)
            # pris i SEK: produkten där den finns, annars proxy skalad till produktens första kurs
            if okq.any() and i.signal != i.product:
                k = int(np.argmax(okq))
                scale = pc[k] / sc[k] if okp[k] and sc[k] else 1.0
                price = np.where(okq, pc, price * scale)
            else:
                price = pc
        # skalbyten och felaktiga justeringar hos Yahoo: dagsrörelser som inte är rimliga för instrumenttypen
        crypto = i.kind == "crypto_tracker"
        hi, lo = (3.0, -0.75) if crypto else (1.0, -0.5)
        bad = (pr > hi) | (pr < lo)
        if bad.any():
            proxy_ok = np.zeros(T, bool)
            if i.product and i.signal != i.product:
                pxr = np.zeros(T); pxr[1:] = np.where(okp[1:] & okp[:-1], sc[1:] / np.where(okp[:-1], sc[:-1], 1) - 1, 0.0)
                proxy_ok = (pxr <= hi) & (pxr >= lo) & okp
                pr = np.where(bad & proxy_ok, pxr, np.where(bad, 0.0, pr))
            else:
                pr = np.where(bad, 0.0, pr)
            issues[i.id] = issues[i.id] + [("orimlig dagsavkastning", str(cal[t])) for t in np.nonzero(bad)[0]]
        d = np.diff(np.log(C[:, j]), prepend=np.nan)
        jump = np.nan_to_num(np.abs(d)) > (np.log(4.0) if crypto or i.group == "crypto_x" else np.log(2.0))
        if jump.any():
            d = np.where(jump, 0.0, d)
            ok = ~np.isnan(C[:, j])
            k0 = int(np.argmax(ok))
            rebuilt = np.full(T, np.nan)
            rebuilt[k0:] = C[k0, j] * np.exp(np.cumsum(np.nan_to_num(d[k0:]) * (np.arange(T - k0) > 0)))
            C[:, j] = np.where(ok, rebuilt, np.nan)
            issues[i.id] = issues[i.id] + [("signalhopp", str(cal[t])) for t in np.nonzero(jump)[0]]
        n_bad = int(bad.sum() + jump.sum())
        if n_bad > 5:            # för många fel: instrumentet stängs av i forskningen
            avail = np.zeros(T, bool)
            issues[i.id] = issues[i.id] + [("utesluten: datakvalitet", n_bad)]
        R[:, j], A[:, j], F[:, j], P[:, j], PS[:, j] = pr, avail, fresh, prox, price
    R[~A] = 0.0
    bench = {}
    for k, sym in BENCH.items():
        s = loaded.get(sym)
        if s is not None:
            bench[k] = align(s, cal)["close"]
    return Panel(cal, ins, C, H, L, V, R, A, F, P, PS, fx, bench, version, issues)


def inventory(panel):
    """Sammanställning av universumet: antal per grupp, historik, köpbarhet och datafel."""
    rows = []
    for j, i in enumerate(panel.ins):
        av = panel.avail[:, j]
        first = str(panel.cal[np.argmax(av)]) if av.any() else None
        prox_share = float(panel.proxy[:, j][av].mean()) if av.any() else None
        excluded = any(k == "utesluten: datakvalitet" for k, _ in panel.issues.get(i.id, []))
        rows.append({"id": i.id, "group": i.group, "asset_class": i.asset_class, "tradable": i.tradable, "first": first, "excluded": excluded,
                     "years": float(av.sum() / 252), "proxy_share": prox_share, "issues": len(panel.issues.get(i.id, [])),
                     "survivorship_biased": i.survivorship_biased, "product": i.product})
    return rows
