package se.dahlander.swingedge.edge

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement
import java.time.LocalDate
import kotlin.math.max
import kotlin.math.min
import kotlin.math.round
import kotlin.math.sqrt

/**
 * Edge Discovery i appen. Forskningen (qa/edge/edge.py) körs separat och publicerar edge-app.json.
 * Appen räknar bara dagens läge med samma frysta strategifamiljer och visar forskningens bedömning bredvid.
 * En kombination blir aldrig handlingsbar genom appen; klassningen kommer alltid från forskningen.
 */
@Serializable
data class EdgeMetrics(val cagr: Double, val sharpe: Double, val maxdd: Double, val trades: Int? = null, val years: Double? = null,
                       val exposure: Double? = null, val vol: Double? = null)

@Serializable
data class EdgeProductCheck(val yahoo: String? = null, val name: String? = null, val excess: Double? = null, val corr: Double? = null,
                            val drift: Double? = null, val years: Double? = null)

@Serializable
data class EdgeCombo(
    val market: String,
    val family: String,
    val params: Map<String, Double> = emptyMap(),
    val evidence: String,
    val riskReduction: Boolean = false,
    val excess: Double,
    val p: Double,
    val q: Double,
    val dsr: Double? = null,
    val test: EdgeMetrics,
    val bh: EdgeMetrics,
    val product: EdgeProductCheck? = null,
    val checks: Map<String, Boolean?> = emptyMap(),
    val subperiods: List<Double> = emptyList(),
    val variants: List<Double> = emptyList(),
    val excessTrain: Double? = null,
)

@Serializable
data class EdgeListing(val name: String? = null, val ticker: String? = null, val isin: String? = null, val marketPlace: String? = null,
                       val currency: String? = null, val avanzaUrl: String? = null, val spread: Double? = null, val owners: Int? = null,
                       val type: String? = null)

@Serializable
data class EdgeMarket(val id: String, val name: String, val assetClass: String, val kind: String, val underlying: String? = null,
                      val status: String, val trade: EdgeListing? = null, val productCount: Int = 0)

@Serializable
data class EdgeFamily(val name: String, val kind: String, val horizon: String)

@Serializable
data class EdgeResearch(
    val generated: String,
    val mappingVerified: String? = null,
    val nCombos: Int,
    val pbo: Double? = null,
    val selection: Map<String, Double> = emptyMap(),
    val portfolio: JsonElement? = null,
    val method: Map<String, String> = emptyMap(),
    val families: Map<String, EdgeFamily>,
    val markets: List<EdgeMarket>,
    val combos: List<EdgeCombo>,
)

enum class Evidence(val label: String, val rank: Int) {
    VALIDATED("Validerad", 3), STRONG("Stark hypotes", 2), HYPOTHESIS("Hypotes", 1), NONE("Ingen edge", 0);
    companion object { fun of(s: String) = entries.firstOrNull { it.label == s } ?: NONE }
}

/** Yahoo-terminer har ibland felaktiga enstaka dagar; samma filter som edge.py. */
fun cleanSpikes(dates: List<String>, closes: List<Double>): Pair<List<String>, List<Double>> {
    val d = mutableListOf<String>(); val c = mutableListOf<Double>()
    for (i in closes.indices) {
        if (i > 0 && i < closes.size - 1) {
            val a = closes[i] / closes[i - 1]; val b = closes[i + 1] / closes[i]
            if ((a > 1.4 && b < 0.72) || (a < 0.72 && b > 1.4)) continue
        }
        d += dates[i]; c += closes[i]
    }
    return d to c
}

object EdgeFamilies {
    private fun sma(c: List<Double>, n: Int): List<Double?> {
        var s = 0.0
        return c.mapIndexed { i, v -> s += v; if (i >= n) s -= c[i - n]; if (i >= n - 1) s / n else null }
    }

    /** Sista handelsdagen i månaden enligt datan; sista stapeln räknas bara om månaden är slut. */
    fun monthEnd(d: List<String>, today: LocalDate = LocalDate.now()): List<Boolean> {
        val now = today.toString().substring(0, 7)
        return d.indices.map { i -> (i + 1 < d.size && d[i + 1].substring(0, 7) != d[i].substring(0, 7)) || (i + 1 == d.size && d[i].substring(0, 7) < now) }
    }

    private fun rsi2(c: List<Double>): List<Double?> {
        val out = MutableList<Double?>(c.size) { null }
        var ag = 0.0; var al = 0.0
        for (i in 1 until c.size) {
            val ch = c[i] - c[i - 1]
            val g = max(ch, 0.0); val lo = max(-ch, 0.0)
            if (i <= 2) { ag += g / 2; al += lo / 2; if (i < 2) continue } else { ag = (ag + g) / 2; al = (al + lo) / 2 }
            out[i] = if (al == 0.0) 100.0 else 100 - 100 / (1 + ag / al)
        }
        return out
    }

    private fun vol20(c: List<Double>): List<Double?> {
        val r = listOf(0.0) + (1 until c.size).map { c[it] / c[it - 1] - 1 }
        return c.indices.map { i ->
            if (i < 20) null else {
                val w = r.subList(i - 19, i + 1); val m = w.average()
                sqrt(w.sumOf { (it - m) * (it - m) } / 19 * 252)
            }
        }
    }

    /** Vikt per dag (null = för kort historik). peers = tillgångsslagets serier för relativt momentum. */
    fun weights(fam: String, c: List<Double>, d: List<String>, p: Map<String, Double>, peers: Map<String, Pair<List<String>, List<Double>>>? = null,
                today: LocalDate = LocalDate.now()): List<Double?> {
        val n = c.size
        val w = MutableList<Double?>(n) { null }
        when (fam) {
            "sma150", "smaN" -> { val m = sma(c, (p["n"] ?: 150.0).toInt()); return c.indices.map { i -> m[i]?.let { if (c[i] > it) 1.0 else 0.0 } } }
            "sma200m" -> {
                val m = sma(c, (p["n"] ?: 200.0).toInt()); val me = monthEnd(d, today); var cur: Double? = null
                for (i in 0 until n) { val mi = m[i] ?: continue; if (me[i] || cur == null) cur = if (c[i] > mi) 1.0 else 0.0; w[i] = cur }
            }
            "tsmom12" -> {
                val lb = (p["lookback"] ?: 252.0).toInt(); val me = monthEnd(d, today); var cur: Double? = null
                for (i in lb until n) { if (me[i] || cur == null) cur = if (c[i] > c[i - lb]) 1.0 else 0.0; w[i] = cur }
            }
            "donchian" -> {
                val a = (p["entry"] ?: 55.0).toInt(); val b = (p["exit"] ?: 20.0).toInt(); var pos = 0.0
                for (i in a until n) {
                    val hi = c.subList(i - a, i).max(); val lo = c.subList(i - b, i).min()
                    if (pos == 0.0 && c[i] > hi) pos = 1.0 else if (pos > 0 && c[i] < lo) pos = 0.0
                    w[i] = pos
                }
            }
            "voltrend" -> {
                val m = sma(c, 200); val v = vol20(c); val tv = p["target"] ?: 0.2
                for (i in 0 until n) {
                    val mi = m[i] ?: continue; val vi = v[i] ?: continue
                    val x = if (c[i] > mi) (if (vi > 0) min(1.0, tv / vi) else 1.0) else 0.0
                    w[i] = round(x * 4) / 4
                }
            }
            "pullback" -> {
                val m200 = sma(c, 200); val m5 = sma(c, 5); val r = rsi2(c); var pos = 0.0; var held = 0
                for (i in 0 until n) {
                    val a = m200[i] ?: continue; val ri = r[i] ?: continue
                    if (pos == 0.0 && c[i] > a && ri < 10) { pos = 1.0; held = 0 } else if (pos > 0) { held++; if (c[i] > m5[i]!! || held >= 10) pos = 0.0 }
                    w[i] = pos
                }
            }
            "relmom" -> {
                val me = monthEnd(d, today); var cur: Double? = null
                val ps = peers ?: return w
                for (i in 0 until n) {
                    if (!me[i] && cur != null) { w[i] = cur; continue }
                    if (i < 252) continue
                    val scores = ps.values.mapNotNull { (pd, pc) ->
                        val k = upperBound(pd, d[i]) - 1
                        if (k >= 252) pc[k - 21] / pc[k - 252] - 1 else null
                    }
                    if (scores.size < 3) continue
                    val mine = c[i - 21] / c[i - 252] - 1
                    val ranked = scores.sortedDescending()
                    val cut = ranked[max(0, ranked.size / 3 - 1)]
                    cur = if (mine >= cut && mine > 0) 1.0 else 0.0
                    w[i] = cur
                }
            }
        }
        return w
    }

    private fun upperBound(a: List<String>, x: String): Int {
        var lo = 0; var hi = a.size
        while (lo < hi) { val m = (lo + hi) / 2; if (a[m] <= x) lo = m + 1 else hi = m }
        return lo
    }
}

enum class SignalState(val label: String) { NEW_BUY("Ny köpsignal"), IN("I marknaden"), NEW_SELL("Ny säljsignal"), OUT("Kontanter"), STALE("Data för gamla"), MISSING("Data saknas") }

data class Opportunity(
    val combo: EdgeCombo,
    val market: EdgeMarket,
    val family: EdgeFamily?,
    val weight: Double?,
    val state: SignalState,
    val dataDate: String?,
    val lastSwitch: String?,
)

object EdgeScanner {
    const val NEW_DAYS = 5

    /** Räknar dagens läge för varje kombination från de underliggande serierna (datum, stängning). */
    fun scan(r: EdgeResearch, series: Map<String, Pair<List<String>, List<Double>>>, today: LocalDate = LocalDate.now()): List<Opportunity> {
        val markets = r.markets.associateBy { it.id }
        val byClass = r.markets.filter { series[it.id] != null }.groupBy { it.assetClass }
        return r.combos.mapNotNull { cb ->
            val m = markets[cb.market] ?: return@mapNotNull null
            val s = series[cb.market]
            if (s == null || s.second.size < 260) return@mapNotNull Opportunity(cb, m, r.families[cb.family], null, SignalState.MISSING, s?.first?.lastOrNull(), null)
            val (d, c) = s
            val peers = if (cb.family == "relmom") byClass[m.assetClass]?.associate { it.id to series.getValue(it.id) } else null
            val w = EdgeFamilies.weights(cb.family, c, d, cb.params, peers, today)
            val last = w.lastOrNull()
            val age = java.time.temporal.ChronoUnit.DAYS.between(LocalDate.parse(d.last()), today)
            var switchIdx = -1
            for (i in w.indices.reversed()) {
                val a = w[i]; val b = w.getOrNull(i - 1)
                if (i > 0 && a != null && b != null && (a > 0) != (b > 0)) { switchIdx = i; break }
            }
            val recent = switchIdx >= 0 && switchIdx >= w.size - NEW_DAYS
            val state = when {
                age > 5 -> SignalState.STALE
                last == null -> SignalState.MISSING
                last > 0 && recent -> SignalState.NEW_BUY
                last > 0 -> SignalState.IN
                recent -> SignalState.NEW_SELL
                else -> SignalState.OUT
            }
            Opportunity(cb, m, r.families[cb.family], last, state, d.last(), if (switchIdx >= 0) d[switchIdx] else null)
        }
    }
}
