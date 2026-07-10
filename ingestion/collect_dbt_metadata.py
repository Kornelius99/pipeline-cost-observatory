"""Parse a dbt run_results.json artifact and load per-model run stats into
the pipeline_runs table.

Usage:
    export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/pipeline_cost
    python ingestion/collect_dbt_metadata.py --run-results-path ./target/run_results.json --team analytics

Every dbt model run is currently costed with the 'snowflake_credit' executor
type by default (change with --executor-type) since dbt itself doesn't know
what warehouse compute it ran on - see README for how to make this precise
by joining against your warehouse's query history.
"""
import argparse
import json
import os
from datetime import datetime

import psycopg2
import psycopg2.extras


def load_run_results(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def extract_model_runs(run_results: dict) -> list:
    """Return a list of dicts: {node_name, started_at, ended_at, status}."""
    runs = []
    for result in run_results.get("results", []):
        timing = result.get("timing", [])
        execute_step = next((t for t in timing if t.get("name") == "execute"), None)
        if not execute_step:
            continue
        runs.append(
            {
                "node_name": result["unique_id"].split(".")[-1],
                "started_at": execute_step["started_at"],
                "ended_at": execute_step["completed_at"],
                "status": result.get("status"),
            }
        )
    return runs


def insert_runs(conn, runs: list, team: str, executor_type: str, raw: dict) -> int:
    inserted = 0
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO teams (team_name) VALUES (%s) ON CONFLICT (team_name) DO NOTHING",
            (team,),
        )
        for run in runs:
            if run["status"] != "success":
                continue  # only cost successful runs
            cur.execute(
                """
                INSERT INTO pipeline_runs
                    (source, pipeline_name, team_id, executor_type, started_at, ended_at, raw_metadata)
                VALUES (
                    'dbt', %s,
                    (SELECT team_id FROM teams WHERE team_name = %s),
                    %s, %s, %s, %s
                )
                """,
                (
                    run["node_name"],
                    team,
                    executor_type,
                    run["started_at"],
                    run["ended_at"],
                    psycopg2.extras.Json(run),
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-results-path", required=True)
    parser.add_argument("--team", default="analytics")
    parser.add_argument("--executor-type", default="snowflake_credit")
    args = parser.parse_args()

    database_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pipeline_cost")

    run_results = load_run_results(args.run_results_path)
    runs = extract_model_runs(run_results)

    conn = psycopg2.connect(database_url)
    try:
        inserted = insert_runs(conn, runs, args.team, args.executor_type, run_results)
    finally:
        conn.close()

    print(f"Inserted {inserted} dbt model run records from {args.run_results_path}.")


if __name__ == "__main__":
    main()
