"""Create (or reset) the daily job that rebuilds the silver tables, then the gold tables, and run it once.

Usage: python databricks/job.py
"""
import pathlib
from databricks.sdk.service import jobs
from databricks.sdk.service.workspace import ImportFormat
from connect import client

HERE = pathlib.Path(__file__).resolve().parent
NAME = "hm_retention_refresh"
w = client()
warehouse = next(iter(w.warehouses.list())).id
folder = f"/Users/{w.current_user.me().user_name}/hm_retention"

# the job runs the same SQL files that live in this repo
w.workspace.mkdirs(folder)
for name in ["02_silver.sql", "03_gold.sql"]:
    with open(HERE / "sql" / name, "rb") as f:
        w.workspace.upload(f"{folder}/{name}", f, format=ImportFormat.RAW, overwrite=True)


def sql_task(key, file, after=None):
    return jobs.Task(task_key=key,
                     depends_on=[jobs.TaskDependency(task_key=after)] if after else None,
                     sql_task=jobs.SqlTask(warehouse_id=warehouse,
                                           file=jobs.SqlTaskFile(path=f"{folder}/{file}", source=jobs.Source.WORKSPACE)))


settings = jobs.JobSettings(
    name=NAME,
    tasks=[sql_task("silver", "02_silver.sql"), sql_task("gold", "03_gold.sql", after="silver")],
    schedule=jobs.CronSchedule(quartz_cron_expression="0 0 6 * * ?", timezone_id="Asia/Kolkata",
                               pause_status=jobs.PauseStatus.UNPAUSED),
    max_concurrent_runs=1,
)
existing = next(iter(w.jobs.list(name=NAME)), None)
if existing:
    w.jobs.reset(existing.job_id, new_settings=settings)
    job_id = existing.job_id
else:
    job_id = w.jobs.create(**settings.as_shallow_dict()).job_id
run = w.jobs.run_now(job_id).result()
print(f"job {job_id}: run {run.run_id} finished {run.state.result_state.value}")
