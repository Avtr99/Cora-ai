-- Single-owner model: member accounts are retired. Their chats and queued
-- jobs transfer to the owner so no data is lost; their sessions end and the
-- member rows are removed.
UPDATE chats SET user_id = 'owner'
    WHERE user_id IN (SELECT id FROM users WHERE role != 'owner');
UPDATE async_query_jobs SET user_id = 'owner'
    WHERE user_id IN (SELECT id FROM users WHERE role != 'owner');
DELETE FROM auth_sessions
    WHERE user_id IN (SELECT id FROM users WHERE role != 'owner');
DELETE FROM users WHERE role != 'owner';
