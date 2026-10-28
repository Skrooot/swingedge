package se.dahlander.swingedge.factor

/**
 * Frysta resultat från granskningen "Granskning av Börslabbets strategier" (28 okt 2026), skript i qa/bl.
 * Historiska forskningsresultat, inte portföljresultat.
 */
enum class FactorEvidence(val label: String, val rank: Int) {
    VERIFIED("Oberoende verifierad", 3),
    PROMISING("Lovande men otillräckligt verifierad", 2),
    DOCUMENTED("Endast publikt dokumenterad", 1),
    NONE("Ingen påvisad robust edge", 0),
}

data class FactorResultRow(val label: String, val cagr: Double?, val sharpe: Double?, val maxDd: Double?)

data class FactorStrategyInfo(
    val key: String,
    val title: String,
    val description: String,
    val markets: String,
    val rebalance: String,
    val horizon: String,
    val evidence: FactorEvidence,
    /** Får strategin ge köp- och säljsignaler i appen (som papperhandel)? */
    val signals: Boolean,
    val rows: List<FactorResultRow>,
    val period: String,
    val verdict: String,
    val blocker: String? = null,
    val scanner: FactorStrategy? = null,
    val publicSource: String,
)

val FACTOR_STRATEGIES = listOf(
    FactorStrategyInfo(
        "gtf", "Global trendföljning",
        "Äger de 3 av 9 tillgångsslag som har högst snitt av 3, 6 och 12 månaders avkastning i SEK. Byter bara när en ny tillgång ligger minst 2 procentenheter högre.",
        "Sverige, Europa, USA, Japan, tillväxtmarknader, svenska småbolag, obligationer, korta räntor, guld",
        "Sista handelsdagen varje månad", "Position (innehav i snitt 7 månader)", FactorEvidence.PROMISING, true,
        listOf(
            FactorResultRow("Global trendföljning", 0.120, 0.93, -0.17),
            FactorResultRow("Köp och behåll världsindex", 0.089, 0.61, -0.40),
            FactorResultRow("Lika vikt nio tillgångar", 0.086, 0.80, -0.26),
            FactorResultRow("Testperiod 2014–2026: GTF", 0.103, 0.84, -0.17),
            FactorResultRow("Testperiod 2014–2026: världsindex", 0.138, 1.01, -0.17),
        ),
        "Aug 2002 – sep 2026, Avanza-fonder i SEK efter avgifter",
        "Reproducerad. Halverade nedgångarna, men fördelen i Sharpe mot världsindex försvann efter 2010 (p = 0,92 på testdata). Används som papperhandel.",
        publicSource = "https://borslabbet.se/global-trendfoljning/",
    ),
    FactorStrategyInfo(
        "gtf_ext", "Utökad global trendföljning (forskningsvariant)",
        "Samma regler på 33 tillgångar: de nio originalen plus råvaror, fler räntor, fastigheter, infrastruktur, sektorer och krypto. Äger en tredjedel (topp 11).",
        "33 tillgångsslag (USA-ETF:er som proxy; handel kräver UCITS-produkter)",
        "Månadsvis", "Position", FactorEvidence.PROMISING, false,
        listOf(
            FactorResultRow("Alla 33, topp 11", 0.182, 1.20, -0.17),
            FactorResultRow("Original 9, topp 3", 0.110, 0.91, -0.17),
            FactorResultRow("+ råvaror, topp 3", 0.093, 0.52, -0.35),
        ),
        "Jan 2013 – sep 2026",
        "Bättre bara när portföljen växer med universumet; inte signifikant (p = 0,14) och en av åtta varianter. Råvaror försämrade.",
        blocker = "Inte Börslabbets modell. Flera tillgångar saknar UCITS-produkt med lång historik.",
        publicSource = "https://borslabbet.se/global-trendfoljning/",
    ),
    FactorStrategyInfo(
        "mom", "Sammansatt momentum",
        "Topp 10 aktier efter snittet av 3, 6 och 12 månaders kursutveckling. Börslabbet tar bort bolag med lägst F-score; det filtret saknas här.",
        "Stockholmsbörsen Large och Mid Cap, över 2 miljarder kr, utan finansbolag",
        "Månadsvis med banding (sälj utanför topp 20) eller kvartalsvis", "Swing/position (3–12 månader)", FactorEvidence.PROMISING, false,
        listOf(
            FactorResultRow("Momentum, banding topp 20", 0.234, 0.94, -0.59),
            FactorResultRow("Lika vikt samma universum", 0.131, 0.67, -0.54),
            FactorResultRow("Lägst momentum", 0.048, 0.25, -0.66),
        ),
        "Jan 2006 – sep 2026, dagens Large + Mid Cap (överlevnadsbias), kurser utan utdelningar",
        "Fördel mot lika vikt (p = 0,06) och tydlig i Europa enligt Ken Frenchs data (+7 %/år bland små bolag efter 2010), men universumet har överlevnadsbias.",
        blocker = "Kräver kurser för avnoterade bolag och historiska bokslut (F-score).",
        scanner = FactorStrategy.MOMENTUM, publicSource = "https://borslabbet.se/sammansatt-momentum/",
    ),
    FactorStrategyInfo(
        "value", "Trendande värde",
        "Topp 40 % efter sammansatt värde, sedan översta fjärdedelen efter momentum. Topp 10 aktier.",
        "Stockholmsbörsen och First North över 2 miljarder kr, utan finansbolag", "Årsvis (mars)", "Position (12 månader)",
        FactorEvidence.DOCUMENTED, false,
        listOf(FactorResultRow("Börslabbet 2001–2021 (utan kostnader)", 0.201, 0.90, -0.63), FactorResultRow("Billigaste 30 % i Sverige, mot marknaden 2010–2025", 0.019, null, null)),
        "Börslabbets backtest; oberoende: Ken French Sverige 1975–2025",
        "Värdepremien i Sverige var +9,9 %/år 2000–2009 men +1,9 %/år och inte signifikant efter 2010.",
        blocker = "Historiska bokslut med publiceringsdatum och avnoterade bolag saknas (Börsdata Pro krävs).",
        scanner = FactorStrategy.VALUE, publicSource = "https://borslabbet.se/trendande-varde/",
    ),
    FactorStrategyInfo(
        "quality", "Trendande kvalitet",
        "Topp 40 % efter sammansatt avkastning på kapital (ROE, ROA, ROIC, FCFROE), sedan momentum. Topp 10 aktier.",
        "Stockholmsbörsen och First North över 2 miljarder kr, utan finansbolag", "Årsvis (mars)", "Position (12 månader)",
        FactorEvidence.DOCUMENTED, false,
        listOf(FactorResultRow("Börslabbet 2001–2021 (utan kostnader)", 0.250, 1.10, -0.57), FactorResultRow("Lönsamma små bolag i Europa, mot marknaden 2010–2026", 0.030, null, null)),
        "Börslabbets backtest; oberoende: Ken French Europa 1990–2026",
        "Lönsamhetspremien finns bland små bolag i Europa (t = 2,0) men inte bland stora efter 2010.",
        blocker = "Historiska bokslut med publiceringsdatum saknas.",
        scanner = FactorStrategy.QUALITY, publicSource = "https://borslabbet.se/trendande-kvalitet/",
    ),
    FactorStrategyInfo(
        "dividend", "Trendande utdelning",
        "Topp 40 % efter direktavkastning, sedan momentum, som ska undvika utdelningsfällor. Topp 10 aktier.",
        "Stockholmsbörsen och First North över 2 miljarder kr, utan finansbolag", "Årsvis (mars)", "Position (12 månader)",
        FactorEvidence.DOCUMENTED, false,
        listOf(FactorResultRow("Börslabbet 2001–2021 (utan kostnader)", 0.217, 1.05, -0.52), FactorResultRow("Hög direktavkastning i Sverige, mot marknaden 2010–2025", 0.010, null, null)),
        "Börslabbets backtest; oberoende: Ken French Sverige 1975–2025",
        "Hög direktavkastning gav +11,8 %/år 2000–2009 men +1,0 %/år efter 2010 (t = 0,5).",
        blocker = "Historiska utdelningar, bokslut och avnoterade bolag saknas.",
        scanner = FactorStrategy.DIVIDEND, publicSource = "https://borslabbet.se/trendande-utdelning/",
    ),
)

