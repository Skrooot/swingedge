package se.dahlander.swingedge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.SwapVert
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import se.dahlander.swingedge.core.AnalysisResult
import se.dahlander.swingedge.core.DEFAULT_SLEEVES
import se.dahlander.swingedge.core.Instrument
import se.dahlander.swingedge.core.Rules
import se.dahlander.swingedge.core.Severity
import se.dahlander.swingedge.core.SignalStatus
import se.dahlander.swingedge.core.StrategyId
import se.dahlander.swingedge.core.nextPlannedAnalysis
import se.dahlander.swingedge.core.num
import se.dahlander.swingedge.core.pct
import se.dahlander.swingedge.core.sek
import se.dahlander.swingedge.data.PortfolioKind

@Composable
fun DashboardScreen(s: UiState, padding: PaddingValues) {
    val r = s.result
    LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item { PortfolioHeader(s) }
        if (r == null) {
            item { SectionCard("Hämtar kurser") { Text("Första analysen körs. Det tar några sekunder.", color = MaterialTheme.colorScheme.onSurfaceVariant) } }
            return@LazyColumn
        }
        item { TodoCard(r) }
        item { BtcCard(r, s) }
        item { EqualWeightCard(r, s) }
        item { SpCard(r, s) }
        item { TargetCard(r) }
        item {
            Text("Signalerna följer reglerna i rapporten Swingstrategier via Avanza (27 okt 2026). Historiska resultat garanterar inget om framtiden. Inget här är ett köp- eller säljråd.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun PortfolioHeader(s: UiState) {
    val r = s.result
    val v = r?.valuation
    SectionCard {
        Text(s.settings.active.label, style = MaterialTheme.typography.labelLarge, color = MaterialTheme.colorScheme.primary)
        Text(if (v == null || v.totalSek <= 0) "–" else sek(v.totalSek), style = MaterialTheme.typography.headlineMedium)
        val dc = v?.dayChangeSek
        if (dc != null && v.totalSek > 0) {
            val base = v.totalSek - dc
            Text("Idag ${if (dc >= 0) "+" else "−"}${sek(kotlin.math.abs(dc))} (${if (dc >= 0) "+" else "−"}${pct(kotlin.math.abs(dc) / base)})",
                color = toneColor(if (dc >= 0) Tone.POSITIVE else Tone.NEGATIVE), style = MaterialTheme.typography.bodyMedium)
        }
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Metric("Investerat", if (v == null) "–" else sek(v.investedSek), Modifier.weight(1f))
            Metric("Kontanter", if (v == null || v.totalSek <= 0) "–" else pct(v.cashSek / v.totalSek, 0), Modifier.weight(1f))
        }
        HorizontalDivider()
        KeyValue("Senaste analys", if (r == null) "–" else fmtTime(r.time))
        KeyValue("Nästa planerade analys", fmtTime(nextPlannedAnalysis(java.time.Instant.now())))
        if (s.settings.active == PortfolioKind.PAPER) Text("Papperskonto med virtuellt kapital.", style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
        if (r?.customSleeves == true) Text("Egna vikter: avviker från den testade modellen 20/40/40.", style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
    }
}

@Composable
private fun TodoCard(r: AnalysisResult) {
    SectionCard("Vad behöver jag göra idag?") {
        r.todo.forEachIndexed { i, t ->
            if (i > 0) HorizontalDivider()
            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                val (icon, tone) = when (t.severity) {
                    Severity.ACTION -> Icons.Filled.SwapVert to Tone.PENDING
                    Severity.WARNING -> Icons.Filled.Warning to Tone.NEGATIVE
                    Severity.INFO -> (if (t.title.startsWith("Inga åtgärder")) Icons.Filled.CheckCircle else Icons.Filled.Info) to Tone.POSITIVE
                }
                Icon(icon, contentDescription = null, tint = toneColor(tone), modifier = Modifier.padding(top = 2.dp))
                Column(Modifier.weight(1f)) {
                    Text(t.title, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold)
                    Text(t.detail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    t.instrument?.let { AvanzaButton(LocalContext.current, it.avanzaUrl) }
                }
            }
        }
    }
}

@Composable
private fun statusPill(status: SignalStatus, invested: Boolean?) {
    when {
        status == SignalStatus.INVALID || invested == null -> StatusPill("Ogiltig, data saknas", Tone.NEGATIVE)
        status == SignalStatus.STALE -> StatusPill(if (invested) "Investerad, men data är föråldrade" else "Kontanter, men data är föråldrade", Tone.NEGATIVE)
        status == SignalStatus.PENDING -> StatusPill(if (invested) "Köp väntar på börsöppning" else "Sälj väntar på börsöppning", Tone.PENDING)
        invested -> StatusPill("Positiv trend: Behåll", Tone.POSITIVE)
        else -> StatusPill("Negativ trend: Avvakta i kontanter", Tone.NEGATIVE)
    }
}

@Composable
private fun BtcCard(r: AnalysisResult, s: UiState) {
    val b = r.btc
    val invested = r.states?.btcInvested
    val sleeve = s.settings.sleeves[StrategyId.BTC_TREND] ?: 0.0
    SectionCard("Bitcoin Trend", trailing = { Text(pct(sleeve, 0), color = MaterialTheme.colorScheme.onSurfaceVariant) }) {
        statusPill(r.btcStatus, invested)
        if (b != null) {
            KeyValue("BTC-USD, stängning ${fmtDate(b.asOf)}", "${num(b.close)} USD")
            KeyValue("SMA${Rules.CRYPTO_SMA}", "${num(b.sma)} USD")
            KeyValue("Avstånd till SMA", pct(b.close / b.sma - 1), valueColor = toneColor(if (b.invested) Tone.POSITIVE else Tone.NEGATIVE))
            KeyValue("Senaste signalbyte", b.lastSwitch?.let { fmtDate(it) } ?: "–")
        }
        KeyValue("Allokerat kapital", if (r.valuation.totalSek > 0 && invested == true) sek(sleeve * r.valuation.totalSek) else if (invested == false) "0 kr, i kontanter" else "–")
        r.checks["BTC-USD"]?.let { if (it.status.name != "OK") Text(it.message, style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.NEGATIVE)) }
        Text("Signalkälla är BTC-USD. Handel sker i Bitcoin Tracker One på Stockholmsbörsen, tidigast vid nästa börsöppning.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun EqualWeightCard(r: AnalysisResult, s: UiState) {
    val sleeve = s.settings.sleeves[StrategyId.EQUAL_WEIGHT] ?: 0.0
    val ins = se.dahlander.swingedge.core.equalWeightInstruments(s.settings.includeGold)
    SectionCard("Lika vikt", trailing = { Text(pct(sleeve, 0), color = MaterialTheme.colorScheme.onSurfaceVariant) }) {
        StatusPill(if (r.rebalanceDue) "Ombalansering denna månad" else "Följer målvikten", if (r.rebalanceDue) Tone.PENDING else Tone.POSITIVE)
        Row(Modifier.fillMaxWidth()) {
            Text("Instrument", style = MaterialTheme.typography.labelSmall, modifier = Modifier.weight(1f), color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("NU", style = MaterialTheme.typography.labelSmall, modifier = Modifier.weight(0.4f), color = MaterialTheme.colorScheme.onSurfaceVariant)
            Text("MÅL", style = MaterialTheme.typography.labelSmall, modifier = Modifier.weight(0.4f), color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        ins.forEach { i ->
            Row(Modifier.fillMaxWidth()) {
                Text(i.shortName, modifier = Modifier.weight(1f))
                Text(pct(r.valuation.holdings[i]?.weight ?: 0.0), modifier = Modifier.weight(0.4f))
                Text(pct(sleeve / ins.size), modifier = Modifier.weight(0.4f))
            }
        }
        Text("Nu = instrumentets andel av hela portföljen, även den del som trendstrategierna äger.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        if (s.settings.includeGold) Text("Guld är ett tillval som testades efter rapporten.", style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
        KeyValue("Nästa ombalansering", "${fmtDate(r.rebalance.nextRebalanceClose)} vid stängning")
        val adj = r.orders.filter { it.reason.startsWith("Månatlig") }
        KeyValue("Justeringsbehov", if (adj.isEmpty()) "Inga" else adj.joinToString { "${if (it.side.name == "BUY") "köp" else "sälj"} ${it.instrument.shortName} ${sek(it.amountSek)}" })
    }
}

@Composable
private fun SpCard(r: AnalysisResult, s: UiState) {
    val sp = r.sp
    val sleeve = s.settings.sleeves[StrategyId.SP500_TREND] ?: 0.0
    SectionCard("S&P 500 Trend", trailing = { Text(pct(sleeve, 0), color = MaterialTheme.colorScheme.onSurfaceVariant) }) {
        statusPill(r.spStatus, r.states?.spInvested)
        if (sp != null) {
            KeyValue("S&P 500, stängning ${fmtDate(sp.latest.date)}", num(sp.latest.close))
            sp.latestSma?.let { KeyValue("SMA${Rules.STOCK_SMA} idag", num(it)) }
            KeyValue("Läge idag", if (sp.latestSma != null && sp.latest.close > sp.latestSma) "Över SMA200" else "Under SMA200")
            KeyValue("Senaste månadsbeslut", "${fmtDate(sp.decision.date)}: ${if (sp.decision.invested) "investera" else "kontanter"}")
            KeyValue("Nästa kontroll", "${fmtDate(sp.nextCheck)} vid stängning")
        }
        Text("Beslutet ändras bara vid månadens sista handelsdag, även om indexet passerar medelvärdet däremellan.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun TargetCard(r: AnalysisResult) {
    val t = r.target ?: return
    SectionCard("Målportfölj") {
        val colors = listOf(MaterialTheme.colorScheme.primary, toneColor(Tone.PENDING), toneColor(Tone.POSITIVE), MaterialTheme.colorScheme.secondary)
        val parts = Instrument.entries.map { it.shortName to (t.total[it] ?: 0.0) }.filter { it.second > 0 }
        AllocationBar(parts, colors)
        parts.forEach { (n, w) -> KeyValue(n, pct(w)) }
        KeyValue("Kontanter", pct(t.cash))
        HorizontalDivider()
        Text("Per strategi", style = MaterialTheme.typography.labelLarge)
        StrategyId.entries.filter { it in t.perStrategy }.forEach { id ->
            val m = t.perStrategy[id] ?: emptyMap()
            KeyValue(id.displayName, if (m.isEmpty()) "Kontanter" else m.entries.joinToString { "${it.key.shortName} ${pct(it.value)}" })
        }
        if (r.customSleeves) Text("Avviker från den testade modellen: standardvikter ${DEFAULT_SLEEVES.values.joinToString("/") { pct(it, 0) }}, lika vikt utan guld, ingen Avantis-kärna.", style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
    }
}
