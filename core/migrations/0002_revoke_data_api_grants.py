"""Take table privileges away from Supabase's Data API roles (anon, authenticated).

The app talks to Postgres as the table owner and never through Supabase's Data API, so those roles
need nothing. Row level security already hides every row from them; revoking the privileges as well
means a table whose RLS gets switched off by mistake is still not readable with the public anon key.

Only runs on Postgres databases that have the Supabase roles; a no-op everywhere else (SQLite, plain Postgres).
"""

from django.db import migrations

REVOKE_SQL = """
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon, authenticated;
    REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon, authenticated;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM anon, authenticated;
  END IF;
END $$;
"""


def revoke(apps, schema_editor):
    if schema_editor.connection.vendor == "postgresql":
        schema_editor.execute(REVOKE_SQL)


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    # Re-granting access to the public roles is never what you want, so there is nothing to undo.
    operations = [migrations.RunPython(revoke, migrations.RunPython.noop)]
