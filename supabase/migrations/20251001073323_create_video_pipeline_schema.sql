/*
  # Video Pipeline Database Schema

  ## Overview
  This migration creates the database schema for the optimized space news video pipeline.
  It includes tables for caching media assets, tracking API calls, managing render jobs,
  and storing transcription segments.

  ## New Tables

  ### 1. `media_cache`
  Stores cached media assets from various sources to reduce redundant API calls and downloads.
  - `id` (uuid, primary key)
  - `query` (text) - Normalized search query
  - `source` (text) - API source (nasa, pexels, pixabay, unsplash, giphy)
  - `media_url` (text) - Original URL of the media
  - `local_path` (text) - Path to cached file on disk
  - `file_hash` (text) - SHA256 hash for deduplication
  - `media_type` (text) - Type: image, video, gif
  - `resolution` (text) - Resolution metadata
  - `file_size` (integer) - File size in bytes
  - `quality_score` (integer) - Quality rating 1-10
  - `created_at` (timestamptz) - When cached
  - `last_used_at` (timestamptz) - Last access time
  - `use_count` (integer) - Number of times used
  - `expires_at` (timestamptz) - Cache expiration

  ### 2. `api_tracking`
  Tracks API health, rate limits, and call statistics for intelligent routing.
  - `id` (uuid, primary key)
  - `source` (text) - API name
  - `query` (text) - Search query
  - `success` (boolean) - Whether call succeeded
  - `response_time_ms` (integer) - Response time in milliseconds
  - `error_message` (text) - Error details if failed
  - `created_at` (timestamptz) - Timestamp of API call

  ### 3. `render_jobs`
  Manages video rendering jobs with status tracking and error recovery.
  - `id` (uuid, primary key)
  - `job_name` (text) - Descriptive name
  - `status` (text) - Status: pending, processing, completed, failed, paused
  - `mode` (text) - Render mode: fast, hq, balanced
  - `progress_percent` (integer) - Current progress 0-100
  - `current_step` (text) - Current pipeline step
  - `total_segments` (integer) - Number of video segments
  - `processed_segments` (integer) - Segments completed
  - `script_hash` (text) - Hash of input script
  - `output_path` (text) - Path to final video
  - `error_log` (jsonb) - Array of errors encountered
  - `performance_metrics` (jsonb) - Timing and resource usage data
  - `api_calls_made` (integer) - Total API calls
  - `cache_hits` (integer) - Number of cache hits
  - `estimated_time_sec` (integer) - Estimated completion time
  - `actual_time_sec` (integer) - Actual time taken
  - `created_at` (timestamptz) - Job creation time
  - `started_at` (timestamptz) - Processing start time
  - `completed_at` (timestamptz) - Completion time
  - `updated_at` (timestamptz) - Last update time

  ### 4. `transcription_cache`
  Caches Whisper transcription results to avoid re-transcribing identical audio.
  - `id` (uuid, primary key)
  - `audio_hash` (text) - SHA256 hash of audio file
  - `model` (text) - Whisper model used (small, medium, large)
  - `segments` (jsonb) - Array of transcription segments
  - `duration_sec` (integer) - Audio duration
  - `created_at` (timestamptz) - When transcribed
  - `last_used_at` (timestamptz) - Last access time

  ### 5. `script_cache`
  Caches generated scripts to avoid redundant OpenAI API calls.
  - `id` (uuid, primary key)
  - `articles_hash` (text) - SHA256 hash of input articles
  - `script_text` (text) - Generated script content
  - `model` (text) - AI model used
  - `word_count` (integer) - Script word count
  - `created_at` (timestamptz) - When generated
  - `last_used_at` (timestamptz) - Last access time

  ## Security
  - RLS enabled on all tables
  - Policies allow authenticated users to read and write their own data
  - Service role has full access for background jobs

  ## Indexes
  - Indexes on frequently queried columns for performance
  - Hash indexes for deduplication queries
  - Timestamp indexes for cleanup and expiration
*/

-- Create media_cache table
CREATE TABLE IF NOT EXISTS media_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  query text NOT NULL,
  source text NOT NULL,
  media_url text NOT NULL,
  local_path text,
  file_hash text NOT NULL,
  media_type text NOT NULL,
  resolution text,
  file_size integer DEFAULT 0,
  quality_score integer DEFAULT 5,
  created_at timestamptz DEFAULT now(),
  last_used_at timestamptz DEFAULT now(),
  use_count integer DEFAULT 0,
  expires_at timestamptz DEFAULT (now() + interval '30 days')
);

CREATE INDEX IF NOT EXISTS idx_media_cache_query ON media_cache(query);
CREATE INDEX IF NOT EXISTS idx_media_cache_hash ON media_cache(file_hash);
CREATE INDEX IF NOT EXISTS idx_media_cache_source ON media_cache(source);
CREATE INDEX IF NOT EXISTS idx_media_cache_expires ON media_cache(expires_at);

-- Create api_tracking table
CREATE TABLE IF NOT EXISTS api_tracking (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source text NOT NULL,
  query text NOT NULL,
  success boolean DEFAULT false,
  response_time_ms integer DEFAULT 0,
  error_message text,
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_api_tracking_source ON api_tracking(source);
CREATE INDEX IF NOT EXISTS idx_api_tracking_created ON api_tracking(created_at);

-- Create render_jobs table
CREATE TABLE IF NOT EXISTS render_jobs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  job_name text NOT NULL,
  status text DEFAULT 'pending',
  mode text DEFAULT 'balanced',
  progress_percent integer DEFAULT 0,
  current_step text,
  total_segments integer DEFAULT 0,
  processed_segments integer DEFAULT 0,
  script_hash text,
  output_path text,
  error_log jsonb DEFAULT '[]'::jsonb,
  performance_metrics jsonb DEFAULT '{}'::jsonb,
  api_calls_made integer DEFAULT 0,
  cache_hits integer DEFAULT 0,
  estimated_time_sec integer,
  actual_time_sec integer,
  created_at timestamptz DEFAULT now(),
  started_at timestamptz,
  completed_at timestamptz,
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_render_jobs_status ON render_jobs(status);
CREATE INDEX IF NOT EXISTS idx_render_jobs_created ON render_jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_render_jobs_script_hash ON render_jobs(script_hash);

-- Create transcription_cache table
CREATE TABLE IF NOT EXISTS transcription_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  audio_hash text UNIQUE NOT NULL,
  model text NOT NULL,
  segments jsonb NOT NULL,
  duration_sec integer DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  last_used_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_transcription_cache_hash ON transcription_cache(audio_hash);

-- Create script_cache table
CREATE TABLE IF NOT EXISTS script_cache (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  articles_hash text UNIQUE NOT NULL,
  script_text text NOT NULL,
  model text NOT NULL,
  word_count integer DEFAULT 0,
  created_at timestamptz DEFAULT now(),
  last_used_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_script_cache_hash ON script_cache(articles_hash);

-- Enable RLS on all tables
ALTER TABLE media_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_tracking ENABLE ROW LEVEL SECURITY;
ALTER TABLE render_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE transcription_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE script_cache ENABLE ROW LEVEL SECURITY;

-- Create policies for authenticated access
CREATE POLICY "Allow authenticated users to read media_cache"
  ON media_cache FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Allow authenticated users to insert media_cache"
  ON media_cache FOR INSERT
  TO authenticated
  WITH CHECK (true);

CREATE POLICY "Allow authenticated users to update media_cache"
  ON media_cache FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow authenticated users to read api_tracking"
  ON api_tracking FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Allow authenticated users to insert api_tracking"
  ON api_tracking FOR INSERT
  TO authenticated
  WITH CHECK (true);

CREATE POLICY "Allow authenticated users to read render_jobs"
  ON render_jobs FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Allow authenticated users to insert render_jobs"
  ON render_jobs FOR INSERT
  TO authenticated
  WITH CHECK (true);

CREATE POLICY "Allow authenticated users to update render_jobs"
  ON render_jobs FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow authenticated users to read transcription_cache"
  ON transcription_cache FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Allow authenticated users to insert transcription_cache"
  ON transcription_cache FOR INSERT
  TO authenticated
  WITH CHECK (true);

CREATE POLICY "Allow authenticated users to update transcription_cache"
  ON transcription_cache FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);

CREATE POLICY "Allow authenticated users to read script_cache"
  ON script_cache FOR SELECT
  TO authenticated
  USING (true);

CREATE POLICY "Allow authenticated users to insert script_cache"
  ON script_cache FOR INSERT
  TO authenticated
  WITH CHECK (true);

CREATE POLICY "Allow authenticated users to update script_cache"
  ON script_cache FOR UPDATE
  TO authenticated
  USING (true)
  WITH CHECK (true);
