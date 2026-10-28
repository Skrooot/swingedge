package se.dahlander.swingedge.data

import android.content.Context
import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import se.dahlander.swingedge.core.BacktestRun
import kotlinx.serialization.json.Json
import se.dahlander.swingedge.core.DEFAULT_SLEEVES
import se.dahlander.swingedge.core.EngineState
import se.dahlander.swingedge.core.SignalRecord
import se.dahlander.swingedge.core.StrategyId
import se.dahlander.swingedge.core.Trade
import java.io.File

@Serializable
enum class PortfolioKind(val label: String) { REAL("Verklig portfölj"), PAPER("Papperskonto") }

@Serializable
data class Settings(
    val sleeves: Map<StrategyId, Double> = DEFAULT_SLEEVES,
    val active: PortfolioKind = PortfolioKind.REAL,
    val notifications: Boolean = true,
    val experimentalRotation: Boolean = false,
    /** Tillval: Xetra-Gold som fjärde instrument i lika vikt (testat efter rapporten). */
    val includeGold: Boolean = false,
    /** Notiser för nya köpsignaler i Global Opportunities, från och med denna evidensnivå. */
    val edgeNotify: Boolean = true,
    val edgeMinEvidence: String = "Stark hypotes",
)

/** Dagsserier för Global Opportunities: marknad -> datum och stängningar, plus vilka köpsignaler som redan notifierats. */
@Serializable
data class EdgeSeriesCache(
    val at: Long = 0,
    val researchAt: Long = 0,
    val series: Map<String, List<List<String>>> = emptyMap(),
    val errors: List<String> = emptyList(),
    val notified: List<String> = emptyList(),
)

/** Ett dagligt värde per portfölj, för utvecklingsgrafen. */
@Serializable
data class Snapshot(val date: String, val totalSek: Double, val depositedSek: Double)

/** Logg över varje körning: indata, beräkning och resultat, så att ett beslut kan återskapas. */
@Serializable
data class RunLog(
    val time: Long,
    val ok: Boolean,
    val checks: List<String>,
    val btc: String?,
    val sp: String?,
    val target: Map<String, Double>,
    val orders: List<String>,
    val trigger: String,
)

/** Enkel fillagring i appens privata katalog. Allt ligger på telefonen. */
class Store(context: Context) {
    private val dir = File(context.filesDir, "swingedge").apply { mkdirs() }
    private val json = Json { ignoreUnknownKeys = true; encodeDefaults = true; allowStructuredMapKeys = true }
    private val lock = Any()

    private fun <T> read(name: String, ser: KSerializer<T>, default: () -> T): T = synchronized(lock) {
        val f = File(dir, name)
        if (!f.exists()) return default()
        try { json.decodeFromString(ser, f.readText()) } catch (e: Exception) { default() }
    }

    private fun <T> write(name: String, ser: KSerializer<T>, value: T) {
        synchronized(lock) {
            val tmp = File(dir, "$name.tmp")
            tmp.writeText(json.encodeToString(ser, value))
            val target = File(dir, name)
            if (!tmp.renameTo(target)) { target.delete(); tmp.renameTo(target) }
        }
    }

    var settings: Settings
        get() = read("settings.json", Settings.serializer()) { Settings() }
        set(v) = write("settings.json", Settings.serializer(), v)

    fun trades(kind: PortfolioKind): List<Trade> = read("trades_${kind.name}.json", ListSerializer(Trade.serializer())) { emptyList() }
    fun saveTrades(kind: PortfolioKind, v: List<Trade>) = write("trades_${kind.name}.json", ListSerializer(Trade.serializer()), v)

    fun engine(kind: PortfolioKind): EngineState = read("engine_${kind.name}.json", EngineState.serializer()) { EngineState() }
    fun saveEngine(kind: PortfolioKind, v: EngineState) = write("engine_${kind.name}.json", EngineState.serializer(), v)

    fun signals(kind: PortfolioKind): List<SignalRecord> = read("signals_${kind.name}.json", ListSerializer(SignalRecord.serializer())) { emptyList() }
    fun appendSignals(kind: PortfolioKind, add: List<SignalRecord>) {
        if (add.isEmpty()) return
        write("signals_${kind.name}.json", ListSerializer(SignalRecord.serializer()), (signals(kind) + add).takeLast(1000))
    }

    fun snapshots(kind: PortfolioKind): List<Snapshot> = read("snap_${kind.name}.json", ListSerializer(Snapshot.serializer())) { emptyList() }
    fun saveSnapshot(kind: PortfolioKind, s: Snapshot) {
        val list = snapshots(kind).filter { it.date != s.date } + s
        write("snap_${kind.name}.json", ListSerializer(Snapshot.serializer()), list.sortedBy { it.date }.takeLast(3000))
    }

    var cache: MarketData.Cache?
        get() = read("market.json", MarketData.Cache.serializer()) { MarketData.Cache() }.takeIf { it.at > 0 }
        set(v) = write("market.json", MarketData.Cache.serializer(), v ?: MarketData.Cache())

    fun runs(): List<RunLog> = read("runs.json", ListSerializer(RunLog.serializer())) { emptyList() }
    fun appendRun(r: RunLog) = write("runs.json", ListSerializer(RunLog.serializer()), (runs() + r).takeLast(300))

    var backtests: List<BacktestRun>
        get() = read("backtests.json", ListSerializer(BacktestRun.serializer())) { emptyList() }
        set(v) = write("backtests.json", ListSerializer(BacktestRun.serializer()), v.takeLast(10))

    /** Forskningsresultatet från edge.py (edge-app.json) som det senast hämtades. */
    var edgeRaw: String?
        get() = synchronized(this) { File(dir, "edge-app.json").takeIf { it.exists() }?.readText() }
        set(v) { synchronized(this) { if (v != null) File(dir, "edge-app.json").writeText(v) } }

    var edgeSeries: EdgeSeriesCache
        get() = read("edge_series.json", EdgeSeriesCache.serializer()) { EdgeSeriesCache() }
        set(v) = write("edge_series.json", EdgeSeriesCache.serializer(), v)

    /** Antal misslyckade datahämtningar i rad och om en notis redan skickats för dem. */
    var fetchFailures: Int
        get() = read("failures.json", Int.serializer()) { 0 }
        set(v) = write("failures.json", Int.serializer(), v)
}
