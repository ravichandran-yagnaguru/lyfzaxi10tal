"""Syncs live Cloud Scheduler jobs to match schedule.yaml's weekly_schedule.
Run this whenever the posting schedule changes -- no Cloud Run redeploy
needed.

Groups by day pattern, not individual time slots: days that fire at the
exact same set of times share one job, with all of that day-group's hours
packed into a single cron entry's hour-list (e.g. "0 9,15 * * 1,4" fires at
both 9:00 and 15:00 on Monday and Thursday) -- a comma hour-list only means
what you'd expect when every combined time shares the same minute value, so
times are additionally split by minute within a day-group on the rare chance
they don't (e.g. "09:00" and "09:15" can't share one hour-list entry). For
the common case of on-the-hour times, this means one job per distinct
day-of-week pattern, not per time slot -- typically far fewer jobs than
grouping by time alone. app.py itself has no schedule-aware logic at all;
every Scheduler trigger is a real, intended post.

Usage: python manage_schedule.py
Requires GCP_PROJECT_ID, GCP_REGION, CLOUD_RUN_URL, SCHEDULER_SERVICE_ACCOUNT_EMAIL
to be set (only relevant once the Cloud Run service is actually deployed).
"""
import sys
from collections import defaultdict

import yaml
from google.cloud import scheduler_v1

import config

JOB_PREFIX = "concept-bot-post"

_CRON_DOW = {
    "sunday": 0, "monday": 1, "tuesday": 2, "wednesday": 3,
    "thursday": 4, "friday": 5, "saturday": 6,
}
_REVERSE_DOW = {v: k for k, v in _CRON_DOW.items()}


def _group_jobs(weekly_schedule: dict) -> list:
    """Returns a list of {"days": {dow,...}, "minute": int, "hours": {h,...}}
    -- one entry per Cloud Scheduler job needed. Days sharing an identical
    time-list become one job (or a few, only if their times don't all share
    a minute)."""
    # 1. group days by their exact (sorted) time-list signature
    by_signature = defaultdict(set)
    for day_name, times in weekly_schedule.items():
        signature = tuple(sorted(times))
        by_signature[signature].add(_CRON_DOW[day_name.lower()])

    # 2. within each day-group, split times by minute so one job's hour-list
    #    always shares a single minute value
    jobs = []
    for signature, days in by_signature.items():
        by_minute = defaultdict(set)
        for time_str in signature:
            hour, minute = time_str.split(":")
            by_minute[int(minute)].add(int(hour))
        for minute, hours in by_minute.items():
            jobs.append({"days": days, "minute": minute, "hours": hours})
    return jobs


def _job_name(client: scheduler_v1.CloudSchedulerClient, index: int) -> str:
    return client.job_path(config.GCP_PROJECT_ID, config.GCP_REGION, f"{JOB_PREFIX}-{index}")


def _build_job(client, index: int, job_spec: dict, timezone: str) -> scheduler_v1.Job:
    hour_field = ",".join(str(h) for h in sorted(job_spec["hours"]))
    dow_field = ",".join(str(d) for d in sorted(job_spec["days"]))
    return scheduler_v1.Job(
        name=_job_name(client, index),
        schedule=f"{job_spec['minute']} {hour_field} * * {dow_field}",
        time_zone=timezone,
        http_target=scheduler_v1.HttpTarget(
            uri=f"{config.CLOUD_RUN_URL}/post",
            http_method=scheduler_v1.HttpMethod.POST,
            oidc_token=scheduler_v1.OidcToken(
                service_account_email=config.SCHEDULER_SERVICE_ACCOUNT_EMAIL,
            ),
        ),
    )


def _describe(job_spec: dict) -> str:
    day_names = sorted(job_spec["days"], key=lambda d: (d - 1) % 7)  # Mon..Sun order
    days_label = ", ".join(_REVERSE_DOW[d] for d in day_names)
    times_label = ", ".join(f"{h:02d}:{job_spec['minute']:02d}" for h in sorted(job_spec["hours"]))
    return f"{times_label} on {days_label}"


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
    jobs_needed = _group_jobs(cfg["weekly_schedule"])

    if len(jobs_needed) > 3:
        print(f"This schedule collapses to {len(jobs_needed)} distinct Cloud Scheduler jobs; the "
              f"free tier covers 3, so the rest cost ~$0.10/month each "
              f"(~${(len(jobs_needed) - 3) * 0.10:.2f}/month total).")
    else:
        print(f"This schedule collapses to {len(jobs_needed)} Cloud Scheduler job(s) -- within "
              f"the free tier of 3, so $0/month for scheduling.")

    client = scheduler_v1.CloudSchedulerClient()
    parent = client.common_location_path(config.GCP_PROJECT_ID, config.GCP_REGION)
    existing = {job.name: job for job in client.list_jobs(parent=parent) if JOB_PREFIX in job.name}

    desired_names = set()
    for i, job_spec in enumerate(jobs_needed, start=1):
        job = _build_job(client, i, job_spec, timezone)
        desired_names.add(job.name)
        label = _describe(job_spec)
        if job.name in existing:
            print(f"Updating {job.name} -> {label} ({timezone})")
            client.update_job(job=job)
        else:
            print(f"Creating {job.name} -> {label} ({timezone})")
            client.create_job(parent=parent, job=job)

    for name in existing:
        if name not in desired_names:
            print(f"Deleting {name} (no longer in schedule.yaml)")
            client.delete_job(name=name)

    print("Schedule sync complete.")


if __name__ == "__main__":
    sync()
