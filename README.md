# SwingEdge

Android-app i Kotlin och Jetpack Compose som dagligen räknar strategierna från rapporten
"Swingstrategier via Avanza" (27 okt 2026) och visar vad du behöver göra. Allt körs på telefonen:
ingen server, inga API-nycklar. Appen lägger inga ordrar; ordrar läggs manuellt i Avanza.

## Strategierna (frysta regler från signals.py)

| Del | Standardvikt | Regel | Instrument |
| --- | --- | --- | --- |
| Bitcoin Trend | 20 % | Investerad när BTC-USD:s senaste färdiga dagsstängning är **över** SMA150. Exakt lika = kontanter (som `c[-1] > m`). Kontroll dagligen. | Bitcoin Tracker One, SE0007126024 |
| Lika vikt | 40 % | En tredjedel var. Ombalansering vid Stockholmsbörsens sista handelsdag i månaden, handel nästa handelsdag, tolerans 2 procentenheter. | XACT OMXS30, SXR8, Bitcoin Tracker One |
| S&P 500 Trend | 40 % | Beslut vid NYSE:s sista handelsdag i månaden: investerad om S&P 500 > SMA200. Oförändrat mellan kontrollerna. | SXR8, IE00B5BMR087 |

En avstängd trendstrategi ger kontanter. Vikter för samma instrument summeras, och det blir en order per instrument.

## Tidsregler och datakontroll

- BTC-dagsstapeln för datum D är färdig 00:00 UTC dag D+1. Ofärdiga staplar används aldrig.
- S&P 500-stapeln är färdig 15 minuter efter NYSE:s stängning (16:00 New York).
- Signaler handlas tidigast vid nästa öppning för produkten (Stockholmsbörsen eller Xetra), med svenska, tyska och amerikanska helgdagar.
- Data som är en eller flera dagar för gamla ger inga nya signaler; tidigare läge behålls. Äldre än fem dagar stoppar signalerna helt (samma regel som signals.py).
- En misslyckad hämtning skapar aldrig en köp- eller säljsignal. Varje körning loggas med indata och resultat (Signaler → Beräkningslogg).

## Avvikelser från signals.py, med motivering

- **S&P 500 vid första körningen:** signals.py tar dagens läge vid första körningen. Appen använder alltid senaste färdiga månadsslut, vilket är vad studiens backtest gjorde.
- **Lika vikt** ersätter rotationen, enligt den rättade rapporten (rotation gav samma Sharpe, 0,92 mot 0,91).
- **Månadsslut** bestäms med börskalendrar i stället för "nästa vardag".

## Funktioner

Översikt med "Vad behöver jag göra idag?", tre strategikort och målportfölj · signalhistorik med status (aktiv, väntar, historisk, ogiltig) och Avanza-länkar · portfölj med köp, sälj, insättning och uttag, genomsnittsmetoden för anskaffningsvärde, realiserat och orealiserat resultat, utvecklingsgraf · papperskonto med virtuellt kapital · forskningsresultat från rapporten och nya backtester på aktuella kurser, redovisade separat · instrumentvy med produkt och signalkälla åtskilda · notiser via WorkManager ungefär varje timme.

## Data

Yahoo Finance chart-API (BTC-USD, ^GSPC, BITCOIN-XBT.ST, XACT-OMXS30.ST, SXR8.DE, EURSEK=X) och Binance som reserv för BTC. Båda är öppna utan nyckel men utan formellt avtal för privat bruk; om Yahoo ändrar sitt API slutar hämtningen fungera och appen visar datafel i stället för signaler.

## Bygga och testa

```bash
export JAVA_HOME=/c/Users/fredrik/android-build/jdk
./gradlew testDebugUnitTest   # 23 tester, bl.a. jämförelse mot Python-reglerna på 4 400 BTC-dagar och 250 månadsslut
./gradlew assembleRelease     # app/build/outputs/apk/release/app-release.apk
```

Testfixturen `app/src/test/resources/parity.json` är exporterad från `qa/swing/strategies.py`.

## Begränsningar

- Release-APK:n är signerad med debug-nyckeln, för egen installation.
- Extraordinära börsstängningar (t.ex. sorgedagar i USA) finns inte i kalendrarna; de fångas av datakontrollen.
- Android kan skjuta upp bakgrundskontrollen vid batterisparläge.
- Nya backtester i appen handlar på stängningen dagen efter signalen (studien använde öppningen), så siffrorna skiljer något.
- Inget i appen är ett köp- eller säljråd.
