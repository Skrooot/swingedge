package se.dahlander.swingedge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import se.dahlander.swingedge.core.Metrics
import se.dahlander.swingedge.core.RESEARCH
import se.dahlander.swingedge.core.ResearchRow
import se.dahlander.swingedge.core.num
import se.dahlander.swingedge.core.pct

@Composable
fun AnalysisScreen(s: UiState, vm: AppViewModel, padding: PaddingValues, openInstruments: () -> Unit = {}) {
    LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            androidx.compose.material3.OutlinedButton(onClick = openInstruments) { Text("Instrument och kursdiagram") }
            Text("Forskningsrapportens resultat", style = MaterialTheme.typography.titleLarge)
            Text("Historiska backtester från rapporten Swingstrategier via Avanza, 27 okt 2026. Det här är inte din portföljs resultat.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        items(RESEARCH) { res ->
            SectionCard(res.strategy.displayName) {
                Text(res.title, style = MaterialTheme.typography.bodyMedium)
                Text("Period: ${res.period}", style = MaterialTheme.typography.bodySmall)
                Text("Källa: ${res.source}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                ResearchTable(listOf(res.strategyRow, res.buyHold) + res.extra)
                Text(res.verdict, style = MaterialTheme.typography.bodySmall)
            }
        }
        item {
            SectionCard("Forward test") {
                Text("Köp- och säljsignaler loggas när appen räknar fram dem och följs upp med produktens kurs därefter. Inget läggs in i efterhand. Kostnad 0,40 % per sida, som i backtestet.",
                    style = MaterialTheme.typography.bodySmall)
                val fw = s.forward
                val done = fw.filter { !it.open && it.returnSek() != null }
                KeyValue("Loggade signaler", "${fw.size} (${fw.count { it.open }} öppna, ${done.size} avslutade)")
                if (done.isNotEmpty()) KeyValue("Snitt per avslutad affär", pct(done.mapNotNull { it.returnSek() }.average()))
                fw.take(10).forEach { e ->
                    val r = e.returnSek()
                    Text("${e.strategy.shortName}: köp ${fmtDate(e.signalDate)} (loggad ${fmtTime(e.loggedAt)})" +
                        (e.entryPrice?.let { " · ingång ${num(it, 2)} ${e.instrument.currency}" } ?: " · väntar på första handelsbara kurs") +
                        (e.exitReason?.let { " · $it" } ?: "") + (r?.let { " · ${pct(it)}" } ?: ""), style = MaterialTheme.typography.bodySmall)
                }
                Text(if (done.size < 20) "För få avslutade affärer för slutsatser. Bitcoin Trend ger cirka 4 affärer per år och S&P 500 Trend färre, så ett meningsfullt forward test tar flera år."
                    else "Jämför med backtestets antaganden: affär på stängningen dagen efter signalen.",
                    style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
            }
        }
        item {
            SectionCard("Nytt backtest på aktuella kurser") {
                Text("Kör samma frysta regler på hela den historik som Yahoo Finance har idag. Appen har bara stängningskurser, så affären görs på stängningen dagen efter signalen. Resultaten kan därför skilja något från rapporten.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    Button(onClick = { vm.runBacktest() }, enabled = !s.backtestRunning) { Text("Kör backtest") }
                    if (s.backtestRunning) CircularProgressIndicator(Modifier.padding(4.dp))
                }
            }
        }
        items(s.backtests) { run ->
            SectionCard("Ny körning ${fmtTime(run.time)}") {
                Text("Data till och med ${fmtDate(run.dataUntil)}. Visas separat från rapportens resultat.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                run.lines.forEach { l ->
                    HorizontalDivider()
                    Text(l.name, style = MaterialTheme.typography.titleSmall)
                    Text("${fmtDate(l.strategy.from)} – ${fmtDate(l.strategy.to)}. ${l.note}.", style = MaterialTheme.typography.bodySmall)
                    ResearchTable(listOfNotNull(row("Strategi", l.strategy), l.buyHold?.let { row(l.buyHoldName, it) }))
                }
                run.errors.forEach { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
            }
        }
    }
}

private fun row(label: String, m: Metrics) = ResearchRow(label, m.cagr, m.sharpe, m.maxDd, m.sortino,
    if (m.trades > 0) m.trades / ((java.time.LocalDate.parse(m.to).toEpochDay() - java.time.LocalDate.parse(m.from).toEpochDay()) / 365.25) else null,
    m.avgHoldDays, m.exposure)

@Composable
private fun ResearchTable(rows: List<ResearchRow>) {
    rows.forEach { r ->
        Text(r.label, style = MaterialTheme.typography.bodyMedium)
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Metric("CAGR", pct(r.cagr), Modifier.weight(1f))
            Metric("Sharpe", num(r.sharpe, 2), Modifier.weight(1f))
            Metric("Max DD", pct(r.maxDd, 0), Modifier.weight(1f))
        }
        val extra = listOfNotNull(
            r.sortino?.let { "Sortino ${num(it, 2)}" },
            r.tradesPerYear?.let { "${num(it, 1)} affärer/år" },
            r.avgHoldDays?.let { "snittinnehav ${num(it)} dagar" },
            r.exposure?.let { "investerad ${pct(it, 0)} av tiden" },
        )
        if (extra.isNotEmpty()) Text(extra.joinToString(" · "), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
