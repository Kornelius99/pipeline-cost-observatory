"""Collect Airflow DAG run history via the Airflow REST API and load it
into the pipeline_runs table.

Usage:
    export AIRFLOW_BASE_URL=http://localhost:8080
    export AIRFLOW_USERNAME=admin
    export AIRFLOW_PASSWORD=admin
    export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pipeline_cost
    python ingestion/collect_airflow_metadata.py --lookback-days 7

Each DAG run's cost is estimated using the 'airflow_worker' executor_type by
default. Tag your DAGs with 'team:<name>' and 'executor:<type>' to get more
accurate team/executor attribution - see README for details.
"""
import argparse
import os
from datetime import datetime, timedelta, timezone

import psycopg2
import psycopg2.extras
import requests


def fetch_dag_runs(base_url: str, auth: tuple, since: datetime) -> list:
    """Page through /api/v1/dags/~/dagRuns filtering by execution_date."""
    runs = []
    offset = 0
    limit = 100
    while True:
        resp = requests.get(
            f"{base_url}/api/v1/dags/~/dagRuns",
            auth=auth,
            params={
                "limit": limit,
                "offset": offset,
                "execution_date_gte": since.isoformat(),
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("dag_runs", [])
        runs.extend(batch)
        if len(batch) < limit:
            break
        offset += limit
    return runs


def parse_tags(dag_id: str, base_url: str, auth: tuple) -> dict:
    """Fetch a DAG's tags and pull out team:/executor: hints if present."""
    resp = requests.get(f"{base_url}/api/v1/dags/{dag_id}", auth=auth, timeout=30)
    resp.raise_for_status()
    tags = [t["name"] for t in resp.json().get("tags", [])]
    team = next((t.split(":", 1)[1] for t in tags if t.startswith("team:")), "unassigned")
    executor = next((t.split(":", 1)[1] for t in tags if t.startswith("executor:")), "airflow_worker")
    return {"team": team, "executor_type": executor}


def upsert_runs(conn, dag_runs: list, base_url: str, auth: tuple) -> int:
    tag_cache: dict = {}
    inserted = 0
    with conn.cursor() as cur:
        for run in dag_runs:
            if not run.get("end_date"):
                continue  # still running, nothing to cost yet
            dag_id = run["dag_id"]
            if dag_id not in tag_cache:
                tag_cache[dag_id] = parse_tags(dag_id, base_url, auth)
            meta = tag_cache[dag_id]

            cur.execute(
                """
                INSERT INTO teams (team_name) VALUES (%s)
                ON CONFLICT (team_name) DO NOTHING
                """,
                (meta["team"],),
            )
            cur.execute(
                """
                INSERT INTO pipeline_runs
                    (source, pipeline_name, team_id, executor_type, started_at, ended_at, raw_metadata)
                VALUES (
                    'airflow', %s,
                    (SELECT team_id FROM teams WHERE team_name = %s),
                    %s, %s, %s, %s
                )
                """,
                (
                    dag_id,
                    meta["team"],
                    meta["executor_type"],
                    run["start_date"],
                    run["end_date"],
                    psycopg2.extras.Json(run),
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lookback-days", type=int, default=7)
    args = parser.parse_args()

    base_url = os.environ["AIRFLOW_BASE_URL"].rstrip("/")
    auth = (os.environ["AIRFLOW_USERNAME"], os.environ["AIRFLOW_PASSWORD"])
    database_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pipeline_cost")

    since = datetime.now(timezone.utc) - timedelta(days=args.lookback_days)
    dag_runs = fetch_dag_runs(base_url, auth, since)

    conn = psycopg2.connect(database_url)
    try:
        inserted = upsert_runs(conn, dag_runs, base_url, auth)
    finally:
        conn.close()

    print(f"Inserted {inserted} Airflow run records from the last {args.lookback_days} day(s).")


if __name__ == "__main__":
    main()
