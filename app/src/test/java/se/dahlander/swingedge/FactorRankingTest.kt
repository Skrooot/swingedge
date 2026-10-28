package se.dahlander.swingedge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import se.dahlander.swingedge.data.FactorRepository
import se.dahlander.swingedge.factor.FactorRanking
import se.dahlander.swingedge.factor.FactorStrategy
import se.dahlander.swingedge.factor.StockSnapshot

class FactorRankingTest {
    private fun s(id: String, mom: Double, pe: Double? = 10.0, dy: Double? = 0.03, roe: Double? = 0.1, cap: Double = 5e9, sector: String = "Industri") =
        StockSnapshot(id, "Bolag $id", id, topSector = sector, price = 100 * (1 + mom), price3m = 100.0, price6m = 100.0, price12m = 100.0,
            pe = pe, pb = 2.0, ps = 1.0, evEbit = 12.0, directYield = dy, roe = roe, roa = roe?.div(2), roce = roe, operatingCashFlow = 1e8,
            marketCap = cap, equityPerShare = 50.0)

    @Test fun compositeMomentumIsMeanOfThreePeriods() {
        val x = StockSnapshot("1", "X", "X", price = 120.0, price3m = 100.0, price6m = 120.0, price12m = 80.0)
        assertEquals((0.2 + 0.0 + 0.5) / 3, FactorRanking.momentum(x)!!, 1e-12)
    }

    @Test fun universeExcludesFinancialsSmallCapsAndMissingHistory() {
        assertFalse(FactorRanking.eligible(s("bank", 0.1, sector = "Finans")))
        assertFalse(FactorRanking.eligible(s("liten", 0.1, cap = 1e9)))
        assertFalse(FactorRanking.eligible(s("ny", 0.1).copy(price12m = null)))
        assertTrue(FactorRanking.eligible(s("ok", 0.1)))
    }

    @Test fun percentileHandlesTiesAndNulls() {
        val p = FactorRanking.percentile(mapOf("a" to 1.0, "b" to 2.0, "c" to 2.0, "d" to 3.0, "e" to null))
        assertEquals(0.0, p.getValue("a"), 1e-12); assertEquals(0.5, p.getValue("b"), 1e-12); assertEquals(0.5, p.getValue("c"), 1e-12)
        assertEquals(1.0, p.getValue("d"), 1e-12); assertFalse("e" in p)
    }

    @Test fun trendingValuePicksCheapStocksThenMomentum() {
        // 50 bolag: låga id = billigast (lågt P/E). Momentum stiger med id. Topp 40 % billigast = id 0..19, sedan högst momentum
        val all = (0 until 50).map { s(it.toString(), mom = it / 100.0, pe = 5.0 + it) }
        val r = FactorRanking.rank(FactorStrategy.VALUE, all)
        assertTrue(r.isNotEmpty())
        assertTrue(r.all { it.stock.id.toInt() < 20 })
        assertEquals("19", r.first().stock.id)
        assertEquals(5, r.size) // fjärdedelen av 20
    }

    @Test fun negativeEarningsRankAsWorstNotMissing() {
        val all = listOf(s("neg", 0.5, pe = -4.0), s("cheap", 0.1, pe = 5.0), s("dear", 0.2, pe = 40.0))
        val prim = FactorRanking.primary(FactorStrategy.VALUE, all)
        assertTrue(prim.getValue("cheap") > prim.getValue("neg"))
    }

    @Test fun parsesAvanzaStockPage() {
        val body = """{"orderbookId":"5269","sectors":[{"sectorName":"Lastbilar"},{"sectorName":"Industri"}],"listing":{"marketListName":"Large Cap Stockholm"},
            "historicalClosingPrices":{"threeMonths":355.5,"sixMonths":319.5,"oneYear":261.1},"quote":{"last":310.5,"spread":0.03},
            "keyIndicators":{"directYield":0.0274,"priceEarningsRatio":16.16,"priceSalesRatio":1.31,"priceBookRatio":3.3,"evEbitRatio":16.53,
            "returnOnEquity":0.2041,"returnOnTotalAssets":0.0553,"returnOnCapitalEmployed":0.1233,"marketCapital":{"value":6.3e11,"currency":"SEK"},
            "equityPerShare":{"value":94.14},"operatingCashFlow":{"value":5.1e10},"reportDate":"2026-10-23"}}"""
        val x = FactorRepository.parseStock("5269", "Volvo B", "VOLV B", body)
        assertEquals("Industri", x.topSector); assertEquals(310.5, x.price!!, 0.0); assertEquals(6.3e11, x.marketCap!!, 0.0)
        assertEquals(16.16, x.pe!!, 0.0); assertEquals(261.1, x.price12m!!, 0.0); assertEquals(5.1e10, x.operatingCashFlow!!, 0.0)
        assertTrue(FactorRanking.eligible(x))
    }
}
