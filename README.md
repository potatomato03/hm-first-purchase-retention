# What does a first purchase say about whether a customer comes back?

An analysis of H&M's real transaction data: 31.8M item purchases from 1.36M customers, September 2018 to September 2020. It looks at which first-time buyers return and what in their first purchase predicts it.

I picked this question because AI shopping products face the same problem. Glance's AI try-on shows a user one look, and the team has to work out which first sessions turn into people who come back. H&M's data is the closest public stand-in: a real fashion retailer at scale.

**Stack:** Databricks (Unity Catalog volume, Delta tables in bronze, silver and gold layers, Databricks SQL, AI/BI dashboard), plus Python (DuckDB, pandas, statsmodels) for the exploratory notebook and the regression.

## Dashboard (Databricks AI/BI)
Page 1 answers "who comes back?". Every chart except the heatmap recalculates when you filter by first purchase month, channel, age, department or club status.

![Dashboard page 1: counters and drivers](databricks/screenshots/page1_top.jpg)
![Dashboard page 1: cohort retention heatmap](databricks/screenshots/page1_heatmap.jpg)

Page 2 shows the evidence behind each data decision, plus the regression results.

![Dashboard page 2: channel check](databricks/screenshots/page2_top.jpg)
![Dashboard page 2: return window and drivers](databricks/screenshots/page2_drivers.jpg)

## Findings
Based on 330,336 first-time buyers between Aug 2019 and Jun 2020.

1. **Most customers are lost right after the first purchase.**
   - Only 32.8% come back within 90 days.
   - After the first two months, cohort retention barely moves: 9% to 14% of a cohort is active in any later month, out to month 12.
2. **An unfinished sign-up is the clearest warning sign.**
   - Customers whose club membership was never completed (PRE-CREATE) come back 17.8% of the time, against 34.0% for active members.
   - Holding every other driver constant, that's 0.45 times the odds (95% CI 0.44 to 0.47).
3. **Breadth beats size.** With basket size held constant, a first basket covering 4 or more product groups has 20% higher odds of a return than a single-group basket.
4. **Deal-only first purchases are weaker.** Customers whose whole first basket was on markdown have 11% lower odds of returning than those who paid full price.
5. **Pandemic online arrivals were not weaker customers.** First-time buyers who came in online while stores were closed returned 33.1% of the time, against 31.2% for online first-timers before the closures.

**Limits**
- The first order explains only a small share of who comes back (pseudo R-squared 0.014), so these are levers, not predictions.
- Club status was recorded when the data was published, so part of that link may run the other way: customers who keep shopping may finish signing up later.
- The store advantage (14% higher odds overall) falls to about 6% when the post-reopening summer of 2020 is excluded.

## What it would mean for an AI try-on product
- **Treat onboarding completion as the activation metric.** For Glance, that's finishing the selfie step. Users who don't finish are the ones to worry about.
- **Suggest a second category in the first session.** Broader first baskets bring people back.
- **Test style-led first experiences against discount-led ones.** Judge them on return rate, not only first conversion.

## Decisions that shape the numbers
All are documented with evidence in [DECISIONS.md](DECISIONS.md).

| Decision | Why |
|---|---|
| An order is one customer, one day, one channel | The data has no order ID |
| Channel 1 = store, channel 2 = online | Channel 1 orders fall to zero from 23 March to the end of April 2020, while stores were closed |
| Cohorts start in August 2019 | The data starts mid-relationship. Before Aug 2019, most "new" customers were existing ones. Their 90-day return rate falls from 69.5% (Sep 2018) to a plateau of 30% to 36% |
| "Came back" = a second order within 90 days | 90 days catches 60.5% of the returns that happen within a year, and keeps the spring 2020 cohorts measurable. A 180-day check gives the same direction for every driver with a real effect |
| Prices are an index | H&M scaled all prices |

## Repository
| Path | What it is |
|---|---|
| `notebooks/analysis.ipynb` | Exploratory analysis, step by step, with every code cell explained line by line |
| `databricks/sql/01_bronze.sql` | Loads the raw files from the Unity Catalog volume into Delta tables |
| `databricks/sql/02_silver.sql` | Builds orders, first purchases and one row per first order with every driver |
| `databricks/sql/03_gold.sql` | Summary tables for the dashboard, with checks against the notebook |
| `databricks/dashboard.py` | Builds and publishes the AI/BI dashboard through the Databricks dashboard API |
| `databricks/dashboard.lvdash.json` | The exported dashboard definition (import it in Databricks via Dashboards → Import) |
| `databricks/run.py`, `connect.py` | Upload the data and run the SQL through the Databricks SDK, signing in with browser OAuth |
| `DECISIONS.md` | Data quality log and the evidence behind each decision |
| `figures/` | Charts from the notebook |
| `exports/` | Result tables from the notebook. `odds_ratios.csv` feeds the dashboard's driver chart |
| `load_data.py` | Downloads the three Kaggle files and converts them to Parquet |

## Reproduce
1. Download `transactions_train.csv`, `customers.csv` and `articles.csv` from the [Kaggle competition](https://www.kaggle.com/competitions/h-and-m-personalized-fashion-recommendations), after accepting its rules, and run `python load_data.py`.
2. Run the notebook to produce the local analysis.
3. For Databricks:
   - set the `DATABRICKS_HOST` environment variable to your workspace URL (sign-in happens in the browser, no token needed)
   - `python databricks/run.py upload`
   - `python databricks/run.py sql databricks/sql/01_bronze.sql`, then the same for `02_silver.sql` and `03_gold.sql`
   - import the dashboard

**Data license:** H&M released the dataset for non-commercial and academic use. The data itself is not in this repository.
