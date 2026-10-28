package se.dahlander.swingedge

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import se.dahlander.swingedge.core.AVANTIS_CORE
import se.dahlander.swingedge.core.DEFAULT_SLEEVES
import se.dahlander.swingedge.core.EW_BASE
import se.dahlander.swingedge.core.Instrument
import se.dahlander.swingedge.core.StrategyId
import se.dahlander.swingedge.core.StrategyStates
import se.dahlander.swingedge.core.effectiveSleeves
import se.dahlander.swingedge.core.target

class AvantisCoreTest {
    @Test fun offLeavesTestedModelUntouched() {
        assertEquals(DEFAULT_SLEEVES, effectiveSleeves(DEFAULT_SLEEVES, 0.0))
        val t = target(StrategyStates(true, true), effectiveSleeves(DEFAULT_SLEEVES, 0.0), EW_BASE)
        assertFalse(StrategyId.AVANTIS_CORE in t.perStrategy)
        AVANTIS_CORE.forEach { assertEquals(0.0, t.total.getValue(it), 0.0) }
    }

    @Test fun halfAvantisScalesSwingEdgeAndSplitsCoreInThirds() {
        val s = effectiveSleeves(DEFAULT_SLEEVES, 0.5)
        assertEquals(0.10, s.getValue(StrategyId.BTC_TREND), 1e-12)
        assertEquals(0.20, s.getValue(StrategyId.EQUAL_WEIGHT), 1e-12)
        assertEquals(0.20, s.getValue(StrategyId.SP500_TREND), 1e-12)
        assertEquals(1.0, s.values.sum(), 1e-12)
        val t = target(StrategyStates(true, true), s, EW_BASE)
        AVANTIS_CORE.forEach { assertEquals(0.5 / 3, t.total.getValue(it), 1e-12) }
        assertEquals(0.10 + 0.20 / 3, t.total.getValue(Instrument.XBT), 1e-12)
        assertEquals(0.0, t.cash, 1e-12)
    }

    @Test fun avantisStaysInvestedWhenTrendsAreOff() {
        val t = target(StrategyStates(false, false), effectiveSleeves(DEFAULT_SLEEVES, 0.5), EW_BASE)
        AVANTIS_CORE.forEach { assertEquals(0.5 / 3, t.total.getValue(it), 1e-12) }
        assertEquals(0.30, t.cash, 1e-12)   // Bitcoin Trend 10 % + S&P 500 Trend 20 % i kontanter
        assertTrue(t.perStrategy.getValue(StrategyId.BTC_TREND).isEmpty())
    }
}
