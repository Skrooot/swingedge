package se.dahlander.swingedge.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import se.dahlander.swingedge.core.Bar
import se.dahlander.swingedge.core.Instrument
import se.dahlander.swingedge.core.Side
import se.dahlander.swingedge.core.Trade
import se.dahlander.swingedge.core.ledger
import se.dahlander.swingedge.core.num
import se.dahlander.swingedge.core.pct
import se.dahlander.swingedge.core.sek
import se.dahlander.swingedge.data.PortfolioKind
import java.time.LocalDate

@Composable
fun PortfolioScreen(s: UiState, vm: AppViewModel, padding: PaddingValues) {
    var dialog by remember { mutableStateOf<Side?>(null) }
    var paperDialog by remember { mutableStateOf(false) }
    val r = s.result
    val led = ledger(s.trades)
    LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                PortfolioKind.entries.forEach { k ->
                    FilterChip(selected = s.settings.active == k, onClick = { vm.setActive(k) }, label = { Text(k.label) })
                }
            }
            Text("Den valda portföljen styr ordrar och notiser.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = { dialog = Side.BUY }) { Text("Köp") }
                Button(onClick = { dialog = Side.SELL }) { Text("Sälj") }
                OutlinedButton(onClick = { dialog = Side.DEPOSIT }) { Text("Insättning") }
                OutlinedButton(onClick = { dialog = Side.WITHDRAW }) { Text("Uttag") }
            }
            if (s.settings.active == PortfolioKind.PAPER) TextButton(onClick = { paperDialog = true }) { Text("Starta om papperskontot") }
        }
        val v = r?.valuation
        item {
            SectionCard("Innehav") {
                if (v == null || v.holdings.isEmpty()) Text("Inga innehav registrerade.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                v?.holdings?.values?.sortedByDescending { it.valueSek }?.forEach { h ->
                    val tgt = r.target?.total?.get(h.position.instrument)
                    Column {
                        Text(h.position.instrument.shortName, style = MaterialTheme.typography.titleSmall)
                        KeyValue("Antal", num(h.position.quantity, 2))
                        KeyValue("Värde", sek(h.valueSek))
                        KeyValue("Andel nu / mål", "${pct(h.weight)} / ${tgt?.let { pct(it) } ?: "–"}")
                        KeyValue("Orealiserat", sek(h.unrealizedSek), valueColor = toneColor(if (h.unrealizedSek >= 0) Tone.POSITIVE else Tone.NEGATIVE))
                    }
                    HorizontalDivider()
                }
                KeyValue("Kontanter", sek(led.cashSek))
                KeyValue("Insatt kapital", sek(led.depositedSek))
                KeyValue("Realiserat resultat", sek(led.realizedSek), valueColor = toneColor(if (led.realizedSek >= 0) Tone.POSITIVE else Tone.NEGATIVE))
                if (v != null && led.depositedSek > 0) KeyValue("Total avkastning", pct(v.totalSek / led.depositedSek - 1), valueColor = toneColor(if (v.totalSek >= led.depositedSek) Tone.POSITIVE else Tone.NEGATIVE))
            }
        }
        if (r?.target != null && v != null && v.totalSek > 0) item {
            SectionCard("Jämfört med målportföljen") {
                Instrument.entries.forEach { ins ->
                    val now = v.holdings[ins]?.weight ?: 0.0
                    val goal = r.target.total[ins] ?: 0.0
                    if (now == 0.0 && goal == 0.0) return@forEach
                    KeyValue(ins.shortName, "${pct(now)} → ${pct(goal)}")
                }
                KeyValue("Kontanter", "${pct(v.cashSek / v.totalSek)} → ${pct(r.target.cash)}")
                if (r.orders.isEmpty()) Text("Inga ordrar behövs just nu.", color = toneColor(Tone.POSITIVE))
                r.orders.forEach { o -> Text("${if (o.side == Side.BUY) "Köp" else "Sälj"} ${o.instrument.shortName} för cirka ${sek(o.amountSek)}: ${o.reason}.") }
            }
        }
        if (s.snapshots.size >= 2) item {
            SectionCard("Utveckling") {
                PriceChart(s.snapshots.map { Bar(LocalDate.parse(it.date), it.totalSek) }, description = "Portföljens värde över tid")
            }
        }
        item { Text("Affärer", style = MaterialTheme.typography.titleMedium) }
        items(s.trades.sortedByDescending { it.date }, key = { it.id }) { t ->
            SectionCard {
                Row {
                    Column(Modifier.weight(1f)) {
                        Text("${t.side.sv()} ${t.instrument?.shortName ?: ""}", style = MaterialTheme.typography.titleSmall)
                        Text(fmtDate(t.date), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        if (t.instrument != null) Text("${num(t.quantity, 2)} st à ${num(t.price, 2)} ${t.instrument.currency}, avgift ${sek(t.feeSek)}" +
                            if (t.instrument.currency != "SEK") ", kurs ${num(t.fxToSek, 4)}" else "", style = MaterialTheme.typography.bodySmall)
                        else Text(sek(t.price), style = MaterialTheme.typography.bodySmall)
                    }
                    IconButton(onClick = { vm.deleteTrade(t.id) }) { Icon(Icons.Filled.Delete, contentDescription = "Ta bort affär") }
                }
            }
        }
    }
    dialog?.let { side -> TradeDialog(side, s, onDismiss = { dialog = null }, onSave = { vm.addTrade(it); dialog = null }) }
    if (paperDialog) {
        var cap by remember { mutableStateOf("100000") }
        AlertDialog(onDismissRequest = { paperDialog = false }, title = { Text("Starta om papperskontot") },
            text = { Column { Text("Alla affärer i papperskontot tas bort och ersätts med ett virtuellt startkapital."); OutlinedTextField(cap, { cap = it }, label = { Text("Startkapital, kr") }, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number)) } },
            confirmButton = { TextButton(onClick = { cap.toDoubleOrNull()?.let { vm.resetPaper(it) }; paperDialog = false }) { Text("Starta om") } },
            dismissButton = { TextButton(onClick = { paperDialog = false }) { Text("Avbryt") } })
    }
}

fun Side.sv() = when (this) { Side.BUY -> "Köp"; Side.SELL -> "Sälj"; Side.DEPOSIT -> "Insättning"; Side.WITHDRAW -> "Uttag" }

@Composable
private fun TradeDialog(side: Side, s: UiState, onDismiss: () -> Unit, onSave: (Trade) -> Unit) {
    val isCash = side == Side.DEPOSIT || side == Side.WITHDRAW
    var ins by remember { mutableStateOf(Instrument.XBT) }
    var date by remember { mutableStateOf(LocalDate.now().toString()) }
    var qty by remember { mutableStateOf("") }
    var price by remember { mutableStateOf("") }
    var fee by remember { mutableStateOf("0") }
    val eursek = s.cache?.series?.get("EURSEK=X")?.let { it.lastPrice ?: it.closes.lastOrNull() }
    var fx by remember { mutableStateOf(eursek?.let { "%.4f".format(it) } ?: "") }
    var error by remember { mutableStateOf<String?>(null) }
    fun d(x: String) = x.replace(',', '.').replace(" ", "").toDoubleOrNull()
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(side.sv()) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if (!isCash) {
                    Row(Modifier.horizontalScroll(androidx.compose.foundation.rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Instrument.entries.forEach { i -> FilterChip(selected = ins == i, onClick = { ins = i; price = s.cache?.series?.get(i.yahoo)?.lastPrice?.let { "%.2f".format(it) } ?: price }, label = { Text(i.ticker.take(11)) }) }
                    }
                    Text(ins.displayName, style = MaterialTheme.typography.bodySmall)
                }
                OutlinedTextField(date, { date = it }, label = { Text("Datum (ÅÅÅÅ-MM-DD)") }, singleLine = true)
                if (!isCash) {
                    OutlinedTextField(qty, { qty = it }, label = { Text("Antal") }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
                    OutlinedTextField(price, { price = it }, label = { Text("Kurs i ${ins.currency}") }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
                    OutlinedTextField(fee, { fee = it }, label = { Text("Courtage och avgifter, kr") }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
                    if (ins.currency != "SEK") OutlinedTextField(fx, { fx = it }, label = { Text("Växelkurs ${ins.currency}/SEK inkl. växlingsavgift") }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
                } else {
                    OutlinedTextField(price, { price = it }, label = { Text("Belopp, kr") }, singleLine = true, keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal))
                }
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                val dt = runCatching { LocalDate.parse(date) }.getOrNull()
                val p = d(price)
                val q = if (isCash) 0.0 else d(qty)
                val f = d(fee) ?: 0.0
                val rate = if (isCash || ins.currency == "SEK") 1.0 else d(fx)
                error = when {
                    dt == null -> "Ange datum som ÅÅÅÅ-MM-DD"
                    p == null || p <= 0 -> "Ange ett pris eller belopp större än noll"
                    !isCash && (q == null || q <= 0) -> "Ange antal större än noll"
                    rate == null || rate <= 0 -> "Ange växelkursen"
                    side == Side.SELL && (ledger(s.trades).positions[ins]?.quantity ?: 0.0) + 1e-9 < q!! -> "Du äger inte så många andelar"
                    else -> null
                }
                if (error == null) onSave(Trade("", dt.toString(), side, if (isCash) null else ins, q ?: 0.0, p!!, f, rate!!))
            }) { Text("Spara") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Avbryt") } },
    )
}
