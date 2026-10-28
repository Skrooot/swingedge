package se.dahlander.swingedge.core

import java.time.Duration
import java.time.Instant
import java.time.LocalDate

/** En dagsstängning. */
data class Bar(val date: LocalDate, val close: Double)

/**
 * Frysta regler från signals.py (studien "Swingstrategier via Avanza"). Ändra inte trösklar eller längder här
 * utan att köra om studien: CRYPTO_SMA = 150, STOCK_SMA = 200, investerad endast när stängning > medelvärde
 * (exakt lika = inte investerad, som `c[-1] > m` i originalet).
 */
object Rules {
    const val CRYPTO_SMA = 150
    const val STOCK_SMA = 200
    /** signals.py stoppar rapporten när en kurs är mer än fem dagar gammal. */
    const val MAX_AGE_DAYS = 5L
    /** Tolerans vid ombalansering, samma som backtestmotorns 2 % (engine.simulate_multi). */
    const val REBALANCE_TOLERANCE = 0.02

    fun sma(closes: List<Double>, n: Int): Double? = if (closes.size < n) null else closes.takeLast(n).average()
    fun invested(close: Double, sma: Double): Boolean = close > sma
}

enum class DataStatus { OK, STALE, BLOCKED, MISSING }

data class DataCheck(val status: DataStatus, val latest: LocalDate?, val expected: LocalDate?, val message: String)

/** Tar bort staplar som inte är färdiga vid tidpunkten now. */
fun completedCryptoBars(bars: List<Bar>, now: Instant): List<Bar> {
    // BTC-dagsstapeln för datum D stänger 00:00 UTC dag D+1
    val today = now.atZone(UTC).toLocalDate()
    return bars.filter { it.date.isBefore(today) }
}

fun completedExchangeBars(bars: List<Bar>, ex: Exchange, now: Instant): List<Bar> {
    val last = ex.lastFinalTradingDay(now)
    return bars.filter { !it.date.isAfter(last) }
}

fun checkCrypto(bars: List<Bar>, now: Instant): DataCheck {
    val expected = now.atZone(UTC).toLocalDate().minusDays(1)
    return check(bars, expected, "BTC-USD")
}

fun checkExchange(bars: List<Bar>, ex: Exchange, now: Instant, name: String): DataCheck =
    check(bars, ex.lastFinalTradingDay(now), name)

private fun check(bars: List<Bar>, expected: LocalDate, name: String): DataCheck {
    val latest = bars.lastOrNull()?.date ?: return DataCheck(DataStatus.MISSING, null, expected, "$name: inga kurser")
    val age = Duration.between(latest.atStartOfDay(), expected.atStartOfDay()).toDays()
    return when {
        age <= 0 -> DataCheck(DataStatus.OK, latest, expected, "$name: senaste stängning $latest")
        age <= Rules.MAX_AGE_DAYS -> DataCheck(DataStatus.STALE, latest, expected,
            "$name: senaste stängning $latest, väntade $expected. Ingen ny signal räknas förrän data är aktuella.")
        else -> DataCheck(DataStatus.BLOCKED, latest, expected,
            "$name: senaste kurs är $age dagar gammal. Signalerna är stoppade.")
    }
}

/** Trendläge per dag: investerad om stängning > SMA(n). Dagar utan full historik ger null. */
fun trendSeries(bars: List<Bar>, n: Int): List<Pair<Bar, Boolean?>> {
    var sum = 0.0
    return bars.mapIndexed { i, b ->
        sum += b.close
        if (i >= n) sum -= bars[i - n].close
        b to (if (i >= n - 1) Rules.invested(b.close, sum / n) else null)
    }
}

data class BtcTrendState(
    val asOf: LocalDate,
    val close: Double,
    val sma: Double,
    val invested: Boolean,
    /** Senaste stängning där läget bytte, och läget efter bytet. */
    val lastSwitch: LocalDate?,
    /** Tidigaste börsöppning för produkten efter att stängningen asOf blev känd. */
    val executableFrom: Instant,
)

fun btcTrend(completed: List<Bar>): BtcTrendState? {
    val s = trendSeries(completed, Rules.CRYPTO_SMA).filter { it.second != null }
    if (s.isEmpty()) return null
    val (last, inv) = s.last()
    var switch: LocalDate? = null
    for (i in s.indices.reversed()) {
        if (i > 0 && s[i].second != s[i - 1].second) { switch = s[i].first.date; break }
    }
    val known = last.date.plusDays(1).atStartOfDay(UTC).toInstant()
    val sma = completed.map { it.close }.let { Rules.sma(it, Rules.CRYPTO_SMA)!! }
    return BtcTrendState(last.date, last.close, sma, inv!!, switch, Instrument.XBT.exchange.nextOpenAtOrAfter(known))
}

data class MonthlyDecision(val date: LocalDate, val close: Double, val sma: Double, val invested: Boolean, val executableFrom: Instant)

data class Sp500TrendState(
    val latest: Bar,
    val latestSma: Double?,
    /** Beslutet som gäller, taget vid senaste månadsskiftets stängning. */
    val decision: MonthlyDecision,
    val previous: MonthlyDecision?,
    val nextCheck: LocalDate,
)

/**
 * Månadsbeslut på varje månads sista stapel i de färdiga staplarna (som engine.month_end_flags i studien).
 * Den allra sista stapeln räknas bara som månadsslut om den är kalenderns sista NYSE-handelsdag; annars kan
 * månaden fortfarande få fler staplar. En oväntat stängd börs eller en saknad kurs på månadens sista dag
 * gör då att föregående handelsdag används, i stället för att månadens beslut uteblir.
 */
fun monthlyDecisions(completed: List<Bar>): List<MonthlyDecision> {
    val closes = completed.map { it.close }
    val out = mutableListOf<MonthlyDecision>()
    var sum = 0.0
    for (i in completed.indices) {
        sum += closes[i]
        if (i >= Rules.STOCK_SMA) sum -= closes[i - Rules.STOCK_SMA]
        val d = completed[i].date
        val monthEnd = if (i + 1 < completed.size) completed[i + 1].date.month != d.month || completed[i + 1].date.year != d.year
            else Exchange.NYSE.isLastTradingDayOfMonth(d)
        if (i >= Rules.STOCK_SMA - 1 && monthEnd) {
            val sma = sum / Rules.STOCK_SMA
            // NYSE stänger 22:00 svensk tid; SXR8 kan handlas först vid Xetras nästa öppning
            val exec = Instrument.SXR8.exchange.nextOpenAtOrAfter(Exchange.NYSE.closeInstant(d))
            out += MonthlyDecision(d, closes[i], sma, Rules.invested(closes[i], sma), exec)
        }
    }
    return out
}

fun sp500Trend(completed: List<Bar>, now: Instant): Sp500TrendState? {
    val decisions = monthlyDecisions(completed)
    val last = decisions.lastOrNull() ?: return null
    val today = now.atZone(NEW_YORK).toLocalDate()
    var check = Exchange.NYSE.lastTradingDayOfMonth(today.year, today.monthValue)
    if (!check.isAfter(last.date)) {
        val nm = today.plusMonths(1)
        check = Exchange.NYSE.lastTradingDayOfMonth(nm.year, nm.monthValue)
    }
    return Sp500TrendState(
        completed.last(), Rules.sma(completed.map { it.close }, Rules.STOCK_SMA), last,
        decisions.getOrNull(decisions.size - 2), check,
    )
}

/** Lika vikt: ombalansering vid Stockholmsbörsens sista handelsdag i månaden, handel nästa handelsdag. */
data class RebalanceSchedule(val lastRebalanceClose: LocalDate, val tradeDay: LocalDate, val nextRebalanceClose: LocalDate)

fun rebalanceSchedule(now: Instant): RebalanceSchedule {
    val ex = Exchange.XSTO
    val d = now.atZone(ex.zone).toLocalDate()
    // senaste månadsslut vars stängning har passerat
    var m = d
    var last = ex.lastTradingDayOfMonth(m.year, m.monthValue)
    if (!ex.isBarFinal(last, now) || last.isAfter(d)) {
        m = d.minusMonths(1)
        last = ex.lastTradingDayOfMonth(m.year, m.monthValue)
    }
    val next = ex.lastTradingDayOfMonth(last.plusMonths(1).year, last.plusMonths(1).monthValue)
    return RebalanceSchedule(last, ex.nextTradingDay(last), next)
}
