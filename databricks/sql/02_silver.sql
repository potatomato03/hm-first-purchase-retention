-- Silver: cleaned, analysis-ready tables. The definitions match the notebook (see DECISIONS.md)

USE workspace.hm_retention;

-- One order = one customer, one day, one channel (the data has no order ID).
-- Channel 1 is store and channel 2 is online, proven by the spring 2020 store closures
CREATE OR REPLACE TABLE silver_orders AS
SELECT customer_id,
       t_dat AS order_date,
       CASE sales_channel_id WHEN 1 THEN 'store' ELSE 'online' END AS channel,
       count(*)   AS items,
       sum(price) AS value
FROM bronze_transactions
GROUP BY customer_id, t_dat, sales_channel_id;

-- Each customer's first shopping day and their next distinct shopping day
CREATE OR REPLACE TABLE silver_first_purchases AS
WITH days AS (
    SELECT customer_id, order_date,
           row_number() OVER (PARTITION BY customer_id ORDER BY order_date) AS day_n
    FROM (SELECT DISTINCT customer_id, order_date FROM silver_orders)
)
SELECT f.customer_id,
       f.order_date                       AS first_date,
       trunc(f.order_date, 'MM')          AS cohort_month,
       datediff(s.order_date, f.order_date) AS days_to_second
FROM days f
LEFT JOIN days s ON s.customer_id = f.customer_id AND s.day_n = 2
WHERE f.day_n = 1;

-- One row per first order from 2019-08-01 (after the burn-in) to 2020-06-24 (last day with a full 90 days of data)
CREATE OR REPLACE TABLE silver_first_orders AS
WITH f AS (
    SELECT * FROM silver_first_purchases
    WHERE first_date BETWEEN DATE'2019-08-01' AND DATE'2020-06-24'
),
typical AS (
    SELECT article_id, median(price) AS typical_price
    FROM bronze_transactions
    GROUP BY article_id
),
items AS (
    SELECT f.customer_id, f.first_date, f.cohort_month, f.days_to_second,
           x.article_id, x.price, x.sales_channel_id,
           a.product_group_name, a.index_group_name, p.typical_price
    FROM f
    JOIN bronze_transactions x ON x.customer_id = f.customer_id AND x.t_dat = f.first_date
    JOIN bronze_articles a     ON a.article_id = x.article_id
    JOIN typical p             ON p.article_id = x.article_id
),
dept AS (
    SELECT customer_id, index_group_name AS main_department,
           row_number() OVER (PARTITION BY customer_id ORDER BY count(*) DESC, index_group_name) AS rnk
    FROM items
    GROUP BY customer_id, index_group_name
),
baskets AS (
    SELECT i.customer_id, i.first_date, i.cohort_month,
           coalesce(any_value(i.days_to_second) <= 90, false)  AS returned_90d,
           coalesce(any_value(i.days_to_second) <= 180, false) AS returned_180d,
           count(*)                             AS items,
           count(DISTINCT i.product_group_name) AS product_groups,
           CASE WHEN max(i.sales_channel_id) = 1 THEN 'store' ELSE 'online' END AS first_channel,
           any_value(d.main_department)         AS main_department,
           avg(CASE WHEN i.price < 0.9 * i.typical_price THEN 1 ELSE 0 END) AS markdown_share,
           sum(i.price)                         AS order_value
    FROM items i
    JOIN dept d ON d.customer_id = i.customer_id AND d.rnk = 1
    GROUP BY i.customer_id, i.first_date, i.cohort_month
)
SELECT b.*,
       CASE WHEN items = 1 THEN '1' WHEN items = 2 THEN '2' WHEN items = 3 THEN '3'
            WHEN items <= 5 THEN '4-5' WHEN items <= 9 THEN '6-9' ELSE '10+' END AS items_band,
       CASE WHEN product_groups >= 4 THEN '4+' ELSE CAST(product_groups AS STRING) END AS groups_band,
       CASE WHEN markdown_share = 0 THEN 'none on markdown'
            WHEN markdown_share = 1 THEN 'all on markdown'
            ELSE 'some on markdown' END AS markdown_band,
       c.age,
       CASE WHEN c.age IS NULL THEN 'unknown' WHEN c.age < 25 THEN '16-24' WHEN c.age < 35 THEN '25-34'
            WHEN c.age < 45 THEN '35-44' WHEN c.age < 55 THEN '45-54' ELSE '55+' END AS age_band,
       CASE WHEN c.club_member_status IN ('ACTIVE', 'PRE-CREATE') THEN c.club_member_status ELSE 'other' END AS club_status,
       CASE WHEN b.first_date < DATE'2020-03-16' THEN 'before closure'
            WHEN b.first_date < DATE'2020-05-04' THEN 'stores closed'
            ELSE 'stores reopening' END AS period
FROM baskets b
JOIN bronze_customers c ON c.customer_id = b.customer_id;

-- Check against the notebook: 330,336 first orders, 32.8% back within 90 days
SELECT count(*) AS first_orders,
       round(100 * avg(CAST(returned_90d AS INT)), 1) AS return_90d_pct
FROM silver_first_orders;
