import pytest

from cost_engine.cost_calculator import (
    RunCost,
    attribute_cost,
    estimate_run_cost,
    flag_anomalies,
)


def test_estimate_run_cost_basic():
    # 1 hour on airflow_worker at $0.10/hr
    cost = estimate_run_cost(duration_sec=3600, executor_type="airflow_worker")
    assert cost == pytest.approx(0.10, rel=1e-6)


def test_estimate_run_cost_half_hour():
    cost = estimate_run_cost(duration_sec=1800, executor_type="airflow_worker")
    assert cost == pytest.approx(0.05, rel=1e-6)


def test_estimate_run_cost_unknown_executor_raises():
    with pytest.raises(ValueError):
        estimate_run_cost(duration_sec=3600, executor_type="quantum_computer")


def test_attribute_cost_returns_run_cost():
    result = attribute_cost(run_id=1, pipeline_name="orders_dag", duration_sec=3600, executor_type="airflow_worker")
    assert isinstance(result, RunCost)
    assert result.run_id == 1
    assert result.pipeline_name == "orders_dag"
    assert result.pricing_rule == "airflow_worker"
    assert result.estimated_cost_usd == pytest.approx(0.10, rel=1e-6)


def test_flag_anomalies_insufficient_history_returns_unmodified():
    costs = [RunCost(run_id=1, pipeline_name="p", estimated_cost_usd=100.0, pricing_rule="x")]
    result = flag_anomalies(costs, history=[1.0, 2.0])
    assert result[0].is_anomaly is False
    assert result[0].anomaly_score is None


def test_flag_anomalies_detects_spike():
    history = [10.0, 11.0, 9.0, 10.5, 9.5, 10.0]
    costs = [RunCost(run_id=1, pipeline_name="p", estimated_cost_usd=50.0, pricing_rule="x")]
    result = flag_anomalies(costs, history=history, z_threshold=2.0)
    assert result[0].is_anomaly is True
    assert result[0].anomaly_score > 2.0


def test_flag_anomalies_no_spike_not_flagged():
    history = [10.0, 11.0, 9.0, 10.5, 9.5, 10.0]
    costs = [RunCost(run_id=1, pipeline_name="p", estimated_cost_usd=10.2, pricing_rule="x")]
    result = flag_anomalies(costs, history=history, z_threshold=2.0)
    assert result[0].is_anomaly is False
