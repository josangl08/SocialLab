"""
Scheduler API Routes

Endpoints for scheduling, canceling, and managing automated post publishing.

Author: SocialLab
Date: 2025-01-16
"""

from datetime import datetime
from typing import Optional
import logging

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, validator

from services.scheduler.post_scheduler import PostScheduler
from database.supabase_client import get_supabase_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])


def get_scheduler() -> PostScheduler:
    """Get the singleton PostScheduler instance."""
    return PostScheduler()


# Pydantic models for request/response
class SchedulePostRequest(BaseModel):
    """Request model for scheduling a post."""
    post_id: int = Field(..., gt=0, description="ID of the post to schedule")
    scheduled_time: datetime = Field(
        ...,
        description="When to publish (ISO 8601 format, UTC timezone)"
    )
    retry_on_failure: bool = Field(
        default=True,
        description="Whether to retry on failure"
    )

    @validator('scheduled_time')
    def validate_future_time(cls, v):
        """Ensure scheduled time is in the future."""
        if v <= datetime.now():
            raise ValueError("scheduled_time must be in the future")
        return v


class SchedulePostResponse(BaseModel):
    """Response model for scheduled post."""
    job_id: str
    post_id: int
    scheduled_time: datetime
    status: str
    message: str


class ReschedulePostRequest(BaseModel):
    """Request model for rescheduling a post."""
    new_scheduled_time: datetime = Field(
        ...,
        description="New publication time (ISO 8601 format, UTC timezone)"
    )

    @validator('new_scheduled_time')
    def validate_future_time(cls, v):
        """Ensure scheduled time is in the future."""
        if v <= datetime.now():
            raise ValueError("new_scheduled_time must be in the future")
        return v


class JobStatusResponse(BaseModel):
    """Response model for job status."""
    job_id: str
    post_id: int
    scheduled_time: datetime
    status: str
    retry_count: int
    error_message: Optional[str]


@router.post("/schedule", response_model=SchedulePostResponse)
async def schedule_post(request: SchedulePostRequest):
    """
    Schedule a post for future publication.

    This endpoint schedules a post to be automatically published
    at the specified time using APScheduler.

    **Requirements:**
    - Post must exist in the database
    - Post must have a valid media_url
    - scheduled_time must be in the future

    **Process:**
    1. Validates post exists and has media
    2. Creates job in APScheduler
    3. Stores job in scheduled_jobs table
    4. Updates post status to 'scheduled'

    **Example:**
    ```json
    {
      "post_id": 123,
      "scheduled_time": "2025-01-17T10:00:00Z",
      "retry_on_failure": true
    }
    ```
    """
    try:
        logger.info(
            f"Scheduling post {request.post_id} for {request.scheduled_time}"
        )

        # Schedule the post
        job_id = get_scheduler().schedule_post(
            post_id=request.post_id,
            scheduled_time=request.scheduled_time,
            retry_on_failure=request.retry_on_failure
        )

        return SchedulePostResponse(
            job_id=job_id,
            post_id=request.post_id,
            scheduled_time=request.scheduled_time,
            status="scheduled",
            message=f"Post scheduled successfully for {request.scheduled_time}"
        )

    except ValueError as e:
        logger.error(f"Validation error scheduling post: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Error scheduling post: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to schedule post: {str(e)}"
        )


@router.delete("/cancel/{post_id}")
async def cancel_scheduled_post(post_id: int):
    """
    Cancel a scheduled post.

    Removes the post from the scheduling queue and reverts
    the post status to 'draft'.

    **Args:**
    - post_id: ID of the post to cancel

    **Returns:**
    - Success message if cancelled
    - 404 if post not found
    - 500 if cancellation fails
    """
    try:
        logger.info(f"Cancelling scheduled post {post_id}")

        success = get_scheduler().cancel_scheduled_post(post_id)

        if not success:
            raise HTTPException(
                status_code=404,
                detail=f"No scheduled job found for post {post_id}"
            )

        return {
            "success": True,
            "post_id": post_id,
            "message": "Post cancelled successfully"
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error cancelling post {post_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to cancel post: {str(e)}"
        )


@router.put("/reschedule/{post_id}")
async def reschedule_post(post_id: int, request: ReschedulePostRequest):
    """
    Reschedule a post to a new time.

    Cancels the existing schedule and creates a new one
    with the updated time.

    **Args:**
    - post_id: ID of the post to reschedule
    - new_scheduled_time: New publication time

    **Example:**
    ```json
    {
      "new_scheduled_time": "2025-01-18T15:00:00Z"
    }
    ```
    """
    try:
        logger.info(
            f"Rescheduling post {post_id} to {request.new_scheduled_time}"
        )

        # Reschedule the post
        job_id = get_scheduler().reschedule_post(
            post_id=post_id,
            new_scheduled_time=request.new_scheduled_time
        )

        return {
            "success": True,
            "job_id": job_id,
            "post_id": post_id,
            "new_scheduled_time": request.new_scheduled_time,
            "message": "Post rescheduled successfully"
        }

    except Exception as e:
        logger.error(f"Error rescheduling post {post_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reschedule post: {str(e)}"
        )


@router.get("/jobs")
async def get_scheduled_jobs(status: Optional[str] = None):
    """
    Get list of scheduled jobs.

    Returns all scheduled jobs, optionally filtered by status.

    **Query Parameters:**
    - status (optional): Filter by status
      - pending: Jobs waiting to execute
      - running: Jobs currently executing
      - completed: Jobs that finished successfully
      - failed: Jobs that failed after max retries
      - cancelled: Jobs that were cancelled
      - retrying: Jobs that failed and are retrying

    **Example:**
    ```
    GET /api/scheduler/jobs?status=pending
    ```
    """
    try:
        jobs = get_scheduler().get_scheduled_jobs(status=status)

        return {
            "count": len(jobs),
            "jobs": jobs
        }

    except Exception as e:
        logger.error(f"Error getting scheduled jobs: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scheduled jobs: {str(e)}"
        )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str):
    """
    Get status of a specific job.

    Returns detailed information about a scheduled job.

    **Args:**
    - job_id: The job ID (e.g., "post_123")

    **Returns:**
    - Job details including status, retry count, and error message
    - 404 if job not found
    """
    try:
        job = get_scheduler().get_job_status(job_id)

        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Job {job_id} not found"
            )

        return JobStatusResponse(
            job_id=job['job_id'],
            post_id=job['post_id'],
            scheduled_time=datetime.fromisoformat(
                job['scheduled_time'].replace('Z', '+00:00')
            ),
            status=job['status'],
            retry_count=job['retry_count'],
            error_message=job.get('error_message')
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error getting job status for {job_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job status: {str(e)}"
        )


@router.get("/posts/{post_id}/status")
async def get_post_schedule_status(post_id: int):
    """
    Get scheduling status for a specific post.

    Returns information about whether a post is scheduled
    and when it will be published.

    **Args:**
    - post_id: ID of the post

    **Returns:**
    - is_scheduled: Whether the post is currently scheduled
    - job_id: Job ID if scheduled
    - scheduled_time: When it will publish
    - status: Current status
    """
    try:
        supabase = get_supabase_client()

        # Get post data
        post_result = supabase.table('posts')\
            .select('status, scheduled_at')\
            .eq('id', post_id)\
            .single()\
            .execute()

        if not post_result.data:
            raise HTTPException(
                status_code=404,
                detail=f"Post {post_id} not found"
            )

        post_data = post_result.data

        # Get job data if scheduled
        job_result = supabase.table('scheduled_jobs')\
            .select('*')\
            .eq('post_id', post_id)\
            .in_('status', ['pending', 'retrying'])\
            .execute()

        job_data = job_result.data[0] if job_result.data else None

        return {
            "post_id": post_id,
            "is_scheduled": post_data['status'] == 'scheduled',
            "post_status": post_data['status'],
            "scheduled_time": post_data.get('scheduled_at'),
            "job_id": job_data['job_id'] if job_data else None,
            "job_status": job_data['status'] if job_data else None,
            "retry_count": job_data['retry_count'] if job_data else 0
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.error(
            f"Error getting schedule status for post {post_id}: {e}"
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get post schedule status: {str(e)}"
        )


@router.post("/test")
async def test_scheduler():
    """
    Test endpoint to verify scheduler is working.

    Returns scheduler information and statistics.

    **Development only - remove in production**
    """
    try:
        # Get APScheduler info
        sch = get_scheduler()
        running_jobs = sch.scheduler.get_jobs()

        return {
            "scheduler_running": sch.scheduler.running,
            "job_count": len(running_jobs),
            "jobs": [
                {
                    "id": job.id,
                    "name": job.name,
                    "next_run_time": str(job.next_run_time)
                }
                for job in running_jobs
            ],
            "message": "Scheduler is operational"
        }

    except Exception as e:
        logger.error(f"Error testing scheduler: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Scheduler test failed: {str(e)}"
        )
