# Forskningsomgång R1

Dataversion `722dc502f9be00c9`. Perioder: utveckling 2000-01-03 – 2015-12-31, validering 2016-01-01 – 2020-12-31, holdout 2021-01-01 – 2026-10-27.

## Resultat: **NO VERIFIED EDGE FOUND**

Ingen finalist klarade valideringskraven. Holdout-perioden har inte använts och sparas till en senare omgång.

## Sökning

- Instrument: 434 (411 köpbara via Avanza), per grupp {'crypto_x': 15, 'etp': 63, 'fx': 5, 'se_stock': 301, 'us_stock': 50}. Registrerade datafel: 1601.
- Unika strategier testade: **6511** (screening 6000, varav giltiga 500; fördjupning 500; förfiningspool 910).
- Utvecklingsperioden har cirka 192 månader. Antalet testade hypoteser är alltså mångdubbelt fler än antalet oberoende observationer; därför används Deflated Sharpe, PBO, SPA och FDR.
- PBO (CSCV) för de 50 bästa på utvecklingsdata: **0,88**.
- SPA-test över finalisterna i valideringen mot respektive jämförelseindex: p = 0,572 (Whites Reality Check p = 0,530).

## Finalister (låsta före validering)

| Strategi | Utv. Sharpe | WF Sharpe | DSR | Grannar | Val. Sharpe | Jämf. | Val. nedgång | Underkänd på |
|---|---|---|---|---|---|---|---|---|
| se_stocks: entry rsi_pullback(n=2, thr=30); filter er_above(L=100, thr=0.2); max 3 positioner rangordnat mom252; slot; beslut monthly | 1,33 | 1,23 | 0,03 | 100 % | 0,62 | 1,09 | -48 % | största nedgång i validering -48% sämre än -35%; slår inte likaviktat köp och behåll på Sharpe i validering; Deflated Sharpe 0.03 < 0.95; PBO 0.88 > 0.3; klarar inte FDR (q 1.00); universumet har överlevnadsbias (dagens bolag); kan inte verifieras |
| se_stocks: entry donchian(n=200); exit ma_below(n=100); filter vol_below(q=0.5); max 10 positioner rangordnat mom252; slot; beslut monthly | 1,36 | 0,90 | 0,06 | 100 % | 0,99 | 1,09 | -45 % | största nedgång i validering -45% sämre än -35%; slår inte likaviktat köp och behåll på Sharpe i validering; Deflated Sharpe 0.06 < 0.95; PBO 0.88 > 0.3; klarar inte FDR (q 1.00); universumet har överlevnadsbias (dagens bolag); kan inte verifieras |
| se_stocks: entry high52(prox=0.1); exit atr_trail(k=6.0); filter er_above(L=50, thr=0.2); max 10 positioner rangordnat mom252; slot; beslut monthly | 1,33 | 0,78 | 0,04 | 100 % | 0,90 | 1,09 | -30 % | slår inte likaviktat köp och behåll på Sharpe i validering; Deflated Sharpe 0.04 < 0.95; PBO 0.88 > 0.3; klarar inte FDR (q 1.00); universumet har överlevnadsbias (dagens bolag); kan inte verifieras |
| us_stocks: entry high52(prox=0.1); exit donchian_low(n=55); filter market_trend(n=200); max 10 positioner rangordnat mom252; slot; beslut monthly | 0,80 | 0,79 | 0,00 | 100 % | 1,10 | 1,04 | -19 % | Deflated Sharpe 0.00 < 0.95; PBO 0.88 > 0.3; klarar inte FDR (q 1.00); universumet har överlevnadsbias (dagens bolag); kan inte verifieras |
| us_stocks: entry donchian(n=100); exit mom_neg(L=126); filter market_trend(n=200); max 10 positioner rangordnat none; slot; beslut monthly | 0,75 | 0,75 | 0,00 | 100 % | 1,14 | 1,04 | -21 % | Deflated Sharpe 0.00 < 0.95; PBO 0.88 > 0.3; klarar inte FDR (q 1.00); universumet har överlevnadsbias (dagens bolag); kan inte verifieras |
| us_stocks: entry rsi_pullback(n=2, thr=10); exit donchian_low(n=20); filter market_trend(n=200); max 3 positioner rangordnat mom126; slot; beslut monthly | 0,81 | 0,45 | 0,00 | 100 % | 1,13 | 1,04 | -28 % | Deflated Sharpe 0.00 < 0.95; PBO 0.88 > 0.3; klarar inte FDR (q 1.00); universumet har överlevnadsbias (dagens bolag); kan inte verifieras |
| etp_core: entry high52(prox=0.05); filter vol_below(q=0.8); alla positioner; slot; beslut monthly | 0,36 | 0,28 | 0,00 | 75 % | 0,32 | 1,40 | -14 % | validerings-Sharpe 0.32 < 0.5; slår inte likaviktat köp och behåll på Sharpe i validering; walk-forward-Sharpe 0.28 < 0.3; Deflated Sharpe 0.00 < 0.95; PBO 0.88 > 0.3; klarar inte FDR (q 1.00) |
| etp_core: entry rsi_pullback(n=3, thr=10); exit mom_neg(L=63); filter er_above(L=100, thr=0.2); max 1 positioner rangordnat mom126; slot; beslut monthly | 0,29 | 0,10 | 0,00 | 29 % | -0,24 | 1,40 | -11 % | validerings-Sharpe -0.24 < 0.5; slår inte likaviktat köp och behåll på Sharpe i validering; walk-forward-Sharpe 0.10 < 0.3; Deflated Sharpe 0.00 < 0.95; PBO 0.88 > 0.3; parameterkänslig: 29% av grannarna håller; klarar inte FDR (q 1.00); för få affärer (0.5/år); för få affärer totalt (9) |
| etp_equity: entry high52(prox=0.1); filter market_trend(n=200); alla positioner; invvol; beslut monthly | 0,21 | -0,06 | 0,00 | 33 % | 0,72 | 0,82 | -17 % | slår inte likaviktat köp och behåll på Sharpe i validering; walk-forward-Sharpe -0.06 < 0.3; Deflated Sharpe 0.00 < 0.95; PBO 0.88 > 0.3; parameterkänslig: 33% av grannarna håller; ingen avkastning vid dubbla kostnader; klarar inte FDR (q 1.00) |
| etp_core: entry mom(L=252); filter market_trend(n=200); max 10 positioner rangordnat mom252; slot; beslut monthly | 0,13 | 0,02 | 0,00 | 50 % | 1,07 | 1,40 | -17 % | slår inte likaviktat köp och behåll på Sharpe i validering; walk-forward-Sharpe 0.02 < 0.3; Deflated Sharpe 0.00 < 0.95; PBO 0.88 > 0.3; parameterkänslig: 50% av grannarna håller; ingen avkastning vid dubbla kostnader; klarar inte FDR (q 1.00) |
| etp_equity: entry always(); exit atr_trail(k=3.0); filter market_trend(n=200); alla positioner; slot; beslut monthly | 0,09 | -0,10 | 0,00 | 25 % | 0,61 | 0,82 | -14 % | slår inte likaviktat köp och behåll på Sharpe i validering; walk-forward-Sharpe -0.10 < 0.3; Deflated Sharpe 0.00 < 0.95; PBO 0.88 > 0.3; parameterkänslig: 25% av grannarna håller; ingen avkastning vid dubbla kostnader; klarar inte FDR (q 1.00) |

## Jämförelse: SwingEdge med guld (app 2.2)

(in-sample: strategin valdes med data 2015–2026)

| Period | Avkastning/år | Sharpe | Största nedgång |
|---|---|---|---|
| Utveckling | 2,6 % | 0,29 | -16 % |
| Validering | 47,8 % | 1,79 | -31 % |
| Holdout | 17,1 % | 1,02 | -23 % |

Körtid 11 minuter. Alla siffror kommer från registret `experiments/registry.sqlite` och filen `R1_report.json`.
