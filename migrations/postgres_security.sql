CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE case_locations (
    tenant_id varchar(36) NOT NULL,
    case_id varchar(36) NOT NULL,
    position geography(Point, 4326) NOT NULL,
    confidence double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    provenance varchar(160) NOT NULL,
    PRIMARY KEY (tenant_id, case_id),
    FOREIGN KEY (tenant_id, case_id) REFERENCES cases(tenant_id, id)
);
CREATE INDEX ix_case_locations_position ON case_locations USING gist(position);
CREATE TABLE report_embeddings (
    tenant_id varchar(36) NOT NULL,
    report_id varchar(36) NOT NULL,
    model_revision varchar(160) NOT NULL,
    embedding vector(1024) NOT NULL,
    PRIMARY KEY (tenant_id, report_id, model_revision),
    FOREIGN KEY (tenant_id, report_id) REFERENCES reports(tenant_id, id)
);

-- Local development migration administrator owns these functions; application role cannot replace them.
CREATE FUNCTION authenticate_token(p_digest text)
RETURNS TABLE(tenant_id varchar, user_id varchar, role varchar)
LANGUAGE sql SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT t.tenant_id, t.user_id, m.role
    FROM public.access_tokens t JOIN public.memberships m
      ON t.tenant_id = m.tenant_id AND t.user_id = m.user_id
    WHERE t.digest = p_digest AND NOT t.revoked AND t.expires_at > now()
$$;
REVOKE ALL ON FUNCTION authenticate_token(text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION authenticate_token(text) TO komsu_app;
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO komsu_app;
GRANT SELECT ON organizations, alembic_version TO komsu_app;
-- SELECT FOR UPDATE requires an UPDATE privilege, but no application endpoint edits organisations.
GRANT UPDATE(id) ON organizations TO komsu_app;
GRANT SELECT, INSERT, UPDATE ON cases, reports, jobs, teams, devices, map_layers, case_locations, report_embeddings TO komsu_app;
GRANT SELECT, INSERT ON dispatches, audit_log, events, review_history TO komsu_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO komsu_app;

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_boundary ON organizations USING (id = current_setting('app.tenant_id', true)) WITH CHECK (id = current_setting('app.tenant_id', true));
DO $$
DECLARE name text;
BEGIN
  FOREACH name IN ARRAY ARRAY['cases','reports','jobs','teams','devices','map_layers','dispatches','audit_log','events','review_history','case_locations','report_embeddings'] LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', name);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', name);
    EXECUTE format('CREATE POLICY tenant_boundary ON %I USING (tenant_id = current_setting(''app.tenant_id'', true)) WITH CHECK (tenant_id = current_setting(''app.tenant_id'', true))', name);
  END LOOP;
END $$;

CREATE FUNCTION sync_case_location() RETURNS trigger LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
  IF NEW.lat IS NOT NULL AND NEW.lon IS NOT NULL THEN
    INSERT INTO case_locations(tenant_id, case_id, position, confidence, provenance)
      VALUES(NEW.tenant_id, NEW.id, ST_SetSRID(ST_MakePoint(NEW.lon, NEW.lat),4326)::geography,
        CASE WHEN NEW.location_status = 'CONFIRMED' THEN 1.0 ELSE 0.0 END, NEW.location_status)
      ON CONFLICT(tenant_id, case_id) DO UPDATE SET position = EXCLUDED.position, confidence = EXCLUDED.confidence, provenance = EXCLUDED.provenance;
  END IF;
  RETURN NEW;
END $$;
CREATE TRIGGER case_location_update AFTER INSERT OR UPDATE OF lat, lon, location_status ON cases FOR EACH ROW EXECUTE FUNCTION sync_case_location();
