package se.dahlander.swingedge.core

/**
 * Frysta resultat från rapporten "Swingstrategier via Avanza" (27 okt 2026). Historiska forskningsresultat,
 * inte portföljresultat. Siffrorna kommer från results.json, results2.json och study_lc.py i studien.
 */
data class ResearchRow(
    val label: String, val cagr: Double, val sharpe: Double, val maxDd: Double, val sortino: Double?,
    val tradesPerYear: Double?, val avgHoldDays: Double?, val exposure: Double?,
)

data class ResearchResult(
    val strategy: StrategyId,
    val title: String,
    val period: String,
    val source: String,
    val strategyRow: ResearchRow,
    val buyHold: ResearchRow,
    val extra: List<ResearchRow> = emptyList(),
    val verdict: String,
)

val RESEARCH = listOf(
    ResearchResult(
        StrategyId.BTC_TREND, "Bitcoin Trend, SMA150 på Bitcoin Tracker One",
        "Test jan 2022 – okt 2026 (parametern vald på 2014–2019)",
        "Yahoo Finance: BITCOIN-XBT.ST och BTC-USD. 0,40 % kostnad per affärssida. Verklig produkt i SEK.",
        ResearchRow("Trendregel SMA150", 0.316, 0.95, -0.338, 1.67, 4.2, 39.0, 0.52),
        ResearchRow("Köp och behåll", 0.120, 0.48, -0.666, 0.71, null, null, 1.0),
        listOf(
            ResearchRow("Samma regel, SMA100", 0.226, 0.74, -0.460, 1.24, 6.0, null, 0.50),
            ResearchRow("Samma regel, SMA200", 0.218, 0.72, -0.445, 1.16, 3.1, null, 0.52),
        ),
        "Starkast stöd i studien. Bootstrap: 81 % sannolikhet att Sharpe är högre än köp och behåll, inte 95 %.",
    ),
    ResearchResult(
        StrategyId.EQUAL_WEIGHT, "Lika vikt: XACT OMXS30, SXR8, Bitcoin Tracker One och Xetra-Gold",
        "Efterhandstest jan 2021 – okt 2026",
        "Yahoo Finance, produkter i SEK. XACT-luckor 2013–2019 fyllda med OMXS30-indexets dagsrörelser.",
        ResearchRow("Lika vikt med guld (används i appen)", 0.220, 1.13, -0.247, null, null, null, 1.0),
        ResearchRow("Köp och behåll Bitcoin Tracker One", 0.220, 0.63, -0.749, 0.95, null, null, 1.0),
        listOf(
            ResearchRow("Utan guld (rapportens version) 2021–2026", 0.222, 0.94, -0.355, null, null, null, 1.0),
            ResearchRow("Utan guld, rapportens test jan 2021 – okt 2026", 0.215, 0.91, -0.362, 1.35, null, null, 1.0),
        ),
        "Guld sänkte största nedgången från −36 % till −25 % med samma avkastning. Valt bland sex varianter, så osäkrare än rapportens resultat.",
    ),
    ResearchResult(
        StrategyId.SP500_TREND, "S&P 500 Trend, SMA200 med månadskontroll",
        "Test jan 2015 – okt 2026 (index som proxy för SXR8)",
        "Yahoo Finance: ^GSPC utan utdelning. 0,40 % kostnad per affärssida.",
        ResearchRow("Trendregel SMA200 (används i appen)", 0.063, 0.57, -0.278, 0.77, 0.9, 206.0, 0.82),
        ResearchRow("Köp och behåll", 0.118, 0.73, -0.339, 1.02, null, null, 1.0),
        listOf(
            ResearchRow("SMA250, vald på träningsdata i studien", 0.072, 0.63, -0.245, 0.85, 0.8, 228.0, 0.82),
            ResearchRow("Walk-forward 1980–2026", 0.077, 0.65, -0.332, null, null, null, null),
            ResearchRow("Köp och behåll 1980–2026", 0.096, 0.60, -0.568, null, null, null, 1.0),
        ),
        "Kraschskydd, inte högre avkastning: halverade största fallet men gav lägre avkastning i tjurmarknader.",
    ),
)

/**
 * Den enda strategin i appen, fryst 28 okt 2026 efter jämförelsen i research/archive/borslabbet/study_winner.py.
 * Reglerna finns i Strategies.kt, Portfolio.kt och Analyzer.kt; den här texten beskriver dem för gränssnittet.
 */
object Strategy {
    const val NAME = "SwingEdge med guld"
    val RULES = listOf(
        "Bitcoin Trend, 20 %: äg Bitcoin Tracker One när BTC-USD:s dagsstängning (00:00 UTC) är över sitt 150-dagars glidande medelvärde, annars kontanter. Exakt på medelvärdet = kontanter.",
        "Lika vikt, 40 %: 10 % vardera i XACT OMXS30, iShares Core S&P 500 (SXR8), Bitcoin Tracker One och Xetra-Gold. Ombalansering efter Stockholmsbörsens sista handelsdag i månaden, när en vikt avviker mer än 2 procentenheter.",
        "S&P 500 Trend, 40 %: äg SXR8 när S&P 500-indexet stänger över sitt 200-dagars glidande medelvärde på månadens sista handelsdag, annars kontanter. Beslutet ändras inte mellan månadssluten.",
        "Exekvering: signalen räknas på färdiga dagsstaplar och handlas tidigast vid nästa börsöppning för produkten (Stockholm för XBT och XACT, Xetra för SXR8 och guld). Helgsignaler för Bitcoin väntar till måndag.",
        "Data äldre än en handelsdag ger inga nya signaler; äldre än fem dagar stoppar signalerna.",
    )
    /** Hela portföljen, månadsdata i SEK efter kostnader (study_winner.py och study_combo.py). */
    val RESULTS = listOf(
        ResearchRow("SwingEdge med guld, jun 2015 – sep 2026", 0.325, 1.31, -0.19, null, null, null, null),
        ResearchRow("Samma, osedda data jan 2020 – sep 2026", 0.245, 1.09, -0.19, null, null, null, null),
        ResearchRow("Världsindex (köp och behåll), jun 2015 – sep 2026", 0.119, 0.84, -0.17, null, null, null, null),
        ResearchRow("Köp och behåll BTC + ETH, jan 2020 – sep 2026", 0.561, 0.92, -0.71, null, null, null, null),
    )
    val WEAKNESSES = listOf(
        "Ingen del är statistiskt säkerställd. Bitcoin Trend har 81 % sannolikhet i bootstrap, inte 95 %.",
        "Avkastningen kommer till stor del från Bitcoin (ungefär en tredjedel av portföljen när trenden är positiv). Bitcoin Trend ensam föll −64 % 2017–2019.",
        "S&P 500 Trend gav kraftigt skydd men lägre avkastning än köp och behåll; den är ett kraschskydd, inte en edge.",
        "Guld lades till efter rapporten och valdes bland sex varianter under en stark period för guld.",
        "Perioden 2015–2026 är kort och präglad av Bitcoins uppgång. Forward test pågår från okt 2026.",
    )
}
