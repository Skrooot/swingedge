package se.dahlander.swingedge

import android.app.Application
import se.dahlander.swingedge.work.AnalysisWorker
import se.dahlander.swingedge.work.Notifier

class SwingEdgeApp : Application() {
    override fun onCreate() {
        super.onCreate()
        Notifier.createChannels(this)
        AnalysisWorker.schedule(this)
    }
}
