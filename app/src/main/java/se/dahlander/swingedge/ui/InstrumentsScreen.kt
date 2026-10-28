package se.dahlander.swingedge.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import se.dahlander.swingedge.core.Bar
import se.dahlander.swingedge.core.Instrument
import se.dahlander.swingedge.core.Rules
import se.dahlander.swingedge.core.SignalType
import se.dahlander.swingedge.core.StrategyId
import se.dahlander.swingedge.core.completedCryptoBars
import se.dahlander.swingedge.core.num
import se.dahlander.swingedge.core.pct
import java.time.Instant
import java.time.LocalDate

private sealed class Pick(val label: String) {
    class Product(val ins: Instrument) : Pick(ins.shortName)
    data object Btc : Pick("BTC-USD (signal)")
    data object Sp : Pick("S&P 500 (signal)")
}

@Composable
fun InstrumentsScreen(s: UiState, padding: PaddingValues) {
    val picks = Instrument.entries.map { Pick.Product(it) } + listOf(Pick.Btc, Pick.Sp)
    var sel by remember { mutableStateOf<Pick>(picks.first()) }
    val ctx = LocalContext.current
    LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                picks.forEach { p -> FilterChip(selected = sel.label == p.label, onClick = { sel = p }, label = { Text(p.label) }) }
            }
        }
        when (val p = sel) {
            is Pick.Product -> item { ProductCard(p.ins, s, ctx) }
            Pick.Btc -> item { SourceCard(s, "BTC-USD", "Bitcoin i USD, signalkälla för Bitcoin Trend", Rules.CRYPTO_SMA, StrategyId.BTC_TREND, crypto = true) }
            Pick.Sp -> item { SourceCard(s, "^GSPC", "S&P 500-index, signalkälla för S&P 500 Trend", Rules.STOCK_SMA, StrategyId.SP500_TREND, crypto = false) }
        }
    }
}

@Composable
private fun ProductCard(ins: Instrument, s: UiState, ctx: android.content.Context) {
    val series = s.cache?.series?.get(ins.yahoo)
    val bars = series?.bars() ?: emptyList()
    SectionCard(ins.displayName) {
        StatusPill("Handelsprodukt på Avanza", Tone.NEUTRAL)
        if (series != null) {
            KeyValue("Senaste kurs", "${num(series.lastPrice ?: series.closes.last(), 2)} ${ins.currency}")
            KeyValue("Kursens tidpunkt", fmtTime(series.lastTime))
        }
        KeyValue("Ticker", ins.ticker)
        KeyValue("ISIN", ins.isin)
        KeyValue("Handelsplats", ins.exchange.label)
        KeyValue("Valuta", ins.currency)
        Text("Underliggande: ${ins.underlying}", style = MaterialTheme.typography.bodySmall)
        PriceChart(bars.takeLast(260), description = "Kursdiagram för ${ins.shortName}, senaste året")
        val strategies = when (ins) {
            Instrument.XBT -> "Bitcoin Trend och Lika vikt"
            Instrument.SXR8 -> "S&P 500 Trend och Lika vikt"
            Instrument.XACT -> "Lika vikt"
            Instrument.GOLD -> if (s.settings.includeGold) "Lika vikt (tillval)" else "Ingen strategi just nu. Kan slås på under Inställningar."
        }
        KeyValue("Används av", strategies)
        if (ins == Instrument.XBT) Text("Priset ovan är certifikatets pris i SEK, inte Bitcoins marknadspris. Signalen räknas på BTC-USD.", style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
        val hist = s.signals.filter { it.instrument == ins && (it.type == SignalType.BUY || it.type == SignalType.SELL || it.type == SignalType.START) }
        if (hist.isNotEmpty()) {
            Text("Historiska signaler", style = MaterialTheme.typography.labelLarge)
            hist.take(10).forEach { Text("${fmtDate(it.signalDate)}: ${it.type.label}, ${it.action}", style = MaterialTheme.typography.bodySmall) }
        }
        AvanzaButton(ctx, ins.avanzaUrl)
    }
}

@Composable
private fun SourceCard(s: UiState, symbol: String, title: String, n: Int, strategy: StrategyId, crypto: Boolean) {
    val series = s.cache?.series?.get(symbol)
    var bars = series?.bars() ?: emptyList()
    if (crypto) bars = completedCryptoBars(bars, Instant.now())
    SectionCard(title) {
        StatusPill("Signalkälla, går inte att köpa", Tone.NEUTRAL)
        if (bars.isEmpty()) { Text("Inga kurser hämtade än."); return@SectionCard }
        val sma = smaSeries(bars, n)
        val last = bars.last()
        KeyValue("Senaste färdiga stängning", "${num(last.close)} (${fmtDate(last.date)})")
        sma.last()?.let { KeyValue("SMA$n", num(it)); KeyValue("Avstånd", pct(last.close / it - 1)) }
        series?.lastTime?.let { KeyValue("Senast hämtad kurs", "${num(series.lastPrice ?: last.close)} kl. ${fmtTime(it)}") }
        val show = bars.takeLast(500)
        val switches = s.signals.filter { it.strategy == strategy && (it.type == SignalType.BUY || it.type == SignalType.SELL) }.map { LocalDate.parse(it.signalDate) }
        PriceChart(show, overlay = sma.takeLast(show.size), markers = switches, description = "$symbol med SMA$n")
        Text("Heldragen linje: kurs. Streckad: SMA$n. Lodräta streck: registrerade signalbyten.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (!crypto) Text("Strategin beslutar bara vid månadens sista handelsdag.", style = MaterialTheme.typography.bodySmall)
    }
}

@Suppress("unused")
private fun List<Bar>.closes() = map { it.close }
