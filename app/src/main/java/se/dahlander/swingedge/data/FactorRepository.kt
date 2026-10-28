package se.dahlander.swingedge.data

import android.content.Context
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import se.dahlander.swingedge.core.STOCKHOLM
import se.dahlander.swingedge.core.SignalRecord
import se.dahlander.swingedge.core.SignalType
import se.dahlander.swingedge.factor.ALLOCATION_ASSETS
import se.dahlander.swingedge.factor.AllocationDecision
import se.dahlander.swingedge.factor.AssetSource
import se.dahlander.swingedge.factor.GlobalAllocation
import se.dahlander.swingedge.factor.StockSnapshot
import java.time.Instant
import java.time.LocalDate
import java.time.YearMonth
import java.time.ZoneOffset
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Factor & Global Allocation. Fondvärden från Avanzas publika fond-API (NAV i SEK efter avgift), guld från Yahoo,
 * dagens nyckeltal från Avanzas aktiesidor. Påverkar aldrig SwingEdges egna strategier eller målportföljen.
 */
class FactorRepository(private val store: Store, private val context: Context? = null) {
    companion object {
        private val json = Json { ignoreUnknownKeys = true }
        const val ALLOCATION_EVERY_MS = 12 * 3600_000L
        const val SCAN_EVERY_MS = 20 * 3600_000L

        /** Avanzas tidsstämpel är midnatt svensk tid den 1:a; värdet är månadens sista NAV. +12 h ger rätt månad. */
        fun fundMonths(body: String): Map<String, Double> {
            val arr = json.parseToJsonElement(body).jsonObject["dataSerie"]?.jsonArray ?: return emptyMap()
            val out = sortedMapOf<String, Double>()
            for (p in arr) {
                val o = p.jsonObject
                val x = o["x"]?.jsonPrimitive?.longOrNull ?: continue
                val y = o["y"]?.jsonPrimitive?.doubleOrNull ?: continue
                out[Instant.ofEpochMilli(x + 12 * 3600_000L).atOffset(ZoneOffset.UTC).toLocalDate().toString().take(7)] = y
            }
            return out
        }

        /** Sista dagsvärdet per månad. */
        fun monthEnds(dates: List<String>, values: List<Double>): Map<String, Double> {
            val out = sortedMapOf<String, Double>()
            for (i in dates.indices) out[dates[i].take(7)] = values[i]
            return out
        }

        fun parseStock(id: String, name: String, ticker: String, body: String): StockSnapshot {
            val o = json.parseToJsonElement(body).jsonObject
            val k = o["keyIndicators"]?.jsonObject ?: JsonObject(emptyMap())
            val h = o["historicalClosingPrices"]?.jsonObject ?: JsonObject(emptyMap())
            val q = o["quote"]?.jsonObject ?: JsonObject(emptyMap())
            fun d(obj: JsonObject, key: String) = (obj[key] as? kotlinx.serialization.json.JsonPrimitive)?.doubleOrNull
            fun v(key: String) = (k[key] as? JsonObject)?.let { d(it, "value") }
            val sectors = (o["sectors"] as? JsonArray)?.mapNotNull { it.jsonObject["sectorName"]?.jsonPrimitive?.content }
            return StockSnapshot(
                id = id, name = name, ticker = ticker,
                list = o["listing"]?.jsonObject?.get("marketListName")?.jsonPrimitive?.content,
                topSector = sectors?.lastOrNull(),
                price = d(q, "last"), price3m = d(h, "threeMonths"), price6m = d(h, "sixMonths"), price12m = d(h, "oneYear"),
                pe = d(k, "priceEarningsRatio"), pb = d(k, "priceBookRatio"), ps = d(k, "priceSalesRatio"), evEbit = d(k, "evEbitRatio"),
                directYield = d(k, "directYield"), roe = d(k, "returnOnEquity"), roa = d(k, "returnOnTotalAssets"), roce = d(k, "returnOnCapitalEmployed"),
                operatingCashFlow = v("operatingCashFlow"), marketCap = v("marketCapital"), equityPerShare = v("equityPerShare"),
                spread = d(q, "spread"), reportDate = k["reportDate"]?.jsonPrimitive?.content,
            )
        }
    }

    data class Allocation(
        val decisions: List<AllocationDecision>,
        val levels: Map<String, Map<String, Double>>,
        val preview: Map<String, Double>,
        val partialMonth: String?,
        val at: Long,
        val errors: List<String>,
        val paperStart: String?,
        val notify: List<SignalRecord> = emptyList(),
    ) {
        val latest get() = decisions.lastOrNull()
        /** Byten (månader då innehaven ändrades), nyast först. */
        val changes get() = decisions.drop(1).filter { it.bought.isNotEmpty() || it.sold.isNotEmpty() }.reversed()

        /** Papperhandelns utveckling sedan appen började följa strategin: lika vikt, ombalansering varje månad, utan kostnader. */
        fun paperReturn(): Double? {
            val start = paperStart ?: return null
            var eq = 1.0; var n = 0
            for (d in decisions) {
                val m = GlobalAllocation.nextMonth(d.signalMonth)
                if (m < start) continue
                val r = d.holdings.mapNotNull { a -> levels[a]?.let { l -> val x = l[d.signalMonth]; val y = l[m]; if (x != null && y != null) y / x - 1 else null } }
                if (r.size != d.holdings.size) break
                eq *= 1 + r.average(); n++
            }
            return if (n > 0) eq - 1 else null
        }
    }

    private fun currentMonth() = YearMonth.now(STOCKHOLM).toString()

    fun cachedAllocation(): Allocation = build(store.allocation)

    private fun build(c: AllocationCache, notify: List<SignalRecord> = emptyList()): Allocation {
        val decisions = GlobalAllocation.run(c.levels)
        val pm = c.partialMonth
        val preview = if (pm != null && c.partial.size == c.levels.size) {
            GlobalAllocation.preview(c.levels.mapValues { (a, l) -> l + (c.partial[a]?.let { mapOf(pm to it) } ?: emptyMap()) }, pm)
        } else emptyMap()
        return Allocation(decisions, c.levels, preview, pm, c.at, c.errors, c.paperStart, notify)
    }

    @Synchronized
    fun refreshAllocation(force: Boolean = false): Allocation {
        var c = store.allocation
        if (!force && System.currentTimeMillis() - c.at < ALLOCATION_EVERY_MS && c.levels.size == ALLOCATION_ASSETS.size) return build(c)
        val month = currentMonth()
        val levels = c.levels.toMutableMap(); val partial = mutableMapOf<String, Double>(); val errors = mutableListOf<String>()
        var eurSek: Map<String, Double>? = null
        for (a in ALLOCATION_ASSETS) {
            try {
                val m: Map<String, Double> = when (a.source) {
                    AssetSource.AVANZA_FUND -> fundMonths(MarketData.get("https://www.avanza.se/_api/fund-guide/chart/${a.sourceId}/infinity?raw=true"))
                    AssetSource.YAHOO_EUR -> {
                        val px = MarketData.yahoo(a.sourceId, "10y")
                        val fx = eurSek ?: MarketData.yahoo("EURSEK=X", "10y").let { monthEnds(it.dates, it.closes) }.also { eurSek = it }
                        val pm = monthEnds(px.dates, px.closes)
                        // valutan fylls framåt om en månad saknas hos Yahoo, som i forskningsskriptet
                        var last: Double? = null
                        pm.mapNotNull { (k, v) -> last = fx[k] ?: last; last?.let { k to v * it } }.toMap()
                    }
                }
                levels[a.id] = m.filterKeys { it < month }
                m[month]?.let { partial[a.id] = it }
            } catch (e: Exception) { errors += "${a.name}: ${e.message}" }
            Thread.sleep(200)
        }
        val firstRun = c.paperStart == null
        c = c.copy(at = System.currentTimeMillis(), levels = levels, partial = partial, partialMonth = month, errors = errors,
            paperStart = c.paperStart ?: month)
        // notis när innehaven ändras vid ett nytt månadsskifte (inte första gången appen räknar)
        val alloc = build(c)
        val notify = mutableListOf<SignalRecord>()
        val d = alloc.latest
        if (d != null && !firstRun && (d.bought.isNotEmpty() || d.sold.isNotEmpty())) {
            val key = "gtf:${d.signalMonth}"
            if (key !in c.notified) {
                fun names(ids: List<String>) = ids.joinToString(", ") { id -> ALLOCATION_ASSETS.first { it.id == id }.name }
                notify += SignalRecord(
                    key = key, time = System.currentTimeMillis(), type = SignalType.REBALANCE, signalDate = d.signalMonth,
                    action = "Global trendföljning: köp ${names(d.bought)}, sälj ${names(d.sold)}",
                    reason = "Papperhandel. Nya topp 3 efter månadsslutet ${d.signalMonth}: ${names(d.holdings)}. Forskningskandidat, inte SwingEdges målportfölj.",
                )
                c = c.copy(notified = (c.notified + key).takeLast(100))
            }
        }
        store.allocation = c
        return build(c, notify)
    }

    /** Aktieuniversumet som följer med appen (Large + Mid Cap Stockholm med Avanzas orderbok-id). */
    fun universe(): List<Triple<String, String, String>> {
        val ctx = context ?: return emptyList()
        val raw = ctx.assets.open("stock_universe.json").bufferedReader().use { it.readText() }
        return json.parseToJsonElement(raw).jsonObject["stocks"]!!.jsonArray.map {
            val o = it.jsonObject
            Triple(o["id"]!!.jsonPrimitive.content, o["name"]!!.jsonPrimitive.content, o["ticker"]!!.jsonPrimitive.content)
        }
    }

    fun cachedScanner(): ScannerCache = store.scanner

    /** Hämtar dagens nyckeltal för hela universumet, sex anrop åt gången. Tar ungefär en halv minut. */
    fun scan(force: Boolean = false, progress: (Int, Int) -> Unit = { _, _ -> }): ScannerCache {
        val old = store.scanner
        if (!force && System.currentTimeMillis() - old.at < SCAN_EVERY_MS && old.stocks.isNotEmpty()) return old
        val u = universe()
        val pool = Executors.newFixedThreadPool(6)
        val done = java.util.concurrent.atomic.AtomicInteger()
        val futures = u.map { (id, name, ticker) ->
            pool.submit<StockSnapshot?> {
                try { parseStock(id, name, ticker, MarketData.get("https://www.avanza.se/_api/market-guide/stock/$id")) }
                catch (e: Exception) { null }
                finally { progress(done.incrementAndGet(), u.size) }
            }
        }
        val stocks = futures.mapNotNull { runCatching { it.get(60, TimeUnit.SECONDS) }.getOrNull() }
        pool.shutdown()
        val out = ScannerCache(System.currentTimeMillis(), stocks, u.size - stocks.size)
        if (stocks.isNotEmpty()) store.scanner = out
        return if (stocks.isNotEmpty()) out else old.copy(errors = u.size)
    }

    /** Nästa ombalansering för Global trendföljning: sista handelsdagen i innevarande månad på Stockholmsbörsen. */
    fun nextRebalance(today: LocalDate = LocalDate.now(STOCKHOLM)): LocalDate {
        val ex = se.dahlander.swingedge.core.Exchange.XSTO
        val d = ex.lastTradingDayOfMonth(today.year, today.monthValue)
        return if (d.isBefore(today)) YearMonth.from(today).plusMonths(1).let { ex.lastTradingDayOfMonth(it.year, it.monthValue) } else d
    }
}
