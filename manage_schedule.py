"""Syncs live Cloud Scheduler jobs to match schedule.yaml's weekly_schedule.
Run this whenever the posting schedule changes -- no Cloud Run redeploy
needed.

Groups purely by time-of-day: every day that fires at a given HH:MM shares
one Cloud Scheduler job (cron's day-of-week list), regardless of which days
they are -- so a time slot shared across several days of the week still only
costs one job. app.py itself has no schedule-aware logic at all; every
Scheduler trigger is a real, intended post.

Usage: python manage_schedule.py
Requires GCP_PROJECT_ID, GCP_REGION, CLOUD_RUN_URL, SCHEDULER_SERVICE_ACCOUNT_EMAIL
to be set (only relevant once the Cloud Run service is actually deployed).
"""
import sys

import yaml
from google.cloud import scheduler_v1

import config

JOB_PREFIX = "concept-bot-post"

_CRON_DOW = {
    "sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3,
    "thursday": 4, "friday": 5, "saturday": 6,
}


def _group_by_time(weekly_schedule: dict) -> dict:
    """{"09:00": {1, 4}, "11:00": {2, 3, 5, 6, 0}, ...} -- time -> set of
    cron day-of-week numbers that fire at that time."""
    by_time: dict = {}
    for day_name, times in weekly_schedule.items():
        dow = _CRON_DOW[day_name.lower()]
        for time_str in times:
            by_time.setdefault(time_str, set()).add(dow)
    return by_time


def _job_name(client: scheduler_v1.CloudSchedulerClient, index: int) -> str:
    return client.job_path(config.GCP_PROJECT_ID, config.GCP_REGION, f"{JOB_PREFIX}-{index}")


def _build_job(client, index: int, time_str: str, days: set, timezone: str) -> scheduler_v1.Job:
    hour, minute = time_str.split(":")
    dow_field = ",".join(str(d) for d in sorted(days))
    return scheduler_v1.Job(
        name=_job_name(client, index),
        schedule=f"{int(minute)} {int(hour)} * * {dow_field}",
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
    timezone = cfg["timezone"]
    by_time = _group_by_time(cfg["weekly_schedule"])

    if len(by_time) > 3:
        print(f"This schedule collapses to {len(by_time)} distinct Cloud Scheduler jobs; the "
              f"free tier covers 3, so the rest cost ~$0.10/month each "
              f"(~${(len(by_time) - 3) * 0.10:.2f}/month total).")

    client = scheduler_v1.CloudSchedulerClient()
    parent = client.common_location_path(config.GCP_PROJECT_ID, config.GCP_REGION)
    existing = {job.name: job for job in client.list_jobs(parent=parent) if JOB_PREFIX in job.name}

    desired_names = set()
    for i, (time_str, days) in enumerate(sorted(by_time.items()), start=1):
        job = _build_job(client, i, time_str, days, timezone)
        desired_names.add(job.name)
        day_names = sorted(days, key=lambda d: (d - 1) % 7)  # Mon..Sun order
        reverse_dow = {v: k for k, v in _CRON_DOW.items()}
        label = ", ".join(reverse_dow[d] for d in day_names)
        if job.name in existing:
            print(f"Updating {job.name} -> {time_str} {timezone} on {label}")
            client.update_job(job=job)
        else:
            print(f"Creating {job.name} -> {time_str} {timezone} on {label}")
            client.create_job(parent=parent, job=job)

    for name in existing:
        if name not in desired_names:
            print(f"Deleting {name} (no longer in schedule.yaml)")
            client.delete_job(name=name)

    print("Schedule sync complete.")


if __name__ == "__main__":
    sync()
