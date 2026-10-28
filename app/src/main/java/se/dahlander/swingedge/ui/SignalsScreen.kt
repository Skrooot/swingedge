package se.dahlander.swingedge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
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
import se.dahlander.swingedge.core.Side
import se.dahlander.swingedge.core.SignalRecord
import se.dahlander.swingedge.core.SignalType
import se.dahlander.swingedge.core.num
import se.dahlander.swingedge.core.pct
import se.dahlander.swingedge.core.sek

enum class RecordStatus(val label: String, val tone: Tone) {
    ACTIVE("Aktiv", Tone.POSITIVE), PENDING("Väntar på nästa handelstillfälle", Tone.PENDING),
    HISTORICAL("Historisk", Tone.NEUTRAL), INVALID("Ogiltig, datafel", Tone.NEGATIVE),
}

fun statusOf(rec: SignalRecord, all: List<SignalRecord>, rebalanceDue: Boolean): RecordStatus {
    if (rec.type == SignalType.DATA_ERROR || rec.type == SignalType.MISSED) return RecordStatus.INVALID
    val newest = all.filter { it.strategy == rec.strategy && it.type != SignalType.DATA_ERROR && it.type != SignalType.MISSED }.maxByOrNull { it.time }
    if (newest?.key != rec.key) return RecordStatus.HISTORICAL
    if (rec.type == SignalType.REBALANCE && !rebalanceDue) return RecordStatus.HISTORICAL
    if (rec.executableFrom != null && rec.executableFrom > System.currentTimeMillis()) return RecordStatus.PENDING
    return RecordStatus.ACTIVE
}

@Composable
fun SignalsScreen(s: UiState, padding: PaddingValues) {
    var showLog by remember { mutableStateOf(false) }
    val ctx = LocalContext.current
    LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = !showLog, onClick = { showLog = false }, label = { Text("Signaler") })
                FilterChip(selected = showLog, onClick = { showLog = true }, label = { Text("Beräkningslogg") })
            }
        }
        if (!showLog) {
            if (s.signals.isEmpty()) item { SectionCard { Text("Inga signaler än. Den första analysen sparar strategiernas startläge.") } }
            items(s.signals, key = { it.key + it.time }) { rec ->
                val st = statusOf(rec, s.signals, s.result?.rebalanceDue == true)
                SectionCard(rec.strategy?.displayName ?: rec.type.label, trailing = { StatusPill(st.label, st.tone) }) {
                    KeyValue("Signaltyp", rec.type.label)
                    KeyValue("Datum och tid", "${fmtDate(rec.signalDate)}, beräknad ${fmtTime(rec.time)}")
                    rec.instrument?.let { KeyValue("Instrument", it.shortName) }
                    val unit = if (rec.strategy == se.dahlander.swingedge.core.StrategyId.SP500_TREND) " punkter" else " USD"
                    rec.underlyingPrice?.let { KeyValue(if (unit == " USD") "BTC-USD vid signalen" else "S&P 500 vid signalen", num(it) + unit) }
                    rec.indicatorValue?.let { KeyValue(rec.indicatorName, num(it) + unit) }
                    rec.targetWeight?.let { KeyValue("Avsedd portföljvikt", pct(it)) }
                    rec.executableFrom?.let { KeyValue("Kan handlas från", fmtTime(it)) }
                    Text("Strategins signal: ${rec.action}.", style = MaterialTheme.typography.bodyMedium)
                    if (st == RecordStatus.ACTIVE || st == RecordStatus.PENDING) {
                        val os = s.result?.orders?.filter { if (rec.instrument == null) it.reason.startsWith("Månatlig") else it.instrument == rec.instrument } ?: emptyList()
                        val act = when {
                            os.isNotEmpty() -> "Föreslagen åtgärd: " + os.joinToString("; ") { o -> "${if (o.side == Side.BUY) "köp" else "sälj"} ${o.instrument.shortName} för cirka ${sek(o.amountSek)}" } + "."
                            s.trades.isEmpty() -> "Föreslagen åtgärd: registrera din portfölj för att få en konkret order."
                            else -> "Föreslagen åtgärd: ingen affär behövs, portföljen har redan rätt innehav."
                        }
                        Text(act, style = MaterialTheme.typography.bodyMedium)
                    }
                    Text("Varför: ${rec.reason}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    rec.instrument?.let { AvanzaButton(ctx, it.avanzaUrl) }
                }
            }
        } else {
            items(s.runs.take(100)) { run ->
                SectionCard(fmtTime(run.time), trailing = { StatusPill(if (run.ok) "Data OK" else "Datafel", if (run.ok) Tone.POSITIVE else Tone.NEGATIVE) }) {
                    Text("Utlöst av: ${run.trigger}", style = MaterialTheme.typography.bodySmall)
                    run.btc?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                    run.sp?.let { Text(it, style = MaterialTheme.typography.bodySmall) }
                    run.checks.forEach { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    if (run.target.isNotEmpty()) Text("Mål: " + run.target.entries.joinToString { "${it.key} ${pct(it.value)}" }, style = MaterialTheme.typography.bodySmall)
                    if (run.orders.isNotEmpty()) Text("Ordrar: " + run.orders.joinToString(), style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}
