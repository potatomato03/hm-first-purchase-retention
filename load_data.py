"""Download the three H&M CSVs from Kaggle and convert them to Parquet for DuckDB.

Needs ~/.kaggle/kaggle.json and the competition rules accepted on kaggle.com.
"""
import subprocess, zipfile, pathlib, duckdb

COMP = "h-and-m-personalized-fashion-recommendations"
RAW = pathlib.Path(__file__).parent / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

for name in ["customers.csv", "articles.csv", "transactions_train.csv"]:
    pq = RAW / name.replace(".csv", ".parquet")
    if pq.exists():
        continue
    if not (RAW / name).exists():
        subprocess.run(["kaggle", "competitions", "download", "-c", COMP, "-f", name, "-p", str(RAW)], check=True)
        z = RAW / f"{name}.zip"
        if z.exists():
            zipfile.ZipFile(z).extractall(RAW)
            z.unlink()
    # article_id has leading zeros, keep it as text
    types = ", types={'article_id': 'VARCHAR'}" if name != "customers.csv" else ""
    duckdb.sql(f"""COPY (SELECT * FROM read_csv('{(RAW / name).as_posix()}', header=true{types}))
                   TO '{pq.as_posix()}' (FORMAT parquet)""")
    print(name, duckdb.sql(f"SELECT count(*) FROM '{pq.as_posix()}'").fetchall()[0][0], "rows")
