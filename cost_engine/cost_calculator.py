"""Core cost attribution and anomaly detection logic.

This module is intentionally dependency-light (just statistics from the
standard library) so it can be unit tested without a database or Spark
cluster - see tests/test_cost_calculator.py.
"""
from dataclasses import dataclass
from statistics import mean, pstdev
from typing import List, Optional

from pricing.pricing_tables import get_rate


@dataclass
class RunCost:
    run_id: int
    pipeline_name: str
    estimated_cost_usd: float
    pricing_rule: str
    is_anomaly: bool = False
    anomaly_score: Optional[float] = None


def estimate_run_cost(duration_sec: float, executor_type: str) -> float:
    """Estimate the $ cost of a single run given its duration and executor type."""
    rate = get_rate(executor_type)
    hours = duration_sec / 3600.0
    return round(hours * rate.usd_per_hour, 4)


def attribute_cost(run_id: int, pipeline_name: str, duration_sec: float, executor_type: str) -> RunCost:
    cost = estimate_run_cost(duration_sec, executor_type)
    return RunCost(
        run_id=run_id,
        pipeline_name=pipeline_name,
        estimated_cost_usd=cost,
        pricing_rule=executor_type,
    )


def flag_anomalies(costs: List[RunCost], history: List[float], z_threshold: float = 2.0) -> List[RunCost]:
    """Flag runs whose cost is more than z_threshold standard deviations above
    the mean of the provided historical cost series (a simple, explainable
    rolling z-score - not a forecasting model).

    `history` should be prior costs for the SAME pipeline, oldest first,
    NOT including the runs being scored.
    """
    if len(history) < 3:
        # Not enough history to compute a meaningful baseline yet.
        return costs

    mu = mean(history)
    sigma = pstdev(history) or 1e-9  # avoid division by zero for constant history

    for run_cost in costs:
        z = (run_cost.estimated_cost_usd - mu) / sigma
        run_cost.anomaly_score = round(z, 3)
        run_cost.is_anomaly = z > z_threshold

    return costs
