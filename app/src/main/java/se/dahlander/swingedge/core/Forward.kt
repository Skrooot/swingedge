package se.dahlander.swingedge.core

import kotlinx.serialization.Serializable

/**
 * Forward test: köp- och säljsignaler loggas när appen faktiskt räknar fram dem, och följs upp med produktens
 * kurser därefter. Inget läggs in i efterhand. Startläget (första körningen) är ingen signal och loggas inte.
 */
@Serializable
data class ForwardEntry(
    val id: String,
    val strategy: StrategyId,
    val instrument: Instrument,
    /** Tidpunkten då appen skapade signalen (inte signaldagen). */
    val loggedAt: Long,
    val signalDate: String,
    val underlyingPrice: Double?,
    val indicator: String,
    val executableFrom: Long?,
    /** Första observerade produktkurs efter att signalen gick att handla, i produktens valuta, och växelkursen. */
    val entryPrice: Double? = null,
    val entryFx: Double? = null,
    val entryTime: Long? = null,
    /** Kostnad per sida som andel (samma som backtestet: 0,40 %). */
    val costPerSide: Double = Backtests.COST_CRYPTO,
    val lastPrice: Double? = null,
    val lastFx: Double? = null,
    val lastTime: Long? = null,
    /** Säljsignalen som stänger positionen; utgångskursen fylls i när den gick att handla. */
    val exitSignal: String? = null,
    val exitExecutableFrom: Long? = null,
    val exitPrice: Double? = null,
    val exitFx: Double? = null,
    val exitTime: Long? = null,
    val exitReason: String? = null,
) {
    val open get() = exitTime == null

    /** Avkastning i SEK efter köp- och säljkostnad, till utgången eller till senaste kurs. */
    fun returnSek(): Double? {
        val e = entryPrice ?: return null; val ef = entryFx ?: return null
        val (p, f) = if (exitPrice != null && exitFx != null) exitPrice to exitFx else (lastPrice ?: return null) to (lastFx ?: return null)
        return (p * f) / (e * ef) * (1 - costPerSide) * (1 - costPerSide) - 1
    }
}

object ForwardTest {
    private val tracked = setOf(SignalType.BUY, SignalType.SELL)

    /** Uppdaterar loggen med nya signaler och dagens kurser. Ren funktion. */
    fun update(log: List<ForwardEntry>, newSignals: List<SignalRecord>, quotes: Map<Instrument, Quote>, nowMs: Long): List<ForwardEntry> {
        val out = log.toMutableList()
        for (s in newSignals) {
            val ins = s.instrument ?: continue
            val strat = s.strategy ?: continue
            if (s.type !in tracked) continue
            if (out.any { it.id == s.key }) continue
            if (s.type == SignalType.SELL) {
                // stäng öppna köp i samma strategi
                for (i in out.indices) {
                    val e = out[i]
                    if (e.strategy == strat && e.open && e.exitSignal == null)
                        out[i] = e.copy(exitSignal = s.key, exitExecutableFrom = s.executableFrom, exitReason = "Säljsignal ${s.signalDate}")
                }
            } else {
                out += ForwardEntry(s.key, strat, ins, nowMs, s.signalDate, s.underlyingPrice, "${s.indicatorName} ${s.indicatorValue ?: ""}".trim(), s.executableFrom)
            }
        }
        for (i in out.indices) {
            val e = out[i]
            val q = quotes[e.instrument] ?: continue
            val qt = q.time.toEpochMilli()
            var x = e
            if (x.entryPrice == null && qt >= (x.executableFrom ?: 0)) x = x.copy(entryPrice = q.price, entryFx = q.fxToSek, entryTime = qt)
            if (x.open) {
                x = x.copy(lastPrice = q.price, lastFx = q.fxToSek, lastTime = qt)
                if (x.exitSignal != null && qt >= (x.exitExecutableFrom ?: 0)) x =
                    if (x.entryPrice != null) x.copy(exitPrice = q.price, exitFx = q.fxToSek, exitTime = qt)
                    else x.copy(exitTime = qt, exitReason = "Säljsignal innan köpet gick att genomföra")
            }
            out[i] = x
        }
        return out
    }
}
