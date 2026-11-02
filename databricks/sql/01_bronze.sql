-- Bronze: the three Kaggle files exactly as delivered, loaded from the Unity Catalog volume into Delta tables

CREATE SCHEMA IF NOT EXISTS workspace.hm_retention;

CREATE VOLUME IF NOT EXISTS workspace.hm_retention.raw;

CREATE OR REPLACE TABLE workspace.hm_retention.bronze_transactions AS
SELECT * FROM read_files('/Volumes/workspace/hm_retention/raw/transactions_train.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.hm_retention.bronze_customers AS
SELECT * FROM read_files('/Volumes/workspace/hm_retention/raw/customers.parquet', format => 'parquet');

CREATE OR REPLACE TABLE workspace.hm_retention.bronze_articles AS
SELECT * FROM read_files('/Volumes/workspace/hm_retention/raw/articles.parquet', format => 'parquet');

-- Check: row counts should be 31,788,324 transactions, 1,371,980 customers and 105,542 articles
SELECT (SELECT count(*) FROM workspace.hm_retention.bronze_transactions) AS transactions,
       (SELECT count(*) FROM workspace.hm_retention.bronze_customers)    AS customers,
       (SELECT count(*) FROM workspace.hm_retention.bronze_articles)     AS articles;
