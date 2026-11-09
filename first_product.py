"""Which first product brings a new customer back?

Compares the 90-day return rate by product type across one-item, full-price, online
first orders, so basket size, discounts and channel cannot explain the gaps. Then
standardises each product's rate to the overall month by age-band mix.

Needs data/hm.duckdb, built by the notebook. Writes exports/first_product.csv.
"""
import pathlib
import duckdb

ROOT = pathlib.Path(__file__).parent
MIN_BUYERS = 500

c = duckdb.connect(str(ROOT / "data" / "hm.duckdb"), read_only=True)
c.execute("""
create temp table x as
select f.returned_90d::int r, f.cohort_month m, a.product_type_name product_type,
       case when cu.age < 30 then 'under 30' when cu.age >= 30 then '30+' else 'unknown' end band
from first_orders f
join t on t.customer_id = f.customer_id and t.t_dat = f.first_date
join a on a.article_id = t.article_id
left join c cu on cu.customer_id = f.customer_id
where f.items = 1 and f.channel = 'online' and f.markdown_share = 0
""")

# The weights must describe the whole sample or the adjusted rates mean nothing.
total_weight = c.execute("""
select sum(wt) from (select count(*) * 1.0 / (select count(*) from x) wt from x group by m, band)
""").fetchone()[0]
assert abs(total_weight - 1) < 1e-9, total_weight

rows = c.execute(f"""
with w as (select m, band, count(*) * 1.0 / (select count(*) from x) wt from x group by 1, 2),
s as (select product_type, m, band, avg(r) rate from x group by 1, 2, 3),
adj as (select product_type, sum(wt * rate) / sum(wt) adj from s join w using (m, band) group by 1),
raw as (select product_type, count(*) n, avg(r) p from x group by 1 having count(*) >= {MIN_BUYERS})
select product_type, n, round(100 * p, 1) return_90d_pct,
       round(100 * adj, 1) adjusted_return_90d_pct,
       round(196 * sqrt(p * (1 - p) / n), 1) margin_95_pp
from raw join adj using (product_type)
order by adjusted_return_90d_pct desc
""").fetchall()
assert rows and all(r[1] >= MIN_BUYERS for r in rows)

with open(ROOT / "exports" / "first_product.csv", "w", encoding="utf-8", newline="\n") as f:
    f.write("product_type,buyers,return_90d_pct,adjusted_return_90d_pct,margin_95_pp\n")
    for r in rows:
        f.write(",".join(map(str, r)) + "\n")

for r in rows:
    print(*r, sep="  ")
