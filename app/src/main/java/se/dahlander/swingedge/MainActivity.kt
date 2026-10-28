package se.dahlander.swingedge

import android.Manifest
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ShowChart
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Insights
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import se.dahlander.swingedge.ui.AnalysisScreen
import se.dahlander.swingedge.ui.AppViewModel
import se.dahlander.swingedge.ui.DashboardScreen
import se.dahlander.swingedge.ui.InstrumentsScreen
import se.dahlander.swingedge.ui.PortfolioScreen
import se.dahlander.swingedge.ui.SettingsScreen
import se.dahlander.swingedge.ui.SignalsScreen
import se.dahlander.swingedge.ui.SwingEdgeTheme

private data class Tab(val route: String, val label: String, val icon: ImageVector)

private val TABS = listOf(
    Tab("dashboard", "Översikt", Icons.Filled.Dashboard),
    Tab("signals", "Signaler", Icons.Filled.NotificationsActive),
    Tab("portfolio", "Portfölj", Icons.Filled.AccountBalanceWallet),
    Tab("analysis", "Analys", Icons.Filled.Insights),
    Tab("instruments", "Instrument", Icons.AutoMirrored.Filled.ShowChart),
)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        val startTab = intent?.getStringExtra("tab")
        setContent { SwingEdgeTheme { App(startTab) } }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun App(startTab: String?) {
    val vm: AppViewModel = viewModel()
    val s by vm.state.collectAsStateWithLifecycle()
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val route = entry?.destination?.route
    val snack = remember { SnackbarHostState() }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    val requestNotifications = { if (Build.VERSION.SDK_INT >= 33) permission.launch(Manifest.permission.POST_NOTIFICATIONS) }
    LaunchedEffect(Unit) {
        if (s.settings.notifications) requestNotifications()
        if (startTab != null && TABS.any { it.route == startTab }) nav.navigate(startTab)
    }
    LaunchedEffect(s.message) { s.message?.let { snack.showSnackbar(it); vm.dismissMessage() } }

    Scaffold(
        topBar = {
            Column {
                TopAppBar(
                    title = { Text(TABS.firstOrNull { it.route == route }?.label?.let { if (it == "Översikt") "SwingEdge" else it } ?: "Inställningar") },
                    actions = {
                        IconButton(onClick = { vm.refresh() }, enabled = !s.loading) { Icon(Icons.Filled.Refresh, contentDescription = "Uppdatera nu") }
                        IconButton(onClick = { nav.navigate("settings") { launchSingleTop = true } }) { Icon(Icons.Filled.Settings, contentDescription = "Inställningar") }
                    },
                )
                if (s.loading) LinearProgressIndicator(Modifier.fillMaxWidth())
            }
        },
        bottomBar = {
            NavigationBar {
                TABS.forEach { t ->
                    NavigationBarItem(
                        selected = route == t.route,
                        onClick = { nav.navigate(t.route) { popUpTo(nav.graph.findStartDestination().id) { saveState = true }; launchSingleTop = true; restoreState = true } },
                        icon = { Icon(t.icon, contentDescription = null) },
                        label = { Text(t.label, style = MaterialTheme.typography.labelSmall) },
                    )
                }
            }
        },
        snackbarHost = { SnackbarHost(snack) },
    ) { padding ->
        NavHost(nav, startDestination = "dashboard") {
            composable("dashboard") { DashboardScreen(s, padding) }
            composable("signals") { SignalsScreen(s, padding) }
            composable("portfolio") { PortfolioScreen(s, vm, padding) }
            composable("analysis") { AnalysisScreen(s, vm, padding) }
            composable("instruments") { InstrumentsScreen(s, padding) }
            composable("settings") { SettingsScreen(s, vm, padding, requestNotifications) }
        }
    }
}
