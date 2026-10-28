# SwingEdge Quant – forsknings- och backtestingmotor

Motorn söker brett efter handelsstrategier och försöker sedan falsifiera dem. Den kan genomföra
reglerna med köpbara produkter via Avanza. Strategin i Android-appen ändras aldrig automatiskt. En ny
strategi kräver godkänd validering, godkänd holdout, paper trading och ett manuellt godkännande.

## Moduler

| Fil | Innehåll |
|---|---|
| `config.py` | Sökvägar, låsta perioder, Avanza-kostnader, forskningsbudget och förregistrerade godkännandekrav |
| `fetch.py` | Hämtar OHLCV från Yahoo, justerat för utdelning och split, med utdelnings- och splithändelser |
| `data.py` | Universum med Avanza-köpbarhet, datakontroll, kalender, omräkning till SEK och paneler |
| `strategies.py` | Indikatorcache, entry, exit, filter, rangordning, positionsstorlek, schema, sökutrymme och generator |
| `fast.py` | Snabb vektoriserad motor: målvikter blir dagsavkastning i SEK efter kostnader |
| `exact.py` | Exakt händelsestyrd motor: ordrar, fyllnader, hela andelar, kontantkonto, courtage med minimum, valuta, spread, slippage, utdelningar och splittar |
| `search.py` | Parallell utvärdering, slumpsökning, successive halving och evolutionär lokal sökning |
| `validate.py` | Walk-forward, parametergrannar, kostnadsstress, delperioder, regimer, koncentration, korsmarknad och krav |
| `stats.py` | Stationär bootstrap, Monte Carlo, Deflated Sharpe, PBO (CSCV), Hansens SPA och Whites RC, Benjamini–Hochberg |
| `registry.py` | Experiment Registry i SQLite: alla experiment inklusive förkastade, data- och kodversion, holdout-lås |
| `champion.py` | Champion och Challenger: förslag, godkännande med namn, versionshistorik, återställning, appens nuvarande strategi |
| `production.py` | Dagens målvikter och åtgärder för den godkända strategin, export till `api/production.json` |
| `run_research.py` | Hela forskningsomgången |
| `report.py` | Läsbar rapport från en omgång |
| `tests/` | 24 automatiska tester av motorer, kostnader, tidsregler, look-ahead, överanpassning och register |

## Tidsregel och kostnader

**Tidsregel:**
- **Beslut:** vid stängning dag t, med data till och med dag t.
- **Exekvering:** vid stängningen på produktens nästa färska handelsdag. En helgdag på börsen skjuter upp affären.
- **Look-ahead:** testerna kontrollerar att målvikterna inte ändras när framtida data ändras, och att en strategi som "vet" morgondagen inte tjänar på det.

**Kostnader**, samma courtageklass som appen:
- **Stockholmsbörsen:** 0,069 %, minst 69 kr.
- **Xetra:** 0,089 %, minst 8 EUR.
- **USA:** 0,089 %, minst 1 USD.
- **Valutaväxling:** 0,25 % i annan valuta än SEK.
- **Spread och slippage:** halva spreaden från Avanzas produktdata, annars ett standardvärde per produkttyp, plus 0,05 % slippage.
- **Kapital:** 100 000 kr, så minimicourtaget slår igenom på små positioner.
- **Kostnadsstress:** testas med 2 och 3 gånger kostnaderna.

## Data och universum

- **Avanza-produkter:** 71 marknader från `research/archive/edge-engine/mapping.json`, med produkter verifierade mot Avanza 28 okt 2026. Signalen räknas på den underliggande marknaden. Avkastningen räknas på Avanza-produkten i SEK. Före produktens start används den underliggande marknaden i SEK minus en uppskattad avgift, och de dagarna markeras som proxy.
- **Aktier:** svenska aktier (301) och 50 stora amerikanska aktier. **De har överlevnadsbias**, eftersom de är dagens bolag, så de kan testas men aldrig godkännas.
- **Bara korsmarknadsvalidering, går inte att köpa:** valutor och 15 mindre kryptovalutor.
- **Datakontroll:**
  - Dubbletter och icke-positiva kurser tas bort.
  - Spikar som vänder direkt tas bort.
  - Långa platta perioder flaggas.
  - Orimliga dagsavkastningar ersätts med den underliggande marknaden. Det gäller till exempel Yahoos skalbyten i vissa ETC-serier.
  - Signalhopp tas bort.
  - Instrument med fler än fem fel stängs av.

## Process och krav (förregistrerade i `config.py`)

1. **Bred screening:** utvecklingsdata 2000–2007.
2. **Fördjupning:** utvecklingsdata 2000–2015.
3. **Evolutionär förfining:** utvecklingsdata.
4. **Finalister låses:** högst en per universum och entry-typ, och högst tre per universum.
5. **Robusthet på utvecklingsdata:**
   - walk-forward med fem fönster 2006–2015
   - parametergrannar och kostnadsstress
   - delperioder och korsmarknad
   - Deflated Sharpe, med alla försök i omgången
   - PBO för de 50 bästa
   - Monte Carlo
6. **Validering 2016–2020:** första gången perioden används. Jämförelse med likaviktat köp och behåll av samma universum, bootstrap-p, FDR över finalisterna, SPA-test och kontroll mot den exakta motorn.
7. **Champion:** högst validerings-Sharpe bland de finalister som klarar **alla** krav. Den fryses i registret.
8. **Holdout 2021 – okt 2026:** körs **en gång**, bara för den frysta kandidaten. Registret vägrar en andra körning. Om ingen kandidat klarar valideringen körs holdout inte alls och sparas till en senare omgång. Resultatet blir då **NO VERIFIED EDGE FOUND**.

**Viktigt om holdout:** perioden 2021–2026 är orörd för den här motorns sökning, men inte för projektet som helhet. Appens nuvarande strategi valdes 2026 med data till och med 2026. Ett holdout-resultat ska därför läsas som ett test av motorns urvalsprocess, inte som helt opåverkad data.

## Köra

```bash
cd research
python -m pip install --user numpy
python -E -m quant.fetch                              # hämtar data till SWINGEDGE_DATA (standard qa/quant/data)
python -E -m unittest discover -s quant/tests -t .    # motorns tester
python -E -m quant.run_research --round R1            # forskningsomgång (återupptas om den avbryts)
python -E -m quant.report R1                          # experiments/R1_report.md
python -E -m quant.production                         # api/production.json för den godkända strategin
```

`-E` stänger av miljövariabler men inte användarens site-packages, där NumPy ligger. Antal processer, budget
och tidsgräns styrs i `config.py`. Seed 20261029 ger samma kandidater varje gång. En ny omgång med andra
perioder eller data får ett nytt omgångs-id. Registret vägrar att återanvända ett id med en annan dataversion.

## Champion och Challenger

- **`production/champion.json`:** den strategi som appen kör. Version 1 är appens nuvarande "SwingEdge med guld".
- **Förslag:** en kandidat som klarar validering och holdout skrivs som förslag till `production/challengers/<omgång>.json`. Det ändrar ingenting i produktionen.
- **Godkännande:** `champion.approve(omgång, godkänd_av, månader_paper_trading)` kräver ett namn och minst sex månaders paper trading. Den gamla versionen sparas i `production/history/`, och `champion.rollback(version)` återställer den.
