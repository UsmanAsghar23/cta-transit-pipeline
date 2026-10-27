"""Every DAG must import cleanly, be tagged, and retry at least twice."""

import pytest
from airflow.models import DagBag

DAG_BAG = DagBag(include_examples=False)


def test_no_import_errors():
    assert not DAG_BAG.import_errors, DAG_BAG.import_errors


@pytest.mark.parametrize("dag_id", list(DAG_BAG.dags))
def test_dag_has_tags_and_retries(dag_id):
    dag = DAG_BAG.dags[dag_id]
    assert dag.tags, f"{dag_id} has no tags"
    assert dag.default_args.get("retries", 0) >= 2, f"{dag_id} needs retries >= 2"
