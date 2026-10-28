# Granskning av Börslabbets strategier (28 okt 2026)

Oberoende test av de strategier som [Börslabbet](https://borslabbet.se/) beskriver publikt. Endast publika sidor
har använts; inga betalda signaler eller portföljer. Inte investeringsrådgivning.

| Strategi | Evidensstatus | Huvudresultat |
| --- | --- | --- |
| Global trendföljning | Lovande men otillräckligt verifierad | Avanza-fonder 2002–2026: 12,0 %/år, Sharpe 0,93, −17 % mot världsindex 8,9 %, 0,61, −40 %. Test 2014–2026: 0,84 mot 1,01. |
| Utökad global trendföljning | Lovande men otillräckligt verifierad | 33 tillgångar, topp 11: Sharpe 1,20 mot 0,91 (2013–2026, p = 0,14). Råvaror försämrade. |
| Sammansatt momentum | Lovande men otillräckligt verifierad | Sharpe 0,94 mot 0,67 för lika vikt (2006–2026), men dagens Large/Mid Cap = överlevnadsbias; F-score saknas. |
| Trendande värde / kvalitet / utdelning | Endast publikt dokumenterad | Kräver historiska bokslut med publiceringsdatum (Börsdata Pro). Ken French: värdepremien i Sverige +1,9 %/år efter 2010 (ej signifikant). |

## Skript (Python 3, bara standardbiblioteket, kör med `python -E -s`)

- `fetch_funds.py` – månadsvärden (NAV i SEK) från Avanzas publika fond-API + guld/valuta från Yahoo → `data/funds.json`.
  Obs: Avanzas tidsstämpel ligger på den 1:a i månaden men värdet är månadens sista NAV (kontrollerat mot SPY i SEK).
- `gtf.py` – Global trendföljning (Börslabbets publika regler), mått, blockbootstrap, deflated Sharpe, PBO.
- `study_gtf.py` – replikering, varianter, train/test, walk-forward → `results_gtf.json`.
- `study_ext.py` – utökat universum (forskningsvariant) → `results_ext.json`.
- `study_mom.py` – sammansatt momentum på svenska aktier (forskningsvariant; kräver kursdata från den tidigare studien i `qa/swing/data`).
- `study_ff.py` – värde, momentum och lönsamhet med Ken Frenchs data (lägg filerna i `ff/`).
- `study_combo.py` – kombinationer med SwingEdges befintliga hinkar (kräver `qa/swing/study3.py`).
- `parity_gtf.py` – facit för appens test `GlobalAllocationParityTest`.
- `build_universe.py` – appens aktieuniversum med Avanza-id (`app/src/main/assets/stock_universe.json`).
- `notes.md` – Börslabbets publika regler och siffror, ordagrant sammanfattade.
