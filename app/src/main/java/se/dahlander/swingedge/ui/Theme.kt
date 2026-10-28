package se.dahlander.swingedge.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

private val Light = lightColorScheme(
    primary = Color(0xFF1F4FD1), onPrimary = Color.White,
    primaryContainer = Color(0xFFDCE4FF), onPrimaryContainer = Color(0xFF0A1F5C),
    secondary = Color(0xFF4A5568), surface = Color(0xFFFFFFFF), onSurface = Color(0xFF151B26),
    surfaceVariant = Color(0xFFEFF2F7), onSurfaceVariant = Color(0xFF586273),
    background = Color(0xFFF5F7FA), onBackground = Color(0xFF151B26),
    surfaceContainer = Color(0xFFF0F3F8), surfaceContainerHigh = Color(0xFFE9EDF4),
    outline = Color(0xFFCBD2DD), outlineVariant = Color(0xFFE1E6EE), error = Color(0xFFB3261E),
)

private val Dark = darkColorScheme(
    primary = Color(0xFF8FA9FF), onPrimary = Color(0xFF0A1F5C),
    primaryContainer = Color(0xFF203A8A), onPrimaryContainer = Color(0xFFDCE4FF),
    secondary = Color(0xFFB4BECC), surface = Color(0xFF151B24), onSurface = Color(0xFFE5EAF1),
    surfaceVariant = Color(0xFF1F2733), onSurfaceVariant = Color(0xFF9AA6B6),
    background = Color(0xFF0F141B), onBackground = Color(0xFFE5EAF1),
    surfaceContainer = Color(0xFF1A212B), surfaceContainerHigh = Color(0xFF222B37),
    outline = Color(0xFF3A4554), outlineVariant = Color(0xFF2A3340), error = Color(0xFFF2B8B5),
)

/** Signalfärger: grönt = investerad/positiv, rött = kontanter/negativ, gult = väntar. Används alltid med text. */
@Immutable
data class SignalColors(val positive: Color, val negative: Color, val pending: Color, val neutral: Color)

val LocalSignalColors = staticCompositionLocalOf { SignalColors(Color(0xFF1B7F4B), Color(0xFFC0392B), Color(0xFFB7791F), Color(0xFF586273)) }

@Composable
fun SwingEdgeTheme(content: @Composable () -> Unit) {
    val dark = isSystemInDarkTheme()
    val base = Typography()
    val num = FontFamily.Default
    val typo = base.copy(
        headlineMedium = base.headlineMedium.copy(fontWeight = FontWeight.SemiBold, letterSpacing = (-0.3).sp),
        titleLarge = base.titleLarge.copy(fontWeight = FontWeight.SemiBold),
        titleMedium = base.titleMedium.copy(fontWeight = FontWeight.SemiBold),
        labelSmall = TextStyle(fontFamily = num, fontWeight = FontWeight.Medium, fontSize = 11.sp, letterSpacing = 0.6.sp),
    )
    val colors = if (dark) SignalColors(Color(0xFF5FD39A), Color(0xFFFF8A7A), Color(0xFFF3C969), Color(0xFF9AA6B6))
    else SignalColors(Color(0xFF1B7F4B), Color(0xFFC0392B), Color(0xFF9A6400), Color(0xFF586273))
    androidx.compose.runtime.CompositionLocalProvider(LocalSignalColors provides colors) {
        MaterialTheme(colorScheme = if (dark) Dark else Light, typography = typo, content = content)
    }
}
