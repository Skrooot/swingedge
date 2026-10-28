package se.dahlander.swingedge

import kotlinx.serialization.json.Json
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

/** Regressionstester för felen som hittades i kvalitetsgranskningen 28 okt 2026. */
class QaRegressionTest {
    private fun at(s: String): Instant = ZonedDateTime.parse(s).toInstant()
    private fun nyse(from: LocalDate, to: LocalDate, skip: Set<LocalDate> = emptySet(), price: (LocalDate) -> Double = { 100.0 + it.toEpochDay() * 0.01 }): List<Bar> {
        val out = mutableListOf<Bar>(); var d = from
        while (!d.isAfter(to)) { if (Exchange.NYSE.isTradingDay(d) && d !in skip) out += Bar(d, price(d)); d = d.plusDays(1) }
        return out
    }

    // F1: saknad kurs (eller oväntat stängd börs) på månadens sista handelsdag
    @Test fun monthDecisionUsesLastAvailableBarWhenMonthEndIsMissing() {
        val missing = LocalDate.of(2026, 3, 31)
        val bars = nyse(LocalDate.of(2025, 1, 2), LocalDate.of(2026, 5, 15), skip = setOf(missing))
        val dates = monthlyDecisions(bars).map { it.date }
        assertTrue(LocalDate.of(2026, 3, 30) in dates)
        assertFalse(missing in dates)
        // en per månad, inga hål
        val months = dates.map { it.withDayOfMonth(1) }
        assertEquals(months.distinct().size, months.size)
        assertTrue(LocalDate.of(2026, 3, 1) in months && LocalDate.of(2026, 4, 1) in months)
    }

    @Test fun unfinishedMonthIsNotADecision() {
        val bars = nyse(LocalDate.of(2025, 1, 2), LocalDate.of(2026, 5, 15))
        val last = monthlyDecisions(bars).last()
        assertEquals(LocalDate.of(2026, 4, 30), last.date)
    }

    @Test fun monthEndsMatchPythonDataDefinitionOnRealHistory() {
        val root = Json.parseToJsonElement(javaClass.classLoader!!.getResource("parity.json")!!.readText()).jsonObject
        val o = root.getValue("sp").jsonObject
        val dates = o.getValue("dates").jsonArray.map { LocalDate.parse(it.jsonPrimitive.content) }
        val closes = o.getValue("closes").jsonArray.map { it.jsonPrimitive.content.toDouble() }
        val bars = dates.zip(closes).map { Bar(it.first, it.second) }
        // engine.month_end_flags: sista stapeln i månaden när nästa stapel finns
        val py = (0 until dates.size - 1).filter { dates[it + 1].month != dates[it].month }.map { dates[it] }.filter { dates.indexOf(it) >= Rules.STOCK_SMA - 1 }
        val k = monthlyDecisions(bars).map { it.date }.filter { it != dates.last() }
        assertEquals(py, k)
    }

    // F2: föråldrade data visas som föråldrade
    @Test fun staleBtcIsShownAsStaleNotActive() {
        val now = at("2026-10-27T10:00:00Z")
        val old = (200 downTo 1).map { k -> Bar(LocalDate.of(2026, 10, 24).minusDays(k.toLong()), 100.0) }
        val sp = nyse(LocalDate.of(2025, 1, 2), LocalDate.of(2026, 10, 26))
        val prev = EngineState(btcInvested = false, btcDate = "2026-10-20", spInvested = true, spDate = "2026-09-30")
        val r = analyze(now, MarketSnapshot(old, sp, emptyMap()), emptyList(), prev)
        assertEquals(DataStatus.STALE, r.checks.getValue("BTC-USD").status)
        assertEquals(SignalStatus.STALE, r.btcStatus)
        assertEquals(SignalStatus.ACTIVE, r.spStatus)
    }

    // F3: orderförslag med hela andelar och kostnad
    @Test fun ordersHaveWholeUnitsCostAndSmallTradeFlag() {
        val t0 = Instant.parse("2026-10-27T10:00:00Z")
        val quotes = mapOf(
            Instrument.XACT to Quote(Instrument.XACT, 400.0, null, t0, 1.0),
            Instrument.SXR8 to Quote(Instrument.SXR8, 600.0, null, t0, 11.0),
        )
        val v = Valuation(10_000.0, 10_000.0, 0.0, emptyMap(), null)
        val tgt = Target(emptyMap(), mapOf(Instrument.XACT to 0.5, Instrument.SXR8 to 0.03), 0.47)
        val o = orders(v, tgt, setOf(Instrument.XACT, Instrument.SXR8), 0.02, quotes) { "test" }
        val xact = o.first { it.instrument == Instrument.XACT }
        assertEquals(12L, xact.quantity)                     // 5 000 kr / 400 kr = 12,5 -> 12 hela
        assertEquals(69.0, xact.costSek!!, 1e-9)             // minimicourtage
        assertTrue(xact.small)                               // 69 kr > 1 % av 5 000 kr
        val sxr8 = o.first { it.instrument == Instrument.SXR8 }
        assertEquals(0L, sxr8.quantity)                      // 300 kr räcker inte till en andel för 6 600 kr
        assertEquals(8 * 11.0 + 300 * 0.0025, sxr8.costSek!!, 1e-9)
        val big = tradeCostSek(Instrument.XACT, 200_000.0, 11.0)
        assertEquals(138.0, big, 1e-9)
    }

    // Forward test
    @Test fun forwardTestLogsOnlyLiveSignalsAndUsesFirstTradablePrice() {
        val exec = Instant.parse("2026-10-27T08:00:00Z")
        fun sig(type: SignalType, key: String, ex: Instant) = SignalRecord(key, 0, StrategyId.BTC_TREND, Instrument.XBT, type, "2026-10-26",
            underlyingPrice = 70000.0, indicatorName = "SMA150", indicatorValue = 65000.0, action = "", reason = "", executableFrom = ex.toEpochMilli())
        fun q(p: Double, t: Instant) = mapOf(Instrument.XBT to Quote(Instrument.XBT, p, null, t, 1.0))
        var log = ForwardTest.update(emptyList(), listOf(sig(SignalType.START, "s", exec)), q(100.0, exec), 1)
        assertTrue(log.isEmpty())
        log = ForwardTest.update(log, listOf(sig(SignalType.BUY, "b", exec)), q(100.0, exec.minusSeconds(3600)), 2)
        assertEquals(1, log.size); assertNull(log[0].entryPrice)          // kursen är från före börsöppningen
        log = ForwardTest.update(log, listOf(sig(SignalType.BUY, "b", exec)), q(101.0, exec.plusSeconds(60)), 3)
        assertEquals(1, log.size); assertEquals(101.0, log[0].entryPrice!!, 0.0)  // ingen dubblett
        val exit = exec.plusSeconds(86400 * 30)
        log = ForwardTest.update(log, listOf(sig(SignalType.SELL, "x", exit)), q(120.0, exit.minusSeconds(60)), 4)
        assertTrue(log[0].open)
        log = ForwardTest.update(log, emptyList(), q(110.0, exit.plusSeconds(60)), 5)
        assertFalse(log[0].open)
        assertEquals(110.0 / 101.0 * 0.996 * 0.996 - 1, log[0].returnSek()!!, 1e-12)
        assertNotNull(log[0].exitReason)
    }
}
