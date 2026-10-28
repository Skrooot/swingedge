# Börslabbet – publika regler och siffror (läst 2026-10-28)
## Aktiestrategier (studie "Vad fungerar på Stockholmsbörsen?")
- Data Börsdata, Sthlm+First North 2001-01-01–2021-12-31, topp 40 % efter börsvärde (>2 mdr kr vid slut; 34 bolag 2001, 260 2021), ex finans.
- Årsrapporter från 2000, kvartalsrapporter från 2012. Ombalans feb/maj/aug/nov-slut, utdelningar antas i maj.
- Survivorship bias: bolag avnoterade före 2012 saknas (de skriver det själva).
- Trendande X: topp 40 % efter primärt kriterium, sedan översta fjärdedelen efter sammansatt momentum (snitt 3/6/12 m) => topp 10 %.
- Sammansatt momentum: ta bort lägst F-score (tröskel ej publik), topp 10 % efter momentum.
- Värde (sammansatt): P/E, P/B, P/S, EV/FCF, EV/EBITDA, direktavkastning. Normalisering ej publik (troligen rank-percentil som i WWOWS).
- Kvalitet (sammansatt ROI): ROE, ROA, ROIC, FCFROE.
- Utdelning: högst direktavkastning.
- Resultat topp 10 % (utan kostnader; "även om vi skulle justera för kostnader..."):
  Index 10,1 % / vol 18,5 / Sharpe 0,55 / DD -54
  Värde 19,0/24,9/0,78/-69; Kvalitet 22,4/19,3/1,09/-50; Momentum 24,9/23,5/1,02/-61
  Tr värde 20,1/21,6/0,90/-63 (kv) ; årsvis 19,2/21,6/0,86/-58
  Tr utdelning 19,2/19,6/0,94/-56 (kv); årsvis 21,7/19,3/1,05/-52
  Tr kvalitet 25,0/21,4/1,10/-57 (kv); årsvis 23,9/22,8/1,00/-58
  Samm. momentum kv 31,3/24,7/1,18/-50; mån+banding 31,9/23,6/1,25/-49; årsvis 24,8/26,6/0,92/-58
  Alla fyra 25,9/20,7/1,16/-56
  100+ varianter testade (deras ord) – multipeltestning ej korrigerad.
- Magic formula 16,5/0,75; F-score 18,0/0,82; EV/EBIT 18,3/0,76.
- Svenska portföljen: backtest t.o.m. mars 2020 + live därefter, 0,5 % kostnad per ombalansering: 19,5/21,0/0,89/-54 vs index 8,9/18,3/0,48/-54.
- Momentumportfölj: topp 10, sälj om utanför topp 20, månadsvis, 0,5 %/byte: 26,2/25,1/1,00/-50 (2001–2025, live från jan 2025 hos Avanza KF).
- Live 5 år (inlägg 2025-09-10, inkl courtage/växling): Svensk 80 % vs index 63 %; Nordisk 159 vs 52; USA 192 vs 64.
- FAQ: 10 aktier per strategi, likavikt, spread ~0,3 %, total ~0,5 %/byte; listor uppdateras 15:e och sista; säsong mars/jun/sep/dec; USA-universum >200 MUSD inkl finans.
## Global trendföljning
- 9 tillgångar: Sverige, Europa, USA, Japan, Tillväxt (från 1993), Sv småbolag (från 2001), Sv obligationer, Sv korta räntor, Guld. Allt i SEK, totalavkastning.
- Topp 3 efter snitt av 3/6/12 m avkastning, sista handelsdagen varje månad, lika vikt 1/3.
- Tröskel: byt endast om ny tillgång har >= 2 procentenheter högre snittmomentum (portföljsidan). Studien: tröskel upp till 5 pe påverkar inte avkastningen, minskar omsättning upp till 1/4.
- Backtest 1972–2025 utan kostnader: 18,5/13,4/0,95/-19 vs världsindex 11,4/14,5/0,46/-49.
- 1995–2009: 20,4/13,2/1,20/-17 vs 6,2/15,0/0,22/-49. 2010–2025: 10,6/10,4/0,96/-12 vs 12,9/12,3/1,00/-17.
- Per decennium 2010-19 9,9 vs 12,9; 2020-25 9,6 vs 12,9.
- Topp1 19,2/0,71/-29 oms 370 %; topp2 18,6/0,87; topp3 18,5/0,95/-19 oms 200 %; topp4 16,9/0,94; topp5 14,9/0,84.
- 3m 15,9/0,80; 6m 16,4/0,83; 12m 18,2/0,95; 3+6+12 18,5/0,95.
- Trendfilter MA12 18,4/0,96/-18; pos avk 18,4/0,95; abs mom 17,6/0,94 – inget förbättrar.
- Sedan 1992: bas 15,7/1,00/-17; med råvaror 16,2/1,05/-14; med fastigheter 15,6/0,93/-19.
- Utan guld 16,8/0,87/-29; med MA12 16,8/0,89/-18.
- Live sedan jan 2018 inkl kostnader: 12,3/11,5/0,98/-13. 6 byten/år, oms 200 %. Signal i SEK.
- Snittexponering: Sverige 16,5, USA 14,9, Japan 12,9, Guld 12,0, Europa 11,0, EM 9,2, Oblig 8,6, Småbolag 8,2, Korta 6,6.
- Svensk trendföljning 1920–2025 (Riksbanksdata, OMX/korta/obl, topp 1): 13,2/11,7/0,73/-26 vs 10,7/16,8/0,42/-63.
- Källor: Faber 2006/2010, Antonacci, Hurst-Ooi-Pedersen 2017, Geczy-Samonov 2017, Lempérière m.fl. 2014, Asness-Moskowitz-Pedersen 2013.
