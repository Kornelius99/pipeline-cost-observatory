"""Streamlit dashboard for pipeline-cost-observatory.

Run with: streamlit run dashboard/app.py
(the docker-compose service does this automatically).
"""
import os

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/pipeline_cost")

st.set_page_config(page_title="Pipeline Cost Observatory", layout="wide")


@st.cache_resource
def get_engine():
    return create_engine(DATABASE_URL)


def load_runs() -> pd.DataFrame:
    engine = get_engine()
    query = """
        SELECT
            r.run_id, r.source, r.pipeline_name, t.team_name, r.executor_type,
            r.started_at, r.ended_at, r.duration_sec,
            c.estimated_cost_usd, c.is_anomaly, c.anomaly_score
        FROM pipeline_runs r
        LEFT JOIN teams t ON t.team_id = r.team_id
        LEFT JOIN cost_estimates c ON c.run_id = r.run_id
        ORDER BY r.started_at DESC
    """
    return pd.read_sql(query, engine)


st.title("Pipeline Cost Observatory")
st.caption("Self-hosted cost attribution for Airflow + dbt. Pricing is illustrative - see pricing/pricing_tables.py.")

df = load_runs()

if df.empty:
    st.warning("No runs found yet. Run the ingestion collectors, or use the seeded sample data from db/schema.sql.")
else:
    col1, col2, col3 = st.columns(3)
    col1.metric("Total estimated cost", f"$ {df['estimated_cost_usd'].fillna(0).sum():,.2f}")
    col2.metric("Runs tracked", f"{len(df):,}")
    col3.metric("Flagged anomalies", int(df["is_anomaly"].fillna(False).sum()))

    st.subheader("Cost by team")
    by_team = df.groupby("team_name", dropna=False)["estimated_cost_usd"].sum().sort_values(ascending=False)
    st.bar_chart(by_team)

    st.subheader("Most expensive pipelines / models")
    by_pipeline = (
        df.groupby("pipeline_name")["estimated_cost_usd"].sum().sort_values(ascending=False).head(15)
    )
    st.bar_chart(by_pipeline)

    st.subheader("Cost over time")
    df["started_date"] = pd.to_datetime(df["started_at"]).dt.date
    trend = df.groupby("started_date")["estimated_cost_usd"].sum()
    st.line_chart(trend)

    st.subheader("Flagged anomalies")
    anomalies = df[df["is_anomaly"] == True]  # noqa: E712
    if anomalies.empty:
        st.info("No anomalies flagged yet.")
    else:
        st.dataframe(
            anomalies[["pipeline_name", "team_name", "started_at", "estimated_cost_usd", "anomaly_score"]]
        )

    with st.expander("Raw run data"):
        st.dataframe(df)
