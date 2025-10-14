-- Migration 009: Create scheduled_jobs table for APScheduler persistence
-- Purpose: Track programmed posts and their execution status
-- Date: 2025-01-16

-- Create scheduled_jobs table
CREATE TABLE IF NOT EXISTS scheduled_jobs (
  id SERIAL PRIMARY KEY,
  job_id TEXT UNIQUE NOT NULL,
  job_type TEXT NOT NULL DEFAULT 'publish_post',
  post_id BIGINT REFERENCES posts(id) ON DELETE CASCADE,
  scheduled_time TIMESTAMP WITH TIME ZONE NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  retry_count INTEGER DEFAULT 0,
  max_retries INTEGER DEFAULT 3,
  error_message TEXT,
  completed_at TIMESTAMP WITH TIME ZONE,
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Add indexes for common queries
CREATE INDEX idx_scheduled_jobs_post_id ON scheduled_jobs(post_id);
CREATE INDEX idx_scheduled_jobs_status ON scheduled_jobs(status);
CREATE INDEX idx_scheduled_jobs_scheduled_time ON scheduled_jobs(scheduled_time);
CREATE INDEX idx_scheduled_jobs_job_id ON scheduled_jobs(job_id);

-- Add check constraint for valid statuses
ALTER TABLE scheduled_jobs
ADD CONSTRAINT check_scheduled_jobs_status
CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'retrying'));

-- Add check constraint for valid job types
ALTER TABLE scheduled_jobs
ADD CONSTRAINT check_scheduled_jobs_job_type
CHECK (job_type IN ('publish_post', 'sync_insights', 'cleanup_old_posts'));

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_scheduled_jobs_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for updated_at
CREATE TRIGGER trigger_scheduled_jobs_updated_at
  BEFORE UPDATE ON scheduled_jobs
  FOR EACH ROW
  EXECUTE FUNCTION update_scheduled_jobs_updated_at();

-- Add RLS (Row Level Security) policies
ALTER TABLE scheduled_jobs ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only see their own scheduled jobs
CREATE POLICY "Users can view their own scheduled jobs"
  ON scheduled_jobs
  FOR SELECT
  USING (
    post_id IN (
      SELECT id FROM posts WHERE user_id = auth.uid()
    )
  );

-- Policy: Users can insert their own scheduled jobs
CREATE POLICY "Users can insert their own scheduled jobs"
  ON scheduled_jobs
  FOR INSERT
  WITH CHECK (
    post_id IN (
      SELECT id FROM posts WHERE user_id = auth.uid()
    )
  );

-- Policy: Users can update their own scheduled jobs
CREATE POLICY "Users can update their own scheduled jobs"
  ON scheduled_jobs
  FOR UPDATE
  USING (
    post_id IN (
      SELECT id FROM posts WHERE user_id = auth.uid()
    )
  );

-- Policy: Users can delete their own scheduled jobs
CREATE POLICY "Users can delete their own scheduled jobs"
  ON scheduled_jobs
  FOR DELETE
  USING (
    post_id IN (
      SELECT id FROM posts WHERE user_id = auth.uid()
    )
  );

-- Add comments for documentation
COMMENT ON TABLE scheduled_jobs IS 'Tracks scheduled posts and their execution status for APScheduler';
COMMENT ON COLUMN scheduled_jobs.job_id IS 'Unique identifier for APScheduler job (e.g., post_123)';
COMMENT ON COLUMN scheduled_jobs.job_type IS 'Type of job: publish_post, sync_insights, cleanup_old_posts';
COMMENT ON COLUMN scheduled_jobs.post_id IS 'Reference to the post being scheduled';
COMMENT ON COLUMN scheduled_jobs.scheduled_time IS 'When the job should execute (UTC timezone)';
COMMENT ON COLUMN scheduled_jobs.status IS 'Current status: pending, running, completed, failed, cancelled, retrying';
COMMENT ON COLUMN scheduled_jobs.retry_count IS 'Number of times the job has been retried';
COMMENT ON COLUMN scheduled_jobs.max_retries IS 'Maximum number of retry attempts allowed';
COMMENT ON COLUMN scheduled_jobs.error_message IS 'Error message if job failed';
COMMENT ON COLUMN scheduled_jobs.completed_at IS 'Timestamp when job completed (success or failure)';
