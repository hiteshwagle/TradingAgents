"""Thread-safe, bounded analysis jobs with optional SQLite persistence."""

from __future__ import annotations

import logging
import os
import sqlite3
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


class _PersistentJobs:
    """Optional SQLite status journal; running graphs fail closed after restart."""

    def __init__(self, path: str):
        self.path = path
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with self.connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS jobs ("
                "analysis_id TEXT PRIMARY KEY, request_json TEXT NOT NULL, "
                "response_json TEXT NOT NULL, events_json TEXT NOT NULL)"
            )

    def connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def save(self, job: _Job) -> None:
        response = AnalysisJobManager._response(job).model_dump_json()
        events = JobEventsResponse(analysis_id=job.analysis_id, events=job.events).model_dump_json()
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO jobs VALUES (?,?,?,?)",
                (job.analysis_id, job.request.model_dump_json(), response, events),
            )

    def delete(self, analysis_id: str) -> None:
        with self.connect() as db:
            db.execute("DELETE FROM jobs WHERE analysis_id=?", (analysis_id,))

    def load(self, limit: int) -> list[_Job]:
        with self.connect() as db:
            rows = db.execute("SELECT * FROM jobs ORDER BY rowid DESC LIMIT ?", (limit,)).fetchall()
        jobs = []
        for analysis_id, request_json, response_json, events_json in reversed(rows):
            request = AnalysisRequest.model_validate_json(request_json)
            response = AnalysisJobResponse.model_validate_json(response_json)
            events = JobEventsResponse.model_validate_json(events_json)
            jobs.append(
                _Job(
                    analysis_id=analysis_id,
                    request=request,
                    status=response.status,
                    created_at=response.created_at,
                    updated_at=response.updated_at,
                    cancel_requested=response.cancel_requested,
                    result=response.result,
                    error=response.error,
                    events=events.events,
                )
            )
        return jobs


class AnalysisJobManager:
    """Run analyses asynchronously and optionally retain terminal state."""

    def __init__(
        self,
        runner=None,
        max_workers: int | None = None,
        max_jobs: int | None = None,
        persistence_path: str | None = None,
    ):
        workers = max_workers if max_workers is not None else int(
            os.getenv("TRADINGAGENTS_API_WORKERS") or "1"
        )
        self.max_jobs = max_jobs if max_jobs is not None else int(
            os.getenv("TRADINGAGENTS_API_MAX_JOBS") or "500"
        )
        if workers < 1 or self.max_jobs < 1:
            raise ValueError("API workers and max jobs must be positive")
        self.runner = runner or AnalysisRunner()
        self.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ta-analysis")
        self._jobs: dict[str, _Job] = {}
        self._lock = RLock()
        configured_path = persistence_path if persistence_path is not None else os.getenv(
            "TRADINGAGENTS_API_DB_PATH", ""
        )
        self._persistent = _PersistentJobs(configured_path) if configured_path else None
        if self._persistent:
            for job in self._persistent.load(self.max_jobs):
                self._jobs[job.analysis_id] = job
                if job.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                    job.status = JobStatus.FAILED
                    job.error = JobError(
                        code="server_restarted",
                        message="Analysis was interrupted by an API restart and must be submitted again",
                    )
                    self._event(job, job.status, "Analysis interrupted by server restart")

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
        if self._persistent:
            self._persistent.save(job)

    def _remove_oldest_terminal_job(self) -> bool:
        terminal = {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}
        for analysis_id, job in self._jobs.items():
            if job.status in terminal:
                del self._jobs[analysis_id]
                if self._persistent:
                    self._persistent.delete(analysis_id)
                return True
        return False

    def submit(self, request: AnalysisRequest) -> AnalysisJobResponse:
        with self._lock:
            if len(self._jobs) >= self.max_jobs and not self._remove_oldest_terminal_job():
                raise JobCapacityError("analysis queue is at capacity")
            job = _Job(analysis_id=f"ana_{uuid4().hex}", request=request)
            self._event(job, JobStatus.QUEUED, "Analysis queued")
            self._jobs[job.analysis_id] = job
            if self._persistent:
                self._persistent.save(job)
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
