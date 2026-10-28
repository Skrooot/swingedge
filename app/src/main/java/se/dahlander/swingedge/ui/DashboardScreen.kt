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
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import se.dahlander.swingedge.core.AnalysisResult
import se.dahlander.swingedge.core.DataStatus
import se.dahlander.swingedge.core.Severity
import se.dahlander.swingedge.core.Side
import se.dahlander.swingedge.core.SignalStatus
import se.dahlander.swingedge.core.Strategy
import se.dahlander.swingedge.core.nextPlannedAnalysis
import se.dahlander.swingedge.core.pct
import se.dahlander.swingedge.core.sek
import se.dahlander.swingedge.data.PortfolioKind

/** Översikt: svarar på om något behöver köpas, säljas eller bevakas idag. */
@Composable
fun DashboardScreen(s: UiState, padding: PaddingValues, openStrategy: () -> Unit) {
    val r = s.result
    LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        if (r == null) {
            item { SectionCard("Hämtar kurser") { Text("Första analysen körs. Det tar några sekunder.", color = MaterialTheme.colorScheme.onSurfaceVariant) } }
            return@LazyColumn
        }
        item { StatusCard(r, openStrategy) }
        item { TodoCard(r) }
        item { PortfolioHeader(s) }
        item {
            Text("Historiska resultat garanterar inget om framtiden. Inget här är ett köp- eller säljråd.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun StatusCard(r: AnalysisResult, openStrategy: () -> Unit) {
    val dataOk = r.checks.values.all { it.status == DataStatus.OK }
    val buys = r.orders.count { it.side == Side.BUY }
    val sells = r.orders.count { it.side == Side.SELL }
    SectionCard(Strategy.NAME, trailing = {
        StatusPill(if (dataOk) "Aktiv" else "Data saknas", if (dataOk) Tone.POSITIVE else Tone.NEGATIVE)
    }) {
        KeyValue("Bitcoin-trend", trendText(r.btcStatus, r.states?.btcInvested))
        KeyValue("S&P 500-trend (månadsbeslut)", trendText(r.spStatus, r.states?.spInvested))
        KeyValue("Lika vikt", if (r.rebalanceDue) "Ombalansering denna månad" else "Nästa ombalansering ${fmtDate(r.rebalance.nextRebalanceClose)}")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            Metric("Köp", buys.toString(), Modifier.weight(1f), valueColor = if (buys > 0) toneColor(Tone.PENDING) else Color.Unspecified)
            Metric("Sälj", sells.toString(), Modifier.weight(1f), valueColor = if (sells > 0) toneColor(Tone.PENDING) else Color.Unspecified)
        }
        HorizontalDivider()
        KeyValue("Senaste analys", fmtTime(r.time))
        KeyValue("Nästa planerade analys", fmtTime(nextPlannedAnalysis(java.time.Instant.now())))
        OutlinedButton(onClick = openStrategy) { Text("Regler, resultat och signallogg") }
    }
}

private fun trendText(status: SignalStatus, invested: Boolean?): String = when {
    status == SignalStatus.INVALID || invested == null -> "Ogiltig, data saknas"
    status == SignalStatus.STALE -> (if (invested) "Positiv" else "Negativ") + ", men data är föråldrade"
    status == SignalStatus.PENDING -> if (invested) "Ny köpsignal, väntar på börsöppning" else "Ny säljsignal, väntar på börsöppning"
    invested -> "Positiv: investerad"
    else -> "Negativ: kontanter"
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
private fun PortfolioHeader(s: UiState) {
    val v = s.result?.valuation
    SectionCard(s.settings.active.label) {
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
        if (s.settings.active == PortfolioKind.PAPER) Text("Papperskonto med virtuellt kapital.", style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
    }
}
