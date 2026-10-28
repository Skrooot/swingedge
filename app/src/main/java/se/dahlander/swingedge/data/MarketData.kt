package se.dahlander.swingedge.data

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.double
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import se.dahlander.swingedge.core.Bar
import se.dahlander.swingedge.core.Instrument
import se.dahlander.swingedge.core.MarketSnapshot
import se.dahlander.swingedge.core.Quote
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneOffset

/**
 * Kurser från Yahoo Finance (chart-API, samma som studien använde) och Binance (offentligt API, reserv för BTC).
 * Båda är öppna utan nyckel. Appen identifierar sig med ett ärligt User-Agent och hämtar sällan.
 */
object MarketData {
    private const val UA = "SwingEdge/1.0 (Android; personlig signalapp)"
    private val json = Json { ignoreUnknownKeys = true }

    @Serializable
    data class Series(
        val symbol: String,
        val currency: String? = null,
        val dates: List<String>,
        val closes: List<Double>,
        /** Senaste handelns pris och tidpunkt enligt källan (kan vara en pågående dag). */
        val lastPrice: Double? = null,
        val lastTime: Long? = null,
        val fetchedAt: Long,
    ) {
        fun bars(): List<Bar> = dates.indices.map { Bar(LocalDate.parse(dates[it]), closes[it]) }
    }

    internal fun get(url: String): String {
        var last: Exception? = null
        repeat(3) { attempt ->
            try {
                val c = URL(url).openConnection() as HttpURLConnection
                c.setRequestProperty("User-Agent", UA)
                c.connectTimeout = 15000
                c.readTimeout = 20000
                val code = c.responseCode
                if (code == 200) return c.inputStream.bufferedReader().use { it.readText() }
                if (code == 404) throw IOException("Hittades inte ($url)")
                last = IOException("Servern svarade $code")
            } catch (e: Exception) {
                last = e
            }
            Thread.sleep(1500L * (attempt + 1))
        }
        throw last ?: IOException("Okänt fel")
    }

    /** Dagsstaplar från Yahoo. range t.ex. "2y"; period1 = 0 ger hela historiken. */
    fun yahoo(symbol: String, range: String? = "2y"): Series {
        val q = URLEncoder.encode(symbol, "UTF-8")
        val span = if (range != null) "range=$range" else "period1=0&period2=${Instant.now().epochSecond}"
        val body = get("https://query1.finance.yahoo.com/v8/finance/chart/$q?$span&interval=1d&events=div%2Csplit")
        val res = json.parseToJsonElement(body).jsonObject["chart"]!!.jsonObject["result"]!!.jsonArray[0].jsonObject
        val meta = res["meta"]!!.jsonObject
        val offset = meta["gmtoffset"]?.jsonPrimitive?.longOrNull ?: 0L
        val ts = (res["timestamp"] as? JsonArray)?.map { it.jsonPrimitive.longOrNull } ?: emptyList()
        val ind = res["indicators"]!!.jsonObject
        val adj = (ind["adjclose"] as? JsonArray)?.getOrNull(0)?.jsonObject?.get("adjclose") as? JsonArray
        val close = (ind["quote"]!!.jsonArray[0].jsonObject["close"] as JsonArray)
        val src = adj ?: close
        val byDate = sortedMapOf<String, Double>()
        for (i in ts.indices) {
            val t = ts[i] ?: continue
            val v = src.getOrNull(i)?.jsonPrimitive?.doubleOrNull ?: continue
            if (v <= 0) continue
            val d = Instant.ofEpochSecond(t + offset).atOffset(ZoneOffset.UTC).toLocalDate().toString()
            byDate[d] = v
        }
        if (byDate.isEmpty()) throw IOException("Inga kurser för $symbol")
        return Series(
            symbol, meta["currency"]?.jsonPrimitive?.content, byDate.keys.toList(), byDate.values.toList(),
            meta["regularMarketPrice"]?.jsonPrimitive?.doubleOrNull,
            meta["regularMarketTime"]?.jsonPrimitive?.longOrNull?.times(1000),
            System.currentTimeMillis(),
        )
    }

    /** BTC-USD från Binance (BTCUSDT) som reserv om Yahoo inte svarar. Datum = UTC-dag som staplarna öppnar. */
    fun binanceBtc(days: Int = 400): Series {
        val body = get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=$days")
        val arr = json.parseToJsonElement(body).jsonArray
        val dates = mutableListOf<String>()
        val closes = mutableListOf<Double>()
        for (k in arr) {
            val a = k.jsonArray
            dates += Instant.ofEpochMilli(a[0].jsonPrimitive.longOrNull!!).atOffset(ZoneOffset.UTC).toLocalDate().toString()
            closes += a[4].jsonPrimitive.content.toDouble()
        }
        return Series("BTC-USD", "USD", dates, closes, closes.lastOrNull(), System.currentTimeMillis(), System.currentTimeMillis())
    }

    @Serializable
    data class Cache(val series: Map<String, Series> = emptyMap(), val errors: List<String> = emptyList(), val at: Long = 0)

    val PRODUCT_SYMBOLS = Instrument.entries.map { it.yahoo }
    const val EURSEK = "EURSEK=X"

    /** Hämtar allt analysen behöver. Fel på en källa stoppar inte de andra; tidigare data behålls som reserv. */
    fun fetchAll(previous: Cache?): Cache {
        val out = (previous?.series ?: emptyMap()).toMutableMap()
        val errors = mutableListOf<String>()
        fun load(key: String, f: () -> Series) {
            try { out[key] = f() } catch (e: Exception) { errors += "$key: ${e.message ?: e.javaClass.simpleName}" }
        }
        load("BTC-USD") {
            try { yahoo("BTC-USD", "2y") } catch (e: Exception) { binanceBtc() }
        }
        load("^GSPC") { yahoo("^GSPC", "2y") }
        for (s in PRODUCT_SYMBOLS + EURSEK) load(s) { yahoo(s, "1y") }
        return Cache(out, errors, System.currentTimeMillis())
    }

    fun snapshot(cache: Cache): MarketSnapshot {
        val fx = cache.series[EURSEK]?.let { it.lastPrice ?: it.closes.last() } ?: 0.0
        val quotes = Instrument.entries.mapNotNull { ins ->
            val s = cache.series[ins.yahoo] ?: return@mapNotNull null
            val price = s.lastPrice ?: s.closes.last()
            val time = s.lastTime ?: s.fetchedAt
            val lastDay = Instant.ofEpochMilli(time).atZone(ins.exchange.zone).toLocalDate().toString()
            val prev = s.dates.indices.lastOrNull { s.dates[it] < lastDay }?.let { s.closes[it] }
            val rate = if (ins.currency == "SEK") 1.0 else fx
            if (rate <= 0) null else ins to Quote(ins, price, prev, Instant.ofEpochMilli(time), rate)
        }.toMap()
        return MarketSnapshot(
            btc = cache.series["BTC-USD"]?.bars() ?: emptyList(),
            sp500 = cache.series["^GSPC"]?.bars() ?: emptyList(),
            quotes = quotes,
            productBars = Instrument.entries.associateWith { cache.series[it.yahoo]?.bars() ?: emptyList() },
            fetchErrors = cache.errors,
        )
    }
}

@Suppress("unused")
private fun JsonObject.d(k: String) = this[k]?.jsonPrimitive?.double
