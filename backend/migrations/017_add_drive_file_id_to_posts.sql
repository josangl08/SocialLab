-- Add drive_file_id to posts so AI-generated drafts can reference their Drive image
ALTER TABLE posts ADD COLUMN IF NOT EXISTS drive_file_id TEXT;
