"""Thread-safe, bounded in-process analysis job manager."""

from __future__ import annotations

import logging
import os
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from .models import (
    AnalysisJobResponse,
    AnalysisRequest,
    AnalysisResult,
    JobError,
    JobEvent,
    JobEventsResponse,
    JobStatus,
)
from .runner import AnalysisRunner

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class _Job:
    analysis_id: str
    request: AnalysisRequest
    status: JobStatus = JobStatus.QUEUED
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    cancel_requested: bool = False
    result: AnalysisResult | None = None
    error: JobError | None = None
    events: list[JobEvent] = field(default_factory=list)
    future: Future | None = None


class JobCapacityError(RuntimeError):
    pass


class AnalysisJobManager:
    """Runs analyses asynchronously; state lasts for this process only."""

    def __init__(self, runner=None, max_workers: int | None = None, max_jobs: int | None = None):
        workers = max_workers or int(os.getenv("TRADINGAGENTS_API_WORKERS", "1"))
        self.max_jobs = max_jobs or int(os.getenv("TRADINGAGENTS_API_MAX_JOBS", "500"))
        if workers < 1 or self.max_jobs < 1:
            raise ValueError("API workers and max jobs must be positive")
        self.runner = runner or AnalysisRunner()
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ta-analysis")
        self._jobs: dict[str, _Job] = {}
        self._lock = RLock()

    def _event(self, job: _Job, status: JobStatus, message: str) -> None:
        job.updated_at = _now()
        job.events.append(
            JobEvent(
                sequence=len(job.events) + 1,
                timestamp=job.updated_at,
                status=status,
                message=message,
            )
        )

    def _remove_oldest_terminal_job(self) -> bool:
        terminal = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
        for analysis_id, job in self._jobs.items():
            if job.status in terminal:
                del self._jobs[analysis_id]
                return True
        return False

    def submit(self, request: AnalysisRequest) -> AnalysisJobResponse:
        with self._lock:
            if len(self._jobs) >= self.max_jobs and not self._remove_oldest_terminal_job():
                raise JobCapacityError("analysis queue is at capacity")
            job = _Job(analysis_id=f"ana_{uuid4().hex}", request=request)
            self._event(job, JobStatus.QUEUED, "Analysis queued")
            self._jobs[job.analysis_id] = job
            job.future = self.executor.submit(self._execute, job.analysis_id)
            return self._response(job)

    def _execute(self, analysis_id: str) -> None:
        with self._lock:
            job = self._jobs[analysis_id]
            if job.cancel_requested:
                job.status = JobStatus.CANCELLED
                self._event(job, job.status, "Analysis cancelled before execution")
                return
            job.status = JobStatus.RUNNING
            self._event(job, job.status, "Analysis started")

        try:
            result = self.runner.run(job.request)
        except Exception:
            logger.exception("TradingAgents analysis failed for job %s", analysis_id)
            with self._lock:
                if job.cancel_requested:
                    job.status = JobStatus.CANCELLED
                    self._event(job, job.status, "Analysis cancelled")
                else:
                    job.status = JobStatus.FAILED
                    job.error = JobError(
                        code="analysis_failed",
                        message=f"Analysis failed; inspect server logs for job {analysis_id}",
                    )
                    self._event(job, job.status, "Analysis failed")
            return

        with self._lock:
            if job.cancel_requested:
                job.status = JobStatus.CANCELLED
                self._event(job, job.status, "Analysis cancelled; completed result discarded")
            else:
                job.status = JobStatus.COMPLETED
                job.result = result
                self._event(job, job.status, "Analysis completed")

    def get(self, analysis_id: str) -> AnalysisJobResponse | None:
        with self._lock:
            job = self._jobs.get(analysis_id)
            return self._response(job) if job else None

    def events(self, analysis_id: str) -> JobEventsResponse | None:
        with self._lock:
            job = self._jobs.get(analysis_id)
            if not job:
                return None
            return JobEventsResponse(analysis_id=analysis_id, events=list(job.events))

    def cancel(self, analysis_id: str) -> AnalysisJobResponse | None:
        with self._lock:
            job = self._jobs.get(analysis_id)
            if not job:
                return None
            if job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
                return self._response(job)
            job.cancel_requested = True
            if job.future is not None and job.future.cancel():
                job.status = JobStatus.CANCELLED
                self._event(job, job.status, "Analysis cancelled before execution")
            else:
                self._event(job, job.status, "Cancellation requested")
            return self._response(job)

    def counts(self) -> dict[str, int]:
        with self._lock:
            return {status.value: sum(j.status == status for j in self._jobs.values()) for status in JobStatus}

    @staticmethod
    def _response(job: _Job) -> AnalysisJobResponse:
        return AnalysisJobResponse(
            analysis_id=job.analysis_id,
            status=job.status,
            created_at=job.created_at,
            updated_at=job.updated_at,
            cancel_requested=job.cancel_requested,
            result=job.result,
            error=job.error,
        )

    def shutdown(self) -> None:
        self.executor.shutdown(wait=False, cancel_futures=True)
