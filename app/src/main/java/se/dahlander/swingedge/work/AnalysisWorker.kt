package se.dahlander.swingedge.work

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import se.dahlander.swingedge.MainActivity
import se.dahlander.swingedge.R
import se.dahlander.swingedge.core.SignalRecord
import se.dahlander.swingedge.core.SignalType
import se.dahlander.swingedge.data.Repository
import java.util.concurrent.TimeUnit

/** Kör analysen ungefär en gång i timmen, även när appen är stängd, och skickar notiser för nya händelser. */
class AnalysisWorker(ctx: Context, params: WorkerParameters) : CoroutineWorker(ctx, params) {
    override suspend fun doWork(): Result = withContext(Dispatchers.IO) {
        val repo = Repository(applicationContext)
        val out = repo.refresh("bakgrund")
        if (repo.store.settings.notifications) Notifier.show(applicationContext, out.notify)
        // Global Opportunities: skanna ungefär en gång per dygn, skilt från SwingEdges egna strategier
        val edge = try { se.dahlander.swingedge.data.EdgeRepository(repo.store).refresh() } catch (e: Exception) { null }
        if (edge != null && repo.store.settings.notifications && repo.store.settings.edgeNotify) Notifier.show(applicationContext, edge.notify)
        Result.success()
    }

    companion object {
        private const val NAME = "swingedge-analysis"
        fun schedule(ctx: Context) {
            val req = PeriodicWorkRequestBuilder<AnalysisWorker>(1, TimeUnit.HOURS, 15, TimeUnit.MINUTES)
                .setConstraints(Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build())
                .build()
            WorkManager.getInstance(ctx).enqueueUniquePeriodicWork(NAME, ExistingPeriodicWorkPolicy.KEEP, req)
        }
    }
}

object Notifier {
    const val CHANNEL_SIGNALS = "signals"
    const val CHANNEL_DATA = "data"

    fun createChannels(ctx: Context) {
        val nm = ctx.getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel(CHANNEL_SIGNALS, "Köp- och säljsignaler", NotificationManager.IMPORTANCE_HIGH)
            .apply { description = "Nya signaler, ändrat strategiläge och månatlig ombalansering" })
        nm.createNotificationChannel(NotificationChannel(CHANNEL_DATA, "Datafel och missade kontroller", NotificationManager.IMPORTANCE_DEFAULT))
    }

    fun show(ctx: Context, events: List<SignalRecord>) {
        if (events.isEmpty()) return
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) return
        val open = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java).putExtra("tab", "signals"),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val nm = NotificationManagerCompat.from(ctx)
        for (e in events.take(5)) {
            val data = e.type == SignalType.DATA_ERROR || e.type == SignalType.MISSED
            val title = when (e.type) {
                SignalType.BUY -> "Köpsignal: ${e.strategy?.displayName ?: ""}"
                SignalType.SELL -> "Säljsignal: ${e.strategy?.displayName ?: ""}"
                SignalType.REBALANCE -> "Dags för månatlig ombalansering"
                SignalType.DATA_ERROR -> "Datauppdateringen misslyckades"
                SignalType.MISSED -> "Planerad kontroll kunde inte göras"
                else -> e.type.label
            }
            val n = NotificationCompat.Builder(ctx, if (data) CHANNEL_DATA else CHANNEL_SIGNALS)
                .setSmallIcon(R.drawable.ic_stat_signal)
                .setContentTitle(title)
                .setContentText(e.action)
                .setStyle(NotificationCompat.BigTextStyle().bigText("${e.action}. ${e.reason}"))
                .setContentIntent(open)
                .setAutoCancel(true)
                .build()
            try { nm.notify(e.key.hashCode(), n) } catch (_: SecurityException) {}
        }
    }
}
