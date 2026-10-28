package se.dahlander.swingedge.core

import java.time.DayOfWeek
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneId
import java.time.ZonedDateTime
import java.time.temporal.TemporalAdjusters

val STOCKHOLM: ZoneId = ZoneId.of("Europe/Stockholm")
val FRANKFURT: ZoneId = ZoneId.of("Europe/Berlin")
val NEW_YORK: ZoneId = ZoneId.of("America/New_York")
val UTC: ZoneId = ZoneId.of("UTC")

/**
 * Handelskalender med regelbaserade helgdagar. Extraordinära stängningar (t.ex. sorgedagar i USA)
 * finns inte med; de syns i stället som saknade kurser och fångas av datakontrollen.
 */
enum class Exchange(val zone: ZoneId, val open: LocalTime, val close: LocalTime, val label: String) {
    XSTO(STOCKHOLM, LocalTime.of(9, 0), LocalTime.of(17, 30), "Stockholmsbörsen"),
    XETR(FRANKFURT, LocalTime.of(9, 0), LocalTime.of(17, 30), "Xetra"),
    NYSE(NEW_YORK, LocalTime.of(9, 30), LocalTime.of(16, 0), "New York");

    fun isTradingDay(d: LocalDate): Boolean {
        if (d.dayOfWeek == DayOfWeek.SATURDAY || d.dayOfWeek == DayOfWeek.SUNDAY) return false
        return d !in holidays(d.year)
    }

    fun nextTradingDay(d: LocalDate): LocalDate {
        var x = d.plusDays(1)
        while (!isTradingDay(x)) x = x.plusDays(1)
        return x
    }

    fun previousTradingDay(d: LocalDate): LocalDate {
        var x = d.minusDays(1)
        while (!isTradingDay(x)) x = x.minusDays(1)
        return x
    }

    /** Sant om d är en handelsdag och nästa handelsdag ligger i en annan månad. */
    fun isLastTradingDayOfMonth(d: LocalDate): Boolean = isTradingDay(d) && nextTradingDay(d).month != d.month

    fun lastTradingDayOfMonth(year: Int, month: Int): LocalDate {
        var x = LocalDate.of(year, month, 1).with(TemporalAdjusters.lastDayOfMonth())
        while (!isTradingDay(x)) x = x.minusDays(1)
        return x
    }

    fun closeInstant(d: LocalDate): Instant = ZonedDateTime.of(d, close, zone).toInstant()
    fun openInstant(d: LocalDate): Instant = ZonedDateTime.of(d, open, zone).toInstant()

    /** Första börsöppning som ligger vid eller efter tidpunkten t. */
    fun nextOpenAtOrAfter(t: Instant): Instant {
        var d = t.atZone(zone).toLocalDate()
        while (true) {
            if (isTradingDay(d)) {
                val o = openInstant(d)
                if (!o.isBefore(t)) return o
            }
            d = d.plusDays(1)
        }
    }

    /** Sant om dagens stapel för d är slutgiltig vid tidpunkten now (15 minuters marginal efter stängning). */
    fun isBarFinal(d: LocalDate, now: Instant): Boolean = !now.isBefore(closeInstant(d).plusSeconds(15 * 60))

    /** Senaste handelsdag vars stängning är slutgiltig vid tidpunkten now. */
    fun lastFinalTradingDay(now: Instant): LocalDate {
        var d = now.atZone(zone).toLocalDate()
        while (!(isTradingDay(d) && isBarFinal(d, now))) d = d.minusDays(1)
        return d
    }

    fun holidays(year: Int): Set<LocalDate> {
        val easter = easterSunday(year)
        val goodFriday = easter.minusDays(2)
        val easterMonday = easter.plusDays(1)
        return when (this) {
            XSTO -> {
                // Midsommarafton = fredagen mellan 19 och 25 juni
                val midsummerEve = (19..25).map { LocalDate.of(year, 6, it) }.first { it.dayOfWeek == DayOfWeek.FRIDAY }
                setOf(
                    LocalDate.of(year, 1, 1), LocalDate.of(year, 1, 6), goodFriday, easterMonday,
                    LocalDate.of(year, 5, 1), easter.plusDays(39), LocalDate.of(year, 6, 6), midsummerEve,
                    LocalDate.of(year, 12, 24), LocalDate.of(year, 12, 25), LocalDate.of(year, 12, 26), LocalDate.of(year, 12, 31),
                )
            }
            XETR -> setOf(
                LocalDate.of(year, 1, 1), goodFriday, easterMonday, LocalDate.of(year, 5, 1),
                LocalDate.of(year, 12, 24), LocalDate.of(year, 12, 25), LocalDate.of(year, 12, 26), LocalDate.of(year, 12, 31),
            )
            NYSE -> buildSet {
                // Nyårsdagen på en lördag flyttas inte till fredagen (NYSE-regel)
                val ny = LocalDate.of(year, 1, 1)
                if (ny.dayOfWeek == DayOfWeek.SUNDAY) add(ny.plusDays(1)) else if (ny.dayOfWeek != DayOfWeek.SATURDAY) add(ny)
                add(nthWeekday(year, 1, DayOfWeek.MONDAY, 3))   // Martin Luther King
                add(nthWeekday(year, 2, DayOfWeek.MONDAY, 3))   // Presidents Day
                add(goodFriday)
                add(LocalDate.of(year, 5, 1).with(TemporalAdjusters.lastInMonth(DayOfWeek.MONDAY))) // Memorial Day
                if (year >= 2022) add(observed(LocalDate.of(year, 6, 19)))                         // Juneteenth
                add(observed(LocalDate.of(year, 7, 4)))
                add(nthWeekday(year, 9, DayOfWeek.MONDAY, 1))   // Labor Day
                add(nthWeekday(year, 11, DayOfWeek.THURSDAY, 4)) // Thanksgiving
                add(observed(LocalDate.of(year, 12, 25)))
            }
        }
    }
}

private fun observed(d: LocalDate): LocalDate = when (d.dayOfWeek) {
    DayOfWeek.SATURDAY -> d.minusDays(1)
    DayOfWeek.SUNDAY -> d.plusDays(1)
    else -> d
}

private fun nthWeekday(year: Int, month: Int, dow: DayOfWeek, n: Int): LocalDate =
    LocalDate.of(year, month, 1).with(TemporalAdjusters.dayOfWeekInMonth(n, dow))

/** Påskdagen enligt den gregorianska kalendern (anonym algoritm). */
fun easterSunday(year: Int): LocalDate {
    val a = year % 19
    val b = year / 100
    val c = year % 100
    val d = b / 4
    val e = b % 4
    val f = (b + 8) / 25
    val g = (b - f + 1) / 3
    val h = (19 * a + b - d - g + 15) % 30
    val i = c / 4
    val k = c % 4
    val l = (32 + 2 * e + 2 * i - h - k) % 7
    val m = (a + 11 * h + 22 * l) / 451
    val month = (h + l - 7 * m + 114) / 31
    val day = ((h + l - 7 * m + 114) % 31) + 1
    return LocalDate.of(year, month, day)
}
