package se.dahlander.swingedge.core

/** Handelsprodukter, verifierade som köp- och säljbara på Avanza 27 okt 2026 (rapporten "Swingstrategier via Avanza"). */
enum class Instrument(
    val displayName: String,
    val shortName: String,
    val ticker: String,
    val isin: String,
    val exchange: Exchange,
    val currency: String,
    val underlying: String,
    val yahoo: String,
    val avanzaUrl: String,
) {
    XBT(
        "XBT Provider Bitcoin Tracker One - SEK", "Bitcoin Tracker One", "BITCOIN XBT", "SE0007126024",
        Exchange.XSTO, "SEK", "Bitcoin (BTC), certifikat från CoinShares XBT Provider. Följer BTC i SEK med cirka 2,5 % årsavgift.",
        "BITCOIN-XBT.ST",
        "https://www.avanza.se/borshandlade-produkter/certifikat-torg/om-certifikatet.html/563966/xbt-provider-bitcoin-tracker-one---sek",
    ),
    XACT(
        "XACT OMXS30 ESG (UCITS ETF)", "XACT OMXS30", "XACT OMXS30", "SE0000693293",
        Exchange.XSTO, "SEK", "OMX Stockholm 30 ESG Responsible Index, fysiskt replikerad indexfond.",
        "XACT-OMXS30.ST",
        "https://www.avanza.se/borshandlade-produkter/etf-torg/om-fonden.html/5510/xact-omxs30-esg-ucits-etf",
    ),
    SXR8(
        "iShares Core S&P 500 UCITS ETF USD (Acc)", "iShares Core S&P 500", "SXR8", "IE00B5BMR087",
        Exchange.XETR, "EUR", "S&P 500, ackumulerande indexfond. Handlas i EUR på Xetra; Avanza växlar SEK med 0,25 %.",
        "SXR8.DE",
        "https://www.avanza.se/borshandlade-produkter/etf-torg/om-fonden.html/1063851/ishares-core-s-p-500-ucits-etf-usd-acc",
    ),
    GOLD(
        "Xetra-Gold ETC", "Xetra-Gold", "4GLD", "DE000A0S9GB0",
        Exchange.XETR, "EUR", "Fysiskt guld, ETC från Deutsche Börse Commodities. Handlas i EUR på Xetra; Avanza växlar SEK med 0,25 %.",
        "4GLD.DE",
        "https://www.avanza.se/borshandlade-produkter/certifikat-torg/om-certifikatet.html/1077331/xetra-gold-etc",
    ),
    AVWC(
        "Avantis Global Equity UCITS ETF", "Avantis Global Equity", "AVWC", "IE000RJECXS5",
        Exchange.XETR, "EUR", "Globala aktier, bred portfölj med lutning mot billiga och lönsamma bolag. Handlas i EUR på Xetra; Avanza växlar SEK med 0,25 %.",
        "AVWC.DE",
        "https://www.avanza.se/borshandlade-produkter/etf-torg/om-fonden.html/1858742/avantis-global-equity-ucits-etf",
    ),
    AVWS(
        "Avantis Global Small Cap Value UCITS ETF", "Avantis Global Small Cap Value", "AVWS", "IE0003R87OG3",
        Exchange.XETR, "EUR", "Globala småbolag med lutning mot värde och lönsamhet. Handlas i EUR på Xetra; Avanza växlar SEK med 0,25 %.",
        "AVWS.DE",
        "https://www.avanza.se/borshandlade-produkter/etf-torg/om-fonden.html/1858741/avantis-global-small-cap-value-ucits-etf",
    ),
    AVEM(
        "Avantis Emerging Markets Equity UCITS ETF", "Avantis Emerging Markets", "AVEM", "IE000K975W13",
        Exchange.XETR, "EUR", "Tillväxtmarknader, bred portfölj med lutning mot billiga och lönsamma bolag. Handlas i EUR på Xetra; Avanza växlar SEK med 0,25 %.",
        "AVEM.DE",
        "https://www.avanza.se/borshandlade-produkter/etf-torg/om-fonden.html/1918246/avantis-emerging-markets-equity-ucits-etf",
    );
}

/** Lika vikt enligt rapporten. Guld är ett tillval som testades efter rapporten (study3.py, 28 okt 2026). */
val EW_BASE = listOf(Instrument.XACT, Instrument.SXR8, Instrument.XBT)
fun equalWeightInstruments(includeGold: Boolean) = if (includeGold) EW_BASE + Instrument.GOLD else EW_BASE

/**
 * Avantis-kärna: köp och behåll av tre Avantis-ETF:er i lika delar, ombalanseras vid månadsslut som lika vikt.
 * Tillval efter rapporten (study_avantis.py, okt 2019 – sep 2026 med amerikanska Avantis-fonder som proxy).
 */
val AVANTIS_CORE = listOf(Instrument.AVWC, Instrument.AVWS, Instrument.AVEM)

/** Vikter med Avantis-kärnan: SwingEdges hinkar skalas ned och kärnan får [avantis] av portföljen. */
fun effectiveSleeves(base: Map<StrategyId, Double>, avantis: Double): Map<StrategyId, Double> =
    if (avantis <= 0.0) base else base.mapValues { it.value * (1 - avantis) } + (StrategyId.AVANTIS_CORE to avantis)

/** Signalkällor. Priset på signalkällan är aldrig priset på produkten. */
enum class SignalSource(val displayName: String, val yahoo: String, val currency: String) {
    BTC_USD("Bitcoin (BTC-USD)", "BTC-USD", "USD"),
    SP500("S&P 500-index", "^GSPC", "USD"),
}

enum class StrategyId(val displayName: String, val shortName: String) {
    BTC_TREND("Bitcoin Trend", "Bitcoin Trend"),
    EQUAL_WEIGHT("Lika vikt", "Lika vikt"),
    SP500_TREND("S&P 500 Trend", "S&P 500 Trend"),
    AVANTIS_CORE("Avantis-kärna", "Avantis"),
}

/** Testade standardvikter. Andra vikter är avvikelser från den testade modellen och märks så i appen. */
val DEFAULT_SLEEVES: Map<StrategyId, Double> = mapOf(
    StrategyId.BTC_TREND to 0.20,
    StrategyId.EQUAL_WEIGHT to 0.40,
    StrategyId.SP500_TREND to 0.40,
)
