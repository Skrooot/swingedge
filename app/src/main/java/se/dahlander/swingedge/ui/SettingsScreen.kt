package se.dahlander.swingedge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material3.FilterChip
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import se.dahlander.swingedge.core.DEFAULT_SLEEVES
import se.dahlander.swingedge.core.StrategyId
import se.dahlander.swingedge.core.pct
import kotlin.math.roundToInt

@Composable
fun SettingsScreen(s: UiState, vm: AppViewModel, padding: PaddingValues, requestNotifications: () -> Unit) {
    var draft by remember(s.settings.sleeves) { mutableStateOf(s.settings.sleeves) }
    val sum = draft.values.sum()
    LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            SectionCard("Portföljdelarnas vikter") {
                Text("Testad modell: Bitcoin Trend 20 %, Lika vikt 40 %, S&P 500 Trend 40 %. Andra vikter är avvikelser från det som testades och märks så i appen.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                DEFAULT_SLEEVES.keys.forEach { id ->
                    Column {
                        Text("${id.displayName}: ${pct(draft[id] ?: 0.0, 0)}")
                        Slider(value = (draft[id] ?: 0.0).toFloat(), onValueChange = { v -> draft = draft + (id to (v * 20).roundToInt() / 20.0) }, valueRange = 0f..1f, steps = 19)
                    }
                }
                Text("Summa ${pct(sum, 0)}${if (kotlin.math.abs(sum - 1.0) > 1e-6) ", måste vara 100 %" else ""}",
                    color = if (kotlin.math.abs(sum - 1.0) > 1e-6) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurface)
                if (draft != DEFAULT_SLEEVES) Text("Avviker från den testade modellen.", color = toneColor(Tone.PENDING), style = MaterialTheme.typography.bodySmall)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { vm.setSleeves(draft) }, enabled = kotlin.math.abs(sum - 1.0) < 1e-6 && draft != s.settings.sleeves) { Text("Spara") }
                    OutlinedButton(onClick = { vm.resetSleeves() }) { Text("Återställ 20/40/40") }
                }
            }
        }
        item {
            SectionCard("Avantis-kärna") {
                Text("Andel av portföljen i Avantis Global Equity, Global Small Cap Value och Emerging Markets, en tredjedel var. Resten följer SwingEdge med vikterna ovan.",
                    style = MaterialTheme.typography.bodyMedium)
                Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    listOf(0.0 to "Av", 0.25 to "25 %", 0.5 to "50 %", 0.75 to "75 %").forEach { (v, l) ->
                        FilterChip(selected = kotlin.math.abs(s.settings.avantisShare - v) < 1e-9, onClick = { vm.setAvantisShare(v) }, label = { Text(l) })
                    }
                }
                if (s.settings.avantisShare > 0) {
                    val e = se.dahlander.swingedge.core.effectiveSleeves(s.settings.sleeves, s.settings.avantisShare)
                    Text("Vikter nu: " + e.entries.joinToString { "${it.key.shortName} ${pct(it.value, 0)}" }, style = MaterialTheme.typography.bodySmall)
                }
                Text("Köp och behåll med ombalansering vid månadsslut, ingen trendregel. Handlas på Xetra i EUR med courtage och 0,25 % växling.",
                    style = MaterialTheme.typography.bodySmall)
                Text("Tillägg efter rapporten. Okt 2019 – sep 2026 (amerikanska Avantis-fonder som proxy, korrelation 0,98–0,99 mot UCITS-fonderna): 50 % Avantis + 50 % SwingEdge med guld gav 19,5 %/år, Sharpe 1,12, största nedgång −19 %, mot 23,7 %, 1,07 och −19 % för SwingEdge med guld. Kort period och inget signifikanstest.",
                    style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
            }
        }
        item {
            SectionCard("Guld i lika vikt") {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Lägg till Xetra-Gold som fjärde instrument", Modifier.weight(1f))
                    Switch(checked = s.settings.includeGold, onCheckedChange = { vm.setIncludeGold(it) })
                }
                Text("Lika-vikt-delen delas då på fyra: XACT OMXS30, SXR8, Bitcoin Tracker One och Xetra-Gold, 10 % var av portföljen med standardvikter.",
                    style = MaterialTheme.typography.bodySmall)
                Text("Tillägg efter rapporten. I efterhandstestet maj 2015 – okt 2026 steg Sharpe för lika vikt från 1,23 till 1,34 och största nedgången minskade från −41 % till −32 %. Guld valdes bland sex testade varianter under en stark period för guld, så resultatet är osäkrare än rapportens.",
                    style = MaterialTheme.typography.bodySmall, color = toneColor(Tone.PENDING))
            }
        }
        item {
            SectionCard("Notiser") {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Notiser om signaler, ombalansering och datafel", Modifier.weight(1f))
                    Switch(checked = s.settings.notifications, onCheckedChange = { vm.setNotifications(it); if (it) requestNotifications() })
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Global trendföljning: notis när innehaven byts vid månadsskiftet (papperhandel)", Modifier.weight(1f))
                    Switch(checked = s.settings.gtfNotify, onCheckedChange = { vm.setGtfNotify(it) })
                }
                Text("Appen kontrollerar ungefär en gång i timmen, även när den är stängd. Android kan skjuta upp kontrollen när batteriet sparas.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        item {
            SectionCard("Om appen") {
                Text("SwingEdge räknar reglerna från rapporten Swingstrategier via Avanza direkt på telefonen. Kurser hämtas från Yahoo Finance, med Binance som reserv för Bitcoin. Factor & Global Allocation hämtar fondvärden och nyckeltal från Avanzas publika webbsidor. Alla innehav, affärer och signaler sparas bara på den här telefonen.",
                    style = MaterialTheme.typography.bodySmall)
                Text("Appen lägger inga ordrar. Avanza har inget officiellt API för privatkunders orderläggning, så ordrar läggs manuellt i Avanza och registreras sedan här.",
                    style = MaterialTheme.typography.bodySmall)
                Text("Inget i appen är ett köp- eller säljråd.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
