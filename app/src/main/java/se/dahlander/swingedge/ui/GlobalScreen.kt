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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.Button
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import se.dahlander.swingedge.core.num
import se.dahlander.swingedge.core.pct
import se.dahlander.swingedge.edge.Evidence
import se.dahlander.swingedge.edge.Opportunity
import se.dahlander.swingedge.edge.SignalState

private enum class GTab(val label: String) { OPP("Möjligheter"), MARKETS("Marknader"), METHOD("Metod") }

private fun evTone(e: Evidence) = when (e) { Evidence.VALIDATED -> Tone.POSITIVE; Evidence.STRONG -> Tone.PENDING; Evidence.HYPOTHESIS -> Tone.NEUTRAL; Evidence.NONE -> Tone.NEGATIVE }
private fun sigTone(s: SignalState) = when (s) { SignalState.NEW_BUY, SignalState.IN -> Tone.POSITIVE; SignalState.NEW_SELL, SignalState.OUT -> Tone.NEUTRAL; else -> Tone.NEGATIVE }

private fun risk(o: Opportunity): String { val v = o.combo.test.vol ?: return "–"; return when { v < 0.12 -> "Låg"; v < 0.25 -> "Medel"; else -> "Hög" } }
private fun liquidity(o: Opportunity): String {
    val t = o.market.trade ?: return "Ingen produkt"
    val sp = t.spread; val ow = t.owners ?: 0
    return when { sp != null && sp <= 0.2 && ow >= 1000 -> "God"; ow >= 200 -> "Medel"; else -> "Låg" }
}

@Composable
fun GlobalScreen(s: UiState, vm: AppViewModel, padding: PaddingValues) {
    var tab by rememberSaveable { mutableStateOf(GTab.OPP) }
    var cls by rememberSaveable { mutableStateOf<String?>(null) }
    var minEv by rememberSaveable { mutableStateOf(Evidence.HYPOTHESIS.rank) }
    var rrOnly by rememberSaveable { mutableStateOf(false) }
    var sig by rememberSaveable { mutableStateOf("Alla") }
    var fam by rememberSaveable { mutableStateOf<String?>(null) }
    var horizon by rememberSaveable { mutableStateOf<String?>(null) }
    var riskF by rememberSaveable { mutableStateOf<String?>(null) }
    var liqF by rememberSaveable { mutableStateOf<String?>(null) }
    var buyable by rememberSaveable { mutableStateOf(true) }
    var fitF by rememberSaveable { mutableStateOf(false) }
    val e = s.edge
    val r = e?.research
    val ops = e?.opportunities ?: emptyList()
    val ctx = LocalContext.current
    LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) { GTab.entries.forEach { t -> FilterChip(selected = tab == t, onClick = { tab = t }, label = { Text(t.label) }) } }
            Text(
                if (r == null) "Forskningsresultatet har inte hämtats än." else
                    "Forskning ${fmtDate(r.generated.take(10))} · ${r.nCombos} kombinationer · kurser ${fmtTime(e.scannedAt.takeIf { it > 0 })}",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text("Separat från dina SwingEdge-strategier. Påverkar inte målportföljen.", style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
        }
        if (r == null) {
            item { SectionCard { Button(onClick = { vm.refreshEdge(true) }, enabled = !s.edgeLoading) { Text(if (s.edgeLoading) "Hämtar…" else "Hämta forskning och kurser") } } }
            e?.errors?.forEach { err -> item { Text(err, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) } }
            return@LazyColumn
        }
        when (tab) {
            GTab.OPP -> {
                val classes = r.markets.map { it.assetClass }.distinct()
                val families = r.families
                item {
                    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        ChipRow(listOf("Alla" to null) + classes.map { it to it }, cls) { cls = it }
                        ChipRow(listOf("Validerad" to Evidence.VALIDATED.rank, "Stark hypotes och bättre" to Evidence.STRONG.rank, "Alla hypoteser" to Evidence.HYPOTHESIS.rank, "Allt" to 0), minEv) { minEv = it ?: 0 }
                        ChipRow(listOf("Alla" to "Alla", "Ny köpsignal" to "Ny köp", "I marknaden" to "In", "Ny säljsignal" to "Ny sälj", "Kontanter" to "Ut"), sig) { sig = it ?: "Alla" }
                        ChipRow(listOf("Alla strategier" to null) + families.map { it.value.name to it.key }, fam) { fam = it }
                        ChipRow(listOf("Alla horisonter" to null) + families.values.map { it.horizon }.distinct().map { it to it }, horizon) { horizon = it }
                        ChipRow(listOf("All risk" to null, "Låg risk" to "Låg", "Medel" to "Medel", "Hög" to "Hög"), riskF) { riskF = it }
                        ChipRow(listOf("All likviditet" to null, "God" to "God", "Medel" to "Medel", "Låg" to "Låg"), liqF) { liqF = it }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("Bara köpbara på Avanza", Modifier.weight(1f)); Switch(buyable, { buyable = it })
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("Bara strategier som tydligt minskade fallen", Modifier.weight(1f)); Switch(rrOnly, { rrOnly = it })
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("Bara god historisk strategilämplighet (positiv på träning och test)", Modifier.weight(1f)); Switch(fitF, { fitF = it })
                        }
                    }
                }
                val list = ops.filter { o ->
                    (cls == null || o.market.assetClass == cls) && Evidence.of(o.combo.evidence).rank >= minEv &&
                        (fam == null || o.combo.family == fam) && (horizon == null || o.family?.horizon == horizon) &&
                        (riskF == null || risk(o) == riskF) && (liqF == null || liquidity(o) == liqF) &&
                        (!buyable || o.market.trade != null) && (!rrOnly || o.combo.riskReduction) && (!fitF || (o.combo.excess > 0 && (o.combo.excessTrain ?: -1.0) > 0)) &&
                        when (sig) { "Ny köp" -> o.state == SignalState.NEW_BUY; "In" -> o.weight != null && o.weight > 0; "Ny sälj" -> o.state == SignalState.NEW_SELL; "Ut" -> o.weight == 0.0; else -> true }
                }.sortedWith(compareByDescending<Opportunity> { it.state == SignalState.NEW_BUY }.thenByDescending { Evidence.of(it.combo.evidence).rank }.thenByDescending { it.combo.excess })
                item { Text("${list.size} av ${ops.size} kombinationer", style = MaterialTheme.typography.labelLarge) }
                items(list.take(200), key = { it.combo.market + it.combo.family }) { o -> OpportunityCard(o, ctx) }
            }
            GTab.MARKETS -> {
                item { Text("Antalet signaler säger något om marknadsbredd, inte om framtida avkastning.", style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING)) }
                val byClass = ops.groupBy { it.market.assetClass }
                items(byClass.keys.sorted()) { c ->
                    val g = byClass.getValue(c)
                    val trendIn = g.filter { it.combo.family == "sma200m" }
                    SectionCard(c) {
                        KeyValue("Marknader", "${g.map { it.market.id }.distinct().size}")
                        KeyValue("Kombinationer med stark hypotes eller validerad", "${g.count { Evidence.of(it.combo.evidence).rank >= Evidence.STRONG.rank }}")
                        KeyValue("Validerade", "${g.count { Evidence.of(it.combo.evidence) == Evidence.VALIDATED }}")
                        KeyValue("I marknaden nu, alla strategier", "${g.count { (it.weight ?: 0.0) > 0 }} av ${g.size}")
                        KeyValue("Nya köpsignaler senaste ${se.dahlander.swingedge.edge.EdgeScanner.NEW_DAYS} dagarna", "${g.count { it.state == SignalState.NEW_BUY }}")
                        if (trendIn.isNotEmpty()) KeyValue("Trendstatus SMA200, andel marknader över", pct(trendIn.count { (it.weight ?: 0.0) > 0 }.toDouble() / trendIn.size, 0))
                    }
                }
            }
            GTab.METHOD -> {
                item {
                    SectionCard("Hur bra är forskningens urval?") {
                        r.pbo?.let { KeyValue("Probability of Backtest Overfitting", pct(it, 0)) }
                        Text("PBO = sannolikheten att den kombination som såg bäst ut i en del av historiken är sämre än medianen i resten. Över 50 % betyder att det bästa resultatet till stor del är slump.",
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        r.selection["spearmanTrainTest"]?.let { KeyValue("Rangkorrelation träning mot test", num(it, 2)) }
                        r.selection["topDecileTestExcess"]?.let { KeyValue("Bästa tiondelen på träning, överavkastning på test", num(it, 2)) }
                        r.selection["restTestExcess"]?.let { KeyValue("Övriga, överavkastning på test", num(it, 2)) }
                        Text("Överavkastning = skillnad i Sharpe mot köp och behåll av samma marknad.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                item { PortfolioCard(r.portfolio as? JsonObject) }
                item {
                    SectionCard("Klassning") {
                        Text("Validerad: positiv överavkastning på testperioden 2016–2026, q-värde under 0,10 efter Benjamini–Hochberg, Deflated Sharpe minst 0,95, minst 5 års test och 5 affärer, positiv i minst 2 av 3 delperioder, parametervarianter håller och verifierad på Avanza-produktens egen kurs.", style = MaterialTheme.typography.bodySmall)
                        Text("Stark hypotes: positiv överavkastning och p under 0,10 före korrigering för multipla test.", style = MaterialTheme.typography.bodySmall)
                        Text("Hypotes: positiv överavkastning utan statistiskt stöd. Ingen edge: sämre än köp och behåll.", style = MaterialTheme.typography.bodySmall)
                        Text("Signal vid stängning, affär vid nästa stängning, 0,40 % kostnad per affärssida (0,15 % för OMXS30). Träning till och med 2015.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
                item {
                    SectionCard("Notiser") {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("Notis vid ny köpsignal", Modifier.weight(1f))
                            Switch(s.settings.edgeNotify, { vm.setEdgeNotify(it, s.settings.edgeMinEvidence) })
                        }
                        ChipRow(listOf("Validerad" to "Validerad", "Stark hypotes" to "Stark hypotes"), s.settings.edgeMinEvidence) { vm.setEdgeNotify(s.settings.edgeNotify, it ?: "Validerad") }
                        Button(onClick = { vm.refreshEdge(true) }, enabled = !s.edgeLoading) { Text(if (s.edgeLoading) "Skannar…" else "Skanna nu") }
                        e.errors.take(5).forEach { Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error) }
                    }
                }
            }
        }
    }
}

@Composable
private fun <T> ChipRow(options: List<Pair<String, T>>, selected: T, onSelect: (T?) -> Unit) {
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        options.forEach { (label, v) -> FilterChip(selected = selected == v, onClick = { onSelect(v) }, label = { Text(label) }) }
    }
}

@Composable
private fun OpportunityCard(o: Opportunity, ctx: android.content.Context) {
    val ev = Evidence.of(o.combo.evidence)
    val cb = o.combo
    SectionCard(o.market.name, trailing = { Text(o.market.assetClass, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }) {
        Text(o.family?.name ?: cb.family, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            StatusPill(o.state.label + (o.lastSwitch?.takeIf { o.state == SignalState.NEW_BUY || o.state == SignalState.NEW_SELL }?.let { " ${fmtDate(it)}" } ?: ""), sigTone(o.state))
            StatusPill(ev.label, evTone(ev))
        }
        Text("Strategilämplighet (test 2016–2026)", style = MaterialTheme.typography.labelLarge)
        KeyValue("Sharpe mot köp och behåll", "${num(cb.test.sharpe, 2)} mot ${num(cb.bh.sharpe, 2)}", valueColor = toneColor(if (cb.excess > 0) Tone.POSITIVE else Tone.NEGATIVE))
        KeyValue("CAGR mot köp och behåll", "${pct(cb.test.cagr)} mot ${pct(cb.bh.cagr)}")
        KeyValue("Största fall mot köp och behåll", "${pct(cb.test.maxdd, 0)} mot ${pct(cb.bh.maxdd, 0)}")
        if (cb.riskReduction) Text("Minskar fallen tydligt utan att försämra Sharpe.", style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.POSITIVE))
        Text("Evidens", style = MaterialTheme.typography.labelLarge)
        KeyValue("Affärer och testår", "${cb.test.trades ?: "–"} affärer, ${cb.test.years?.let { num(it, 1) } ?: "–"} år")
        KeyValue("p / q (efter multipeltest) / Deflated Sharpe", "${num(cb.p, 2)} / ${num(cb.q, 2)} / ${cb.dsr?.let { num(it, 2) } ?: "–"}")
        KeyValue("Delperioder med överavkastning", "${cb.subperiods.count { it > 0 }} av ${cb.subperiods.size}")
        if (cb.variants.isNotEmpty()) KeyValue("Parametervarianter som håller", "${cb.variants.count { it > 0 }} av ${cb.variants.size}")
        val pv = cb.product
        KeyValue("Verifierad på Avanza-produkten", when {
            pv?.excess == null -> "Ej testad"
            cb.checks["productVerified"] == true -> "Ja, ${num(pv.excess, 2)} i överavkastning"
            else -> "Nej (${num(pv.excess, 2)}, korrelation ${pv.corr?.let { num(it, 2) } ?: "–"})"
        })
        pv?.drift?.let { if (o.market.kind == "future_front") KeyValue("Produkt mot termin, per år", pct(it), valueColor = toneColor(if (it < 0) Tone.NEGATIVE else Tone.POSITIVE)) }
        Text("Aktuellt tillfälle", style = MaterialTheme.typography.labelLarge)
        KeyValue("Data till och med", o.dataDate?.let { fmtDate(it) } ?: "–")
        KeyValue("Risk och likviditet", "${risk(o)} risk, ${liquidity(o)} likviditet")
        val t = o.market.trade
        if (t != null) {
            KeyValue("Produkt", "${t.name} (${t.ticker}, ${t.marketPlace}, ${t.currency})")
            t.avanzaUrl?.let { AvanzaButton(ctx, it) }
        } else Text("Ingen köpbar produkt utan hävstång hittades på Avanza. Endast forskning.", style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.NEGATIVE))
    }
}

@Composable
private fun PortfolioCard(p: JsonObject?) {
    SectionCard("Kombinera flera strategier") {
        if (p == null) { Text("Inget portföljtest i forskningen."); return@SectionCard }
        fun m(k: String) = p[k]?.jsonObject
        val st = m("strategy"); val bh = m("buyHold")
        Text("Kombinationer valda bara på träningsdata (överavkastning över 0,10 till och med 2015), viktade efter omvänd volatilitet och testade ${p["from"]?.jsonPrimitive?.content} – ${p["to"]?.jsonPrimitive?.content}.",
            style = MaterialTheme.typography.bodySmall)
        KeyValue("Antal kombinationer", p["n"]?.jsonPrimitive?.intOrNull?.toString() ?: "–")
        if (st != null && bh != null) {
            fun d(o: JsonObject, k: String) = o[k]?.jsonPrimitive?.doubleOrNull ?: 0.0
            HorizontalDivider()
            KeyValue("Strategierna: CAGR, Sharpe, största fall", "${pct(d(st, "cagr"))}, ${num(d(st, "sharpe"), 2)}, ${pct(d(st, "maxdd"), 0)}")
            KeyValue("Köp och behåll samma marknader", "${pct(d(bh, "cagr"))}, ${num(d(bh, "sharpe"), 2)}, ${pct(d(bh, "maxdd"), 0)}")
        }
        Text("Riskhantering i praktiken: sprid på flera tillgångsslag, låt ingen marknad ta mer än en liten del, och kom ihåg att råvaror och krypto rör sig kraftigt.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Suppress("unused")
private fun Modifier.full() = this.fillMaxWidth()
