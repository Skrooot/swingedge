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
import se.dahlander.swingedge.core.DEFAULT_SLEEVES
import se.dahlander.swingedge.core.SignalRecord
import se.dahlander.swingedge.core.StrategyId
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
    val edge: se.dahlander.swingedge.data.EdgeRepository.Result? = null,
    val edgeLoading: Boolean = false,
    val backtestRunning: Boolean = false,
    val allocation: se.dahlander.swingedge.data.FactorRepository.Allocation? = null,
    val allocationLoading: Boolean = false,
    val scanner: se.dahlander.swingedge.data.ScannerCache? = null,
    /** Pågående Factor Scanner-skanning: (klara, totalt). */
    val scanProgress: Pair<Int, Int>? = null,
    val message: String? = null,
)

class AppViewModel(app: Application) : AndroidViewModel(app) {
    private val repo = Repository(app)
    private val _state = MutableStateFlow(UiState())
    val state: StateFlow<UiState> = _state

    private val edgeRepo = se.dahlander.swingedge.data.EdgeRepository(repo.store)
    private val factorRepo = se.dahlander.swingedge.data.FactorRepository(repo.store, app)

    fun refreshAllocation(force: Boolean) {
        if (_state.value.allocationLoading) return
        _state.update { it.copy(allocationLoading = true) }
        viewModelScope.launch(Dispatchers.IO) {
            val r = try { factorRepo.refreshAllocation(force) } catch (e: Exception) { null }
            if (r != null && repo.store.settings.notifications && repo.store.settings.gtfNotify) Notifier.show(getApplication(), r.notify)
            _state.update { it.copy(allocation = r ?: it.allocation, allocationLoading = false, message = if (r == null) "Fondvärdena kunde inte hämtas" else it.message) }
        }
    }

    fun scan(force: Boolean) {
        if (_state.value.scanProgress != null) return
        _state.update { it.copy(scanProgress = 0 to 1) }
        viewModelScope.launch(Dispatchers.IO) {
            val r = try { factorRepo.scan(force) { d, n -> _state.update { it.copy(scanProgress = d to n) } } } catch (e: Exception) { null }
            _state.update { it.copy(scanner = r ?: it.scanner, scanProgress = null, message = if (r == null || r.stocks.isEmpty()) "Skanningen misslyckades" else it.message) }
        }
    }

    fun nextRebalance() = factorRepo.nextRebalance()

    fun setGtfNotify(on: Boolean) {
        repo.store.settings = repo.store.settings.copy(gtfNotify = on)
        reload(null)
    }

    fun refreshEdge(force: Boolean) {
        if (_state.value.edgeLoading) return
        _state.update { it.copy(edgeLoading = true) }
        viewModelScope.launch(Dispatchers.IO) {
            val r = try { edgeRepo.refresh(force) } catch (e: Exception) { null }
            if (r != null && repo.store.settings.notifications && repo.store.settings.edgeNotify) Notifier.show(getApplication(), r.notify)
            _state.update { it.copy(edge = r ?: it.edge, edgeLoading = false, message = if (r == null) "Skanningen misslyckades" else it.message) }
        }
    }

    fun setEdgeNotify(on: Boolean, min: String) {
        repo.store.settings = repo.store.settings.copy(edgeNotify = on, edgeMinEvidence = min)
        reload(null)
    }

    init {
        viewModelScope.launch(Dispatchers.IO) { _state.update { it.copy(edge = edgeRepo.cached()) }; refreshEdge(false) }
        viewModelScope.launch(Dispatchers.IO) { _state.update { it.copy(allocation = factorRepo.cachedAllocation(), scanner = factorRepo.cachedScanner().takeIf { c -> c.at > 0 }) } }
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

    fun setSleeves(s: Map<StrategyId, Double>) {
        repo.store.settings = repo.store.settings.copy(sleeves = s)
        recompute()
    }

    fun resetSleeves() = setSleeves(DEFAULT_SLEEVES)

    fun setAvantisShare(v: Double) {
        repo.store.settings = repo.store.settings.copy(avantisShare = v)
        recompute()
    }

    fun setIncludeGold(on: Boolean) {
        repo.store.settings = repo.store.settings.copy(includeGold = on)
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
