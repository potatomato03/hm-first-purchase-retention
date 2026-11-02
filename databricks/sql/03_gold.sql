-- Gold: small summary tables that feed the dashboard. Run each statement in the Databricks SQL editor

USE workspace.hm_retention;

-- 1. Weekly orders by channel. Shows the store channel dropping to zero in spring 2020
CREATE OR REPLACE TABLE gold_weekly_channel AS
SELECT CAST(date_trunc('WEEK', order_date) AS DATE) AS week,
       channel,
       count(*) AS orders
FROM silver_orders
GROUP BY 1, 2;

-- 2. Burn-in check: share of each month's buyers seen for the first time, and how often they return within 90 days
CREATE OR REPLACE TABLE gold_burn_in AS
WITH buyers AS (
    SELECT trunc(order_date, 'MM') AS month, count(DISTINCT customer_id) AS buyers
    FROM silver_orders
    GROUP BY 1
),
new AS (
    SELECT cohort_month AS month,
           count(*) AS new_customers,
           100 * avg(CASE WHEN days_to_second <= 90 THEN 1 ELSE 0 END) AS return_90d_pct
    FROM silver_first_purchases
    WHERE first_date <= date_sub(DATE'2020-09-22', 90)
    GROUP BY 1
)
SELECT b.month, b.buyers, n.new_customers,
       round(100 * n.new_customers / b.buyers, 1) AS pct_new,
       round(n.return_90d_pct, 1) AS return_90d_pct,
       b.month >= DATE'2019-08-01' AS after_burn_in
FROM buyers b
JOIN new n ON n.month = b.month;

-- 3. Return window: share of clean first-time buyers (Aug to 22 Sep 2019) who have ordered again by each day
CREATE OR REPLACE TABLE gold_return_window AS
WITH base AS (
    SELECT days_to_second FROM silver_first_purchases
    WHERE first_date BETWEEN DATE'2019-08-01' AND DATE'2019-09-22'
)
SELECT d.id AS day,
       round(100 * count_if(days_to_second <= d.id) / count(*), 2) AS pct_back
FROM base
CROSS JOIN range(1, 366) AS d
GROUP BY d.id;

-- 4. Monthly cohort retention, months 1 to 12, only months fully inside the data
CREATE OR REPLACE TABLE gold_cohort_retention AS
WITH cust AS (
    SELECT customer_id, cohort_month FROM silver_first_purchases
    WHERE cohort_month >= DATE'2019-08-01'
),
active AS (
    SELECT DISTINCT o.customer_id, c.cohort_month,
           CAST(months_between(trunc(o.order_date, 'MM'), c.cohort_month) AS INT) AS k
    FROM silver_orders o
    JOIN cust c ON c.customer_id = o.customer_id
),
sizes AS (
    SELECT cohort_month, count(*) AS cohort_size FROM cust GROUP BY 1
)
SELECT a.cohort_month, s.cohort_size, a.k,
       count(*) AS active_customers,
       round(100 * count(*) / s.cohort_size, 2) AS retention_pct
FROM active a
JOIN sizes s ON s.cohort_month = a.cohort_month
WHERE a.k BETWEEN 1 AND 12
  AND add_months(a.cohort_month, a.k + 1) <= DATE'2020-09-01'
GROUP BY a.cohort_month, s.cohort_size, a.k;

-- 5. Odds ratios from the logistic regression in the notebook (statistics stay in Python, results come back as a table)
CREATE OR REPLACE TABLE gold_odds_ratios AS
SELECT * FROM read_files('/Volumes/workspace/hm_retention/raw/odds_ratios.csv', format => 'csv', header => true);

-- 6. The same drivers in percentage points (average marginal effects from the notebook), which the dashboard charts
CREATE OR REPLACE TABLE gold_marginal_effects AS
SELECT * FROM read_files('/Volumes/workspace/hm_retention/raw/marginal_effects.csv', format => 'csv', header => true);

-- Checks against the notebook
SELECT 'cohort Aug 2019, month 1' AS check, retention_pct AS value FROM gold_cohort_retention
WHERE cohort_month = DATE'2019-08-01' AND k = 1
UNION ALL
SELECT 'back within 90 days, clean cohorts', pct_back FROM gold_return_window WHERE day = 90
UNION ALL
SELECT 'Oct 2018 pct new', pct_new FROM gold_burn_in WHERE month = DATE'2018-10-01';
