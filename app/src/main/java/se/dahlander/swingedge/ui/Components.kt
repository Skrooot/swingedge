package se.dahlander.swingedge.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.OpenInNew
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import se.dahlander.swingedge.core.Bar
import se.dahlander.swingedge.core.STOCKHOLM
import java.time.Instant
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale

val SV: Locale = Locale.forLanguageTag("sv-SE")
private val DT = DateTimeFormatter.ofPattern("d MMM yyyy HH:mm", SV).withZone(STOCKHOLM)
private val D = DateTimeFormatter.ofPattern("d MMM yyyy", SV)
fun fmtTime(ms: Long?): String = ms?.let { DT.format(Instant.ofEpochMilli(it)) } ?: "–"
fun fmtTime(t: Instant): String = DT.format(t)
fun fmtDate(d: LocalDate): String = D.format(d)
fun fmtDate(s: String): String = runCatching { D.format(LocalDate.parse(s)) }.getOrDefault(s)

fun openUrl(ctx: Context, url: String) = ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))

@Composable
fun SectionCard(title: String? = null, modifier: Modifier = Modifier, trailing: @Composable (() -> Unit)? = null, content: @Composable ColumnScope.() -> Unit) {
    Card(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (title != null) Row(verticalAlignment = Alignment.CenterVertically) {
                Text(title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                trailing?.invoke()
            }
            content()
        }
    }
}

enum class Tone { POSITIVE, NEGATIVE, PENDING, NEUTRAL }

@Composable
fun toneColor(t: Tone): Color {
    val c = LocalSignalColors.current
    return when (t) { Tone.POSITIVE -> c.positive; Tone.NEGATIVE -> c.negative; Tone.PENDING -> c.pending; Tone.NEUTRAL -> c.neutral }
}

/** Statusetikett med text, så att färg aldrig är enda bäraren av information. */
@Composable
fun StatusPill(text: String, tone: Tone) {
    val c = toneColor(tone)
    Row(
        Modifier.clip(RoundedCornerShape(50)).background(c.copy(alpha = 0.12f)).padding(horizontal = 10.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(8.dp).clip(CircleShape).background(c))
        Spacer(Modifier.width(6.dp))
        Text(text, style = MaterialTheme.typography.labelMedium, color = c, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
fun KeyValue(label: String, value: String, modifier: Modifier = Modifier, valueColor: Color = Color.Unspecified) {
    Row(modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
        Text(value, style = MaterialTheme.typography.bodyMedium, fontWeight = FontWeight.Medium, color = valueColor, maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
fun Metric(label: String, value: String, modifier: Modifier = Modifier, sub: String? = null, valueColor: Color = Color.Unspecified) {
    Column(modifier) {
        Text(label.uppercase(SV), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleLarge, color = valueColor)
        if (sub != null) Text(sub, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun AvanzaButton(ctx: Context, url: String, label: String = "Öppna i Avanza") {
    TextButton(onClick = { openUrl(ctx, url) }) {
        Text(label)
        Spacer(Modifier.width(6.dp))
        Icon(Icons.AutoMirrored.Filled.OpenInNew, contentDescription = null, modifier = Modifier.size(16.dp))
    }
}

/**
 * Linjediagram för kurser. [overlay] ritas streckad (t.ex. glidande medelvärde), [markers] är datum för signalbyten.
 */
@Composable
fun PriceChart(bars: List<Bar>, modifier: Modifier = Modifier, overlay: List<Double?>? = null, markers: List<LocalDate> = emptyList(), description: String) {
    if (bars.size < 2) { Text("För lite kurshistorik för ett diagram.", color = MaterialTheme.colorScheme.onSurfaceVariant); return }
    val line = MaterialTheme.colorScheme.primary
    val over = MaterialTheme.colorScheme.onSurfaceVariant
    val grid = MaterialTheme.colorScheme.outlineVariant
    val mark = LocalSignalColors.current.pending
    val values = bars.map { it.close } + (overlay?.filterNotNull() ?: emptyList())
    val lo = values.min(); val hi = values.max(); val span = (hi - lo).takeIf { it > 0 } ?: 1.0
    Column(modifier) {
        Canvas(Modifier.fillMaxWidth().height(180.dp).semantics { contentDescription = description }) {
            val w = size.width; val h = size.height
            fun x(i: Int) = i / (bars.size - 1f) * w
            fun y(v: Double) = (h - 8f) - ((v - lo) / span).toFloat() * (h - 16f)
            for (k in 0..3) drawLine(grid, Offset(0f, h * k / 3f), Offset(w, h * k / 3f), 1f)
            val idx = bars.withIndex().associate { it.value.date to it.index }
            markers.mapNotNull { idx[it] }.forEach { i -> drawLine(mark, Offset(x(i), 0f), Offset(x(i), h), 2f, pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 6f))) }
            overlay?.let { o ->
                val p = Path(); var started = false
                o.forEachIndexed { i, v -> if (v != null) { if (!started) { p.moveTo(x(i), y(v)); started = true } else p.lineTo(x(i), y(v)) } }
                drawPath(p, over, style = Stroke(2.5f, pathEffect = PathEffect.dashPathEffect(floatArrayOf(10f, 8f))))
            }
            val p = Path()
            bars.forEachIndexed { i, b -> if (i == 0) p.moveTo(x(i), y(b.close)) else p.lineTo(x(i), y(b.close)) }
            drawPath(p, line, style = Stroke(4f))
            drawCircle(line, 7f, Offset(x(bars.size - 1), y(bars.last().close)))
        }
        Row(Modifier.fillMaxWidth()) {
            Text(fmtDate(bars.first().date), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
            Text(fmtDate(bars.last().date), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

/** Glidande medelvärde per stapel (null tills n staplar finns). */
fun smaSeries(bars: List<Bar>, n: Int): List<Double?> {
    var sum = 0.0
    return bars.mapIndexed { i, b -> sum += b.close; if (i >= n) sum -= bars[i - n].close; if (i >= n - 1) sum / n else null }
}

/** Fördelningsstapel: andel per post i ordning, med text bredvid. */
@Composable
fun AllocationBar(parts: List<Pair<String, Double>>, colors: List<Color>) {
    Row(Modifier.fillMaxWidth().height(12.dp).clip(RoundedCornerShape(6.dp)).background(MaterialTheme.colorScheme.surfaceVariant)) {
        parts.forEachIndexed { i, (_, v) -> if (v > 0.001) Box(Modifier.weight(v.toFloat()).height(12.dp).background(colors[i % colors.size])) }
        val rest = 1.0 - parts.sumOf { it.second }
        if (rest > 0.001) Spacer(Modifier.weight(rest.toFloat()))
    }
}
