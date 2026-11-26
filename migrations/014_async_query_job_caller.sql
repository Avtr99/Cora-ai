ALTER TABLE async_query_jobs ADD COLUMN caller TEXT NOT NULL DEFAULT 'owner';
UPDATE async_query_jobs SET caller = user_id;
