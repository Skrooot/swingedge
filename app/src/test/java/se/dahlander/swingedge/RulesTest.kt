package se.dahlander.swingedge

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.double
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import se.dahlander.swingedge.core.*
import java.time.Instant
import java.time.LocalDate
import java.time.ZonedDateTime

class RulesTest {
    private fun at(s: String): Instant = ZonedDateTime.parse(s).toInstant()

    /** n dagliga BTC-staplar som slutar dagen före [end], alla på [base], sista på [last]. */
    private fun btcBars(end: LocalDate, base: Double, last: Double, n: Int = 200): List<Bar> =
        (n downTo 1).map { k -> Bar(end.minusDays(k.toLong()), if (k == 1) last else base) }

    private fun nyseBars(from: LocalDate, to: LocalDate, price: (LocalDate) -> Double): List<Bar> {
        val out = mutableListOf<Bar>()
        var d = from
        while (!d.isAfter(to)) { if (Exchange.NYSE.isTradingDay(d)) out += Bar(d, price(d)); d = d.plusDays(1) }
        return out
    }

    private val noTrades = emptyList<Trade>()

    // ---------- Bitcoin Trend ----------
    @Test fun btcAboveSma150IsInvested() {
        val s = btcTrend(btcBars(LocalDate.of(2026, 10, 27), 100.0, 130.0))!!
        assertTrue(s.invested)
        assertEquals(100.2, s.sma, 1e-9)
    }

    @Test fun btcBelowSma150IsCash() {
        assertFalse(btcTrend(btcBars(LocalDate.of(2026, 10, 27), 100.0, 70.0))!!.invested)
    }

    @Test fun btcExactlyOnSma150IsCashLikeOriginal() {
        // signals.py: on = c[-1] > m  ->  lika med medelvärdet är inte investerad
        val s = btcTrend(btcBars(LocalDate.of(2026, 10, 27), 100.0, 100.0))!!
        assertEquals(s.close, s.sma, 1e-12)
        assertFalse(s.invested)
    }

    @Test fun unfinishedBtcBarIsDropped() {
        val now = at("2026-10-27T15:00:00Z")
        val bars = btcBars(LocalDate.of(2026, 10, 28), 100.0, 50.0) // sista stapeln = 27 okt, inte klar
        val done = completedCryptoBars(bars, now)
        assertEquals(LocalDate.of(2026, 10, 26), done.last().date)
    }

    @Test fun weekendBtcSignalWaitsForStockholmOpen() {
        // Stapeln för lördag 24 okt stänger 00:00 UTC söndag -> tidigast måndag 09:00 svensk tid
        val s = btcTrend(btcBars(LocalDate.of(2026, 10, 25), 100.0, 130.0))!!
        assertEquals(LocalDate.of(2026, 10, 24), s.asOf)
        assertEquals(at("2026-10-26T09:00:00+01:00"), s.executableFrom)
    }

    @Test fun weekendSignalIsPendingNotTraded() {
        val now = at("2026-10-25T10:00:00Z") // söndag
        val r = analyze(now, MarketSnapshot(btcBars(LocalDate.of(2026, 10, 25), 100.0, 130.0), spAbove(now), emptyMap()), noTrades, EngineState())
        assertEquals(SignalStatus.PENDING, r.btcStatus)
    }

    // ---------- S&P 500 Trend ----------
    private fun spAbove(now: Instant) = nyseBars(LocalDate.of(2025, 1, 2), now.atZone(NEW_YORK).toLocalDate().minusDays(1)) { 100.0 + it.toEpochDay() * 0.01 }

    @Test fun sp500AboveAndBelowSma200AtMonthEnd() {
        val up = nyseBars(LocalDate.of(2025, 1, 2), LocalDate.of(2026, 9, 30)) { 100.0 + it.toEpochDay() * 0.01 }
        assertTrue(monthlyDecisions(up).last().invested)
        val down = nyseBars(LocalDate.of(2025, 1, 2), LocalDate.of(2026, 9, 30)) { 500.0 - it.toEpochDay() * 0.01 }
        assertFalse(monthlyDecisions(down).last().invested)
        assertEquals(LocalDate.of(2026, 9, 30), monthlyDecisions(up).last().date)
    }

    @Test fun sp500DecisionIsFrozenBetweenMonthEnds() {
        val now = at("2026-10-27T22:00:00Z")
        val base = nyseBars(LocalDate.of(2025, 1, 2), LocalDate.of(2026, 9, 30)) { 100.0 + it.toEpochDay() * 0.01 }
        // Krasch i oktober: under SMA200 dagligen, men beslutet från 30 sep gäller till oktobers månadsslut
        val crash = base + nyseBars(LocalDate.of(2026, 10, 1), LocalDate.of(2026, 10, 27)) { 10.0 }
        val s = sp500Trend(completedExchangeBars(crash, Exchange.NYSE, now), now)!!
        assertTrue(s.decision.invested)
        assertEquals(LocalDate.of(2026, 9, 30), s.decision.date)
        assertEquals(LocalDate.of(2026, 10, 30), s.nextCheck)
        assertTrue(s.latest.close < s.latestSma!!)
    }

    @Test fun sp500BarBeforeUsCloseIsNotUsed() {
        val now = at("2026-10-30T19:00:00Z") // 15:00 i New York, månadens sista handelsdag
        val bars = nyseBars(LocalDate.of(2025, 1, 2), LocalDate.of(2026, 10, 30)) { 100.0 + it.toEpochDay() * 0.01 }
        val done = completedExchangeBars(bars, Exchange.NYSE, now)
        assertEquals(LocalDate.of(2026, 10, 29), done.last().date)
        assertEquals(LocalDate.of(2026, 9, 30), monthlyDecisions(done).last().date)
    }

    @Test fun sp500MonthEndDecisionTradesNextXetraDay() {
        val bars = nyseBars(LocalDate.of(2025, 1, 2), LocalDate.of(2026, 10, 30)) { 100.0 + it.toEpochDay() * 0.01 }
        val d = monthlyDecisions(bars).last()
        assertEquals(LocalDate.of(2026, 10, 30), d.date)
        assertEquals(at("2026-11-02T09:00:00+01:00"), d.executableFrom)
    }

    // ---------- Kalendrar ----------
    @Test fun closedDays() {
        assertFalse(Exchange.XSTO.isTradingDay(LocalDate.of(2026, 6, 19)))  // midsommarafton
        assertFalse(Exchange.XSTO.isTradingDay(LocalDate.of(2026, 4, 3)))   // långfredag
        assertFalse(Exchange.XSTO.isTradingDay(LocalDate.of(2026, 5, 14)))  // Kristi himmelsfärd
        assertTrue(Exchange.XETR.isTradingDay(LocalDate.of(2026, 5, 14)))
        assertFalse(Exchange.NYSE.isTradingDay(LocalDate.of(2026, 11, 26))) // Thanksgiving
        assertFalse(Exchange.NYSE.isTradingDay(LocalDate.of(2026, 7, 3)))   // 4 juli på en lördag -> fredag
        assertEquals(LocalDate.of(2026, 4, 5), easterSunday(2026))
        assertEquals(LocalDate.of(2026, 12, 30), Exchange.XSTO.lastTradingDayOfMonth(2026, 12))
    }

    @Test fun signalOnSwedishHolidayWaitsForNextOpen() {
        // BTC-stängning torsdag 18 juni blir känd 19 juni (midsommarafton) -> måndag 22 juni 09:00
        val s = btcTrend(btcBars(LocalDate.of(2026, 6, 19), 100.0, 130.0))!!
        assertEquals(at("2026-06-22T09:00:00+02:00"), s.executableFrom)
    }

    // ---------- Datakvalitet ----------
    @Test fun staleDataKeepsPreviousStateAndGivesNoNewSignal() {
        val now = at("2026-10-27T10:00:00Z")
        val old = btcBars(LocalDate.of(2026, 10, 24), 100.0, 130.0) // senaste 23 okt, väntade 26 okt
        val prev = EngineState(btcInvested = false, btcDate = "2026-10-20", spInvested = true, spDate = "2026-09-30")
        val r = analyze(now, MarketSnapshot(old, spAbove(now), emptyMap()), noTrades, prev)
        assertEquals(DataStatus.STALE, r.checks.getValue("BTC-USD").status)
        assertEquals(false, r.state.btcInvested)
        assertTrue(r.newSignals.none { it.strategy == StrategyId.BTC_TREND })
    }

    @Test fun dataOlderThanFiveDaysBlocksSignals() {
        val now = at("2026-10-27T10:00:00Z")
        val old = btcBars(LocalDate.of(2026, 10, 15), 100.0, 130.0)
        val r = analyze(now, MarketSnapshot(old, spAbove(now), emptyMap()), noTrades, EngineState())
        assertEquals(DataStatus.BLOCKED, r.checks.getValue("BTC-USD").status)
        assertNull(r.btc)
        assertEquals(SignalStatus.INVALID, r.btcStatus)
        assertNull(r.target)
        assertTrue(r.newSignals.any { it.type == SignalType.DATA_ERROR })
    }

    @Test fun missingDataGivesNoFalseSignal() {
        val now = at("2026-10-27T10:00:00Z")
        val prev = EngineState(btcInvested = true, btcDate = "2026-10-25", spInvested = true, spDate = "2026-09-30")
        val r = analyze(now, MarketSnapshot(emptyList(), emptyList(), emptyMap(), fetchErrors = listOf("Nätverksfel")), noTrades, prev)
        assertTrue(r.newSignals.none { it.type == SignalType.BUY || it.type == SignalType.SELL })
        assertEquals(true, r.state.btcInvested)
    }

    // ---------- Portfölj ----------
    // Fryst strategi: SwingEdge med guld, 20/40/40 med lika vikt på fyra produkter
    @Test fun combinedWeightsWhenBothTrendsOn() {
        val t = target(StrategyStates(btcInvested = true, spInvested = true))
        assertEquals(0.5, t.total.getValue(Instrument.SXR8), 1e-9)
        assertEquals(0.3, t.total.getValue(Instrument.XBT), 1e-9)
        assertEquals(0.1, t.total.getValue(Instrument.XACT), 1e-9)
        assertEquals(0.1, t.total.getValue(Instrument.GOLD), 1e-9)
        assertEquals(0.0, t.cash, 1e-9)
    }

    @Test fun frozenStrategyHasOnlyItsFourProducts() {
        assertEquals(setOf(Instrument.XBT, Instrument.XACT, Instrument.SXR8, Instrument.GOLD), Instrument.entries.toSet())
        assertEquals(listOf(Instrument.XACT, Instrument.SXR8, Instrument.XBT, Instrument.GOLD), EW_BASE)
        assertEquals(mapOf(StrategyId.BTC_TREND to 0.2, StrategyId.EQUAL_WEIGHT to 0.4, StrategyId.SP500_TREND to 0.4), DEFAULT_SLEEVES)
    }

    @Test fun trendOffGoesToCashNotOtherInstruments() {
        val t = target(StrategyStates(btcInvested = false, spInvested = false))
        assertEquals(0.1, t.total.getValue(Instrument.SXR8), 1e-9)
        assertEquals(0.1, t.total.getValue(Instrument.XBT), 1e-9)
        assertEquals(0.1, t.total.getValue(Instrument.GOLD), 1e-9)
        assertEquals(0.6, t.cash, 1e-9)
    }

    private fun quotes() = mapOf(
        Instrument.XBT to Quote(Instrument.XBT, 100.0, 100.0, Instant.EPOCH, 1.0),
        Instrument.XACT to Quote(Instrument.XACT, 100.0, 100.0, Instant.EPOCH, 1.0),
        Instrument.SXR8 to Quote(Instrument.SXR8, 10.0, 10.0, Instant.EPOCH, 10.0),
        Instrument.GOLD to Quote(Instrument.GOLD, 10.0, 10.0, Instant.EPOCH, 10.0),
    )

    @Test fun sameInstrumentInTwoStrategiesGivesOneOrder() {
        val trades = listOf(Trade("1", "2026-10-01", Side.DEPOSIT, price = 100000.0))
        val v = value(ledger(trades), quotes())
        val o = orders(v, target(StrategyStates(true, true)), Instrument.entries.toSet(), 0.02) { "x" }
        assertEquals(4, o.size)
        assertEquals(1, o.count { it.instrument == Instrument.SXR8 })
        assertEquals(50000.0, o.first { it.instrument == Instrument.SXR8 }.amountSek, 1.0)
    }

    @Test fun averageCostAndRealizedResult() {
        val l = ledger(listOf(
            Trade("1", "2026-01-01", Side.DEPOSIT, price = 10000.0),
            Trade("2", "2026-01-02", Side.BUY, Instrument.XACT, 10.0, 100.0, feeSek = 10.0),
            Trade("3", "2026-01-03", Side.BUY, Instrument.XACT, 10.0, 200.0, feeSek = 10.0),
            Trade("4", "2026-02-01", Side.SELL, Instrument.XACT, 5.0, 300.0, feeSek = 5.0),
        ))
        val p = l.positions.getValue(Instrument.XACT)
        assertEquals(15.0, p.quantity, 1e-9)
        assertEquals(151.0, p.avgCostSek, 1e-9)       // (1010 + 2010) / 20
        assertEquals(1495.0 - 755.0, p.realizedSek, 1e-9)
        assertEquals(10000.0 - 3020.0 + 1495.0, l.cashSek, 1e-9)
    }

    @Test fun monthlyRebalanceDueAfterMonthEndAndDoneWithinTolerance() {
        val now = at("2026-11-02T10:00:00+01:00")
        val sched = rebalanceSchedule(now)
        assertEquals(LocalDate.of(2026, 10, 30), sched.lastRebalanceClose)
        assertEquals(LocalDate.of(2026, 11, 2), sched.tradeDay)
        val btc = btcBars(LocalDate.of(2026, 11, 2), 100.0, 130.0)
        val sp = nyseBars(LocalDate.of(2025, 1, 2), LocalDate.of(2026, 10, 30)) { 100.0 + it.toEpochDay() * 0.01 }
        // portfölj som drivit iväg: allt i XACT
        val trades = listOf(Trade("1", "2026-10-01", Side.DEPOSIT, price = 100000.0), Trade("2", "2026-10-01", Side.BUY, Instrument.XACT, 1000.0, 100.0))
        val prev = EngineState(btcInvested = true, btcDate = "2026-10-31", spInvested = true, spDate = "2026-10-30", alignedBtc = true, alignedSp = true, rebalancedFor = "2026-09-30")
        val r = analyze(now, MarketSnapshot(btc, sp, quotes()), trades, prev)
        assertTrue(r.rebalanceDue)
        assertEquals(setOf(Instrument.XACT, Instrument.SXR8, Instrument.XBT, Instrument.GOLD), r.orders.map { it.instrument }.toSet())
        assertEquals("2026-09-30", r.state.rebalancedFor)
        // efter ombalansering inom toleransen markeras månaden som klar
        val aligned = listOf(Trade("1", "2026-10-01", Side.DEPOSIT, price = 100000.0),
            Trade("2", "2026-11-02", Side.BUY, Instrument.XACT, 100.0, 100.0),
            Trade("3", "2026-11-02", Side.BUY, Instrument.XBT, 300.0, 100.0),
            Trade("4", "2026-11-02", Side.BUY, Instrument.SXR8, 500.0, 10.0, fxToSek = 10.0),
            Trade("5", "2026-11-02", Side.BUY, Instrument.GOLD, 100.0, 10.0, fxToSek = 10.0))
        val r2 = analyze(now, MarketSnapshot(btc, sp, quotes()), aligned, r.state)
        assertTrue(r2.orders.isEmpty())
        assertEquals("2026-10-30", r2.state.rebalancedFor)
    }

    @Test fun noRepeatedNotificationsForSameEvent() {
        val now = at("2026-10-27T10:00:00Z")
        val snap = MarketSnapshot(btcBars(LocalDate.of(2026, 10, 27), 100.0, 130.0), spAbove(now), emptyMap())
        val prev = EngineState(btcInvested = false, btcDate = "2026-10-25", spInvested = true, spDate = "2026-09-30")
        val r1 = analyze(now, snap, noTrades, prev)
        assertEquals(1, r1.newSignals.count { it.type == SignalType.BUY })
        val r2 = analyze(now.plusSeconds(3600), snap, noTrades, r1.state)
        assertTrue(r2.newSignals.none { it.type == SignalType.BUY })
    }

    // ---------- Jämförelse mot Python-originalet ----------
    @Test fun matchesPythonRulesOnHistory() {
        val text = javaClass.classLoader!!.getResource("parity.json")!!.readText()
        val root = Json.parseToJsonElement(text).jsonObject
        fun load(key: String): Triple<List<Bar>, List<Double?>, JsonObject> {
            val o = root.getValue(key).jsonObject
            val dates = o.getValue("dates").jsonArray.map { LocalDate.parse(it.jsonPrimitive.content) }
            val closes = o.getValue("closes").jsonArray.map { it.jsonPrimitive.double }
            val w = o.getValue("python_weight").jsonArray.map { it.jsonPrimitive.doubleOrNull }
            return Triple(dates.zip(closes).map { Bar(it.first, it.second) }, w, o)
        }
        // Bitcoin: dagligt läge
        val (btc, wBtc) = load("btc")
        val k = trendSeries(btc, Rules.CRYPTO_SMA)
        var compared = 0
        for (i in btc.indices) {
            val py = wBtc[i] ?: continue
            assertEquals("BTC ${btc[i].date}", py > 0.5, k[i].second)
            compared++
        }
        assertTrue(compared > 4000)
        // S&P 500: läget efter varje månadsslut ska vara detsamma som Pythons månadsvisa vikt
        val (sp, wSp) = load("sp")
        val dec = monthlyDecisions(sp).associateBy { it.date }
        var months = 0
        for (i in sp.indices) {
            val d = dec[sp[i].date] ?: continue
            val py = wSp[i] ?: continue
            assertEquals("S&P ${sp[i].date}", py > 0.5, d.invested)
            months++
        }
        assertTrue("jämförde $months månader", months > 230)
        assertNotNull(dec)
    }
}

class FirstRunTest {
    @Test fun firstRunDoesNotFlagPassedMonthEndAsRebalance() {
        val now = java.time.ZonedDateTime.parse("2026-10-27T10:00:00+01:00").toInstant()
        val btc = (200 downTo 1).map { k -> Bar(LocalDate.of(2026, 10, 27).minusDays(k.toLong()), 100.0) }
        val sp = mutableListOf<Bar>()
        var d = LocalDate.of(2025, 1, 2)
        while (d.isBefore(LocalDate.of(2026, 10, 27))) { if (Exchange.NYSE.isTradingDay(d)) sp += Bar(d, 100.0 + d.toEpochDay() * 0.01); d = d.plusDays(1) }
        val r = analyze(now, MarketSnapshot(btc, sp, emptyMap()), emptyList(), EngineState())
        assertFalse(r.rebalanceDue)
        assertTrue(r.newSignals.none { it.type == SignalType.REBALANCE })
        assertEquals("2026-09-30", r.state.rebalancedFor)
    }
}
