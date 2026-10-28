package se.dahlander.swingedge.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import se.dahlander.swingedge.core.Strategy

/** Inställningar: bara notiser. Strategins vikter är frysta och kan inte ändras här. */
@Composable
fun SettingsScreen(s: UiState, vm: AppViewModel, padding: PaddingValues, requestNotifications: () -> Unit) {
    LazyColumn(Modifier.padding(padding), contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
        item {
            SectionCard("Notiser") {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Notiser om köp, sälj, ombalansering och datafel", Modifier.weight(1f))
                    Switch(checked = s.settings.notifications, onCheckedChange = { vm.setNotifications(it); if (it) requestNotifications() })
                }
                Text("Appen kontrollerar ungefär en gång i timmen, även när den är stängd. Android kan skjuta upp kontrollen när batteriet sparas.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        item {
            SectionCard("Om appen") {
                Text("SwingEdge följer en enda fryst strategi, ${Strategy.NAME}: 20 % Bitcoin Trend, 40 % lika vikt (XACT OMXS30, SXR8, Bitcoin Tracker One, Xetra-Gold) och 40 % S&P 500 Trend. Vikterna kan inte ändras i appen; en ändring kräver en ny validering.",
                    style = MaterialTheme.typography.bodySmall)
                Text("Kurser hämtas från Yahoo Finance, med Binance som reserv för Bitcoin. Allt räknas och sparas på telefonen. Appen lägger inga ordrar; affärer görs manuellt i Avanza och registreras här.",
                    style = MaterialTheme.typography.bodySmall)
                Text("Inget i appen är ett köp- eller säljråd.", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}
