# Deployment guide

Three ways to run this, from quickest to most production-like.

## 1. Local, Docker Compose (fastest way to see it working)

```bash
git clone https://github.com/Kornelius99/pipeline-cost-observatory.git
cd pipeline-cost-observatory
docker compose up --build
```

Dashboard: http://localhost:8501. Postgres is seeded via db/schema.sql with a couple of teams; the dashboard will show "no runs found" until you either run the collectors against a real Airflow/dbt or insert sample pipeline_runs rows yourself for a demo.

## 2. Render (real cloud deployment, free tier, no server management)

1. Fork this repository to your own GitHub account.
2. Sign in to your own Render account at render.com (you create and control this account, not me).
3. Go to the Blueprints page and click "New Blueprint Instance", then select your fork.
4. Render reads render.yaml and provisions a free Postgres database plus the dashboard web service automatically, wiring DATABASE_URL for you.
5. Point your own collector runs (from your laptop, a GitHub Action, or an Airflow task) at that same DATABASE_URL to start populating real data.

## 3. Kubernetes (Helm chart)

The chart in helm/pipeline-cost-observatory only deploys the dashboard - bring your own managed Postgres (RDS, Cloud SQL, Azure Database for PostgreSQL) rather than running a stateful database in-cluster.

```bash
kubectl create secret generic pipeline-cost-observatory-db \
  --from-literal=DATABASE_URL='postgresql://user:pass@your-managed-postgres:5432/pipeline_cost'

helm install pco ./helm/pipeline-cost-observatory
```

Then run db/schema.sql once against that database (e.g. via psql) before the collectors run for the first time.

## Scheduling the collectors

- Airflow: add collect_airflow_metadata.py as a final task in a lightweight "housekeeping" DAG that runs hourly, or trigger it from a webhook on DAG completion.
- dbt: add python ingestion/collect_dbt_metadata.py --run-results-path ./target/run_results.json as a step immediately after dbt build in your CI/CD job, while target/run_results.json still exists.

## Honesty note

I have written and reviewed this deployment configuration carefully, but have not personally executed a Render deploy or a live Helm install against a real cluster (I don't have a cloud account or Kubernetes cluster available to me). Please treat the first real deploy as a test run, and open an issue in this repo if something in these instructions doesn't match reality.
