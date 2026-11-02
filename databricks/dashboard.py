"""Create or update the AI/BI dashboard, publish it, and save its definition to databricks/dashboard.lvdash.json.

Usage: python databricks/dashboard.py
"""
import csv, json, pathlib
from databricks.sdk.service.dashboards import Dashboard
from connect import client

HERE = pathlib.Path(__file__).resolve().parent
NAME = "H&M first-purchase retention"
T = "workspace.hm_retention"
PCT = {"type": "number-percent", "decimalPlaces": {"type": "max", "places": 1}}
# target = today's return rate plus the lift the experiment is sized to detect (exports/experiment.csv)
exp = next(csv.DictReader(open(HERE.parent / "exports" / "experiment.csv", encoding="utf8")))
TARGET = round(float(exp["baseline"]) + float(exp["mde_pp"]) / 100, 4)

datasets = {
    # 180 days is only knowable for first purchases by 2020-03-26, so later ones stay NULL and AVG skips them
    "first_orders": f"""SELECT *, CAST(returned_90d AS INT) AS came_back, {TARGET} AS target,
       CASE WHEN first_date <= DATE'2020-03-26' THEN CAST(returned_180d AS INT) END AS came_back_180,
       CASE items_band WHEN '1' THEN '01' WHEN '2' THEN '02' WHEN '3' THEN '03'
            WHEN '4-5' THEN '04-05' WHEN '6-9' THEN '06-09' ELSE '10+' END AS items_in_basket
FROM {T}.silver_first_orders""",
    "cohorts": f"SELECT date_format(cohort_month, 'yyyy-MM') AS cohort, k, retention_pct FROM {T}.gold_cohort_retention",
    "weekly_channel": f"SELECT * FROM {T}.gold_weekly_channel",
    "burn_in": f"SELECT * FROM {T}.gold_burn_in",
    "return_window": f"SELECT * FROM {T}.gold_return_window",
    "marginal_effects": f"""SELECT driver_group, CAST(pp_change AS DOUBLE) AS pp_change
FROM {T}.gold_marginal_effects""",
}

n = 0
def wid():
    global n
    n += 1
    return f"w{n}"


def place(widget, x, y, w, h):
    return {"widget": widget, "position": {"x": x, "y": y, "width": w, "height": h}}


def text(lines, x, y, w, h):
    # the lines are joined as-is, so each needs its own newline to stay a separate paragraph or list item
    return place({"name": wid(), "multilineTextboxSpec": {"lines": [l + "\n" for l in lines]}}, x, y, w, h)


def query(ds, fields):
    return [{"name": "main_query", "query": {"datasetName": ds, "disaggregated": False,
             "fields": [{"name": k, "expression": v} for k, v in fields.items()]}}]


def counter(title, ds, name, expr, x, y, w=2, h=3, fmt=None):
    enc = {"value": {"fieldName": name, "displayName": title}}
    if fmt:
        enc["value"]["format"] = fmt
    return place({"name": wid(), "queries": query(ds, {name: expr}),
                  "spec": {"version": 2, "widgetType": "counter", "encodings": enc,
                           "frame": {"showTitle": True, "title": title}}}, x, y, w, h)


def chart(kind, title, ds, x_field, y_field, y_expr, pos, color=None, y_fmt=None, x_type="categorical",
          y_title=None, x_title=None, horizontal=False):
    fields = {x_field: f"`{x_field}`", y_field: y_expr}
    if color:
        fields[color] = f"`{color}`"
    xe = {"fieldName": x_field, "scale": {"type": x_type}, "displayName": x_title or x_field}
    ye = {"fieldName": y_field, "scale": {"type": "quantitative"}, "displayName": y_title or y_field}
    if y_fmt:
        ye["format"] = y_fmt
    if horizontal:
        xe["scale"]["sort"] = {"by": "x"}   # order the bars by value, not alphabetically
    enc = {"x": ye, "y": xe} if horizontal else {"x": xe, "y": ye}
    if color:
        enc["color"] = {"fieldName": color, "scale": {"type": "categorical"}, "displayName": color}
    spec = {"version": 3, "widgetType": kind, "encodings": enc, "frame": {"showTitle": True, "title": title}}
    if kind == "bar" and color:
        spec["mark"] = {"layout": "group"}
    return place({"name": wid(), "queries": query(ds, fields), "spec": spec}, *pos)


def flt(title, field, x, y, w, kind="filter-multi-select"):
    return place({"name": wid(),
                  "queries": [{"name": "f_first_orders", "query": {"datasetName": "first_orders", "disaggregated": False,
                               "fields": [{"name": field, "expression": f"`{field}`"}]}}],
                  "spec": {"version": 2, "widgetType": kind,
                           "encodings": {"fields": [{"fieldName": field, "displayName": title, "queryName": "f_first_orders"}]},
                           "frame": {"showTitle": True, "title": title}}}, x, y, w, 2)


back = "avg(came_back)"
back_expr = "AVG(`came_back`)"
page1 = [
    text(["## Who comes back after their first H&M purchase?",
          "330,336 first-time buyers, Aug 2019 to Jun 2020. \"Came back\" means a second order within 90 days. "
          "Filters apply to every chart on this page except the cohort heatmap."], 0, 0, 6, 2),
    flt("First purchase month", "cohort_month", 0, 2, 2, "filter-date-range-picker"),
    flt("First channel", "first_channel", 2, 2, 1),
    flt("Age", "age_band", 3, 2, 1),
    flt("Department", "main_department", 4, 2, 1),
    flt("Club status", "club_status", 5, 2, 1),
    counter("First-time buyers", "first_orders", "buyers", "COUNT(`customer_id`)", 0, 4),
    counter("Back within 90 days", "first_orders", back, back_expr, 2, 4, fmt=PCT),
    counter("Back within 180 days (first bought by Mar 2020)", "first_orders", "avg(came_back_180)", "AVG(`came_back_180`)", 4, 4, fmt=PCT),
    # trend against target: two series on one line chart, both averaged per first-purchase month
    place({"name": wid(),
           "queries": query("first_orders", {"cohort_month": "`cohort_month`", back: back_expr, "avg(target)": "AVG(`target`)"}),
           "spec": {"version": 3, "widgetType": "line",
                    "encodings": {"x": {"fieldName": "cohort_month", "scale": {"type": "temporal"}, "displayName": "first purchase month"},
                                  "y": {"scale": {"type": "quantitative"}, "format": PCT,
                                        "fields": [{"fieldName": back, "displayName": "back within 90 days"},
                                                   {"fieldName": "avg(target)", "displayName": f"target ({TARGET:.1%})"}]}},
                    "frame": {"showTitle": True,
                              "title": f"Return-rate trend by first-purchase month vs target ({TARGET:.1%} = today + the 1 pp lift the experiment is sized for)"}}},
          0, 7, 6, 6),
    chart("bar", "Unfinished signup (PRE-CREATE) is the biggest warning sign", "first_orders",
          "club_status", back, back_expr, (0, 13, 3, 6), y_fmt=PCT, y_title="back within 90 days", x_title="club status"),
    chart("bar", "Broader first baskets come back more", "first_orders",
          "groups_band", back, back_expr, (3, 13, 3, 6), y_fmt=PCT, y_title="back within 90 days", x_title="product groups in first basket"),
    chart("bar", "Bigger first baskets come back more", "first_orders",
          "items_in_basket", back, back_expr, (0, 19, 3, 6), y_fmt=PCT, y_title="back within 90 days", x_title="items in first basket"),
    chart("bar", "Deal-only first baskets come back less", "first_orders",
          "markdown_band", back, back_expr, (3, 19, 3, 6), y_fmt=PCT, y_title="back within 90 days", x_title="markdown items in first basket"),
    chart("bar", "Store closures did not bring weaker online customers", "first_orders",
          "period", back, back_expr, (0, 25, 3, 6), color="first_channel", y_fmt=PCT, y_title="back within 90 days", x_title="when they first bought"),
    chart("bar", "Younger first-time buyers come back a little more", "first_orders",
          "age_band", back, back_expr, (3, 25, 3, 6), y_fmt=PCT, y_title="back within 90 days", x_title="age"),
    place({"name": wid(), "queries": query("cohorts", {"k": "`k`", "cohort": "`cohort`", "sum(retention_pct)": "SUM(`retention_pct`)"}),
           "spec": {"version": 3, "widgetType": "heatmap",
                    "encodings": {"x": {"fieldName": "k", "scale": {"type": "categorical"}, "displayName": "months after first month"},
                                  "y": {"fieldName": "cohort", "scale": {"type": "categorical"}, "displayName": "first purchase month"},
                                  "color": {"fieldName": "sum(retention_pct)", "scale": {"type": "quantitative"}, "displayName": "% buying again"}},
                    "frame": {"showTitle": True, "title": "% of each cohort buying again k months later: the drop happens right after the first purchase"}}},
          0, 31, 6, 8),
]

page2 = [
    text(["## How the data was prepared",
          "- **Order:** one customer, one day, one channel (the data has no order ID).",
          "- **Channel 1 = store:** its orders fall to zero while stores were closed in spring 2020.",
          "- **Cohorts start Aug 2019:** before that, most \"new\" customers were existing ones the data had not seen yet.",
          "- **90-day window:** catches about 60% of the returns that happen within a year, and keeps the spring 2020 cohorts measurable.",
          "- Prices are scaled by H&M, so no currency appears anywhere."], 0, 0, 6, 3),
    chart("line", "Weekly orders by channel: channel 1 drops to zero when stores close", "weekly_channel",
          "week", "sum(orders)", "SUM(`orders`)", (0, 4, 6, 6), color="channel", x_type="temporal", y_title="orders per week"),
    chart("bar", "Share of each month's buyers seen for the first time", "burn_in",
          "month", "sum(pct_new)", "SUM(`pct_new`)", (0, 10, 3, 6), x_type="temporal", y_title="% new"),
    chart("line", "90-day return rate of each month's 'new' buyers settles from Aug 2019", "burn_in",
          "month", "sum(return_90d_pct)", "SUM(`return_90d_pct`)", (3, 10, 3, 6), x_type="temporal", y_title="% back within 90 days"),
    chart("line", "% of first-time buyers who have ordered again, by day", "return_window",
          "day", "sum(pct_back)", "SUM(`pct_back`)", (0, 16, 3, 7), x_type="quantitative", y_title="% back"),
    chart("bar", "Percentage points more or less likely to come back, each driver with the others held constant", "marginal_effects",
          "driver_group", "sum(pp_change)", "SUM(`pp_change`)", (3, 16, 3, 7),
          y_title="pp vs reference group", x_title="driver", horizontal=True),
]

spec = {
    "datasets": [{"name": k, "displayName": k, "queryLines": [v]} for k, v in datasets.items()],
    "pages": [{"name": "who_comes_back", "displayName": "Who comes back?", "layout": page1},
              {"name": "data_prep", "displayName": "How the data was prepared", "layout": page2}],
}

w = client()
warehouse = next(iter(w.warehouses.list())).id
existing = [d for d in w.lakeview.list() if d.display_name == NAME]
body = Dashboard(display_name=NAME, serialized_dashboard=json.dumps(spec), warehouse_id=warehouse)
if existing:
    d = w.lakeview.update(existing[0].dashboard_id, body)
else:
    d = w.lakeview.create(body)
w.lakeview.publish(d.dashboard_id, embed_credentials=True, warehouse_id=warehouse)
saved = w.lakeview.get(d.dashboard_id)
(HERE / "dashboard.lvdash.json").write_text(json.dumps(json.loads(saved.serialized_dashboard), indent=2))
print("dashboard:", f"{w.config.host}/dashboardsv3/{d.dashboard_id}/published")
