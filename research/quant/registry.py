"""Experiment Registry (SQLite). Varje testad strategi sparas, även förkastade, med data- och kodversion.

Holdout-skyddet ligger här: en omgång kan frysa exakt en champion-kandidat och köra holdout exakt en gång,
och bara för den frysta specifikationen. Försök att köra igen, eller med en annan strategi, ger ett fel.
"""
import datetime as dt
import json
import os
import sqlite3
import subprocess

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS rounds (round_id TEXT PRIMARY KEY, created TEXT, config TEXT, data_version TEXT,
  code_version TEXT, seed INTEGER, notes TEXT);
CREATE TABLE IF NOT EXISTS experiments (exp_id TEXT PRIMARY KEY, round_id TEXT, stage TEXT, spec_id TEXT, spec TEXT,
  description TEXT, universe TEXT, complexity INTEGER, method TEXT, seed INTEGER, n_combinations INTEGER,
  cost_model TEXT, period TEXT, result TEXT, score REAL, status TEXT, reason TEXT, created TEXT);
CREATE INDEX IF NOT EXISTS ix_exp ON experiments(round_id, stage, spec_id);
CREATE TABLE IF NOT EXISTS frozen (round_id TEXT PRIMARY KEY, spec_id TEXT, spec TEXT, frozen_at TEXT, selection TEXT);
CREATE TABLE IF NOT EXISTS holdout (round_id TEXT PRIMARY KEY, spec_id TEXT, result TEXT, run_at TEXT);
CREATE TABLE IF NOT EXISTS champion (version INTEGER PRIMARY KEY AUTOINCREMENT, spec_id TEXT, spec TEXT, round_id TEXT,
  approved_by TEXT, approved_at TEXT, status TEXT, evidence TEXT);
"""


class HoldoutError(RuntimeError):
    pass


def code_version():
    try:
        h = subprocess.run(["git", "-C", config.REPO, "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", config.REPO, "status", "--porcelain", "research/quant"], capture_output=True, text=True).stdout.strip()
        return h + ("+lokala ändringar" if dirty else "")
    except Exception:
        return "okänd"


def now():
    return dt.datetime.now().isoformat(timespec="seconds")


class Registry:
    def __init__(self, path=config.REGISTRY):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)

    def close(self):
        self.db.close()

    def new_round(self, round_id, cfg, data_version, seed, notes=""):
        row = self.db.execute("SELECT data_version FROM rounds WHERE round_id=?", (round_id,)).fetchone()
        if row:
            if row[0] != data_version:
                raise RuntimeError(f"Omgång {round_id} finns redan med dataversion {row[0]}, nu {data_version}. Starta en ny omgång.")
            return False
        self.db.execute("INSERT INTO rounds VALUES (?,?,?,?,?,?,?)", (round_id, now(), json.dumps(cfg, default=str), data_version, code_version(), seed, notes))
        self.db.commit()
        return True

    def done(self, round_id, stage, spec_id):
        return self.db.execute("SELECT result, score, status FROM experiments WHERE exp_id=?", (f"{round_id}:{stage}:{spec_id}",)).fetchone()

    def log(self, round_id, stage, spec_id, spec, description, method, seed, n_comb, period, result, score, status, reason=None):
        self.db.execute("INSERT OR REPLACE INTO experiments VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            f"{round_id}:{stage}:{spec_id}", round_id, stage, spec_id, json.dumps(spec), description, spec["universe"],
            None if spec is None else _complexity(spec), method, seed, n_comb,
            json.dumps({"courtage": config.COURTAGE, "fx": config.FX_FEE, "slippage": config.SLIPPAGE}), json.dumps(period),
            json.dumps(result, default=float), score, status, reason, now()))

    def commit(self):
        self.db.commit()

    def trials(self, round_id, stage=None):
        q = "SELECT COUNT(DISTINCT spec_id) FROM experiments WHERE round_id=?" + (" AND stage=?" if stage else "")
        return self.db.execute(q, (round_id, stage) if stage else (round_id,)).fetchone()[0]

    def results(self, round_id, stage):
        rows = self.db.execute("SELECT spec_id, spec, result, score, status, reason FROM experiments WHERE round_id=? AND stage=?", (round_id, stage)).fetchall()
        return [{"spec_id": a, "spec": json.loads(b), "result": json.loads(c), "score": d, "status": e, "reason": f} for a, b, c, d, e, f in rows]

    # ---- holdout-skydd ----
    def freeze(self, round_id, spec_id, spec, selection):
        if self.db.execute("SELECT 1 FROM frozen WHERE round_id=?", (round_id,)).fetchone():
            raise HoldoutError(f"Omgång {round_id} har redan en fryst kandidat.")
        self.db.execute("INSERT INTO frozen VALUES (?,?,?,?,?)", (round_id, spec_id, json.dumps(spec), now(), json.dumps(selection, default=float)))
        self.db.commit()

    def frozen(self, round_id):
        r = self.db.execute("SELECT spec_id, spec, frozen_at, selection FROM frozen WHERE round_id=?", (round_id,)).fetchone()
        return None if r is None else {"spec_id": r[0], "spec": json.loads(r[1]), "frozen_at": r[2], "selection": json.loads(r[3])}

    def holdout_allowed(self, round_id, spec_id):
        f = self.frozen(round_id)
        if f is None:
            raise HoldoutError("Ingen fryst kandidat: holdout får bara köras efter att strategin frysts.")
        if f["spec_id"] != spec_id:
            raise HoldoutError(f"Holdout får bara köras för den frysta kandidaten {f['spec_id']}, inte {spec_id}.")
        if self.db.execute("SELECT 1 FROM holdout WHERE round_id=?", (round_id,)).fetchone():
            raise HoldoutError(f"Holdout för omgång {round_id} är redan körd och får inte köras om.")
        return True

    def record_holdout(self, round_id, spec_id, result):
        self.holdout_allowed(round_id, spec_id)
        self.db.execute("INSERT INTO holdout VALUES (?,?,?,?)", (round_id, spec_id, json.dumps(result, default=float), now()))
        self.db.commit()

    def holdout(self, round_id):
        r = self.db.execute("SELECT spec_id, result, run_at FROM holdout WHERE round_id=?", (round_id,)).fetchone()
        return None if r is None else {"spec_id": r[0], "result": json.loads(r[1]), "run_at": r[2]}


def _complexity(spec):
    from .strategies import complexity
    return complexity(spec)
