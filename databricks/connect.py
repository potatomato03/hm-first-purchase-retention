"""Shared Databricks connection. Signs in through the browser (OAuth), so no token is stored in the repo.

Set DATABRICKS_HOST to your workspace URL first, e.g. https://dbc-xxxxxxxx-xxxx.cloud.databricks.com
"""
import os
from databricks.sdk import WorkspaceClient

CATALOG, SCHEMA, VOLUME = "workspace", "hm_retention", "raw"


def client():
    return WorkspaceClient(host=os.environ["DATABRICKS_HOST"], auth_type="external-browser")


if __name__ == "__main__":
    w = client()
    print("signed in as", w.current_user.me().user_name)
    for wh in w.warehouses.list():
        print("warehouse:", wh.name, wh.id, wh.state)
