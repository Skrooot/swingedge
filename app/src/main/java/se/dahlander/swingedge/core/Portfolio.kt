package se.dahlander.swingedge.core

import kotlinx.serialization.Serializable
import kotlin.math.abs

@Serializable
enum class Side { BUY, SELL, DEPOSIT, WITHDRAW }

/**
 * En registrerad affär. Pris och avgift anges i instrumentets valuta; fxToSek räknar om till kronor
 * (1.0 för SEK-instrument). Insättning och uttag har instrument = null och belopp i [price] (SEK).
 */
@Serializable
data class Trade(
    val id: String,
    val date: String,
    val side: Side,
    val instrument: Instrument? = null,
    val quantity: Double = 0.0,
    val price: Double = 0.0,
    val feeSek: Double = 0.0,
    val fxToSek: Double = 1.0,
    val note: String = "",
)

data class Position(
    val instrument: Instrument,
    val quantity: Double,
    /** Genomsnittligt anskaffningsvärde i SEK per andel, inklusive courtage (genomsnittsmetoden). */
    val avgCostSek: Double,
    val realizedSek: Double,
)

data class Ledger(val cashSek: Double, val positions: Map<Instrument, Position>, val depositedSek: Double, val realizedSek: Double)

/** Bokför affärer i datumordning med genomsnittsmetoden, som Skatteverket använder. */
fun ledger(trades: List<Trade>): Ledger {
    var cash = 0.0
    var deposited = 0.0
    val pos = mutableMapOf<Instrument, Position>()
    for (t in trades.sortedWith(compareBy({ it.date }, { it.id }))) {
        when (t.side) {
            Side.DEPOSIT -> { cash += t.price; deposited += t.price }
            Side.WITHDRAW -> { cash -= t.price; deposited -= t.price }
            Side.BUY -> {
                val ins = t.instrument ?: continue
                val cost = t.quantity * t.price * t.fxToSek + t.feeSek
                cash -= cost
                val p = pos[ins] ?: Position(ins, 0.0, 0.0, 0.0)
                val q = p.quantity + t.quantity
                pos[ins] = p.copy(quantity = q, avgCostSek = (p.quantity * p.avgCostSek + cost) / q)
            }
            Side.SELL -> {
                val ins = t.instrument ?: continue
                val p = pos[ins] ?: Position(ins, 0.0, 0.0, 0.0)
                val proceeds = t.quantity * t.price * t.fxToSek - t.feeSek
                cash += proceeds
                val q = p.quantity - t.quantity
                pos[ins] = p.copy(
                    quantity = if (abs(q) < 1e-9) 0.0 else q,
                    realizedSek = p.realizedSek + proceeds - t.quantity * p.avgCostSek,
                )
            }
        }
    }
    return Ledger(cash, pos, deposited, pos.values.sumOf { it.realizedSek })
}

/** Senaste kurs för en produkt, i produktens valuta, med tidpunkt. */
data class Quote(val instrument: Instrument, val price: Double, val previousClose: Double?, val time: java.time.Instant, val fxToSek: Double)

data class Holding(val position: Position, val valueSek: Double, val weight: Double, val unrealizedSek: Double, val dayChangeSek: Double?)

data class Valuation(val totalSek: Double, val cashSek: Double, val investedSek: Double, val holdings: Map<Instrument, Holding>, val dayChangeSek: Double?)

fun value(ledger: Ledger, quotes: Map<Instrument, Quote>): Valuation {
    val values = ledger.positions.values.filter { it.quantity > 0 }.associate { p ->
        val q = quotes[p.instrument]
        p.instrument to (if (q == null) p.quantity * p.avgCostSek else p.quantity * q.price * q.fxToSek)
    }
    val invested = values.values.sum()
    val total = invested + ledger.cashSek
    var dayChange: Double? = 0.0
    val holdings = ledger.positions.values.filter { it.quantity > 0 }.associate { p ->
        val v = values.getValue(p.instrument)
        val q = quotes[p.instrument]
        val dc = if (q?.previousClose != null) p.quantity * (q.price - q.previousClose) * q.fxToSek else null
        if (dc == null) dayChange = null else dayChange = dayChange?.plus(dc)
        p.instrument to Holding(p, v, if (total > 0) v / total else 0.0, v - p.quantity * p.avgCostSek, dc)
    }
    return Valuation(total, ledger.cashSek, invested, holdings, dayChange)
}

/** Strategiernas läge som målportföljen räknas från. */
data class StrategyStates(val btcInvested: Boolean, val spInvested: Boolean)

/** Målvikt per instrument och per strategi. En avstängd trendstrategi ger kontanter, inte andra instrument. */
data class Target(val perStrategy: Map<StrategyId, Map<Instrument, Double>>, val total: Map<Instrument, Double>, val cash: Double)

fun target(states: StrategyStates, sleeves: Map<StrategyId, Double> = DEFAULT_SLEEVES): Target {
    val btc = sleeves.getValue(StrategyId.BTC_TREND)
    val ew = sleeves.getValue(StrategyId.EQUAL_WEIGHT)
    val sp = sleeves.getValue(StrategyId.SP500_TREND)
    val per = mapOf(
        StrategyId.BTC_TREND to if (states.btcInvested) mapOf(Instrument.XBT to btc) else emptyMap(),
        StrategyId.EQUAL_WEIGHT to listOf(Instrument.XACT, Instrument.SXR8, Instrument.XBT).associateWith { ew / 3 },
        StrategyId.SP500_TREND to if (states.spInvested) mapOf(Instrument.SXR8 to sp) else emptyMap(),
    )
    val total = Instrument.entries.associateWith { ins -> per.values.sumOf { it[ins] ?: 0.0 } }
    return Target(per, total, 1.0 - total.values.sum())
}

data class Order(val instrument: Instrument, val side: Side, val amountSek: Double, val fromWeight: Double, val toWeight: Double, val reason: String)

/**
 * En order per instrument, även när flera strategier äger samma instrument (vikterna summeras först).
 * [instruments] begränsar vilka instrument som får ordrar (t.ex. bara de vars trend just bytt läge).
 */
fun orders(valuation: Valuation, target: Target, instruments: Set<Instrument>, tolerance: Double, reason: (Instrument) -> String): List<Order> {
    if (valuation.totalSek <= 0) return emptyList()
    return instruments.sortedBy { it.ordinal }.mapNotNull { ins ->
        val now = valuation.holdings[ins]?.weight ?: 0.0
        val goal = target.total[ins] ?: 0.0
        val diff = goal - now
        if (abs(diff) <= tolerance) null
        else Order(ins, if (diff > 0) Side.BUY else Side.SELL, abs(diff) * valuation.totalSek, now, goal, reason(ins))
    }
}
