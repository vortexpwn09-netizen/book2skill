from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .core.compiler import build_skill_package


@dataclass
class ProcessingJob:
    title: str
    source_text: str
    job_id: str = field(default_factory=lambda: uuid4().hex)
    status: str = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    package: dict[str, Any] | None = None
    error: str | None = None

    def mark_running(self) -> None:
        self.status = "running"
        self.updated_at = datetime.now(timezone.utc)

    def mark_completed(self, package: dict[str, Any]) -> None:
        self.status = "completed"
        self.package = package
        self.updated_at = datetime.now(timezone.utc)

    def mark_failed(self, error: str) -> None:
        self.status = "failed"
        self.error = error
        self.updated_at = datetime.now(timezone.utc)


JOB_STORE: dict[str, ProcessingJob] = {}


def create_processing_job(title: str, source_text: str) -> ProcessingJob:
    job = ProcessingJob(title=title, source_text=source_text)
    JOB_STORE[job.job_id] = job
    return job


def process_job(job: ProcessingJob) -> dict[str, Any]:
    job.mark_running()
    try:
        package = build_skill_package(title=job.title, text=job.source_text, max_items=10)
        job.mark_completed(package)
        return package
    except Exception as exc:  # pragma: no cover - safety guard
        job.mark_failed(str(exc))
        raise


def get_job(job_id: str) -> ProcessingJob | None:
    return JOB_STORE.get(job_id)
