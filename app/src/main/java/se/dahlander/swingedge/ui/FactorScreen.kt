package se.dahlander.swingedge.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import se.dahlander.swingedge.core.num
import se.dahlander.swingedge.core.pct
import se.dahlander.swingedge.data.FactorRepository
import se.dahlander.swingedge.factor.ALLOCATION_ASSETS
import se.dahlander.swingedge.factor.FACTOR_STRATEGIES
import se.dahlander.swingedge.factor.FactorEvidence
import se.dahlander.swingedge.factor.FactorRanking
import se.dahlander.swingedge.factor.FactorStrategy
import se.dahlander.swingedge.factor.FactorStrategyInfo
import se.dahlander.swingedge.factor.GlobalAllocation

private enum class FTab(val label: String) { STRATS("Strategier"), ALLOC("Global Allocation"), SCAN("Factor Scanner") }

private fun evTone(e: FactorEvidence) = when (e) {
    FactorEvidence.VERIFIED -> Tone.POSITIVE; FactorEvidence.PROMISING -> Tone.PENDING; FactorEvidence.DOCUMENTED -> Tone.NEUTRAL; FactorEvidence.NONE -> Tone.NEGATIVE
}

private fun assetName(id: String) = ALLOCATION_ASSETS.firstOrNull { it.id == id }?.name ?: id
private fun signed(x: Double?) = x?.let { (if (it > 0) "+" else "") + pct(it) } ?: "–"
private fun monthText(m: String) = fmtDate("$m-01").substringAfter(' ')

/** Factor & Global Allocation: Börslabbets publika principer, granskade. Skilt från SwingEdges egna strategier. */
@Composable
fun FactorScreen(s: UiState, vm: AppViewModel, padding: PaddingValues, header: @Composable () -> Unit) {
    var tab by rememberSaveable { mutableStateOf(FTab.STRATS) }
    var strat by rememberSaveable { mutableStateOf(FactorStrategy.MOMENTUM) }
    val ctx = LocalContext.current
    val a = s.allocation
    val sc = s.scanner
    LaunchedEffect(Unit) { vm.refreshAllocation(false) }
    LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            header()
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FTab.entries.forEach { t -> FilterChip(selected = tab == t, onClick = { tab = t }, label = { Text(t.label) }) }
            }
            Text("Forskning från granskningen av Börslabbets strategier (28 okt 2026). Påverkar inte SwingEdges målportfölj. Inte investeringsrådgivning.",
                style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
        }
        when (tab) {
            FTab.STRATS -> items(FACTOR_STRATEGIES, key = { it.key }) { info -> StrategyCard(info, s, ctx) { if (info.scanner != null) { strat = info.scanner; tab = FTab.SCAN } else tab = FTab.ALLOC } }
            FTab.ALLOC -> {
                item {
                    SectionCard("Global trendföljning", trailing = { StatusPill("Papperhandel", Tone.PENDING) }) {
                        Text("Topp 3 av 9 tillgångsslag efter snittet av 3, 6 och 12 månaders avkastning i SEK. Byte bara när en ny tillgång ligger minst 2 procentenheter högre.",
                            style = MaterialTheme.typography.bodyMedium)
                        val d = a?.latest
                        if (d == null) {
                            Text(if (s.allocationLoading) "Hämtar fondvärden från Avanza…" else "Inga fondvärden än.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                        } else {
                            KeyValue("Beslut efter månadsslut", monthText(d.signalMonth))
                            KeyValue("Gäller under", monthText(GlobalAllocation.nextMonth(d.signalMonth)))
                            KeyValue("Nästa ombalansering", fmtDate(vm.nextRebalance()))
                            KeyValue("Kurser hämtade", fmtTime(a.at.takeIf { it > 0 }))
                            a.paperReturn()?.let { KeyValue("Papperhandel sedan ${monthText(a.paperStart!!)}", signed(it)) }
                            if (d.bought.isNotEmpty() || d.sold.isNotEmpty()) {
                                Text("Senaste byte: köp ${d.bought.joinToString { assetName(it) }}, sälj ${d.sold.joinToString { assetName(it) }}",
                                    color = toneColor(Tone.PENDING), fontWeight = FontWeight.SemiBold)
                            }
                        }
                        a?.errors?.forEach { Text(it, style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.NEGATIVE)) }
                        OutlinedButton(onClick = { vm.refreshAllocation(true) }, enabled = !s.allocationLoading) { Text(if (s.allocationLoading) "Hämtar…" else "Uppdatera fondvärden") }
                    }
                }
                val d = a?.latest
                if (d != null) {
                    item {
                        SectionCard("Topp tre och hur du äger dem") {
                            d.holdings.forEach { id ->
                                val asset = ALLOCATION_ASSETS.first { it.id == id }
                                Column {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text("${asset.name} · 33 %", fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                                        if (id in d.bought) StatusPill("Ny", Tone.POSITIVE)
                                    }
                                    Text("${asset.product} · ${asset.isin} · avgift ${asset.fee}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    AvanzaButton(ctx, asset.avanzaUrl)
                                }
                            }
                            Text("Fonder handlas utan courtage; lägg ordern före fondens stopptid. Guld handlas på Xetra i EUR. Appen lägger inga order.",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    item {
                        SectionCard("Rangordning efter ${monthText(d.signalMonth)}") {
                            val ms = GlobalAllocation.months(a.levels.values.flatMap { it.keys }.min(), d.signalMonth)
                            val i = ms.lastIndex
                            Row { listOf("Tillgång" to 1.6f, "3 m" to 1f, "6 m" to 1f, "12 m" to 1f, "Snitt" to 1f).forEach { (t, w) ->
                                Text(t, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(w)) } }
                            d.scores.entries.sortedByDescending { it.value }.forEachIndexed { r, (id, v) ->
                                val l = a.levels[id] ?: emptyMap()
                                val held = id in d.holdings
                                Row {
                                    Text("${r + 1}. ${assetName(id)}", modifier = Modifier.weight(1.6f), fontWeight = if (held) FontWeight.SemiBold else FontWeight.Normal,
                                        color = if (held) toneColor(Tone.POSITIVE) else MaterialTheme.colorScheme.onSurface, style = MaterialTheme.typography.bodySmall)
                                    listOf(3, 6, 12).forEach { n -> Text(signed(GlobalAllocation.change(l, ms, i, n)), Modifier.weight(1f), style = MaterialTheme.typography.bodySmall) }
                                    Text(signed(v), Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
                                }
                            }
                            Text("Grönt = ägs. En tillgång kan ägas trots lägre rang om skillnaden mot den nya är under 2 procentenheter.",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                    if (a.preview.isNotEmpty() && a.partialMonth != null) {
                        item {
                            SectionCard("Just nu, pågående ${monthText(a.partialMonth)}") {
                                Text("Förhandsvisning med senaste NAV. Signalen räknas först vid månadsslutet.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                a.preview.entries.sortedByDescending { it.value }.take(5).forEachIndexed { r, (id, v) -> KeyValue("${r + 1}. ${assetName(id)}", signed(v)) }
                            }
                        }
                    }
                    item {
                        SectionCard("Byten (köp- och säljsignaler)") {
                            val ch = a.changes.take(12)
                            if (ch.isEmpty()) Text("Inga byten i historiken.", color = MaterialTheme.colorScheme.onSurfaceVariant)
                            ch.forEach { c ->
                                Column {
                                    Text(monthText(c.signalMonth), style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    Text("Köp ${c.bought.joinToString { assetName(it) }} · sälj ${c.sold.joinToString { assetName(it) }}", style = MaterialTheme.typography.bodyMedium)
                                }
                            }
                            Text("Historiken räknas från ${monthText(a.decisions.first().signalMonth)}, när alla nio fonderna har 12 månaders kurser.",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
            }
            FTab.SCAN -> {
                item {
                    SectionCard("Factor Scanner") {
                        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            FactorStrategy.entries.forEach { f -> FilterChip(selected = strat == f, onClick = { strat = f }, label = { Text(f.title) }) }
                        }
                        Text(strat.rule, style = MaterialTheme.typography.bodyMedium)
                        StatusPill("Forskningskandidat – inga signaler", Tone.NEUTRAL)
                        Text("Dagens nyckeltal och kursändringar från Avanza för Large och Mid Cap Stockholm, över 2 miljarder kr, utan finansbolag. " +
                            "Förenklad jämfört med Börslabbet: EV/EBIT i stället för EV/EBITDA och EV/FCF, ROCE i stället för ROIC, inget F-score. Kursändringar utan utdelningar.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        KeyValue("Senaste skanning", fmtTime(sc?.at?.takeIf { it > 0 }))
                        sc?.let { if (it.errors > 0) KeyValue("Kunde inte hämtas", "${it.errors} bolag") }
                        s.scanProgress?.let { (d, n) -> LinearProgressIndicator(progress = { d.toFloat() / n }, modifier = Modifier.fillMaxWidth()); Text("$d av $n bolag", style = MaterialTheme.typography.bodySmall) }
                        Button(onClick = { vm.scan(true) }, enabled = s.scanProgress == null) { Text("Skanna nu (cirka 270 bolag)") }
                    }
                }
                val stocks = sc?.stocks ?: emptyList()
                if (stocks.isNotEmpty()) {
                    val ranked = FactorRanking.rank(strat, stocks)
                    item { Text("${stocks.count { FactorRanking.eligible(it) }} bolag i universumet · visar topp ${ranked.size}", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    items(ranked, key = { it.stock.id }) { r ->
                        SectionCard {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("${r.rank}. ${r.stock.name}", fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                                Text(signed(r.momentum), color = toneColor(if (r.momentum >= 0) Tone.POSITIVE else Tone.NEGATIVE))
                            }
                            Text(r.note, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            val st = r.stock
                            Text(listOfNotNull(st.list?.removeSuffix(" Stockholm"), st.pe?.let { "P/E ${num(it, 1)}" }, st.pb?.let { "P/B ${num(it, 1)}" },
                                st.directYield?.let { "Dir.avk ${pct(it)}" }, st.roe?.let { "ROE ${pct(it)}" }, st.spread?.let { "Spread ${num(it, 2)} %" }).joinToString(" · "),
                                style = MaterialTheme.typography.bodySmall)
                            AvanzaButton(ctx, "https://www.avanza.se/aktier/om-aktien.html/${st.id}/${st.ticker.lowercase().replace(' ', '-')}")
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun StrategyCard(info: FactorStrategyInfo, s: UiState, ctx: android.content.Context, open: () -> Unit) {
    SectionCard(info.title, trailing = { StatusPill(info.evidence.label, evTone(info.evidence)) }) {
        Text(info.description, style = MaterialTheme.typography.bodyMedium)
        KeyValue("Marknader", info.markets)
        KeyValue("Ombalansering", info.rebalance)
        KeyValue("Horisont", info.horizon)
        KeyValue("Signaler i appen", if (info.signals) "Ja, som papperhandel" else "Nej, forskningskandidat")
        when {
            info.key == "gtf" -> {
                val d = s.allocation?.latest
                KeyValue("Senaste analys", d?.let { "Efter ${monthText(it.signalMonth)}" } ?: "–")
                KeyValue("Aktuella innehav", d?.holdings?.joinToString { assetName(it) } ?: "–")
            }
            info.scanner != null -> {
                val st = s.scanner?.stocks.orEmpty()
                KeyValue("Senaste skanning", fmtTime(s.scanner?.at?.takeIf { it > 0 }))
                if (st.isNotEmpty()) KeyValue("Kandidater nu", FactorRanking.rank(info.scanner, st, 3).joinToString { it.stock.name })
            }
        }
        HorizontalDivider()
        Text("Historiska resultat · ${info.period}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        info.rows.forEach { r ->
            KeyValue(r.label, listOfNotNull(r.cagr?.let { (if (r.sharpe == null) "+" else "") + pct(it) + if (r.sharpe == null) "/år" else "" },
                r.sharpe?.let { "Sharpe ${num(it, 2)}" }, r.maxDd?.let { "DD ${pct(it, 0)}" }).joinToString(" · "))
        }
        Text(info.verdict, style = MaterialTheme.typography.bodyMedium)
        info.blocker?.let { Text("Forskningshinder: $it", style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.NEGATIVE)) }
        Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
            TextButton(onClick = open) { Text(if (info.scanner != null) "Visa i Factor Scanner" else "Visa allokering") }
            TextButton(onClick = { openUrl(ctx, info.publicSource) }) { Text("Börslabbets beskrivning") }
        }
    }
}
