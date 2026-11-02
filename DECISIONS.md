# Decisions and data log

Every number below comes from the notebook section named next to it (notebooks/analysis.ipynb), run against the Kaggle files.

## Data quality (notebook sections 2 and 3)
- **Coverage.** 31,788,324 item rows, 1,362,281 buyers and 104,547 articles, from 2018-09-20 to 2020-09-22.
- **Transactions are complete.** No missing customer, article, price or channel values. Every transaction key exists in customers.csv and articles.csv. 9,699 customers in customers.csv never bought anything.
- **Duplicate rows.** 2,974,905 extra rows share the same customer, day, article, price and channel. The data has no quantity column, so they are read as extra units of the same item, not as errors.
- **Prices are scaled.** They run from 0.000017 to 0.59, with a median of 0.025. Revenue is reported only as an index.
- **Orders.** An order is one customer, one day, one channel, which gives 9,174,457 orders (median 2 items, mean 3.46). One order has 570 items (likely a reseller or bulk buyer). Orders like this are capped or excluded where basket size is a driver.
- **Customer fields.** Age runs from 16 to 99, median 32, with 15,861 missing.
  - club_member_status values: ACTIVE 1,272,491, PRE-CREATE 92,960, LEFT CLUB 467, missing 6,062.
  - fashion_news_frequency values: NONE, Regularly, Monthly, missing, and 2 rows holding the literal text "None".
  - FN and Active are 1 or missing, where missing means 0.

## Order tables (notebook section 4)
- The order and first-purchase tables reconcile exactly with the raw transactions: every item row and every buyer is accounted for, with one first-purchase row per buyer.
- A second order in a different channel on the same day does not count as a return. A return is the next distinct day with an order.

## Decision 1: channel 1 is stores and channel 2 is online (notebook section 5)
- H&M never documented the channel codes.
- In the week of 2020-03-16, channel 1 orders fell to 5,011. From the week of 2020-03-23 to the week of 2020-04-27 they were 0 (1 order in the last week).
- That makes 5 full weeks with zero channel 1 orders, from the weeks of 2020-03-23 to 2020-04-20.
- Channel 1 came back in May 2020 (13,675 orders in the week of 2020-05-04).
- This matches stores closing in spring 2020, so channel 1 is read as stores and channel 2 as online.

## Decision 2: burn-in, with cohorts starting 2019-08 (notebook section 6)
- The data starts mid-relationship for many customers, so early "first purchases" are often existing customers.
- **Share of buyers first seen that month.** This share falls from 77.6% (Oct 2018) to 21.0% (Mar 2019) and 14.6% (Jul 2019), then levels off at about 9 to 14% from Aug 2019.
- **90-day return rate.** This rate tells the same story: 69.5% for the Sep 2018 cohort, 42.9% for Jan 2019, then a plateau of 29.8 to 36.3% from Aug 2019.
- **Decision.** Cohorts start at 2019-08, after an 11-month burn-in. A customer "new" in Aug 2019 or later had no purchase in at least the previous 10.5 months, so they are either new or reactivated after a long lapse.
- **Consequence.** The spring 2019 cohorts are still inside the burn-in. Their return rates (Apr 2019: 43.3%) are inflated by existing customers, so the spring 2020 cohorts are compared with the post-burn-in cohorts around them, not with spring 2019. The original plan was to compare with spring 2019.

## Decision 3: the return window is 90 days (notebook section 7)
- Measured on first purchases from 2019-08-01 to 2019-09-22: 47,002 customers who are past the burn-in and each have a full year of data after their first purchase.
- A first pass measured this on Jan to Sep 2019 first purchases. Those cohorts fall inside the burn-in, so it was redone on clean cohorts.
- **When second orders arrive.** 57.9% of first buyers order again within 365 days. Among the 27,194 who return within a year, the gap has a median of 61 days (p25 14, p75 153, p90 265).
- **Share of year-returners captured by each window.** 30 days: 35.5%. 90 days: 60.5%. 180 days: 79.2%.
- **Decision: 90 days.**
  - It captures about 60% of customers who return within the year.
  - It is a standard quarterly window.
  - It keeps every cohort up to late June 2020 observable, including the store-closure cohorts.
  - A 180-day window would end the usable cohorts at March 2020 and lose the spring 2020 comparison entirely.
  - 180 days is run as a robustness check on the cohorts where it fits.

## Early findings (notebook sections 6 and 8)
- **Retention flattens fast.** Monthly retention for the Aug 2019 to Jul 2020 cohorts is 11.8 to 18.0% in month 1, then holds at about 9 to 14% through month 12. There is no long decay after the first two months.
- **Seasonal bumps.** Month 9 and month 12 rise for the 2019 cohorts (Aug 2019: 10.4% in month 6, 11.8% in month 12).
- **April 2020 cohort.** It was the largest post-burn-in cohort, at 40,689 customers against 23,563 to 36,990 in the other months, and it was acquired almost entirely online. Its 90-day return rate was 32.4%, in line with the cohorts around it (29.8 to 32.8%). May 2020 reached 36.3%, the highest after burn-in.
