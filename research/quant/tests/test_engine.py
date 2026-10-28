"""Tester av backtestmotorerna och valideringen på syntetiska data med handräknade svar.
Kör: python -E -m unittest discover -s quant/tests -t .   (från research/)"""
import math
import os
import tempfile
import unittest

import numpy as np

from quant import config, exact, fast, stats
from quant import metrics as M
from quant import strategies as S
from quant.data import Instrument, Panel, clean
from quant.registry import HoldoutError, Registry


def panel(prices, fresh=None, cur="SEK", exch="XSTO", kind="etf", start="2020-01-01", fxval=1.0, spread=None):
    prices = np.asarray(prices, float)
    if prices.ndim == 1:
        prices = prices[:, None]
    T, N = prices.shape
    d = np.arange(np.datetime64(start), np.datetime64(start) + 3 * T, dtype="datetime64[D]")
    cal = d[np.is_busday(d)][:T]
    ins = [Instrument(f"x{j}", f"x{j}", "etp", "Aktieindex", f"X{j}", f"X{j}", cur, exch, kind, True,
                      avanza={"spread_pct": spread} if spread is not None else {}) for j in range(N)]
    fresh = np.ones((T, N), bool) if fresh is None else np.asarray(fresh, bool).reshape(T, N)
    fx = {"SEK": np.ones(T), "EUR": np.full(T, fxval), "USD": np.full(T, fxval)}
    px = prices * (fxval if cur != "SEK" else 1.0)
    ret = np.zeros((T, N)); ret[1:] = px[1:] / px[:-1] - 1
    return Panel(cal, ins, prices.copy(), prices.copy(), prices.copy(), np.zeros((T, N)), ret, np.ones((T, N), bool), fresh,
                 np.zeros((T, N), bool), px, fx, {}, "test", {})


def zero_costs():
    saved = (dict(config.COURTAGE), config.FX_FEE, config.SLIPPAGE, dict(config.HALF_SPREAD_DEFAULT))
    for k in config.COURTAGE:
        config.COURTAGE[k] = (0.0, 0.0)
    config.FX_FEE = 0.0; config.SLIPPAGE = 0.0
    for k in config.HALF_SPREAD_DEFAULT:
        config.HALF_SPREAD_DEFAULT[k] = 0.0
    return saved


def restore(saved):
    config.COURTAGE.clear(); config.COURTAGE.update(saved[0]); config.FX_FEE = saved[1]; config.SLIPPAGE = saved[2]
    config.HALF_SPREAD_DEFAULT.clear(); config.HALF_SPREAD_DEFAULT.update(saved[3])


def one_signal(T, N, t, w=1.0, j=0):
    W = np.zeros((T, N)); D = np.zeros(T, bool); D[t] = True; W[t, j] = w
    return W, D


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.saved = zero_costs()

    def tearDown(self):
        restore(self.saved)

    def test_buy_executes_next_day_close(self):
        # beslut dag 2: köp vid stängning dag 3 (pris 103), avkastning från dag 4
        p = panel([100, 101, 102, 103, 110, 121])
        W, D = one_signal(6, 1, 2)
        r = fast.run(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]))["r"]
        self.assertAlmostEqual(r[3], 0.0)                     # ingen avkastning på exekveringsdagen
        self.assertAlmostEqual(r[4], 110 / 103 - 1)
        self.assertAlmostEqual(float(np.prod(1 + r)), 121 / 103)

    def test_signal_price_is_never_the_fill_price(self):
        # en "perfekt" signal på dagens hopp ska inte kunna fånga hoppet
        p = panel([100, 100, 200, 200])
        W, D = one_signal(4, 1, 1)                            # beslut dag 1, priset hoppar dag 2
        r = fast.run(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]))["r"]
        self.assertAlmostEqual(float(np.prod(1 + r)), 1.0)    # köp sker först vid 200
        e = exact.run_panel(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]))
        self.assertEqual(e["book"].fills[0].price, 200.0)

    def test_sell(self):
        p = panel([100, 100, 100, 110, 120, 60])
        W = np.zeros((6, 1)); D = np.zeros(6, bool); D[1] = True; W[1, 0] = 1.0; D[3] = True   # sälj-beslut dag 3
        r = fast.run(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]))["r"]
        self.assertAlmostEqual(float(np.prod(1 + r)), 1.2)    # såld vid 120 dag 4, kraschen dag 5 missas

    def test_holiday_defers_execution(self):
        fresh = [True, True, True, False, True, True]
        p = panel([100, 100, 100, 100, 150, 150], fresh=fresh)
        W, D = one_signal(6, 1, 2)                            # nästa dag är stängd: köp först dag 4 till 150
        r = fast.run(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]))["r"]
        self.assertAlmostEqual(float(np.prod(1 + r)), 1.0)
        e = exact.run_panel(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]))
        self.assertEqual(e["book"].fills[0].t, 4)


class CostTests(unittest.TestCase):
    def test_minimum_courtage_and_rate(self):
        self.assertEqual(exact.courtage(10_000, "XSTO"), 69.0)              # 0,069 % = 6,90 < 69
        self.assertAlmostEqual(exact.courtage(200_000, "XSTO"), 138.0)
        self.assertEqual(exact.courtage(100, "XETRA"), 8.0)

    def test_exact_fees_spread_and_fx(self):
        p = panel([100.0] * 6, cur="EUR", exch="XETRA", fxval=11.0, spread=0.002)   # halv spread 0,1 %
        W, D = one_signal(6, 1, 1, w=0.5)
        e = exact.run_panel(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]), capital=100_000)
        f = e["book"].fills[0]
        self.assertAlmostEqual(f.price, 100 * (1 + 0.001 + config.SLIPPAGE))
        q = math.floor(0.5 * 100_000 / (100 * 11.0))
        self.assertEqual(f.qty, q)
        notional = q * f.price
        fee = max(config.COURTAGE["XETRA"][0] * notional, 8.0) * 11.0 + notional * 11.0 * config.FX_FEE
        self.assertAlmostEqual(f.fee_sek, fee)
        self.assertAlmostEqual(e["book"].cash, 100_000 - notional * 11.0 - fee)
        self.assertGreaterEqual(e["book"].cash, 0)

    def test_fast_costs_reduce_return(self):
        p = panel([100.0] * 10)
        W, D = one_signal(10, 1, 1)
        a = fast.run(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]))["summary"]
        b = fast.run(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]), stress=2.0)["r"].sum()
        self.assertLess(float(np.prod(1 + fast.run(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]))["r"])), 1.0)
        self.assertLess(b, 0)


class CashAndEventsTests(unittest.TestCase):
    def setUp(self):
        self.saved = zero_costs()

    def tearDown(self):
        restore(self.saved)

    def test_cash_never_negative_with_simultaneous_buys(self):
        p = panel(np.full((6, 3), 100.0))
        W = np.zeros((6, 3)); D = np.zeros(6, bool); D[1] = True; W[1] = [0.5, 0.5, 0.5]   # vill köpa 150 %
        e = exact.run_panel(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]), capital=10_000)
        self.assertGreaterEqual(e["book"].cash, 0)
        self.assertLessEqual(int(e["book"].shares.sum()) * 100, 10_000)

    def test_dividend_and_split_in_raw_mode(self):
        T = 6
        price = np.array([[100.0], [100.0], [100.0], [50.0], [50.0], [50.0]])     # split 2:1 dag 3
        fxr = np.ones((T, 1)); fresh = np.ones((T, 1), bool)
        W, D = one_signal(T, 1, 0)
        ev = {3: [(0, "split", 2.0)], 4: [(0, "div", 1.0)]}
        res = exact.simulate(price, fxr, fresh, W, D, "changes", ["XSTO"], ["SEK"], np.zeros(1), 0, T - 1, 10_000, events=ev)
        self.assertEqual(int(res["book"].shares[0]), 200)
        self.assertAlmostEqual(res["equity"][-1], 200 * 50 + 200 * 1.0)

    def test_missing_data_is_not_traded(self):
        price = np.array([[100.0], [np.nan], [100.0], [100.0]])
        fresh = np.array([[True], [False], [True], [True]])
        W, D = one_signal(4, 1, 0)
        res = exact.simulate(price, np.ones((4, 1)), fresh, W, D, "changes", ["XSTO"], ["SEK"], np.zeros(1), 0, 3, 10_000)
        self.assertEqual(res["book"].fills[0].t, 2)

    def test_monthly_rebalance_resets_drift(self):
        a = np.concatenate([np.full(25, 100.0), np.full(25, 200.0)])
        b = np.full(50, 100.0)
        p = panel(np.stack([a, b], axis=1))
        W = np.zeros((50, 2)); D = np.zeros(50, bool)
        for t in (0, 30):
            D[t] = True; W[t] = [0.5, 0.5]
        res = fast.run(p, W, D, "rebalance", str(p.cal[0]), str(p.cal[-1]))
        self.assertEqual(res["turnover"] > 1.0, True)        # köp 100 % + ombalansering efter driften


class MetricTests(unittest.TestCase):
    def test_cagr_sharpe_maxdd(self):
        r = np.full(252, (1.1) ** (1 / 252) - 1)
        s = M.summary(r)
        self.assertAlmostEqual(s["cagr"], 0.1, places=9)
        self.assertAlmostEqual(M.max_drawdown([0.1, -0.5, 0.2]), -0.5)
        x = np.array([0.01, -0.01] * 126)
        self.assertAlmostEqual(M.summary(x)["sharpe"], 0.0, places=9)

    def test_buy_and_hold_equals_price_ratio(self):
        saved = zero_costs()
        try:
            rng = np.random.default_rng(0)
            prices = 100 * np.cumprod(1 + rng.normal(0, 0.01, 300))
            p = panel(prices)
            W, D = one_signal(300, 1, 0)
            r = fast.run(p, W, D, "changes", str(p.cal[0]), str(p.cal[-1]))["r"]
            self.assertAlmostEqual(float(np.prod(1 + r)), prices[-1] / prices[1], places=9)
        finally:
            restore(saved)


class LookAheadTests(unittest.TestCase):
    def test_targets_do_not_depend_on_future_data(self):
        rng = np.random.default_rng(7)
        T, N = 700, 4
        prices = 100 * np.cumprod(1 + rng.normal(0.0003, 0.015, (T, N)), axis=0)
        base = panel(prices)
        cut = 500
        changed = prices.copy(); changed[cut + 1:] *= rng.uniform(0.5, 1.5, (T - cut - 1, N))
        alt = panel(changed)
        r2 = np.random.default_rng(11)
        for _ in range(25):
            spec = S.sample(r2)
            spec["universe"] = "etp_all"
            W1, D1, _ = S.targets(spec, S.Indicators(base), list(range(N)))
            W2, D2, _ = S.targets(spec, S.Indicators(alt), list(range(N)))
            np.testing.assert_allclose(W1[:cut + 1], W2[:cut + 1], err_msg=S.describe(spec))

    def test_peeking_strategy_is_caught_by_engine_timing(self):
        # en strategi som "vet" morgondagens avkastning tjänar på det bara om motorn tillåter samma-dag-exekvering
        saved = zero_costs()
        try:
            rng = np.random.default_rng(3)
            prices = 100 * np.cumprod(1 + rng.normal(0, 0.02, 400))
            p = panel(prices)
            fut = np.zeros(400); fut[:-1] = prices[1:] / prices[:-1] - 1
            W = (fut > 0).astype(float)[:, None]; D = np.ones(400, bool)
            r = fast.run(p, W, D, "rebalance", str(p.cal[0]), str(p.cal[-1]), tol=0.0)["r"]
            self.assertLess(M.summary(r)["sharpe"], 1.5)      # med fusk vid stängning t skulle Sharpe bli > 10
        finally:
            restore(saved)


class OverfitTests(unittest.TestCase):
    def test_dsr_rejects_best_of_many_noise_strategies(self):
        rng = np.random.default_rng(5)
        R = rng.normal(0, 0.01, (1500, 500))
        sh = np.array([stats.sharpe(R[:, k]) for k in range(500)])
        best = int(np.argmax(sh))
        self.assertGreater(sh[best], 0.8)                      # ser bra ut enskilt
        self.assertLess(stats.deflated_sharpe(R[:, best], sh)["dsr"], 0.95)

    def test_pbo_high_for_noise(self):
        rng = np.random.default_rng(6)
        res = stats.pbo_cscv(rng.normal(0, 0.03, (120, 60)), S=10)
        self.assertGreater(res["pbo"], 0.3)

    def test_pbo_low_for_real_edge(self):
        rng = np.random.default_rng(8)
        M_ = rng.normal(0, 0.03, (120, 30)); M_[:, 0] += 0.02
        self.assertLess(stats.pbo_cscv(M_, S=10)["pbo"], 0.1)

    def test_spa(self):
        # storlek: under nollhypotesen ska testet sällan förkasta (nominellt 5 %, SPA är något konservativt)
        rej = [stats.spa_test(np.random.default_rng(100 + s).normal(0, 0.01, (1000, 20)), reps=300)["spa_p"] < 0.05 for s in range(20)]
        self.assertLessEqual(sum(rej), 3)
        noise = np.random.default_rng(9).normal(0, 0.01, (1000, 20))
        edge = noise.copy(); edge[:, 3] += 0.002
        self.assertLess(stats.spa_test(edge, reps=300)["spa_p"], 0.05)

    def test_bh(self):
        q, ok = stats.bh_fdr([0.001, 0.02, 0.04, 0.5], q=0.10)
        self.assertEqual(ok, [True, True, True, False])


class ReproducibilityAndRegistryTests(unittest.TestCase):
    def test_same_seed_same_specs(self):
        a = [S.spec_id(S.sample(np.random.default_rng(42))) for _ in range(1)]
        b = [S.spec_id(S.sample(np.random.default_rng(42))) for _ in range(1)]
        self.assertEqual(a, b)

    def test_holdout_runs_once_and_only_for_frozen(self):
        with tempfile.TemporaryDirectory() as d:
            reg = Registry(os.path.join(d, "r.sqlite"))
            reg.new_round("t", {}, "v", 1)
            spec = S.sample(np.random.default_rng(1))
            with self.assertRaises(HoldoutError):
                reg.record_holdout("t", "abc", {})
            reg.freeze("t", "abc", spec, {})
            with self.assertRaises(HoldoutError):
                reg.record_holdout("t", "other", {})
            reg.record_holdout("t", "abc", {"sharpe": 1})
            with self.assertRaises(HoldoutError):
                reg.record_holdout("t", "abc", {"sharpe": 2})
            reg.close()

    def test_data_cleaning_flags_spikes(self):
        rows = [["2020-01-0%d" % (i + 1), 1, 1, 1, c, 0] for i, c in enumerate([100, 101, 300, 102, 103])]
        s = clean("X", "SEK", rows)
        self.assertEqual(len(s.close), 4)
        self.assertTrue(any(k == "spik" for k, _ in s.issues))


class FastVsExactTests(unittest.TestCase):
    def test_engines_agree_on_simple_strategy(self):
        rng = np.random.default_rng(12)
        T, N = 800, 3
        prices = 100 * np.cumprod(1 + rng.normal(0.0004, 0.012, (T, N)), axis=0)
        p = panel(prices)
        spec = {"universe": "etp_all", "entry": {"type": "ma_above", "n": 50, "ma": "sma"}, "exit": {"type": "default"},
                "filter": None, "confirm": 1, "rank": "none", "max_pos": 0, "sizing": "slot", "schedule": "weekly"}
        W, D, mode = S.targets(spec, S.Indicators(p), [0, 1, 2])
        a = fast.run(p, W, D, mode, str(p.cal[60]), str(p.cal[-1]), capital=1_000_000)["summary"]
        b = exact.run_panel(p, W, D, mode, str(p.cal[60]), str(p.cal[-1]), capital=1_000_000)["summary"]
        self.assertLess(abs(a["cagr"] - b["cagr"]), 0.01)


if __name__ == "__main__":
    unittest.main()
