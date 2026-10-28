package se.dahlander.swingedge

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.double
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.int
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import se.dahlander.swingedge.edge.EdgeFamilies
import se.dahlander.swingedge.edge.cleanSpikes

/** Appens strategifamiljer i Global Opportunities ska ge exakt samma läge som forskningsmotorn edge.py. */
class EdgeParityTest {
    @Test fun familiesMatchPythonResearchEngine() {
        val root = Json.parseToJsonElement(javaClass.classLoader!!.getResource("edge_parity.json")!!.readText()).jsonObject
        var compared = 0
        for ((key, v) in root) {
            val o = v.jsonObject
            val fam = key.substringAfter(':')
            val dates = o.getValue("dates").jsonArray.map { it.jsonPrimitive.content }
            val closes = o.getValue("closes").jsonArray.map { it.jsonPrimitive.double }
            val params = o.getValue("params").jsonObject.mapValues { it.value.jsonPrimitive.double }
            val py = o.getValue("weights").jsonArray.map { it.jsonPrimitive.doubleOrNull }
            val warm = o.getValue("warmup").jsonPrimitive.int
            val k = EdgeFamilies.weights(fam, closes, dates, params)
            for (i in warm until dates.size - 2) {
                val p = py[i] ?: continue
                assertEquals("$key ${dates[i]}", p, k[i] ?: Double.NaN, 1e-9)
                compared++
            }
        }
        assertTrue("jämförde $compared dagar", compared > 10000)
    }

    @Test fun spikeFilterRemovesOneDayErrors() {
        val (d, c) = cleanSpikes(listOf("a", "b", "c", "d"), listOf(100.0, 200.0, 101.0, 102.0))
        assertEquals(listOf("a", "c", "d"), d)
        assertEquals(3, c.size)
    }
}
