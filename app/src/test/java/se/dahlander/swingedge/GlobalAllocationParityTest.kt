package se.dahlander.swingedge

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.double
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import se.dahlander.swingedge.data.FactorRepository
import se.dahlander.swingedge.factor.GlobalAllocation

/** Appens Global trendföljning ska ge exakt samma innehav som forskningsskriptet qa/bl/gtf.py, månad för månad. */
class GlobalAllocationParityTest {
    private val root = Json.parseToJsonElement(javaClass.classLoader!!.getResource("gtf_parity.json")!!.readText()).jsonObject
    private val levels = root.getValue("levels").jsonObject.mapValues { (_, v) -> v.jsonObject.mapValues { it.value.jsonPrimitive.double } }

    @Test fun holdingsMatchPythonEveryMonth() {
        val py = root.getValue("decisions").jsonArray.map { it.jsonObject }
        val k = GlobalAllocation.run(levels).associateBy { it.signalMonth }
        var n = 0
        for (d in py) {
            val m = d.getValue("signalMonth").jsonPrimitive.content
            val want = d.getValue("holdings").jsonArray.map { it.jsonPrimitive.content }.sorted()
            assertEquals("innehav efter $m", want, k.getValue(m).holdings.sorted())
            n++
        }
        assertTrue(n > 90)
        assertEquals(root.getValue("first").jsonPrimitive.content, GlobalAllocation.run(levels).first().signalMonth)
    }

    @Test fun thresholdKeepsHoldingWhenGapIsSmall() {
        // Platt historik i 13 månader (alla lika -> A, B, C ägs), sista månaden: A +50 %, B +40 %, C +30 %, D varierar
        val ms = GlobalAllocation.months("2020-01", "2021-02")
        fun series(last: Double) = ms.associateWith { if (it == "2021-02") last else 100.0 }
        fun run(d: Double) = GlobalAllocation.run(linkedMapOf("A" to series(150.0), "B" to series(140.0), "C" to series(130.0), "D" to series(d)))
        assertEquals(listOf("A", "B", "C"), run(100.0).first().holdings)
        val small = run(131.0).last()                       // D ligger 1 procentenhet före C
        assertEquals(listOf("A", "B", "C"), small.holdings.sorted())
        assertTrue(small.bought.isEmpty())
        val big = run(133.5).last()                         // 3,5 procentenheter före C
        assertEquals(listOf("A", "B", "D"), big.holdings.sorted())
        assertEquals(listOf("D"), big.bought); assertEquals(listOf("C"), big.sold)
        val noThreshold = GlobalAllocation.run(linkedMapOf("A" to series(150.0), "B" to series(140.0), "C" to series(130.0), "D" to series(131.0)), threshold = 0.0).last()
        assertEquals(listOf("A", "B", "D"), noThreshold.holdings.sorted())
    }

    @Test fun avanzaMonthLabelIsShiftedToTheRightMonth() {
        // 2024-10-31T23:00Z = 1 nov 00:00 svensk tid; värdet är novembers sista NAV (kontrollerat mot SPY i SEK)
        val m = FactorRepository.fundMonths("""{"id":"1505","dataSerie":[{"x":1730415600000,"y":661.5},{"x":1727733600000,"y":613.8},{"x":1733007600000,"y":null}]}""")
        assertEquals(mapOf("2024-10" to 613.8, "2024-11" to 661.5), m)
    }
}
