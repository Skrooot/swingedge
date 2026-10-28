package se.dahlander.swingedge.factor

import kotlinx.serialization.Serializable

/**
 * Dagens nyckeltal för en aktie, som Avanza visar dem (market-guide). Kursändringarna är utan utdelningar.
 * Historiska nyckeltal med publiceringsdatum finns inte här, så rangordningen kan aldrig backtestas med dessa data.
 */
@Serializable
data class StockSnapshot(
    val id: String,
    val name: String,
    val ticker: String,
    val list: String? = null,
    val topSector: String? = null,
    val price: Double? = null,
    val price3m: Double? = null,
    val price6m: Double? = null,
    val price12m: Double? = null,
    val pe: Double? = null,
    val pb: Double? = null,
    val ps: Double? = null,
    val evEbit: Double? = null,
    val directYield: Double? = null,
    val roe: Double? = null,
    val roa: Double? = null,
    val roce: Double? = null,
    val operatingCashFlow: Double? = null,
    val marketCap: Double? = null,
    val equityPerShare: Double? = null,
    val spread: Double? = null,
    val reportDate: String? = null,
)

enum class FactorStrategy(val title: String, val short: String, val rule: String) {
    VALUE("Trendande värde", "Värde",
        "Topp 40 % efter sammansatt värde (E/P, B/P, S/P, EBIT/EV, kassaflöde/pris, direktavkastning), sedan högst momentum."),
    QUALITY("Trendande kvalitet", "Kvalitet",
        "Topp 40 % efter sammansatt avkastning på kapital (ROE, ROA, ROCE, kassaflöde/eget kapital), sedan högst momentum."),
    DIVIDEND("Trendande utdelning", "Utdelning", "Topp 40 % efter direktavkastning, sedan högst momentum."),
    MOMENTUM("Sammansatt momentum", "Momentum", "Högst snitt av 3, 6 och 12 månaders kursutveckling. F-score-filtret saknas (kräver bokslutsdata)."),
}

data class RankedStock(val stock: StockSnapshot, val rank: Int, val momentum: Double, val primary: Double?, val note: String)

/**
 * Förenklad, aktuell rangordning enligt Börslabbets publika principer. Avvikelser från originalet (avsiktliga,
 * eftersom data saknas): EV/EBIT i stället för EV/EBITDA och EV/FCF, ROCE i stället för ROIC, operativt
 * kassaflöde i stället för fritt kassaflöde, och inget F-score. Resultatet är en forskningskandidat, inte en signal.
 */
object FactorRanking {
    const val MIN_MARKET_CAP = 2e9
    const val TOP = 10
    private const val PRIMARY_SHARE = 0.4
    private const val MOMENTUM_SHARE = 0.25

    fun momentum(s: StockSnapshot): Double? {
        val p = s.price ?: return null
        val parts = listOf(s.price3m, s.price6m, s.price12m)
        if (parts.any { it == null || it <= 0 }) return null
        return parts.map { p / it!! - 1 }.average()
    }

    fun eligible(s: StockSnapshot): Boolean =
        (s.marketCap ?: 0.0) >= MIN_MARKET_CAP && s.topSector != "Finans" && momentum(s) != null

    /** Percentilrang (0–1, högre = bättre) för varje aktie som har ett värde; null-värden får ingen rang. */
    fun percentile(values: Map<String, Double?>): Map<String, Double> {
        val have = values.filterValues { it != null }.mapValues { it.value!! }
        if (have.size < 2) return have.mapValues { 0.5 }
        val sorted = have.entries.sortedBy { it.value }
        val out = HashMap<String, Double>()
        var i = 0
        while (i < sorted.size) {
            var j = i
            while (j + 1 < sorted.size && sorted[j + 1].value == sorted[i].value) j++
            val r = (i + j) / 2.0 / (sorted.size - 1)
            for (k in i..j) out[sorted[k].key] = r
            i = j + 1
        }
        return out
    }

    private fun inv(x: Double?) = x?.let { if (it > 0) 1 / it else 0.0 }   // negativ vinst = sämst, inte saknad

    /** Snitt av percentilrangerna; kräver minst [min] av måtten. */
    private fun composite(stocks: List<StockSnapshot>, min: Int, vararg metrics: (StockSnapshot) -> Double?): Map<String, Double> {
        val ranks = metrics.map { f -> percentile(stocks.associate { it.id to f(it) }) }
        return stocks.mapNotNull { s ->
            val r = ranks.mapNotNull { it[s.id] }
            if (r.size >= min) s.id to r.average() else null
        }.toMap()
    }

    fun primary(strategy: FactorStrategy, stocks: List<StockSnapshot>): Map<String, Double> = when (strategy) {
        FactorStrategy.VALUE -> composite(stocks, 4,
            { inv(it.pe) }, { inv(it.pb) }, { inv(it.ps) }, { inv(it.evEbit) },
            { s -> s.operatingCashFlow?.let { c -> s.marketCap?.takeIf { it > 0 }?.let { c / it } } }, { it.directYield })
        FactorStrategy.QUALITY -> composite(stocks, 3,
            { it.roe }, { it.roa }, { it.roce },
            { s -> val eq = s.equityPerShare?.let { e -> s.marketCap?.let { m -> s.price?.takeIf { it > 0 }?.let { p -> e * m / p } } }
                if (eq != null && eq > 0) s.operatingCashFlow?.div(eq) else null })
        FactorStrategy.DIVIDEND -> stocks.filter { (it.directYield ?: 0.0) > 0 }.associate { it.id to it.directYield!! }
        FactorStrategy.MOMENTUM -> emptyMap()
    }

    fun rank(strategy: FactorStrategy, all: List<StockSnapshot>, top: Int = TOP): List<RankedStock> {
        val univ = all.filter { eligible(it) }
        val mom = univ.associate { it.id to momentum(it)!! }
        if (strategy == FactorStrategy.MOMENTUM) {
            return univ.sortedByDescending { mom.getValue(it.id) }.take(top)
                .mapIndexed { i, s -> RankedStock(s, i + 1, mom.getValue(s.id), null, "Momentum ${pctTxt(mom.getValue(s.id))}") }
        }
        val prim = primary(strategy, univ)
        val keep = (univ.size * PRIMARY_SHARE).toInt().coerceAtLeast(1)
        val firstStep = univ.filter { it.id in prim }.sortedByDescending { prim.getValue(it.id) }.take(keep)
        // översta fjärdedelen efter momentum (= topp 10 % av universumet), varav de [top] första visas
        val quarter = (firstStep.size * MOMENTUM_SHARE).toInt().coerceAtLeast(1)
        return firstStep.sortedByDescending { mom.getValue(it.id) }.take(minOf(quarter, top))
            .mapIndexed { i, s -> RankedStock(s, i + 1, mom.getValue(s.id), prim[s.id], "${strategy.short}rang ${pctTxt(prim[s.id] ?: 0.0, signed = false)} · momentum ${pctTxt(mom.getValue(s.id))}") }
    }

    private fun pctTxt(x: Double, signed: Boolean = true) = (if (signed && x > 0) "+" else "") + "%.0f %%".format(java.util.Locale.forLanguageTag("sv-SE"), x * 100)
}
