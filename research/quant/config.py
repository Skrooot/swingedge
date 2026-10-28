"""All konfiguration för forskningsmotorn på ett ställe: sökvägar, perioder, kostnader, budget och godkännandekrav.

Perioderna är låsta för forskningsomgång 1 (2026-10-29). Ändras de måste en ny omgång startas i registret;
holdout-perioden får aldrig användas för att välja eller justera en strategi.
"""
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(ROOT))
# Kursdata versioneras inte i Git (storlek, licens); datasetets hash sparas i registret.
DATA_DIR = os.environ.get("SWINGEDGE_DATA", "C:/Users/fredrik/android-build/qa/quant/data")
MAPPING = os.path.join(REPO, "research", "archive", "edge-engine", "mapping.json")
UNIVERSE = os.path.join(REPO, "research", "archive", "edge-engine", "universe.json")
REGISTRY = os.environ.get("SWINGEDGE_REGISTRY", os.path.join(ROOT, "experiments", "registry.sqlite"))
RESULTS_DIR = os.path.join(ROOT, "experiments")
PRODUCTION = os.path.join(ROOT, "production")

# ---- perioder (beslutsdatum) ----
START = "2000-01-03"
DEV = ("2000-01-03", "2015-12-31")          # discovery, development, optimering, walk-forward
VALIDATION = ("2016-01-01", "2020-12-31")   # oberoende validering av frysta finalister
HOLDOUT = ("2021-01-01", "2026-10-27")      # används en gång, för en fryst champion
WF_FOLDS = [("2000-01-03", "2005-12-31", "2006-01-01", "2007-12-31"),   # (träning från, till, test från, till)
            ("2000-01-03", "2007-12-31", "2008-01-01", "2009-12-31"),
            ("2000-01-03", "2009-12-31", "2010-01-01", "2011-12-31"),
            ("2000-01-03", "2011-12-31", "2012-01-01", "2013-12-31"),
            ("2000-01-03", "2013-12-31", "2014-01-01", "2015-12-31")]
WARMUP_DAYS = 260   # indikatorer får använda data före periodens start, men avkastning räknas inom perioden

# ---- Avanza-kostnader (courtageklass Medium, som appen) ----
CAPITAL_SEK = 100_000.0
COURTAGE = {  # (andel, minimum i handelsvalutan)
    "XSTO": (0.00069, 69.0),     # Stockholmsbörsen, First North
    "XETRA": (0.00089, 8.0),     # EUR
    "US": (0.00089, 1.0),        # USD, amerikanska aktier
}
FX_FEE = 0.0025                  # valutaväxling per affär i annan valuta än SEK
SLIPPAGE = 0.0005                # per sida
HALF_SPREAD_DEFAULT = {"etf": 0.0010, "certificate": 0.0025, "stock": 0.0015, "crypto_tracker": 0.0025}
COST_STRESS = [1.0, 2.0, 3.0]    # multiplikatorer i kostnadskänsligheten

# ---- forskningsbudget (omgång 1) ----
SEED = 20261029
N_SCREEN = 6000                  # slumpade kandidater i bred screening
HALVING_KEEP = (0.33, 0.15)      # andel som går vidare efter steg 1 respektive 2
N_REFINE = 40                    # kandidater som förfinas med lokal sökning
REFINE_GENERATIONS = 3
REFINE_CHILDREN = 8
N_FINALISTS = 12
MAX_WORKERS = max(1, (os.cpu_count() or 2) - 2)
MAX_MINUTES = 240

# ---- godkännandekrav (förregistrerade, gäller validering och holdout) ----
GATES = {
    "min_years": 4.0,
    "max_drawdown": -0.35,
    "min_validation_sharpe": 0.50,
    "min_wf_sharpe": 0.30,
    "beat_benchmark_sharpe": True,      # validering: Sharpe > likaviktat köp och behåll av samma universum
    "min_dsr": 0.95,                    # Deflated Sharpe Ratio (sannolikhet) på utvecklingsdata
    "max_pbo": 0.30,                    # Probability of Backtest Overfitting för urvalet
    "min_neighbor_share": 0.60,         # andel parametergrannar med minst halva Sharpe
    "cost_stress_positive": 2.0,        # avkastning över kontanter ska vara positiv vid 2x kostnader
    "max_fdr_q": 0.10,                  # Benjamini–Hochberg över finalisternas validerings-p
    "min_trades_per_year": {"daily": 6.0, "weekly": 3.0, "monthly": 1.0},
    "min_total_trades": 30,
    "max_exact_gap_cagr": 0.02,         # snabb vs exakt motor, absolut skillnad i CAGR
    "holdout_min_sharpe": 0.30,
    "holdout_max_drawdown": -0.40,
}
