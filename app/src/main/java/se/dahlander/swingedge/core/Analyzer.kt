package se.dahlander.swingedge.core

import kotlinx.serialization.Serializable
import java.time.Instant
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Rådata för en analys. Kurserna för signalkällor och produkter hålls isär. */
data class MarketSnapshot(
    val btc: List<Bar>,
    val sp500: List<Bar>,
    val quotes: Map<Instrument, Quote>,
    val productBars: Map<Instrument, List<Bar>> = emptyMap(),
    val fetchErrors: List<String> = emptyList(),
)

@Serializable
enum class SignalType(val label: String) {
    START("Startläge"), BUY("Köp"), SELL("Sälj"), HOLD("Behåll"), WAIT("Avvakta"),
    REBALANCE("Ombalansera"), DATA_ERROR("Datafel"), MISSED("Missad kontroll"),
}

@Serializable
data class SignalRecord(
    val key: String,
    val time: Long,
    val strategy: StrategyId? = null,
    val instrument: Instrument? = null,
    val type: SignalType,
    val signalDate: String,
    val underlyingPrice: Double? = null,
    val indicatorName: String = "",
    val indicatorValue: Double? = null,
    val targetWeight: Double? = null,
    val action: String,
    val reason: String,
    val executableFrom: Long? = null,
    /** Indata och beräkning, så att beslutet kan återskapas. */
    val inputs: Map<String, String> = emptyMap(),
)

/** Det som sparas mellan körningar. */
@Serializable
data class EngineState(
    val btcInvested: Boolean? = null,
    val btcDate: String? = null,
    val spInvested: Boolean? = null,
    val spDate: String? = null,
    /** Läget som portföljen senast var anpassad till. Ett byte mot detta ger en order. */
    val alignedBtc: Boolean? = null,
    val alignedSp: Boolean? = null,
    /** Månadsslutet (ÅÅÅÅ-MM-DD) vars ombalansering är klar. */
    val rebalancedFor: String? = null,
    val emitted: List<String> = emptyList(),
    val lastSuccess: Long? = null,
    val failures: Int = 0,
)

enum class Severity { INFO, ACTION, WARNING }

data class TodoItem(val severity: Severity, val title: String, val detail: String, val instrument: Instrument? = null)

enum class SignalStatus(val label: String) { ACTIVE("Aktiv"), PENDING("Väntar på börsöppning"), INVALID("Ogiltig, data saknas") }

data class AnalysisResult(
    val time: Instant,
    val checks: Map<String, DataCheck>,
    val btc: BtcTrendState?,
    val btcStatus: SignalStatus,
    val sp: Sp500TrendState?,
    val spStatus: SignalStatus,
    val rebalance: RebalanceSchedule,
    val rebalanceDue: Boolean,
    val states: StrategyStates?,
    val target: Target?,
    val valuation: Valuation,
    val orders: List<Order>,
    val todo: List<TodoItem>,
    val newSignals: List<SignalRecord>,
    val state: EngineState,
    val customSleeves: Boolean,
)

private val SV = Locale.forLanguageTag("sv-SE")
fun sek(v: Double): String = num(v) + " kr"
fun pct(v: Double, d: Int = 1): String = String.format(SV, "%.${d}f %%", v * 100)
fun num(v: Double, d: Int = 0): String = String.format(SV, "%,.${d}f", v).replace(' ', ' ').replace(' ', ' ')
private val TIME = DateTimeFormatter.ofPattern("d MMM HH:mm", SV).withZone(STOCKHOLM)
fun stockholmTime(t: Instant): String = TIME.format(t)

/**
 * Kör hela analysen. Ren funktion: samma indata ger samma resultat, och inget beslut tas på
 * ofärdiga staplar eller på data som är äldre än en handelsdag.
 */
fun analyze(
    now: Instant,
    market: MarketSnapshot,
    trades: List<Trade>,
    prev: EngineState,
    sleeves: Map<StrategyId, Double> = DEFAULT_SLEEVES,
    ew: List<Instrument> = EW_BASE,
): AnalysisResult {
    val btcBars = completedCryptoBars(market.btc, now)
    val spBars = completedExchangeBars(market.sp500, Exchange.NYSE, now)
    val checks = linkedMapOf(
        "BTC-USD" to checkCrypto(btcBars, now),
        "S&P 500" to checkExchange(spBars, Exchange.NYSE, now, "S&P 500"),
    )
    val btcCheck = checks.getValue("BTC-USD")
    val spCheck = checks.getValue("S&P 500")
    val signals = mutableListOf<SignalRecord>()
    val emitted = prev.emitted.toMutableSet()
    fun emit(r: SignalRecord) { if (r.key !in emitted) { emitted += r.key; signals += r } }

    // ---- Bitcoin Trend ----
    val btc = if (btcCheck.status == DataStatus.MISSING || btcCheck.status == DataStatus.BLOCKED) null else btcTrend(btcBars)
    val btcFresh = btcCheck.status == DataStatus.OK && btc != null
    var btcInvested = prev.btcInvested
    var btcDate = prev.btcDate
    if (btcFresh) {
        btc!!
        val changed = prev.btcInvested != null && prev.btcInvested != btc.invested
        btcInvested = btc.invested
        btcDate = btc.asOf.toString()
        val type = when {
            prev.btcInvested == null -> SignalType.START
            changed && btc.invested -> SignalType.BUY
            changed -> SignalType.SELL
            else -> null
        }
        if (type != null) emit(SignalRecord(
            key = "btc:${btc.asOf}:${btc.invested}", time = now.toEpochMilli(), strategy = StrategyId.BTC_TREND,
            instrument = Instrument.XBT, type = type, signalDate = btc.asOf.toString(), underlyingPrice = btc.close,
            indicatorName = "SMA${Rules.CRYPTO_SMA}", indicatorValue = btc.sma,
            targetWeight = if (btc.invested) sleeves[StrategyId.BTC_TREND] else 0.0,
            action = if (btc.invested) "Bitcoin Trend ska vara investerad i Bitcoin Tracker One" else "Bitcoin Trend ska ligga i kontanter",
            reason = "BTC-USD stängde ${num(btc.close)} USD ${if (btc.invested) "över" else "under eller på"} SMA${Rules.CRYPTO_SMA} ${num(btc.sma)} USD den ${btc.asOf}.",
            executableFrom = btc.executableFrom.toEpochMilli(),
            inputs = mapOf("bars" to btcBars.size.toString(), "close" to btc.close.toString(), "sma" to btc.sma.toString(),
                "asOf" to btc.asOf.toString(), "rule" to "investerad om close > SMA150"),
        ))
    }
    val btcStatus = when {
        btc == null || btcInvested == null -> SignalStatus.INVALID
        btcFresh && now.isBefore(btc.executableFrom) -> SignalStatus.PENDING
        else -> SignalStatus.ACTIVE
    }

    // ---- S&P 500 Trend ----
    val sp = if (spCheck.status == DataStatus.MISSING || spCheck.status == DataStatus.BLOCKED) null else sp500Trend(spBars, now)
    var spInvested = prev.spInvested
    var spDate = prev.spDate
    if (sp != null) {
        // Månadsbeslutet bygger på en redan passerad månadsstängning och påverkas inte av dagens data
        val d = sp.decision
        val changed = prev.spInvested != null && prev.spInvested != d.invested
        if (prev.spDate != d.date.toString() || prev.spInvested == null) {
            val type = when {
                prev.spInvested == null -> SignalType.START
                changed && d.invested -> SignalType.BUY
                changed -> SignalType.SELL
                else -> SignalType.HOLD
            }
            emit(SignalRecord(
                key = "sp:${d.date}:${d.invested}", time = now.toEpochMilli(), strategy = StrategyId.SP500_TREND,
                instrument = Instrument.SXR8, type = type, signalDate = d.date.toString(), underlyingPrice = d.close,
                indicatorName = "SMA${Rules.STOCK_SMA}", indicatorValue = d.sma,
                targetWeight = if (d.invested) sleeves[StrategyId.SP500_TREND] else 0.0,
                action = if (d.invested) "S&P 500 Trend ska vara investerad i SXR8" else "S&P 500 Trend ska ligga i kontanter",
                reason = "Månadskontroll ${d.date}: S&P 500 stängde ${num(d.close)} ${if (d.invested) "över" else "under eller på"} SMA${Rules.STOCK_SMA} ${num(d.sma)}.",
                executableFrom = d.executableFrom.toEpochMilli(),
                inputs = mapOf("monthEnd" to d.date.toString(), "close" to d.close.toString(), "sma" to d.sma.toString(),
                    "rule" to "investerad om månadsslutets close > SMA200"),
            ))
        }
        spInvested = d.invested
        spDate = d.date.toString()
    }
    val spStatus = when {
        sp == null || spInvested == null -> SignalStatus.INVALID
        now.isBefore(sp.decision.executableFrom) -> SignalStatus.PENDING
        else -> SignalStatus.ACTIVE
    }

    // ---- Data som saknas ----
    val failed = checks.values.filter { it.status != DataStatus.OK } + market.fetchErrors.map { DataCheck(DataStatus.MISSING, null, null, it) }
    val todayKey = now.atZone(STOCKHOLM).toLocalDate()
    if (checks.values.any { it.status == DataStatus.BLOCKED || it.status == DataStatus.MISSING }) emit(SignalRecord(
        key = "datafail:$todayKey", time = now.toEpochMilli(), type = SignalType.DATA_ERROR, signalDate = todayKey.toString(),
        action = "Inga nya signaler förrän data finns", reason = failed.joinToString(" ") { it.message },
    ))

    // ---- Målportfölj och ordrar ----
    val states = if (btcInvested != null && spInvested != null) StrategyStates(btcInvested, spInvested) else null
    val tgt = states?.let { target(it, sleeves, ew) }
    val valuation = value(ledger(trades), market.quotes)
    val schedule = rebalanceSchedule(now)
    val todayXsto = now.atZone(STOCKHOLM).toLocalDate()
    // Första körningen: portföljen byggs upp mot målet, så redan passerade månadsslut räknas som klara
    val firstRun = prev.rebalancedFor == null
    val rebalanceDue = !firstRun && prev.rebalancedFor != schedule.lastRebalanceClose.toString() && !todayXsto.isBefore(schedule.tradeDay)
    val empty = valuation.holdings.isEmpty()

    var aligned = prev.copy()
    val ords = mutableListOf<Order>()
    if (tgt != null && valuation.totalSek > 0) {
        val flagged = mutableSetOf<Instrument>()
        if (empty) flagged += Instrument.entries
        if (prev.alignedBtc != null && prev.alignedBtc != states.btcInvested) flagged += Instrument.XBT
        if (prev.alignedSp != null && prev.alignedSp != states.spInvested) flagged += Instrument.SXR8
        if (rebalanceDue) flagged += ew
        ords += orders(valuation, tgt, flagged, Rules.REBALANCE_TOLERANCE) { ins ->
            when {
                empty -> "Bygg upp målportföljen"
                ins == Instrument.XBT && prev.alignedBtc != states.btcInvested -> if (states.btcInvested) "Bitcoin-trenden blev positiv" else "Bitcoin-trenden blev negativ"
                ins == Instrument.SXR8 && prev.alignedSp != states.spInvested -> if (states.spInvested) "S&P 500 över SMA200 vid månadsskiftet" else "S&P 500 under SMA200 vid månadsskiftet"
                else -> "Månatlig ombalansering till lika vikt"
            }
        }
        // Portföljen räknas som anpassad när instrumentet ligger inom toleransen mot målet
        val within = { ins: Instrument -> ords.none { it.instrument == ins } }
        aligned = aligned.copy(
            alignedBtc = if (prev.alignedBtc == null || within(Instrument.XBT)) states.btcInvested else prev.alignedBtc,
            alignedSp = if (prev.alignedSp == null || within(Instrument.SXR8)) states.spInvested else prev.alignedSp,
            rebalancedFor = if (rebalanceDue && ew.all(within)) schedule.lastRebalanceClose.toString() else prev.rebalancedFor,
        )
        if (rebalanceDue) emit(SignalRecord(
            key = "rebalance:${schedule.lastRebalanceClose}", time = now.toEpochMilli(), strategy = StrategyId.EQUAL_WEIGHT,
            type = SignalType.REBALANCE, signalDate = schedule.lastRebalanceClose.toString(),
            targetWeight = sleeves[StrategyId.EQUAL_WEIGHT]!! / ew.size,
            action = "Ombalansera ${ew.joinToString { it.shortName }} till lika vikt",
            reason = "Månadsslut på Stockholmsbörsen ${schedule.lastRebalanceClose}. Handel från ${schedule.tradeDay}.",
        ))
    }

    // ---- Vad behöver jag göra idag? ----
    val todo = mutableListOf<TodoItem>()
    failed.forEach { todo += TodoItem(Severity.WARNING, "Data saknas eller är gamla", it.message) }
    if (trades.isEmpty()) todo += TodoItem(Severity.INFO, "Registrera ditt kapital",
        "Lägg in en insättning och dina innehav under Portfölj, så räknar appen fram konkreta ordrar.")
    for (o in ords) {
        val pending = when (o.instrument) {
            Instrument.XBT -> btcStatus == SignalStatus.PENDING
            Instrument.SXR8 -> spStatus == SignalStatus.PENDING && o.reason.startsWith("S&P")
            else -> false
        }
        val openAt = o.instrument.exchange.nextOpenAtOrAfter(now)
        todo += TodoItem(Severity.ACTION,
            "${if (o.side == Side.BUY) "Köp" else "Sälj"} ${o.instrument.shortName} för cirka ${sek(o.amountSek)}",
            "${o.reason}. Från ${pct(o.fromWeight)} till ${pct(o.toWeight)} av portföljen." +
                if (pending || now.isBefore(openAt)) " Kan läggas tidigast ${stockholmTime(openAt)}." else "",
            o.instrument)
    }
    if (rebalanceDue && ords.isEmpty() && valuation.totalSek > 0) todo += TodoItem(Severity.INFO, "Månadens ombalansering är klar", "Alla ${ew.size} instrument ligger inom 2 procentenheter från målvikten.")
    if (signals.any { it.type == SignalType.BUY || it.type == SignalType.SELL } && ords.isEmpty() && trades.isNotEmpty() && valuation.totalSek > 0)
        todo += TodoItem(Severity.INFO, "Strategin bytte läge", "Portföljen ligger redan inom toleransen mot målvikten.")
    if (todo.none { it.severity != Severity.INFO } && trades.isNotEmpty()) todo.add(0, TodoItem(Severity.INFO, "Inga åtgärder krävs", "Portföljen följer strategin."))

    val ok = btcFresh && sp != null && spCheck.status == DataStatus.OK
    if (firstRun) aligned = aligned.copy(rebalancedFor = schedule.lastRebalanceClose.toString())
    val state = aligned.copy(
        btcInvested = btcInvested, btcDate = btcDate, spInvested = spInvested, spDate = spDate,
        emitted = emitted.toList().takeLast(300),
        lastSuccess = if (ok) now.toEpochMilli() else prev.lastSuccess,
        failures = if (ok) 0 else prev.failures + 1,
    )
    val custom = sleeves != DEFAULT_SLEEVES || ew != EW_BASE
    return AnalysisResult(now, checks, btc, btcStatus, sp, spStatus, schedule, rebalanceDue, states, tgt, valuation, ords, todo, signals, state, custom)
}

/** Nästa planerade analys: efter BTC:s dagsstängning 00:00 UTC och efter NYSE:s stängning. */
fun nextPlannedAnalysis(now: Instant): Instant {
    val btc = now.atZone(UTC).toLocalDate().plusDays(1).atStartOfDay(UTC).toInstant().plusSeconds(20 * 60)
    var d = now.atZone(NEW_YORK).toLocalDate()
    var nyse = Exchange.NYSE.closeInstant(d).plusSeconds(20 * 60)
    while (!Exchange.NYSE.isTradingDay(d) || !nyse.isAfter(now)) { d = d.plusDays(1); nyse = Exchange.NYSE.closeInstant(d).plusSeconds(20 * 60) }
    return if (btc.isBefore(nyse)) btc else nyse
}

fun LocalDate.sv(): String = DateTimeFormatter.ofPattern("d MMMM yyyy", SV).format(this)
