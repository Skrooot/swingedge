package se.dahlander.swingedge.factor

import java.text.Normalizer

/**
 * Global trendföljning enligt Börslabbets publika regler (borslabbet.se/global-trendfoljning, läst 28 okt 2026):
 * topp 3 av 9 tillgångar efter snittet av 3, 6 och 12 månaders avkastning i SEK, beslut vid månadsslut,
 * byte bara när en ny tillgång ligger minst 2 procentenheter högre. Samma regler som qa/bl/gtf.py
 * (paritet: GlobalAllocationParityTest). Signalerna räknas av SwingEdge, inte av Börslabbet.
 */
enum class AssetSource { AVANZA_FUND, YAHOO_EUR }

data class AllocationAsset(
    val id: String,
    val name: String,
    val product: String,
    val isin: String,
    val source: AssetSource,
    /** Avanzas orderbok-id för fonder, Yahoo-symbol för guld. */
    val sourceId: String,
    val avanzaUrl: String,
    val fee: String,
)

private fun slug(s: String) = Normalizer.normalize(s.lowercase(), Normalizer.Form.NFD).replace(Regex("\\p{M}"), "")
    .replace(Regex("[^a-z0-9]+"), "-").trim('-')

private fun fund(id: String, name: String, product: String, isin: String, avanza: Int, fee: String) =
    AllocationAsset(id, name, product, isin, AssetSource.AVANZA_FUND, avanza.toString(),
        "https://www.avanza.se/fonder/om-fonden.html/$avanza/${slug(product)}", fee)

val ALLOCATION_ASSETS = listOf(
    fund("SE", "Sverige", "Länsförsäkringar Sverige Index", "SE0002656611", 159608, "0,21 %"),
    fund("EU", "Europa", "Skandia Europa Exponering", "SE0000810772", 581, "0,36 %"),
    fund("US", "USA", "Storebrand USA A SEK", "SE0000594111", 1505, "0,21 %"),
    fund("JP", "Japan", "Skandia Japan Exponering", "SE0000810764", 1263, "0,36 %"),
    fund("EM", "Tillväxtmarknader", "Länsförsäkringar Tillväxtmarknad Index A", "SE0005796331", 487076, "0,52 %"),
    fund("SMB", "Svenska småbolag", "PLUS Småbolag Sverige Index", "SE0010323642", 789175, "0,42 %"),
    fund("BOND", "Svenska obligationer", "Carnegie Obligationsfond A", "SE0000709313", 2098, "0,52 %"),
    fund("SHORT", "Svenska korta räntor", "Handelsbanken Kortränta Defensiv A1", "SE0000356305", 2028, "0,19 %"),
    AllocationAsset("GOLD", "Guld", "Xetra-Gold ETC (4GLD)", "DE000A0S9GB0", AssetSource.YAHOO_EUR, "4GLD.DE",
        "https://www.avanza.se/borshandlade-produkter/certifikat-torg/om-certifikatet.html/1077331/xetra-gold-etc",
        "ingen förvaltningsavgift; courtage + 0,25 % växling"),
)

data class AllocationDecision(
    /** Månaden vars sista värden beslutet bygger på (YYYY-MM). Innehaven gäller månaden efter. */
    val signalMonth: String,
    /** Sammansatt momentum per tillgång som hade 12 månaders historik. */
    val scores: Map<String, Double>,
    val holdings: List<String>,
    val bought: List<String>,
    val sold: List<String>,
)

object GlobalAllocation {
    const val TOP = 3
    const val THRESHOLD = 0.02
    val LOOKBACK = listOf(3, 6, 12)

    fun nextMonth(m: String): String {
        val y = m.take(4).toInt(); val mo = m.drop(5).toInt()
        return if (mo == 12) "%04d-01".format(y + 1) else "%04d-%02d".format(y, mo + 1)
    }

    fun months(from: String, to: String): List<String> {
        val out = mutableListOf<String>(); var m = from
        while (m <= to) { out += m; m = nextMonth(m) }
        return out
    }

    /** Snitt av avkastningen över [look] månader fram till och med [i], eller null om någon månad saknas. */
    fun momentum(level: Map<String, Double>, ms: List<String>, i: Int, look: List<Int> = LOOKBACK): Double? {
        val n = look.max()
        if (i - n < 0) return null
        for (j in i - n..i) if (level[ms[j]] == null) return null
        return look.map { level.getValue(ms[i]) / level.getValue(ms[i - it]) - 1 }.average()
    }

    /**
     * Kör reglerna över hela historiken. [levels] = tillgång -> (månad -> månadsslutsvärde), bara hela månader.
     * Första beslutet tas den första månaden då alla tillgångar har 12 månaders historik.
     */
    fun run(levels: Map<String, Map<String, Double>>, top: Int = TOP, threshold: Double = THRESHOLD, look: List<Int> = LOOKBACK): List<AllocationDecision> {
        val all = levels.values.flatMap { it.keys }
        if (all.isEmpty()) return emptyList()
        val ms = months(all.min(), all.max())
        val first = ms.indices.firstOrNull { i -> levels.values.all { momentum(it, ms, i, look) != null } } ?: return emptyList()
        var hold = mutableListOf<String>()
        val out = mutableListOf<AllocationDecision>()
        for (i in first until ms.size) {
            val sc = levels.mapNotNull { (a, l) -> momentum(l, ms, i, look)?.let { a to it } }.toMap()
            val before = hold.toList()
            hold = hold.filter { it in sc }.toMutableList()
            val rank = sc.keys.sortedByDescending { sc.getValue(it) }
            for (a in rank) { if (hold.size >= top) break; if (a !in hold) hold += a }
            // tröskel: byt bästa utomstående mot sämsta innehav så länge skillnaden är minst tröskeln
            while (true) {
                val outs = rank.filter { it !in hold }
                if (outs.isEmpty() || hold.isEmpty()) break
                val worst = hold.minBy { sc.getValue(it) }; val best = outs.first()
                if (sc.getValue(best) >= sc.getValue(worst) + threshold && sc.getValue(best) > sc.getValue(worst)) hold[hold.indexOf(worst)] = best else break
            }
            out += AllocationDecision(ms[i], sc, hold.toList(), hold.filter { it !in before }, before.filter { it !in hold })
        }
        return out
    }

    /** Rangordning just nu (inklusive en pågående månad), för förhandsvisning. Ändrar inga innehav. */
    fun preview(levels: Map<String, Map<String, Double>>, month: String, look: List<Int> = LOOKBACK): Map<String, Double> {
        val all = levels.values.flatMap { it.keys } + month
        val ms = months(all.min(), all.max())
        val i = ms.indexOf(month)
        return levels.mapNotNull { (a, l) -> momentum(l, ms, i, look)?.let { a to it } }.toMap()
    }

    /** Avkastning över n månader fram till [i], för tabellen i appen. */
    fun change(level: Map<String, Double>, ms: List<String>, i: Int, n: Int): Double? {
        if (i - n < 0) return null
        val a = level[ms[i - n]] ?: return null; val b = level[ms[i]] ?: return null
        return b / a - 1
    }
}
