package se.dahlander.swingedge

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.double
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Test
import se.dahlander.swingedge.core.Backtests
import se.dahlander.swingedge.core.Bar
import se.dahlander.swingedge.core.metrics
import java.time.LocalDate

/** Appens backtest mot en oberoende Python-implementation av samma regler (qa/bl/ref_backtest.py) på riktig historik. */
class BacktestReferenceTest {
    private val root = Json.parseToJsonElement(javaClass.classLoader!!.getResource("backtest_ref.json")!!.readText()).jsonObject
    private fun bars(k: String) = root.getValue(k).jsonObject.let { o ->
        o.getValue("dates").jsonArray.map { LocalDate.parse(it.jsonPrimitive.content) }.zip(o.getValue("closes").jsonArray.map { it.jsonPrimitive.double }) { d, c -> Bar(d, c) }
    }
    private fun ref(k: String) = root.getValue("ref").jsonObject.getValue(k).jsonObject

    @Test fun bitcoinTrendOnProductMatchesReference() {
        val (s, _) = Backtests.btcOnProduct(bars("btc"), bars("xbt"))
        val m = metrics(s)!!; val r = ref("btc").getValue("metrics").jsonObject
        assertEquals(r.getValue("cagr").jsonPrimitive.double, m.cagr, 1e-9)
        assertEquals(r.getValue("sharpe").jsonPrimitive.double, m.sharpe, 1e-9)
        assertEquals(r.getValue("maxdd").jsonPrimitive.double, m.maxDd, 1e-9)
        assertEquals(ref("btc").getValue("entries").jsonPrimitive.int, s.trades.size)
    }

    @Test fun sp500TrendOnIndexMatchesReference() {
        val (s, _) = Backtests.sp500OnIndex(bars("sp"))
        val m = metrics(s)!!; val r = ref("sp").getValue("metrics").jsonObject
        assertEquals(r.getValue("cagr").jsonPrimitive.double, m.cagr, 1e-9)
        assertEquals(r.getValue("sharpe").jsonPrimitive.double, m.sharpe, 1e-9)
        assertEquals(r.getValue("maxdd").jsonPrimitive.double, m.maxDd, 1e-9)
    }
}
