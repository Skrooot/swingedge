package se.dahlander.swingedge.data

import android.content.Context
import se.dahlander.swingedge.core.AnalysisResult
import se.dahlander.swingedge.core.BacktestLine
import se.dahlander.swingedge.core.BacktestRun
import se.dahlander.swingedge.core.Rules
import se.dahlander.swingedge.core.Backtests
import se.dahlander.swingedge.core.Instrument
import se.dahlander.swingedge.core.SignalRecord
import se.dahlander.swingedge.core.SignalType
import se.dahlander.swingedge.core.analyze
import se.dahlander.swingedge.core.ledger
import se.dahlander.swingedge.core.metrics
import se.dahlander.swingedge.core.repairGaps
import se.dahlander.swingedge.core.toSek
import se.dahlander.swingedge.core.value
import java.time.Instant
import java.time.LocalDate

/** Samordnar hämtning, analys och lagring. Används av både appen och bakgrundsjobbet. */
class Repository(context: Context) {
    companion object { private val REFRESH_LOCK = Any() }
    val store = Store(context.applicationContext)

    data class Outcome(val result: AnalysisResult, val cache: MarketData.Cache, val fetchOk: Boolean, val notify: List<SignalRecord>)

    /**
     * Hämtar kurser (om [fetch]) och kör analysen för den aktiva portföljen. Misslyckas hämtningen används
     * tidigare kurser, och datakontrollen avgör om de är för gamla för nya signaler.
     */
    // Ett lås för hela processen: appen och bakgrundsjobbet har var sin Repository-instans. Utan det kunde två
    // samtidiga körningar läsa samma tidigare läge och skicka samma notis två gånger.
    fun refresh(trigger: String, fetch: Boolean = true, now: Instant = Instant.now()): Outcome = synchronized(REFRESH_LOCK) { refreshLocked(trigger, fetch, now) }

    private fun refreshLocked(trigger: String, fetch: Boolean, now: Instant): Outcome {
        val settings = store.settings
        val prevCache = store.cache
        var cache = prevCache ?: MarketData.Cache()
        var fetchOk = true
        if (fetch) {
            cache = try { MarketData.fetchAll(prevCache) } catch (e: Exception) {
                (prevCache ?: MarketData.Cache()).copy(errors = listOf("Hämtningen misslyckades: ${e.message}"))
            }
            fetchOk = cache.errors.isEmpty()
            store.cache = cache
            store.fetchFailures = if (fetchOk) 0 else store.fetchFailures + 1
        }
        val kind = settings.active
        val prev = store.engine(kind)
        val result = analyze(now, MarketData.snapshot(cache), store.trades(kind), prev, se.dahlander.swingedge.core.DEFAULT_SLEEVES, se.dahlander.swingedge.core.EW_BASE)
        store.saveEngine(kind, result.state)
        store.appendSignals(kind, result.newSignals)
        // forward test: bara signaler som skapas nu, följda med produktens kurser
        store.saveForward(kind, se.dahlander.swingedge.core.ForwardTest.update(store.forward(kind), result.newSignals, MarketData.snapshot(cache).quotes, now.toEpochMilli()))

        val notify = result.newSignals.filter { it.type != SignalType.START && it.type != SignalType.HOLD }.toMutableList()
        // Misslyckad uppdatering: notis efter tre misslyckade försök i rad, högst en gång per dag
        if (fetch && store.fetchFailures == 3) notify += SignalRecord(
            key = "fetchfail:${LocalDate.now()}", time = now.toEpochMilli(), type = SignalType.DATA_ERROR,
            signalDate = LocalDate.now().toString(), action = "Kontrollera internetanslutningen",
            reason = "Kurserna kunde inte hämtas tre gånger i rad. ${cache.errors.firstOrNull() ?: ""}",
        ).also { store.appendSignals(kind, listOf(it)) }
        // Planerad kontroll som inte kunnat genomföras: ingen lyckad analys på över 26 timmar
        val last = result.state.lastSuccess
        if (last != null && now.toEpochMilli() - last > 26 * 3600_000L) {
            val key = "missed:${LocalDate.now()}"
            if (key !in prev.emitted) {
                val r = SignalRecord(key = key, time = now.toEpochMilli(), type = SignalType.MISSED, signalDate = LocalDate.now().toString(),
                    action = "Öppna appen och uppdatera", reason = "Ingen fullständig analys sedan ${Instant.ofEpochMilli(last)}.")
                notify += r
                store.appendSignals(kind, listOf(r))
                store.saveEngine(kind, result.state.copy(emitted = result.state.emitted + key))
            }
        }
        val led = ledger(store.trades(kind))
        if (result.valuation.totalSek > 0) store.saveSnapshot(kind, Snapshot(LocalDate.now().toString(), result.valuation.totalSek, led.depositedSek))
        store.appendRun(RunLog(
            now.toEpochMilli(), fetchOk, result.checks.values.map { "${it.status}: ${it.message}" } + cache.errors,
            result.btc?.let { "BTC ${it.asOf} close ${it.close} SMA150 ${it.sma} streak ${it.streak}/${Rules.CRYPTO_CONFIRM} -> ${if (it.invested) "investerad" else "kontanter"}" },
            result.sp?.let { "S&P ${it.decision.date} close ${it.decision.close} SMA200 ${it.decision.sma} -> ${if (it.decision.invested) "investerad" else "kontanter"}" },
            result.target?.total?.mapKeys { it.key.name } ?: emptyMap(),
            result.orders.map { "${it.side} ${it.instrument.name} ${it.amountSek.toInt()} kr" },
            trigger,
        ))
        return Outcome(result, cache, fetchOk, notify)
    }

    /** Valfri portfölj räknad mot senaste kurser, utan att ändra den aktiva portföljens tillstånd. */
    fun preview(kind: PortfolioKind, now: Instant = Instant.now()): AnalysisResult? {
        val cache = store.cache ?: return null
        return analyze(now, MarketData.snapshot(cache), store.trades(kind), store.engine(kind), se.dahlander.swingedge.core.DEFAULT_SLEEVES, se.dahlander.swingedge.core.EW_BASE)
    }

    /** Nytt backtest med de frysta reglerna på hela den historik som Yahoo har. */
    fun runBacktest(): BacktestRun {
        val errors = mutableListOf<String>()
        fun load(s: String) = try { MarketData.yahoo(s, null).bars() } catch (e: Exception) { errors += "$s: ${e.message}"; emptyList() }
        val btc = load("BTC-USD"); val xbt = load(Instrument.XBT.yahoo); val sp = load("^GSPC")
        val sxr8 = load(Instrument.SXR8.yahoo); val xact = load(Instrument.XACT.yahoo); val omx = load("^OMX"); val eursek = load("EURSEK=X")
        val gold = load(Instrument.GOLD.yahoo)
        val lines = mutableListOf<BacktestLine>()
        if (btc.isNotEmpty() && xbt.isNotEmpty()) {
            val (s, b) = Backtests.btcOnProduct(btc, xbt)
            for (from in listOf<LocalDate?>(null, LocalDate.of(2022, 1, 1))) {
                metrics(s, from)?.let { lines += BacktestLine("Bitcoin Trend på Bitcoin Tracker One" + if (from != null) ", från 2022" else ", hela historiken", it, metrics(b, from), "Köp och behåll", "Affär på stängningen dagen efter signalen") }
            }
        }
        if (sp.isNotEmpty()) {
            val (s, b) = Backtests.sp500OnIndex(sp)
            for (from in listOf(LocalDate.of(1980, 1, 1), LocalDate.of(2015, 1, 1))) {
                metrics(s, from)?.let { lines += BacktestLine("S&P 500 Trend på index, från ${from.year}", it, metrics(b, from), "Köp och behåll", "Index utan utdelning som proxy för SXR8") }
            }
        }
        if (xact.isNotEmpty() && omx.isNotEmpty() && sxr8.isNotEmpty() && eursek.isNotEmpty() && xbt.isNotEmpty() && gold.isNotEmpty()) {
            val xactFixed = repairGaps(xact, omx)
            val ew = Backtests.equalWeight(listOf(xactFixed, toSek(sxr8, eursek), xbt, toSek(gold, eursek)),
                listOf(Backtests.COST_SE, Backtests.COST_FOREIGN, Backtests.COST_CRYPTO, Backtests.COST_FOREIGN))
            for (from in listOf<LocalDate?>(null, LocalDate.of(2021, 1, 1))) {
                metrics(ew, from)?.let { lines += BacktestLine("Lika vikt, fyra produkter i SEK" + if (from != null) ", från 2021" else ", hela historiken", it, null, "", "Ombalansering vid Stockholmsbörsens månadsslut") }
            }
        }
        val run = BacktestRun(System.currentTimeMillis(), listOf(btc, sp, xbt).mapNotNull { it.lastOrNull()?.date }.minOrNull()?.toString() ?: "", lines, errors)
        store.backtests = store.backtests + run
        return run
    }

    fun valuationOf(kind: PortfolioKind) = store.cache?.let { value(ledger(store.trades(kind)), MarketData.snapshot(it).quotes) }
}
