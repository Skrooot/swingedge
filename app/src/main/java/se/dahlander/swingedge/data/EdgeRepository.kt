package se.dahlander.swingedge.data

import kotlinx.serialization.json.Json
import se.dahlander.swingedge.core.SignalRecord
import se.dahlander.swingedge.core.SignalType
import se.dahlander.swingedge.edge.EdgeResearch
import se.dahlander.swingedge.edge.EdgeScanner
import se.dahlander.swingedge.edge.Evidence
import se.dahlander.swingedge.edge.Opportunity
import se.dahlander.swingedge.edge.SignalState
import se.dahlander.swingedge.edge.cleanSpikes
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDate

/**
 * Daglig skanning för Global Opportunities. Forskningen hämtas från GitHub (publicerad av edge.py),
 * kurserna för de underliggande marknaderna från Yahoo. Skanningen ändrar aldrig SwingEdges egna strategier.
 */
class EdgeRepository(private val store: Store) {
    companion object {
        const val RESEARCH_URL = "https://raw.githubusercontent.com/Skrooot/swingedge/main/research/edge-app.json"
        private val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
        const val SCAN_EVERY_MS = 20 * 3600_000L
    }

    data class Result(val research: EdgeResearch?, val opportunities: List<Opportunity>, val scannedAt: Long, val errors: List<String>, val notify: List<SignalRecord>)

    fun research(): EdgeResearch? = store.edgeRaw?.let { runCatching { json.decodeFromString(EdgeResearch.serializer(), it) }.getOrNull() }

    private fun download(url: String): String {
        val c = URL(url).openConnection() as HttpURLConnection
        c.setRequestProperty("User-Agent", "SwingEdge/1.1 (Android)")
        c.connectTimeout = 15000; c.readTimeout = 30000
        if (c.responseCode != 200) throw java.io.IOException("Servern svarade ${c.responseCode}")
        return c.inputStream.bufferedReader().use { it.readText() }
    }

    /** Senast sparade läge, utan nätverk. */
    fun cached(): Result {
        val r = research()
        val cache = store.edgeSeries
        return Result(r, if (r == null) emptyList() else EdgeScanner.scan(r, toSeries(cache)), cache.at, cache.errors, emptyList())
    }

    private fun toSeries(c: EdgeSeriesCache) = c.series.mapValues { (_, rows) -> rows.map { it[0] } to rows.map { it[1].toDouble() } }

    /** Hämtar forskning (högst en gång per dygn) och kurser, räknar dagens signaler och väljer vilka som ska notifieras. */
    @Synchronized
    fun refresh(force: Boolean = false): Result {
        val errors = mutableListOf<String>()
        var cache = store.edgeSeries
        if (force || System.currentTimeMillis() - cache.researchAt > 24 * 3600_000L || store.edgeRaw == null) {
            try {
                val raw = download(RESEARCH_URL)
                json.decodeFromString(EdgeResearch.serializer(), raw)
                store.edgeRaw = raw
                cache = cache.copy(researchAt = System.currentTimeMillis())
            } catch (e: Exception) { errors += "Forskningsresultatet kunde inte hämtas: ${e.message}" }
        }
        val r = research() ?: return Result(null, emptyList(), cache.at, errors, emptyList())
        if (force || System.currentTimeMillis() - cache.at > SCAN_EVERY_MS) {
            val series = cache.series.toMutableMap()
            for (m in r.markets) {
                val sym = m.underlying ?: continue
                try {
                    val s = MarketData.yahoo(sym, "2y")
                    val (d, c) = cleanSpikes(s.dates, s.closes)
                    series[m.id] = d.indices.map { listOf(d[it], c[it].toString()) }
                } catch (e: Exception) { errors += "${m.name}: ${e.message}" }
                Thread.sleep(250)
            }
            cache = cache.copy(at = System.currentTimeMillis(), series = series, errors = errors.toList())
        }
        val ops = EdgeScanner.scan(r, toSeries(cache))
        val min = Evidence.of(store.settings.edgeMinEvidence).rank
        val notified = cache.notified.toMutableSet()
        val notify = mutableListOf<SignalRecord>()
        for (o in ops) {
            if (o.state != SignalState.NEW_BUY || Evidence.of(o.combo.evidence).rank < min || o.lastSwitch == null) continue
            val key = "edge:${o.combo.market}:${o.combo.family}:${o.lastSwitch}"
            if (key in notified) continue
            notified += key
            notify += SignalRecord(
                key = key, time = System.currentTimeMillis(), type = SignalType.BUY, signalDate = o.lastSwitch,
                action = "Ny köpsignal: ${o.market.name}, ${o.family?.name ?: o.combo.family}",
                reason = "${o.combo.evidence} i forskningen. Överavkastning i Sharpe på testperioden ${"%+.2f".format(o.combo.excess)}." +
                    (o.market.trade?.name?.let { " Produkt: $it." } ?: " Ingen köpbar produkt hittad."),
            )
        }
        store.edgeSeries = cache.copy(notified = notified.toList().takeLast(500))
        return Result(r, ops, cache.at, cache.errors + errors, notify)
    }

    /** Nya köpsignaler de senaste dagarna, för notisernas text. */
    fun isFresh(o: Opportunity, today: LocalDate = LocalDate.now()) = o.lastSwitch?.let { !LocalDate.parse(it).isBefore(today.minusDays(7)) } == true
}
