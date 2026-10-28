package se.dahlander.swingedge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import se.dahlander.swingedge.core.AnalysisResult
import se.dahlander.swingedge.core.Instrument
import se.dahlander.swingedge.core.Order
import se.dahlander.swingedge.core.RESEARCH
import se.dahlander.swingedge.core.Rules
import se.dahlander.swingedge.core.Side
import se.dahlander.swingedge.core.StrategyId
import se.dahlander.swingedge.core.num
import se.dahlander.swingedge.core.pct
import se.dahlander.swingedge.core.sek
import se.dahlander.swingedge.data.MarketData

enum class Action(val label: String, val tone: Tone, val rank: Int) {
    BUY("Köp", Tone.PENDING, 0), SELL("Sälj", Tone.PENDING, 0), HOLD("Behåll", Tone.POSITIVE, 1), WAIT("Avvakta", Tone.NEUTRAL, 2),
}

data class Opportunity(val ins: Instrument, val action: Action, val goal: Double, val now: Double, val order: Order?)

/** Åtgärd per produkt, härledd från strategins målvikt, nuvarande innehav och dagens orderförslag. */
fun opportunities(r: AnalysisResult): List<Opportunity> = Instrument.entries.map { ins ->
    val goal = r.target?.total?.get(ins) ?: 0.0
    val now = r.valuation.holdings[ins]?.weight ?: 0.0
    val order = r.orders.firstOrNull { it.instrument == ins }
    val action = when {
        order != null -> if (order.side == Side.BUY) Action.BUY else Action.SELL
        goal > 0 && now > 0 -> Action.HOLD
        goal > 0 -> Action.BUY
        now > 0 -> Action.SELL
        else -> Action.WAIT
    }
    Opportunity(ins, action, goal, now, order)
}.sortedWith(compareBy({ it.action.rank }, { -it.goal }))

/** Handelsmöjligheter: strategins fyra produkter, de med en åtgärd först. */
@Composable
fun OpportunitiesScreen(s: UiState, padding: PaddingValues) {
    val r = s.result
    val ctx = LocalContext.current
    LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (r == null) { item { SectionCard { Text("Ingen analys än.") } }; return@LazyColumn }
        val ops = opportunities(r)
        item {
            val n = ops.count { it.order != null }
            Text(if (n == 0) "Inga köp- eller säljorder behövs idag. Målvikterna nedan gäller tills nästa signal eller ombalansering."
                else "$n produkter behöver en affär. De visas först.",
                style = MaterialTheme.typography.bodyMedium)
            if (s.trades.isEmpty()) Text("Registrera ditt kapital under Portfölj för att få belopp och antal andelar.",
                style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
        }
        items(ops, key = { it.ins.name }) { o -> OpportunityCard(o, r, s.cache, ctx) }
    }
}

@Composable
private fun OpportunityCard(o: Opportunity, r: AnalysisResult, cache: MarketData.Cache?, ctx: android.content.Context) {
    val ins = o.ins
    val series = cache?.series?.get(ins.yahoo)
    val price = series?.let { it.lastPrice ?: it.closes.lastOrNull() }
    SectionCard(ins.shortName, trailing = { StatusPill(o.action.label, o.action.tone) }) {
        KeyValue("Ticker", "${ins.ticker} · ${ins.exchange.label} · ${ins.currency}")
        KeyValue("Senaste kurs", price?.let { "${num(it, 2)} ${ins.currency}" + (series.lastTime?.let { t -> ", ${fmtTime(t)}" } ?: "") } ?: "–")
        KeyValue("Målvikt / nu", "${pct(o.goal)} / ${pct(o.now)}")
        o.order?.let { KeyValue("Order", "${if (it.side == Side.BUY) "Köp" else "Sälj"} cirka ${sek(it.amountSek)}" + (it.quantity?.let { q -> ", $q st" } ?: "")) }
        if (price != null && (o.action == Action.BUY || o.action == Action.HOLD))
            KeyValue("Köpzon", "${num(price * 0.99, 2)}–${num(price * 1.01, 2)} ${ins.currency}")
        HorizontalDivider()
        indicators(ins, r).forEach { (k, v) -> KeyValue(k, v) }
        Text("Exit: ${exitRule(ins, r)}", style = MaterialTheme.typography.bodySmall)
        history(ins)?.let { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        AvanzaButton(ctx, ins.avanzaUrl)
    }
}

private fun indicators(ins: Instrument, r: AnalysisResult): List<Pair<String, String>> = when (ins) {
    Instrument.XBT -> r.btc?.let { b -> listOf(
        "BTC-USD ${fmtDate(b.asOf)}" to "${num(b.close)} USD",
        "SMA${Rules.CRYPTO_SMA}" to "${num(b.sma)} USD (${pct(b.close / b.sma - 1)})",
        "Senaste trendbyte" to (b.lastSwitch?.let { fmtDate(it) } ?: "–"),
    ) } ?: listOf("Bitcoin-trend" to "data saknas")
    Instrument.SXR8 -> r.sp?.let { p -> listOfNotNull(
        "S&P 500 ${fmtDate(p.latest.date)}" to num(p.latest.close),
        p.latestSma?.let { "SMA${Rules.STOCK_SMA} idag" to "${num(it)} (${pct(p.latest.close / it - 1)})" },
        "Månadsbeslut ${fmtDate(p.decision.date)}" to if (p.decision.invested) "investera" else "kontanter",
        "Nästa kontroll" to fmtDate(p.nextCheck),
    ) } ?: listOf("S&P 500-trend" to "data saknas")
    else -> listOf("Lika vikt" to "10 % av portföljen, ombalansering ${fmtDate(r.rebalance.nextRebalanceClose)}")
}

private fun exitRule(ins: Instrument, r: AnalysisResult): String = when (ins) {
    Instrument.XBT -> "Bitcoin Trend-delen (20 %) säljs när BTC-USD stänger under SMA150" +
        (r.btc?.let { " (i dag ${num(it.sma)} USD)" } ?: "") + ". Lika vikt-delen (10 %) behålls och ombalanseras månadsvis."
    Instrument.SXR8 -> "S&P 500 Trend-delen (40 %) säljs om indexet stänger under SMA200 på månadens sista handelsdag" +
        (r.sp?.let { " (nästa kontroll ${fmtDate(it.nextCheck)})" } ?: "") + ". Lika vikt-delen (10 %) behålls."
    else -> "Ingen exitregel. Andelen ombalanseras till 10 % efter månadens sista handelsdag om den avviker mer än 2 procentenheter."
}

private fun history(ins: Instrument): String? {
    val id = when (ins) { Instrument.XBT -> StrategyId.BTC_TREND; Instrument.SXR8 -> StrategyId.SP500_TREND; else -> StrategyId.EQUAL_WEIGHT }
    val res = RESEARCH.firstOrNull { it.strategy == id } ?: return null
    val row = if (id == StrategyId.EQUAL_WEIGHT) res.extra.firstOrNull { it.label.contains("guld") } ?: res.strategyRow else res.strategyRow
    return "Historik (${res.strategy.displayName}, ${res.period}): ${pct(row.cagr)}/år, Sharpe ${num(row.sharpe, 2)}, största nedgång ${pct(row.maxDd, 0)}. " +
        "Köp och behåll: ${pct(res.buyHold.cagr)}/år, största nedgång ${pct(res.buyHold.maxDd, 0)}."
}
