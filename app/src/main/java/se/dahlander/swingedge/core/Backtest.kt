package se.dahlander.swingedge.core

import kotlinx.serialization.Serializable
import java.time.LocalDate
import kotlin.math.abs
import kotlin.math.pow
import kotlin.math.sqrt

/**
 * Nya backtester i appen med samma frysta regler som i studien. Förenkling mot studiens motor (engine.py):
 * appen har bara stängningskurser, så affären görs på stängningen dagen efter signalen i stället för
 * på öppningen. Resultaten visas därför separat och märks som nya körningar.
 */
@Serializable
data class Metrics(
    val from: String, val to: String, val cagr: Double, val total: Double, val maxDd: Double,
    val sharpe: Double, val sortino: Double, val exposure: Double, val trades: Int, val avgHoldDays: Double?,
)

@Serializable
data class BacktestLine(val name: String, val strategy: Metrics, val buyHold: Metrics?, val buyHoldName: String, val note: String)

@Serializable
data class BacktestRun(val time: Long, val dataUntil: String, val lines: List<BacktestLine>, val errors: List<String> = emptyList())

class Sim(val dates: List<LocalDate>, val returns: DoubleArray, val exposure: DoubleArray, val trades: List<Pair<Int, Int>>)

/** w[t] bestäms vid stängning t och handlas vid stängning t+1. Kostnad per handlad andel. */
fun simulate(dates: List<LocalDate>, closes: List<Double>, w: List<Double?>, cost: Double): Sim {
    val n = closes.size
    val r = DoubleArray(n)
    val ex = DoubleArray(n)
    val trades = mutableListOf<Pair<Int, Int>>()
    var pos = 0.0
    var entry = -1
    for (t in 1 until n) {
        var eq = 1 + pos * (closes[t] / closes[t - 1] - 1)
        val tgt = w[t - 1] ?: 0.0
        if (abs(tgt - pos) > 1e-9) {
            eq *= 1 - abs(tgt - pos) * cost
            if (pos == 0.0) entry = t
            if (tgt == 0.0 && entry >= 0) { trades += entry to t; entry = -1 }
            pos = tgt
        }
        r[t] = eq - 1
        ex[t] = pos
    }
    if (entry >= 0) trades += entry to n - 1
    return Sim(dates, r, ex, trades)
}

fun metrics(sim: Sim, from: LocalDate? = null, dpy: Int = 252): Metrics? {
    val idx = sim.dates.indices.filter { from == null || !sim.dates[it].isBefore(from) }
    if (idx.size < 30) return null
    var eq = 1.0; var peak = 1.0; var mdd = 0.0
    val rs = idx.map { sim.returns[it] }
    for (x in rs) { eq *= 1 + x; peak = maxOf(peak, eq); mdd = minOf(mdd, eq / peak - 1) }
    val years = (sim.dates[idx.last()].toEpochDay() - sim.dates[idx.first()].toEpochDay()) / 365.25
    val mean = rs.average()
    val sd = sqrt(rs.sumOf { (it - mean) * (it - mean) } / (rs.size - 1))
    val dd = sqrt(rs.sumOf { minOf(it, 0.0).pow(2) } / rs.size)
    val tr = sim.trades.filter { idx.first() <= it.first }
    return Metrics(
        sim.dates[idx.first()].toString(), sim.dates[idx.last()].toString(),
        if (years > 0 && eq > 0) eq.pow(1 / years) - 1 else -1.0, eq - 1, mdd,
        if (sd > 0) mean / sd * sqrt(dpy.toDouble()) else 0.0,
        if (dd > 0) mean / dd * sqrt(dpy.toDouble()) else 0.0,
        idx.map { sim.exposure[it] }.average(), tr.size,
        if (tr.isEmpty()) null else tr.map { (a, b) -> (sim.dates[b].toEpochDay() - sim.dates[a].toEpochDay()).toDouble() }.average(),
    )
}

/** Fyller luckor i en produkts kurser med indexets dagsrörelser (samma metod som engine.repair_gaps). */
fun repairGaps(prod: List<Bar>, index: List<Bar>): List<Bar> {
    val pm = prod.associate { it.date to it.close }
    val im = index.associate { it.date to it.close }
    val days = index.map { it.date }.filter { !it.isBefore(prod.first().date) }
    val known = days.filter { it in pm }
    val out = sortedMapOf<LocalDate, Double>()
    known.forEach { out[it] = pm.getValue(it) }
    for (i in 0 until known.size - 1) {
        val a = known[i]; val b = known[i + 1]
        val gap = days.filter { it.isAfter(a) && it.isBefore(b) }
        if (gap.isEmpty()) continue
        val k = (pm.getValue(b) / pm.getValue(a)) / (im.getValue(b) / im.getValue(a))
        val steps = gap.size + 1
        gap.forEachIndexed { j, d -> out[d] = pm.getValue(a) * (im.getValue(d) / im.getValue(a)) * k.pow((j + 1).toDouble() / steps) }
    }
    return out.map { Bar(it.key, it.value) }
}

/** Kurs i SEK med valutakursen samma dag (saknas den används föregående). */
fun toSek(bars: List<Bar>, fx: List<Bar>): List<Bar> {
    val f = fx.sortedBy { it.date }
    var k = 0
    var last: Double? = null
    return bars.mapNotNull { b ->
        while (k < f.size && !f[k].date.isAfter(b.date)) { last = f[k].close; k++ }
        last?.let { Bar(b.date, b.close * it) }
    }
}

object Backtests {
    const val COST_SE = 0.0015
    const val COST_FOREIGN = 0.0040
    const val COST_CRYPTO = 0.0040

    /** Bitcoin Trend på produkten: signal från BTC-USD med datum före produktdagen. */
    fun btcOnProduct(btc: List<Bar>, xbt: List<Bar>): Pair<Sim, Sim> {
        val trend = trendSeries(btc, Rules.CRYPTO_SMA)
        var k = 0
        var cur: Boolean? = null
        val w = xbt.map { p ->
            while (k < trend.size && trend[k].first.date.isBefore(p.date)) { cur = trend[k].second ?: cur; k++ }
            cur?.let { if (it) 1.0 else 0.0 }
        }
        val dates = xbt.map { it.date }
        val c = xbt.map { it.close }
        return simulate(dates, c, w, COST_CRYPTO) to simulate(dates, c, List(c.size) { 1.0 }, COST_CRYPTO)
    }

    /** S&P 500 Trend på index (proxy, som i studien): beslut vid varje månadsslut, oförändrat däremellan. */
    fun sp500OnIndex(sp: List<Bar>): Pair<Sim, Sim> {
        val dec = monthlyDecisions(sp).associateBy { it.date }
        var cur: Double? = null
        val w = sp.map { b -> dec[b.date]?.let { cur = if (it.invested) 1.0 else 0.0 }; cur }
        val dates = sp.map { it.date }
        val c = sp.map { it.close }
        return simulate(dates, c, w, COST_FOREIGN) to simulate(dates, c, List(c.size) { 1.0 }, COST_FOREIGN)
    }

    /** Lika vikt i tre produkter (SEK), ombalansering vid Stockholmsbörsens månadsslut, handel nästa dag. */
    fun equalWeight(series: List<List<Bar>>, costs: List<Double>): Sim {
        val common = series.map { s -> s.map { it.date }.toSet() }.reduce { a, b -> a intersect b }.sorted()
        val maps = series.map { s -> s.associate { it.date to it.close } }
        val m = series.size
        val r = DoubleArray(common.size)
        var w = DoubleArray(m)
        var rebalanceNext = true
        for (t in 1 until common.size) {
            var g = 0.0
            for (j in 0 until m) g += w[j] * (maps[j].getValue(common[t]) / maps[j].getValue(common[t - 1]) - 1)
            var eq = 1 + g
            w = DoubleArray(m) { j -> w[j] * maps[j].getValue(common[t]) / maps[j].getValue(common[t - 1]) / eq }
            if (rebalanceNext) {
                eq *= 1 - (0 until m).sumOf { j -> abs(1.0 / m - w[j]) * costs[j] }
                w = DoubleArray(m) { 1.0 / m }
                rebalanceNext = false
            }
            if (Exchange.XSTO.isLastTradingDayOfMonth(common[t])) rebalanceNext = true
            r[t] = eq - 1
        }
        return Sim(common, r, DoubleArray(common.size) { 1.0 }, emptyList())
    }
}
