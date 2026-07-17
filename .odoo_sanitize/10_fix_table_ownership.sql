-- Reassign all public-schema objects to the database owner.
--
-- Oduflow copy-mode templates can leave tables owned by the template's
-- role (e.g. u_2_fs19) while the new environment connects as its own role;
-- Odoo then cannot even load the registry. On correctly-provisioned
-- databases every object is already owned by the database owner and this
-- script is a no-op.
DO $$
DECLARE
    target TEXT;
    r RECORD;
BEGIN
    SELECT pg_catalog.pg_get_userbyid(datdba) INTO target
      FROM pg_database WHERE datname = current_database();

    FOR r IN SELECT tablename AS name FROM pg_tables
              WHERE schemaname = 'public' AND tableowner <> target LOOP
        EXECUTE format('ALTER TABLE public.%I OWNER TO %I', r.name, target);
    END LOOP;

    FOR r IN SELECT sequencename AS name FROM pg_sequences
              WHERE schemaname = 'public' AND sequenceowner <> target LOOP
        EXECUTE format('ALTER SEQUENCE public.%I OWNER TO %I', r.name, target);
    END LOOP;

    FOR r IN SELECT c.relname AS name
               FROM pg_class c
               JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE c.relkind = 'v' AND n.nspname = 'public'
                AND pg_catalog.pg_get_userbyid(c.relowner) <> target LOOP
        EXECUTE format('ALTER VIEW public.%I OWNER TO %I', r.name, target);
    END LOOP;

    FOR r IN SELECT c.relname AS name
               FROM pg_class c
               JOIN pg_namespace n ON n.oid = c.relnamespace
              WHERE c.relkind = 'm' AND n.nspname = 'public'
                AND pg_catalog.pg_get_userbyid(c.relowner) <> target LOOP
        EXECUTE format('ALTER MATERIALIZED VIEW public.%I OWNER TO %I', r.name, target);
    END LOOP;
END $$;
