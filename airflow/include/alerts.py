"""Failure alerts: Slack if a webhook is configured, otherwise the task log."""

import logging
import os

import requests

log = logging.getLogger(__name__)


def notify_failure(context):
    ti = context["ti"]
    message = (
        f":rotating_light: Airflow task failed: {ti.dag_id}.{ti.task_id}\n"
        f"Run: {ti.run_id}\n"
        f"Error: {context.get('exception')}"
    )

    webhook_url = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook_url:
        log.error(message)
        return

    try:
        requests.post(webhook_url, json={"text": message}, timeout=10).raise_for_status()
    except requests.RequestException:
        # A broken alert channel shouldn't hide the original failure, so just log it.
        log.exception("Could not send Slack alert. Original message: %s", message)
