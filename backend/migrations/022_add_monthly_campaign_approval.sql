-- Migration: Add status, generated_by, and resolved_at to monthly_campaigns
ALTER TABLE monthly_campaigns
    ADD COLUMN status       TEXT NOT NULL DEFAULT 'approved'
        CHECK (status IN ('pending_approval', 'approved', 'rejected')),
    ADD COLUMN generated_by TEXT NOT NULL DEFAULT 'manual'
        CHECK (generated_by IN ('manual', 'hermes')),
    ADD COLUMN resolved_at  TIMESTAMPTZ;
