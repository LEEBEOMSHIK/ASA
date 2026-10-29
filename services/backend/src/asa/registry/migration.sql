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
