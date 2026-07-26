"""Syncs live Cloud Scheduler jobs to match schedule.yaml. Run this whenever
the posting schedule changes — no Cloud Run redeploy needed.

Usage: python manage_schedule.py
Requires GCP_PROJECT_ID, GCP_REGION, CLOUD_RUN_URL, SCHEDULER_SERVICE_ACCOUNT_EMAIL
to be set (only relevant once the Cloud Run service is actually deployed).
"""
import sys

import yaml
from google.cloud import scheduler_v1

import config

JOB_PREFIX = "concept-bot-post"


def _job_name(client: scheduler_v1.CloudSchedulerClient, index: int) -> str:
    return client.job_path(config.GCP_PROJECT_ID, config.GCP_REGION, f"{JOB_PREFIX}-{index}")


def _build_job(client, index: int, time_str: str, timezone: str) -> scheduler_v1.Job:
    hour, minute = time_str.split(":")
    return scheduler_v1.Job(
        name=_job_name(client, index),
        schedule=f"{int(minute)} {int(hour)} * * *",
        time_zone=timezone,
        http_target=scheduler_v1.HttpTarget(
            uri=f"{config.CLOUD_RUN_URL}/post",
            http_method=scheduler_v1.HttpMethod.POST,
            oidc_token=scheduler_v1.OidcToken(
                service_account_email=config.SCHEDULER_SERVICE_ACCOUNT_EMAIL,
            ),
        ),
    )


def sync():
    required = [
        ("GCP_PROJECT_ID", config.GCP_PROJECT_ID),
        ("CLOUD_RUN_URL", config.CLOUD_RUN_URL),
        ("SCHEDULER_SERVICE_ACCOUNT_EMAIL", config.SCHEDULER_SERVICE_ACCOUNT_EMAIL),
    ]
    missing = [name for name, val in required if not val]
    if missing:
        print(f"Missing required env vars: {', '.join(missing)}. Set these once the Cloud Run "
              f"service is deployed, before running this script.")
        sys.exit(1)

    with open("schedule.yaml") as f:
        cfg = yaml.safe_load(f)
    times = cfg["times"]
    timezone = cfg["timezone"]

    if len(times) > 3:
        print(f"schedule.yaml lists {len(times)} times; Cloud Scheduler's free tier covers 3 "
              f"jobs/month, so job(s) beyond the 3rd will incur a small charge (~$0.10/mo each).")

    client = scheduler_v1.CloudSchedulerClient()
    parent = client.common_location_path(config.GCP_PROJECT_ID, config.GCP_REGION)
    existing = {job.name: job for job in client.list_jobs(parent=parent) if JOB_PREFIX in job.name}

    desired_names = set()
    for i, time_str in enumerate(times, start=1):
        job = _build_job(client, i, time_str, timezone)
        desired_names.add(job.name)
        if job.name in existing:
            print(f"Updating {job.name} -> {time_str} {timezone}")
            client.update_job(job=job)
        else:
            print(f"Creating {job.name} -> {time_str} {timezone}")
            client.create_job(parent=parent, job=job)

    for name in existing:
        if name not in desired_names:
            print(f"Deleting {name} (no longer in schedule.yaml)")
            client.delete_job(name=name)

    print("Schedule sync complete.")


if __name__ == "__main__":
    sync()
