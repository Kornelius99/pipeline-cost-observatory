"""Editable pricing tables used by cost_engine/cost_calculator.py.

These are ILLUSTRATIVE unit costs, not official cloud list prices. Replace
them with your organization's actual contracted rates before trusting the
dollar figures this project produces.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ExecutorRate:
    executor_type: str
    usd_per_hour: float
    description: str


# $/hour by executor type. Add rows here as you onboard new compute types.
EXECUTOR_RATES = {
    "databricks_dbu_allpurpose": ExecutorRate(
        executor_type="databricks_dbu_allpurpose",
        usd_per_hour=0.55 * 4,  # illustrative: 4 DBU/hr cluster * $0.55/DBU
        description="Databricks all-purpose compute, small cluster",
    ),
    "databricks_dbu_jobs": ExecutorRate(
        executor_type="databricks_dbu_jobs",
        usd_per_hour=0.30 * 4,
        description="Databricks jobs compute, small cluster",
    ),
    "fargate_vcpu": ExecutorRate(
        executor_type="fargate_vcpu",
        usd_per_hour=0.04048 * 2,  # illustrative: 2 vCPU task
        description="AWS Fargate task, 2 vCPU / 4GB",
    ),
    "airflow_worker": ExecutorRate(
        executor_type="airflow_worker",
        usd_per_hour=0.10,
        description="Generic Airflow worker node amortized cost",
    ),
    "snowflake_credit": ExecutorRate(
        executor_type="snowflake_credit",
        usd_per_hour=2.00,  # illustrative: 1 credit/hour on X-Small warehouse
        description="Snowflake X-Small warehouse",
    ),
}


def get_rate(executor_type: str) -> ExecutorRate:
    """Look up the hourly rate for an executor type, raising a clear error
    if it hasn't been configured yet (fail loudly rather than silently
    reporting a $0 cost).
    """
    try:
        return EXECUTOR_RATES[executor_type]
    except KeyError as exc:
        known = ", ".join(sorted(EXECUTOR_RATES))
        raise ValueError(
            f"Unknown executor_type '{executor_type}'. Known types: {known}. "
            "Add it to pricing/pricing_tables.py first."
        ) from exc
