"""
Post Scheduler Service

Manages scheduled post publishing using APScheduler.
Provides job persistence, retry logic, and automatic job restoration.

Author: SocialLab
Date: 2025-01-16
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

from database.supabase_client import get_supabase_admin_client
from services.publisher.instagram_publisher import (
    InstagramPublisher,
    InstagramPublishError
)

logger = logging.getLogger(__name__)


def publish_post_job(post_id: int) -> None:
    """
    Standalone function to publish a post (called by APScheduler).

    This function is independent of PostScheduler instance to avoid
    serialization issues with pickle.

    Args:
        post_id: ID of the post to publish
    """
    logger.info(f"⏰ Executing scheduled publication of post {post_id}")

    # Create fresh instances (no serialization issues)
    supabase = get_supabase_admin_client()
    publisher = InstagramPublisher()

    try:
        # Update job status to running
        supabase.table('scheduled_jobs').update({
            'status': 'running'
        }).eq('post_id', post_id).eq('status', 'pending').execute()

        # Get post data
        post_result = supabase.table('posts')\
            .select('*')\
            .eq('id', post_id)\
            .single()\
            .execute()

        if not post_result.data:
            raise ValueError(f"Post {post_id} not found")

        post_data = post_result.data

        # Get Instagram account ID
        instagram_result = supabase.table('instagram_accounts')\
            .select('id')\
            .eq('user_id', post_data['user_id'])\
            .eq('is_active', True)\
            .single()\
            .execute()

        if not instagram_result.data:
            raise ValueError(
                f"No active Instagram account found for user "
                f"{post_data['user_id']}"
            )

        instagram_account_id = instagram_result.data['id']

        # Publish to Instagram
        logger.info(f"📤 Publishing post {post_id} to Instagram...")
        result = publisher.publish_post(
            media_url=post_data['media_url'],
            caption=post_data.get('content', ''),
            instagram_account_id=instagram_account_id,
            post_type=post_data.get('media_product_type', 'FEED'),
            video_url=post_data.get('video_url')
        )

        # Update post as published
        supabase.table('posts').update({
            'status': 'published',
            'instagram_post_id': result.get('id'),
            'publication_date': datetime.now().isoformat()
        }).eq('id', post_id).execute()

        # Mark job as completed
        supabase.table('scheduled_jobs').update({
            'status': 'completed',
            'completed_at': datetime.now().isoformat()
        }).eq('post_id', post_id).execute()

        logger.info(f"✅ Post {post_id} published successfully")

    except Exception as e:
        logger.error(f"❌ Error publishing post {post_id}: {e}")

        # Update job status
        job_result = supabase.table('scheduled_jobs')\
            .select('retry_count, max_retries')\
            .eq('post_id', post_id)\
            .single()\
            .execute()

        if job_result.data:
            retry_count = job_result.data.get('retry_count', 0)
            max_retries = job_result.data.get('max_retries', 3)

            if retry_count < max_retries:
                # Calculate retry time (exponential backoff)
                # 1st retry: 5 min, 2nd: 15 min, 3rd: 30 min
                delay_minutes = 5 * (2 ** retry_count)
                retry_time = datetime.now(timezone.utc) + timedelta(
                    minutes=delay_minutes
                )

                # Create singleton scheduler instance
                from services.scheduler.post_scheduler import PostScheduler
                scheduler_instance = PostScheduler()

                # Schedule retry job in APScheduler
                job_id = f"post_{post_id}"
                scheduler_instance.scheduler.add_job(
                    func=publish_post_job,
                    trigger=DateTrigger(run_date=retry_time),
                    args=[post_id],
                    id=job_id,
                    name=f"Publish post {post_id} (retry {retry_count + 1})",
                    replace_existing=True
                )

                # Update job in database with new retry time and status
                supabase.table('scheduled_jobs').update({
                    'status': 'retrying',
                    'retry_count': retry_count + 1,
                    'error_message': str(e),
                    'scheduled_time': retry_time.isoformat()
                }).eq('post_id', post_id).execute()

                logger.info(
                    f"🔄 Scheduled retry {retry_count + 1}/{max_retries} "
                    f"for post {post_id} at {retry_time.isoformat()} "
                    f"(in {delay_minutes} minutes)"
                )
            else:
                # Max retries reached
                supabase.table('scheduled_jobs').update({
                    'status': 'failed',
                    'error_message': str(e),
                    'completed_at': datetime.now().isoformat()
                }).eq('post_id', post_id).execute()

                supabase.table('posts').update({
                    'status': 'failed'
                }).eq('id', post_id).execute()

                logger.error(f"❌ Post {post_id} failed after {max_retries} retries")

        raise


class PostScheduler:
    """
    Schedules and manages automated post publishing.

    Features:
    - Schedule posts for future publication
    - Persist jobs in PostgreSQL
    - Automatic retry on failure
    - Job cancellation and rescheduling
    - Restore pending jobs on restart
    """

    _instance = None  # Singleton instance

    def __new__(cls):
        """Implement singleton pattern to avoid multiple schedulers."""
        if cls._instance is None:
            cls._instance = super(PostScheduler, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the scheduler with PostgreSQL persistence."""
        if self._initialized:
            return

        self.supabase = get_supabase_admin_client()
        self.publisher = InstagramPublisher()

        # Configure job store with PostgreSQL
        database_url = os.getenv('DATABASE_URL')
        if not database_url:
            raise ValueError("DATABASE_URL not configured")

        jobstores = {
            'default': SQLAlchemyJobStore(url=database_url)
        }

        # Configure thread pool executor
        executors = {
            'default': ThreadPoolExecutor(max_workers=5)
        }

        # Configure job defaults
        job_defaults = {
            'coalesce': False,  # Run all missed jobs
            'max_instances': 1,  # One instance per job
            'misfire_grace_time': 300  # 5 minutes grace period
        }

        # Create and start scheduler
        self.scheduler = BackgroundScheduler(
            jobstores=jobstores,
            executors=executors,
            job_defaults=job_defaults,
            timezone='UTC'
        )

        # Add event listeners
        self.scheduler.add_listener(
            self._job_executed_listener,
            EVENT_JOB_EXECUTED
        )
        self.scheduler.add_listener(
            self._job_error_listener,
            EVENT_JOB_ERROR
        )

        # Start scheduler
        self.scheduler.start()
        logger.info("PostScheduler initialized and started")

        # Restore pending jobs from database
        self._restore_pending_jobs()

        self._initialized = True

    def schedule_post(
        self,
        post_id: int,
        scheduled_time: datetime,
        retry_on_failure: bool = True
    ) -> str:
        """
        Schedules a post for future publication.

        Args:
            post_id: ID of the post in the posts table
            scheduled_time: When to publish (UTC timezone)
            retry_on_failure: Whether to retry on failure

        Returns:
            job_id: ID of the created job

        Raises:
            ValueError: If post doesn't exist or is invalid
        """
        try:
            # Validate post exists and is in correct status
            post = self.supabase.table('posts')\
                .select('*')\
                .eq('id', post_id)\
                .single()\
                .execute()

            if not post.data:
                raise ValueError(f"Post {post_id} not found")

            if not post.data.get('media_url'):
                raise ValueError(
                    f"Post {post_id} missing media_url"
                )

            # Create job ID
            job_id = f"post_{post_id}"

            # Remove existing job from APScheduler if any
            try:
                self.scheduler.remove_job(job_id)
                logger.info(f"Removed existing job {job_id} from APScheduler")
            except Exception:
                pass  # Job doesn't exist, that's fine

            # Remove existing job from database if any
            try:
                self.supabase.table('scheduled_jobs')\
                    .delete()\
                    .eq('job_id', job_id)\
                    .execute()
                logger.info(f"Removed existing job {job_id} from database")
            except Exception:
                pass  # Job doesn't exist in DB, that's fine

            # Ensure scheduled_time is timezone-aware (UTC)
            if scheduled_time.tzinfo is None:
                # Naive datetime - assume it's already in UTC
                scheduled_time_aware = scheduled_time.replace(tzinfo=timezone.utc)
            else:
                # Already timezone-aware
                scheduled_time_aware = scheduled_time

            # Create new job in APScheduler with timezone-aware datetime
            job = self.scheduler.add_job(
                func=publish_post_job,
                trigger=DateTrigger(run_date=scheduled_time_aware),
                args=[post_id],
                id=job_id,
                name=f"Publish post {post_id}",
                replace_existing=True
            )

            # Store in scheduled_jobs table (fresh insert)
            self.supabase.table('scheduled_jobs').insert({
                'job_id': job.id,
                'job_type': 'publish_post',
                'post_id': post_id,
                'scheduled_time': scheduled_time.isoformat(),
                'status': 'pending',
                'retry_count': 0,
                'max_retries': 3 if retry_on_failure else 0
            }).execute()

            # Update post status
            self.supabase.table('posts').update({
                'status': 'scheduled',
                'scheduled_at': scheduled_time.isoformat()
            }).eq('id', post_id).execute()

            logger.info(
                f"Post {post_id} scheduled for {scheduled_time} "
                f"(job_id: {job.id})"
            )

            return job.id

        except Exception as e:
            logger.error(f"Error scheduling post {post_id}: {e}")
            raise

    def cancel_scheduled_post(self, post_id: int) -> bool:
        """
        Cancels a scheduled post.

        Args:
            post_id: ID of the post to cancel

        Returns:
            True if cancelled successfully
        """
        try:
            job_id = f"post_{post_id}"

            # Remove from APScheduler
            self.scheduler.remove_job(job_id)

            # Update database
            self.supabase.table('scheduled_jobs').update({
                'status': 'cancelled',
                'completed_at': datetime.now().isoformat()
            }).eq('job_id', job_id).execute()

            self.supabase.table('posts').update({
                'status': 'draft'  # Revert to draft
            }).eq('id', post_id).execute()

            logger.info(f"Cancelled scheduled post {post_id}")
            return True

        except Exception as e:
            logger.error(f"Error cancelling post {post_id}: {e}")
            return False

    def reschedule_post(
        self,
        post_id: int,
        new_scheduled_time: datetime
    ) -> str:
        """
        Reschedules a post to a new time.

        Args:
            post_id: ID of the post
            new_scheduled_time: New publication time

        Returns:
            New job ID
        """
        logger.info(
            f"Rescheduling post {post_id} to {new_scheduled_time}"
        )

        # Cancel existing schedule
        self.cancel_scheduled_post(post_id)

        # Create new schedule
        return self.schedule_post(post_id, new_scheduled_time)

    def get_scheduled_jobs(
        self,
        status: Optional[str] = None
    ) -> List[Dict]:
        """
        Gets list of scheduled jobs.

        Args:
            status: Filter by status (pending, completed, failed, etc.)

        Returns:
            List of scheduled jobs
        """
        try:
            query = self.supabase.table('scheduled_jobs').select('*')

            if status:
                query = query.eq('status', status)

            result = query.order('scheduled_time', desc=False).execute()
            return result.data or []

        except Exception as e:
            logger.error(f"Error getting scheduled jobs: {e}")
            return []

    def get_job_status(self, job_id: str) -> Optional[Dict]:
        """
        Gets status of a specific job.

        Args:
            job_id: The job ID

        Returns:
            Job data or None if not found
        """
        try:
            result = self.supabase.table('scheduled_jobs')\
                .select('*')\
                .eq('job_id', job_id)\
                .single()\
                .execute()

            return result.data if result.data else None

        except Exception as e:
            logger.error(f"Error getting job status for {job_id}: {e}")
            return None

    def _restore_pending_jobs(self) -> None:
        """
        Restores pending jobs from database on scheduler startup.

        This ensures scheduled posts survive server restarts.
        Also detects orphaned posts with status='scheduled' but no job.
        """
        try:
            logger.info("Restoring pending scheduled jobs...")

            # Step 1: Restore jobs from scheduled_jobs table
            pending_jobs = self.supabase.table('scheduled_jobs')\
                .select('*')\
                .in_('status', ['pending', 'retrying'])\
                .gte('scheduled_time', datetime.now(timezone.utc).isoformat())\
                .execute()

            restored_count = 0

            for job in pending_jobs.data or []:
                try:
                    # Recreate job in APScheduler
                    scheduled_time_str = job['scheduled_time'].replace('Z', '+00:00')
                    scheduled_time = datetime.fromisoformat(scheduled_time_str)

                    # Ensure it's timezone-aware
                    if scheduled_time.tzinfo is None:
                        scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)

                    self.scheduler.add_job(
                        func=publish_post_job,
                        trigger=DateTrigger(run_date=scheduled_time),
                        args=[job['post_id']],
                        id=job['job_id'],
                        name=f"Publish post {job['post_id']}",
                        replace_existing=True
                    )

                    restored_count += 1
                    logger.info(f"Restored job {job['job_id']}")

                except Exception as e:
                    logger.error(
                        f"Failed to restore job {job['job_id']}: {e}"
                    )

            logger.info(f"Restored {restored_count} jobs from scheduled_jobs table")

            # Step 2: Auto-detect orphaned posts with status='scheduled'
            logger.info("Checking for orphaned scheduled posts...")

            orphaned_posts = self.supabase.table('posts')\
                .select('id, scheduled_at')\
                .eq('status', 'scheduled')\
                .not_.is_('scheduled_at', 'null')\
                .gte('scheduled_at', datetime.now(timezone.utc).isoformat())\
                .execute()

            orphaned_count = 0

            for post in orphaned_posts.data or []:
                try:
                    post_id = post['id']
                    job_id = f"post_{post_id}"

                    # Check if job already exists in scheduled_jobs
                    existing_job = self.supabase.table('scheduled_jobs')\
                        .select('job_id')\
                        .eq('job_id', job_id)\
                        .in_('status', ['pending', 'retrying'])\
                        .execute()

                    if existing_job.data:
                        # Job already exists, skip
                        continue

                    # Orphaned post found! Create job for it
                    scheduled_time_str = post['scheduled_at'].replace('Z', '+00:00')
                    scheduled_time = datetime.fromisoformat(scheduled_time_str)

                    # Ensure timezone-aware
                    if scheduled_time.tzinfo is None:
                        scheduled_time = scheduled_time.replace(tzinfo=timezone.utc)

                    logger.warning(
                        f"Found orphaned post {post_id} scheduled for "
                        f"{scheduled_time}. Creating job..."
                    )

                    # Create job in APScheduler
                    self.scheduler.add_job(
                        func=publish_post_job,
                        trigger=DateTrigger(run_date=scheduled_time),
                        args=[post_id],
                        id=job_id,
                        name=f"Publish post {post_id}",
                        replace_existing=True
                    )

                    # Create entry in scheduled_jobs table
                    self.supabase.table('scheduled_jobs').insert({
                        'job_id': job_id,
                        'job_type': 'publish_post',
                        'post_id': post_id,
                        'scheduled_time': scheduled_time.isoformat(),
                        'status': 'pending',
                        'retry_count': 0,
                        'max_retries': 3
                    }).execute()

                    orphaned_count += 1
                    logger.info(f"Created job for orphaned post {post_id}")

                except Exception as e:
                    logger.error(
                        f"Failed to create job for orphaned post {post.get('id')}: {e}"
                    )

            if orphaned_count > 0:
                logger.warning(
                    f"Auto-scheduled {orphaned_count} orphaned posts"
                )
            else:
                logger.info("No orphaned scheduled posts found")

            total_jobs = restored_count + orphaned_count
            logger.info(
                f"Scheduler ready with {total_jobs} total jobs "
                f"({restored_count} restored + {orphaned_count} orphaned)"
            )

        except Exception as e:
            logger.error(f"Error restoring pending jobs: {e}")

    def _job_executed_listener(self, event) -> None:
        """Listener for successful job executions."""
        logger.debug(f"Job {event.job_id} executed successfully")

    def _job_error_listener(self, event) -> None:
        """Listener for job execution errors."""
        logger.error(
            f"Job {event.job_id} failed with exception: {event.exception}"
        )

    def shutdown(self, wait: bool = True) -> None:
        """
        Shuts down the scheduler gracefully.

        Args:
            wait: Whether to wait for running jobs to complete
        """
        logger.info("Shutting down PostScheduler...")
        self.scheduler.shutdown(wait=wait)
        logger.info("PostScheduler shutdown complete")
