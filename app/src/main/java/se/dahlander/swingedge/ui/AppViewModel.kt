package se.dahlander.swingedge.ui

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import se.dahlander.swingedge.core.AnalysisResult
import se.dahlander.swingedge.core.BacktestRun
import se.dahlander.swingedge.core.SignalRecord
import se.dahlander.swingedge.core.Trade
import se.dahlander.swingedge.data.MarketData
import se.dahlander.swingedge.data.PortfolioKind
import se.dahlander.swingedge.data.Repository
import se.dahlander.swingedge.data.RunLog
import se.dahlander.swingedge.data.Settings
import se.dahlander.swingedge.data.Snapshot
import se.dahlander.swingedge.work.Notifier
import java.util.UUID

data class UiState(
    val loading: Boolean = false,
    val result: AnalysisResult? = null,
    val cache: MarketData.Cache? = null,
    val signals: List<SignalRecord> = emptyList(),
    val trades: List<Trade> = emptyList(),
    val settings: Settings = Settings(),
    val snapshots: List<Snapshot> = emptyList(),
    val backtests: List<BacktestRun> = emptyList(),
    val runs: List<RunLog> = emptyList(),
    val forward: List<se.dahlander.swingedge.core.ForwardEntry> = emptyList(),
    val backtestRunning: Boolean = false,
    val message: String? = null,
)

class AppViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = Repository(app)
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    init {
        // Visa sparade kurser direkt och hämta nya i bakgrunden
        viewModelScope.launch(Dispatchers.IO) {
            // Utan sparade kurser finns inget att räkna på ännu; annars skulle det loggas som ett datafel
            if (repo.store.cache != null) reload(repo.refresh("appstart", fetch = false).result) else reload(null)
            refresh()
        }
    }

    private fun reload(result: AnalysisResult?) {
        val s = repo.store
        val kind = s.settings.active
        _state.update {
            it.copy(result = result ?: it.result, cache = s.cache, signals = s.signals(kind).reversed(), trades = s.trades(kind),
                settings = s.settings, snapshots = s.snapshots(kind), backtests = s.backtests.reversed(), runs = s.runs().reversed(),
                forward = s.forward(kind).reversed())
        }
    }

    fun refresh() {
        if (_state.value.loading) return
        _state.update { it.copy(loading = true) }
        viewModelScope.launch(Dispatchers.IO) {
            val out = try { repo.refresh("manuell") } catch (e: Exception) { null }
            if (out != null && repo.store.settings.notifications) Notifier.show(getApplication(), out.notify)
            reload(out?.result)
            _state.update { it.copy(loading = false, message = if (out == null) "Analysen kunde inte köras" else if (!out.fetchOk) "Alla kurser kunde inte hämtas. Äldre kurser används där de finns." else null) }
        }
    }

    /** Räknar om utan att hämta nya kurser, t.ex. efter en registrerad affär. */
    private fun recompute() = viewModelScope.launch(Dispatchers.IO) { reload(repo.refresh("ändring", fetch = false).result) }

    fun addTrade(t: Trade) {
        val kind = repo.store.settings.active
        repo.store.saveTrades(kind, repo.store.trades(kind) + t.copy(id = UUID.randomUUID().toString()))
        recompute()
    }

    fun deleteTrade(id: String) {
        val kind = repo.store.settings.active
        repo.store.saveTrades(kind, repo.store.trades(kind).filter { it.id != id })
        recompute()
    }

    fun setActive(kind: PortfolioKind) {
        repo.store.settings = repo.store.settings.copy(active = kind)
        recompute()
    }

    fun setNotifications(on: Boolean) {
        repo.store.settings = repo.store.settings.copy(notifications = on)
        reload(null)
    }

    fun resetPaper(capital: Double) {
        repo.store.saveTrades(PortfolioKind.PAPER, listOf(Trade(UUID.randomUUID().toString(), java.time.LocalDate.now().toString(),
            se.dahlander.swingedge.core.Side.DEPOSIT, price = capital, note = "Virtuellt startkapital")))
        repo.store.saveEngine(PortfolioKind.PAPER, repo.store.engine(PortfolioKind.PAPER).copy(alignedBtc = null, alignedSp = null, rebalancedFor = null))
        recompute()
    }

    fun runBacktest() {
        if (_state.value.backtestRunning) return
        _state.update { it.copy(backtestRunning = true) }
        viewModelScope.launch(Dispatchers.IO) {
            try { repo.runBacktest() } catch (e: Exception) { _state.update { it.copy(message = "Backtestet misslyckades: ${e.message}") } }
            reload(null)
            _state.update { it.copy(backtestRunning = false) }
        }
    }

    fun dismissMessage() = _state.update { it.copy(message = null) }
}
