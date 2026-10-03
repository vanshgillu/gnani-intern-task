-- backend creates these on startup, this is just for reference

CREATE TYPE file_status AS ENUM (
  'uploaded', 'transcribing', 'transcribed', 'summarizing', 'completed', 'failed'
);

CREATE TABLE users (
  id UUID PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE audio_files (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
  filename VARCHAR(512) NOT NULL,
  content_type VARCHAR(128),
  size_bytes INTEGER NOT NULL,
  storage_path VARCHAR(1024) NOT NULL,
  language_code VARCHAR(64) NOT NULL,
  status file_status NOT NULL,
  gnani_job_id VARCHAR(64),
  gnani_status VARCHAR(32),
  transcript TEXT,
  detected_language VARCHAR(16),
  duration_seconds DOUBLE PRECISION,
  summary TEXT,
  error TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_audio_files_user_id ON audio_files (user_id);

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE audio_files ENABLE ROW LEVEL SECURITY;
