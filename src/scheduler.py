"""
Scheduler compatibility wrapper for Reddit Plus v2.
Points directly to src.jobs.runner.
"""

from src.jobs.runner import JobRunner, job_runner, log_event, activity_logs

# Legacy alias
scheduler_manager = job_runner

__all__ = [
    "JobRunner",
    "job_runner",
    "scheduler_manager",
    "log_event",
    "activity_logs",
]