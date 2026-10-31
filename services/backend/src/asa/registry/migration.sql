CREATE TABLE IF NOT EXISTS registry_workspaces (
    id uuid PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS registry_agents (
    workspace_id uuid NOT NULL REFERENCES registry_workspaces(id),
    id uuid NOT NULL, revision integer NOT NULL DEFAULT 1 CHECK (revision > 0),
    draft jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(workspace_id,id)
);
CREATE TABLE IF NOT EXISTS registry_versions (
    workspace_id uuid NOT NULL, agent_id uuid NOT NULL, version integer NOT NULL,
    source_revision integer NOT NULL, definition jsonb NOT NULL, digest text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY(workspace_id,agent_id,version),
    UNIQUE(workspace_id,agent_id,source_revision),
    FOREIGN KEY(workspace_id,agent_id) REFERENCES registry_agents(workspace_id,id)
);
CREATE TABLE IF NOT EXISTS registry_agent_tools (
    workspace_id uuid NOT NULL, agent_id uuid NOT NULL, version integer NOT NULL,
    alias text NOT NULL, PRIMARY KEY(workspace_id,agent_id,version),
    UNIQUE(workspace_id,alias),
    FOREIGN KEY(workspace_id,agent_id,version)
        REFERENCES registry_versions(workspace_id,agent_id,version)
);
CREATE TABLE IF NOT EXISTS registry_sessions (
    token_hash text PRIMARY KEY, workspace_id uuid NOT NULL REFERENCES registry_workspaces(id),
    expires_at timestamptz NOT NULL
);
CREATE TABLE IF NOT EXISTS customer_requests (
    workspace_id uuid NOT NULL, id uuid NOT NULL, agent_id uuid NOT NULL,
    version integer NOT NULL, input jsonb NOT NULL, source_id uuid,
    status text NOT NULL DEFAULT 'saved'
        CHECK (status IN ('saved','queued','running','succeeded','failed','cancelled')),
    result jsonb, error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(workspace_id,id),
    FOREIGN KEY(workspace_id,agent_id,version)
        REFERENCES registry_agent_tools(workspace_id,agent_id,version),
    FOREIGN KEY(workspace_id,source_id) REFERENCES customer_requests(workspace_id,id)
);
CREATE INDEX IF NOT EXISTS customer_requests_recent
    ON customer_requests(workspace_id,created_at DESC,id DESC);
CREATE TABLE IF NOT EXISTS script_stages (
    workspace_id uuid NOT NULL, request_id uuid NOT NULL,
    revision integer NOT NULL DEFAULT 0, head_version integer NOT NULL DEFAULT 0,
    approved_version integer, PRIMARY KEY(workspace_id,request_id),
    FOREIGN KEY(workspace_id,request_id) REFERENCES customer_requests(workspace_id,id)
);
CREATE TABLE IF NOT EXISTS script_versions (
    workspace_id uuid NOT NULL, request_id uuid NOT NULL, version integer NOT NULL,
    operation_id uuid NOT NULL, title text NOT NULL, narration text NOT NULL,
    source text NOT NULL CHECK(source IN ('manual','ai')), base_version integer,
    instruction text NOT NULL DEFAULT '', created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(workspace_id,request_id,version), UNIQUE(workspace_id,request_id,operation_id),
    FOREIGN KEY(workspace_id,request_id) REFERENCES script_stages(workspace_id,request_id)
);
CREATE TABLE IF NOT EXISTS script_attempts (
    workspace_id uuid NOT NULL, request_id uuid NOT NULL, id uuid NOT NULL,
    base_version integer NOT NULL DEFAULT 0, instruction text NOT NULL,
    status text NOT NULL CHECK(status IN ('queued','running','succeeded','unknown','cancelled')),
    prompt text NOT NULL, model_profile text NOT NULL, provider text, model text,
    created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz,
    finished_at timestamptz, result_version integer,
    PRIMARY KEY(workspace_id,request_id,id),
    FOREIGN KEY(workspace_id,request_id) REFERENCES script_stages(workspace_id,request_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS script_one_active_attempt
    ON script_attempts(workspace_id,request_id) WHERE status IN ('queued','running');
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='script_version_immutable_trigger'
                  AND tgrelid='script_versions'::regclass) THEN
        CREATE FUNCTION script_version_immutable() RETURNS trigger LANGUAGE plpgsql
        AS $fn$ BEGIN RAISE EXCEPTION 'script_version_immutable'; END $fn$;
        CREATE TRIGGER script_version_immutable_trigger BEFORE UPDATE OR DELETE ON script_versions
        FOR EACH ROW EXECUTE FUNCTION script_version_immutable();
    END IF;
END $$;
CREATE OR REPLACE FUNCTION registry_version_immutable() RETURNS trigger
LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'published_version_immutable'; END $$;
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='registry_version_immutable_trigger'
                  AND tgrelid='registry_versions'::regclass) THEN
        CREATE TRIGGER registry_version_immutable_trigger BEFORE UPDATE OR DELETE ON registry_versions
        FOR EACH ROW EXECUTE FUNCTION registry_version_immutable();
    END IF;
END $$;
CREATE TABLE IF NOT EXISTS automation_drafts (
    workspace_id uuid NOT NULL REFERENCES registry_workspaces(id),
    id uuid NOT NULL,
    revision integer NOT NULL DEFAULT 1,
    draft jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace_id, id)
);
CREATE TABLE IF NOT EXISTS automation_runs (
    workspace_id uuid NOT NULL REFERENCES registry_workspaces(id), id uuid NOT NULL,
    automation_id uuid NOT NULL, revision integer NOT NULL, definition jsonb NOT NULL,
    manifest jsonb NOT NULL, prompt text NOT NULL, status text NOT NULL DEFAULT 'queued',
    steps jsonb NOT NULL DEFAULT '[]', next_step integer NOT NULL DEFAULT 0,
    error text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    schedule_id uuid, occurrence timestamptz,
    PRIMARY KEY(workspace_id,id), UNIQUE(workspace_id,schedule_id,occurrence),
    FOREIGN KEY(workspace_id,automation_id) REFERENCES automation_drafts(workspace_id,id)
);
CREATE TABLE IF NOT EXISTS automation_schedules (
    workspace_id uuid NOT NULL, automation_id uuid NOT NULL, revision integer NOT NULL DEFAULT 1,
    enabled boolean NOT NULL, kind text NOT NULL, time text NOT NULL, next_at timestamptz,
    prompt text NOT NULL, definition jsonb NOT NULL, manifest jsonb NOT NULL,
    definition_revision integer NOT NULL, note text NOT NULL DEFAULT '',
    PRIMARY KEY(workspace_id,automation_id),
    FOREIGN KEY(workspace_id,automation_id) REFERENCES automation_drafts(workspace_id,id)
);
CREATE TABLE IF NOT EXISTS automation_worker_status (
    workspace_id uuid PRIMARY KEY REFERENCES registry_workspaces(id),
    seen_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS automation_ai_calls (
    workspace_id uuid NOT NULL, run_id uuid NOT NULL, step_id text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(), usage jsonb,
    PRIMARY KEY(workspace_id,run_id,step_id),
    FOREIGN KEY(workspace_id,run_id) REFERENCES automation_runs(workspace_id,id)
);

ALTER TABLE automation_runs ADD COLUMN IF NOT EXISTS graph_state jsonb;
ALTER TABLE automation_runs ADD COLUMN IF NOT EXISTS requested_by text;
ALTER TABLE automation_runs ADD COLUMN IF NOT EXISTS started_at timestamptz;
ALTER TABLE automation_schedules ADD COLUMN IF NOT EXISTS requested_by text;
ALTER TABLE customer_requests ADD COLUMN IF NOT EXISTS requested_by text;

CREATE TABLE IF NOT EXISTS ai_usage_events (
    workspace_id uuid NOT NULL REFERENCES registry_workspaces(id), id uuid NOT NULL,
    run_id text NOT NULL, request_id text NOT NULL, source text NOT NULL,
    requested_by text, automation_id text, name text NOT NULL, revision integer,
    step_id text NOT NULL, step_name text NOT NULL, provider text NOT NULL, model text NOT NULL,
    status text NOT NULL DEFAULT 'incomplete', created_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz, duration_ms integer, original_request jsonb,
    messages jsonb, response jsonb, usage jsonb, pricing jsonb,
    estimated_usd numeric, cost_state text NOT NULL DEFAULT 'unknown', error_code text,
    PRIMARY KEY(workspace_id,id)
);
CREATE INDEX IF NOT EXISTS ai_usage_events_time ON ai_usage_events(workspace_id,created_at DESC,id);
CREATE INDEX IF NOT EXISTS ai_usage_events_run ON ai_usage_events(workspace_id,run_id);
ALTER TABLE ai_usage_events ADD COLUMN IF NOT EXISTS requested_at timestamptz;

CREATE TABLE IF NOT EXISTS workspace_model_catalog (
 workspace_id uuid PRIMARY KEY REFERENCES registry_workspaces(id),
 revision integer NOT NULL DEFAULT 1,
 definition jsonb NOT NULL
);

ALTER TABLE script_attempts ADD COLUMN IF NOT EXISTS automatic boolean NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS script_queue_pending ON script_attempts(workspace_id,created_at)
 WHERE automatic AND status='queued';
CREATE TABLE IF NOT EXISTS script_worker_status (
 workspace_id uuid PRIMARY KEY REFERENCES registry_workspaces(id),
 seen_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE script_attempts ADD COLUMN IF NOT EXISTS error_code text;
ALTER TABLE script_attempts DROP CONSTRAINT IF EXISTS script_attempts_status_check;
ALTER TABLE script_attempts ADD CONSTRAINT script_attempts_status_check
 CHECK(status IN ('queued','running','succeeded','unknown','cancelled','failed'));

ALTER TABLE customer_requests ADD COLUMN IF NOT EXISTS is_test boolean NOT NULL DEFAULT false;

ALTER TABLE script_versions ADD COLUMN IF NOT EXISTS answer jsonb;

ALTER TABLE script_attempts ADD COLUMN IF NOT EXISTS live_output jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS character_projects (
 workspace_id uuid NOT NULL REFERENCES registry_workspaces(id), id uuid NOT NULL,
 request_id uuid NOT NULL, name text NOT NULL, characters jsonb NOT NULL,
 approved jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(workspace_id,id), UNIQUE(workspace_id,request_id)
);
CREATE TABLE IF NOT EXISTS character_image_jobs (
 workspace_id uuid NOT NULL, id uuid NOT NULL, project_id uuid NOT NULL,
 character_id text NOT NULL, version integer NOT NULL, model text NOT NULL,
 character jsonb NOT NULL, change text NOT NULL, base_id uuid,
 status text NOT NULL DEFAULT 'queued', error_code text, image bytea,
 usage jsonb, estimated_usd numeric, created_at timestamptz NOT NULL DEFAULT now(),
 started_at timestamptz, finished_at timestamptz,
 PRIMARY KEY(workspace_id,id),
 FOREIGN KEY(workspace_id,project_id) REFERENCES character_projects(workspace_id,id),
 UNIQUE(workspace_id,project_id,character_id,version)
);
CREATE UNIQUE INDEX IF NOT EXISTS character_image_active
 ON character_image_jobs(workspace_id,project_id,character_id) WHERE status IN ('queued','running');
CREATE TABLE IF NOT EXISTS image_worker_status (
 workspace_id uuid PRIMARY KEY REFERENCES registry_workspaces(id),
 seen_at timestamptz NOT NULL DEFAULT now()
);

-- Bind image projects to immutable agent answer versions, preserving existing v1 images.
ALTER TABLE character_projects ADD COLUMN IF NOT EXISTS source_version integer NOT NULL DEFAULT 1;
ALTER TABLE character_projects DROP CONSTRAINT IF EXISTS character_projects_workspace_id_request_id_key;
CREATE UNIQUE INDEX IF NOT EXISTS character_project_answer_version
 ON character_projects(workspace_id,request_id,source_version);

-- Reversible scope decisions for versioned follow-up work of any supported kind.
CREATE TABLE IF NOT EXISTS work_item_preferences (
 workspace_id uuid NOT NULL REFERENCES registry_workspaces(id), request_id uuid NOT NULL,
 source_version integer NOT NULL, kind text NOT NULL, item_id text NOT NULL,
 excluded boolean NOT NULL DEFAULT false, updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(workspace_id,request_id,source_version,kind,item_id)
);
ALTER TABLE work_item_preferences ADD COLUMN IF NOT EXISTS reviewed_version integer NOT NULL DEFAULT 0;

-- Transactional hints only: DB rows remain the source of truth.
ALTER TABLE character_image_jobs ADD COLUMN IF NOT EXISTS review_error_code text;

CREATE TABLE IF NOT EXISTS asset_reviews (
 workspace_id uuid NOT NULL REFERENCES registry_workspaces(id), id uuid NOT NULL,
 project_id uuid NOT NULL, image_id uuid NOT NULL, agent_ref text NOT NULL,
 definition jsonb NOT NULL, character jsonb NOT NULL, change text NOT NULL DEFAULT '',
 status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','running','succeeded','failed','unknown')),
 result jsonb, error_code text, automatic boolean NOT NULL DEFAULT false,
 created_at timestamptz NOT NULL DEFAULT now(), started_at timestamptz, finished_at timestamptz,
 PRIMARY KEY(workspace_id,id),
 FOREIGN KEY(workspace_id,image_id) REFERENCES character_image_jobs(workspace_id,id),
 FOREIGN KEY(workspace_id,project_id) REFERENCES character_projects(workspace_id,id)
);
CREATE UNIQUE INDEX IF NOT EXISTS asset_review_active ON asset_reviews(workspace_id,image_id)
 WHERE status IN ('queued','running');
CREATE UNIQUE INDEX IF NOT EXISTS asset_review_auto ON asset_reviews(workspace_id,image_id)
 WHERE automatic;

CREATE OR REPLACE FUNCTION asa_notify_change() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
  wid text;
  topic text;
BEGIN
  IF TG_OP='UPDATE' AND NEW IS NOT DISTINCT FROM OLD THEN RETURN NEW; END IF;
  IF TG_OP='DELETE' THEN wid := OLD.workspace_id::text;
  ELSE wid := NEW.workspace_id::text; END IF;
  PERFORM pg_notify('asa_changes', wid || ':state');
  topic := CASE TG_TABLE_NAME WHEN 'script_attempts' THEN 'script'
           WHEN 'character_image_jobs' THEN 'image'
           WHEN 'asset_reviews' THEN 'image'
           WHEN 'automation_runs' THEN 'automation'
           WHEN 'automation_schedules' THEN 'automation' ELSE NULL END;
  IF topic IS NOT NULL THEN
    IF TG_TABLE_NAME='automation_schedules' THEN
      PERFORM pg_notify('asa_changes', wid || ':' || topic);
    ELSIF TG_OP <> 'DELETE' THEN
      IF NEW.status='queued' THEN
        PERFORM pg_notify('asa_changes', wid || ':' || topic);
      END IF;
    END IF;
  END IF;
  IF TG_OP='DELETE' THEN RETURN OLD; ELSE RETURN NEW; END IF;
END $$;
DO $$
DECLARE tab text;
BEGIN
  FOREACH tab IN ARRAY ARRAY['customer_requests','script_stages','script_versions',
    'asset_reviews','script_attempts','character_projects','character_image_jobs','work_item_preferences',
    'automation_runs','automation_schedules','workspace_model_catalog','registry_sessions']
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS asa_change ON %I', tab);
    EXECUTE format('CREATE TRIGGER asa_change AFTER INSERT OR UPDATE OR DELETE ON %I '
      'FOR EACH ROW EXECUTE FUNCTION asa_notify_change()', tab);
  END LOOP;
END $$;
