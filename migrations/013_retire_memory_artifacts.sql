-- The conversation-memory subsystem was removed. The app_settings row that
-- held the auto-generated SECRET_KEY existed only for memory user-ID
-- anonymization and is no longer read.
DELETE FROM app_settings WHERE key = 'secret_key';
