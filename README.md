# SwingEdge

Android-app i Kotlin och Jetpack Compose för en enda fryst strategi, **SwingEdge med guld**. Appen räknar
signalerna på telefonen varje timme och visar vad du behöver köpa, sälja eller bevaka idag. Den har ingen server
och inga API-nycklar och lägger inga ordrar. Affärer görs manuellt i Avanza och registreras i appen.

Ladda ner: [SwingEdge.apk](https://github.com/Skrooot/swingedge/raw/main/SwingEdge.apk) (version 2.0).
Inget i appen är ett köp- eller säljråd.

## Strategin (fryst 28 okt 2026)

| Del | Vikt | Regel | Produkt (Avanza) |
| --- | --- | --- | --- |
| Bitcoin Trend | 20 % | Investerad när BTC-USD:s senaste färdiga dagsstängning (00:00 UTC) är **över** SMA150, annars kontanter. Exakt lika = kontanter. | Bitcoin Tracker One, SE0007126024, First North Stockholm, SEK |
| Lika vikt | 40 % | 10 % vardera. Ombalansering efter Stockholmsbörsens sista handelsdag i månaden, när en vikt avviker mer än 2 procentenheter. | XACT OMXS30 (SE0000693293), SXR8 (IE00B5BMR087), Bitcoin Tracker One, Xetra-Gold (DE000A0S9GB0) |
| S&P 500 Trend | 40 % | Beslut på NYSE:s sista handelsdag i månaden: investerad om S&P 500 > SMA200, annars kontanter. Oförändrat mellan besluten. | SXR8, Xetra, EUR |

- **Målvikter med båda trenderna positiva:** SXR8 50 %, Bitcoin Tracker One 30 %, XACT 10 %, guld 10 %.
- **Exekvering:** handel tidigast vid nästa öppning för produkten, alltså Stockholm för XBT och XACT och Xetra för SXR8 och guld. Svenska, tyska och amerikanska helgdagar räknas med. Bitcoin-signaler som kommer på helgen väntar till måndag.
- **Datakontroll:** data som är en dag gammal eller mer ger inga nya signaler och visas som föråldrade. Data äldre än fem dagar stoppar signalerna helt.
- **Reglerna ligger på ett ställe:** `core/Strategies.kt` (indikatorer), `core/Portfolio.kt` (vikter och ordrar) och `core/Analyzer.kt` (signaler och datakontroll). Vikterna kan inte ändras i appen. En ändring kräver en ny validering.

### Varför den här strategin

Strategin valdes 28 oktober 2026 bland alla som fanns i projektet, se `research/archive/borslabbet/study_winner.py`.
Tabellen visar samma osedda månader, jan 2020 – sep 2026, efter kostnader:

| Kandidat | Avkastning/år | Sharpe | Största nedgång |
| --- | --- | --- | --- |
| Kryptotrend SMA150 (BTC + ETH) | 48,0 % | 0,91 | −42 % (−50 % dagsvis) |
| **SwingEdge med guld** | **24,5 %** | **1,09** | **−19 %** |
| Global trendföljning (Börslabbet) | 10,0 % | 0,69 | −17 % |
| Köp och behåll BTC + ETH | 56,1 % | 0,92 | −71 % |

Kryptotrend hade högst avkastning, men vinsten kom från några få stora trender. Utan de tre bästa affärerna per
tillgång sjönk avkastningen till 3 % per år, och största nedgången var −50 %. SwingEdge med guld valdes för sin
lägre risk och höga Sharpe. Trend på SMA150 gav ingen fördel på 67 av 69 testade marknader (bara på Bitcoin och
Ether). Momentum och faktorstrategier kunde inte testas utan överlevnadsbias.

Hela portföljen jun 2015 – sep 2026: **32,5 % per år, Sharpe 1,31, största nedgång −19 %**. Världsindex gav
11,9 %, 0,84 och −17 % under samma period.

### Kända svagheter

- **Inget är statistiskt säkerställt.** Bitcoin Trend har 81 % sannolikhet i bootstrap, inte 95 %.
- **Avkastningen kommer till stor del från Bitcoin.** Bitcoin Trend ensam föll −64 % på produkten 2017–2019.
- **S&P 500 Trend** är ett kraschskydd. Den har gett lägre avkastning än köp och behåll.
- **Guldet lades till efter rapporten.** Det valdes bland sex varianter under en stark period för guld.
- **Forward-testet började i oktober 2026.** Ett meningsfullt test tar flera år.

## Appen

- **Översikt:** om strategin är aktiv, trendlägen, antal köp- och säljorder, senaste och nästa analys, "Vad behöver jag göra idag?" och portföljvärde.
- **Möjligheter:** de fyra produkterna med åtgärderna Köp, Behåll, Sälj eller Avvakta. För varje produkt visas kurs, målvikt och nuvarande vikt, order med antal andelar och kostnad, köpzon, indikatorer, exakt exitregel, historik och Avanza-länk. Produkter med en åtgärd visas först.
- **Portfölj:** innehav, värde, total avkastning, exponering mot målet, ordrar och kontantandel. Här registrerar du köp, sälj, insättningar och uttag med genomsnittsmetoden, och kan använda ett papperskonto.
- **Strategin** (från Översikt): regler, resultat, svagheter, signallogg och beräkningslogg, forward test och nya backtester på aktuella kurser.
- **Notiser:** WorkManager kontrollerar ungefär en gång i timmen och skickar notis vid köp, sälj, ombalansering och datafel, utan dubbletter.

### Borttaget i version 2.0

Allt finns kvar i Git-taggen `v1.4.1-full` och i grenen `archive/full-platform`.

- **Edge Discovery och Global Opportunities:** 8 strategifamiljer på 71 marknader, notiser och forskningshämtning från GitHub.
- **Factor & Global Allocation:** Global trendföljning, Factor Scanner, strategijämförelse och aktieuniversum.
- **Tillval och inställningar:** Avantis-kärnan, guld som tillval (nu en fast del), viktreglage och notisinställningar för de borttagna delarna.
- **Skärmar:** instrumentvyn (ersatt av Möjligheter), Global-fliken och Analys-fliken (nu Strategin).
- **Tester:** för de borttagna modulerna (Edge-paritet, Global trendföljning, faktorrangordning och Avantis).
- **Cachefiler på telefonen:** för de borttagna funktionerna. De raderas vid första starten, medan portföljer, affärer och signaler behålls.

Forskningen är flyttad till `research/archive/` för spårbarhet.

## Data

Yahoo Finance chart-API (BTC-USD, ^GSPC, BITCOIN-XBT.ST, XACT-OMXS30.ST, SXR8.DE, 4GLD.DE, EURSEK=X), med Binance som
reserv för BTC. Båda är öppna utan nyckel men saknar formellt avtal. Om Yahoo ändrar sitt API visar appen datafel i
stället för signaler.

## Bygga, testa och installera

```bash
export JAVA_HOME=/c/Users/fredrik/android-build/jdk
./gradlew testDebugUnitTest assembleRelease
```

Testerna (32 st) jämför bland annat reglerna med Python-originalet på över 4 000 BTC-dagar och över 230 S&P-månadsslut,
och appens backtest med en oberoende Python-referens (`research/archive/borslabbet/ref_backtest.py`). APK:n hamnar i
`app/build/outputs/apk/release/app-release.apk`. Installera den genom att öppna filen på telefonen och tillåta
installation från okänd källa. Den är signerad med debug-nyckeln, för egen installation.
