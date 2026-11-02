"""Upload the raw Parquet files to the Unity Catalog volume, or run a .sql file on the SQL warehouse.

Usage:
    python databricks/run.py upload                      (all four files)
    python databricks/run.py upload exports/odds_ratios.csv
    python databricks/run.py sql databricks/sql/01_bronze.sql
"""
import sys, time, pathlib
from databricks.sdk.service.sql import StatementState
from connect import client, CATALOG, SCHEMA, VOLUME

ROOT = pathlib.Path(__file__).resolve().parent.parent
w = client()
warehouse = next(iter(w.warehouses.list())).id


def run(statement):
    # every call is its own session, so USE does not carry over: pass catalog and schema each time
    r = w.statement_execution.execute_statement(statement=statement, warehouse_id=warehouse, wait_timeout="50s",
                                                catalog=CATALOG, schema=SCHEMA)
    while r.status.state in (StatementState.PENDING, StatementState.RUNNING):
        time.sleep(3)
        r = w.statement_execution.get_statement(r.statement_id)
    if r.status.state != StatementState.SUCCEEDED:
        raise RuntimeError(f"{r.status.state}: {r.status.error.message if r.status.error else ''}\n{statement[:300]}")
    if r.manifest and r.manifest.schema and r.result and r.result.data_array:
        cols = [c.name for c in r.manifest.schema.columns]
        print(" | ".join(cols))
        for row in r.result.data_array[:60]:
            print(" | ".join(str(v) for v in row))


if sys.argv[1] == "upload":
    run(f"CREATE SCHEMA IF NOT EXISTS {CATALOG}.{SCHEMA}")
    run(f"CREATE VOLUME IF NOT EXISTS {CATALOG}.{SCHEMA}.{VOLUME}")
    # the regression results come from the notebook's export, so the dashboard can show them
    files = sys.argv[2:] or ["data/raw/customers.parquet", "data/raw/articles.parquet",
                             "data/raw/transactions_train.parquet", "exports/odds_ratios.csv"]
    for rel in files:
        src = ROOT / rel
        name = src.name
        t0 = time.time()
        with open(src, "rb") as f:
            w.files.upload(f"/Volumes/{CATALOG}/{SCHEMA}/{VOLUME}/{name}", f, overwrite=True)
        print(f"uploaded {name} ({src.stat().st_size / 1e6:.0f} MB) in {time.time() - t0:.0f}s")
else:
    # statements are split on ';', so never put a semicolon inside a comment
    for stmt in pathlib.Path(sys.argv[2]).read_text().split(";"):
        body = "\n".join(l for l in stmt.splitlines() if not l.strip().startswith("--")).strip()
        if body:
            t0 = time.time()
            print(f"\n== {body.splitlines()[0][:90]}")
            run(body)
            print(f"   ({time.time() - t0:.0f}s)")
