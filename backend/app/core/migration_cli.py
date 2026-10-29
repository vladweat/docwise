"""One-shot entrypoint for RLS role setup and Alembic migrations."""

from sqlalchemy import create_engine, text

from app.core.config import get_settings
from app.core.migrations import run_migrations


def ensure_rls_runtime_role() -> None:
    """Create/grant the non-superuser app role using the migration DB owner."""
    engine = create_engine(get_settings().database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    DO $$
                    BEGIN
                        IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'docwise_rls') THEN
                            EXECUTE 'CREATE ROLE docwise_rls NOLOGIN NOSUPERUSER '
                                || 'NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS';
                        END IF;
                        EXECUTE 'ALTER ROLE docwise_rls NOLOGIN NOSUPERUSER '
                            || 'NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS';
                        EXECUTE format('GRANT CONNECT ON DATABASE %I TO docwise_rls', current_database());
                        EXECUTE format('GRANT docwise_rls TO %I', current_user);
                        EXECUTE format(
                            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
                            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO docwise_rls',
                            current_user
                        );
                        EXECUTE format(
                            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
                            'REVOKE TRUNCATE, REFERENCES, TRIGGER ON TABLES FROM docwise_rls',
                            current_user
                        );
                        EXECUTE format(
                            'ALTER DEFAULT PRIVILEGES FOR ROLE %I IN SCHEMA public '
                            'GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO docwise_rls',
                            current_user
                        );
                    END;
                    $$
                    """
                )
            )
            connection.execute(text("GRANT USAGE ON SCHEMA public TO docwise_rls"))
            connection.execute(
                text(
                    "GRANT SELECT, INSERT, UPDATE, DELETE "
                    "ON ALL TABLES IN SCHEMA public TO docwise_rls"
                )
            )
            connection.execute(
                text("REVOKE TRUNCATE, REFERENCES, TRIGGER ON ALL TABLES IN SCHEMA public FROM docwise_rls")
            )
            connection.execute(
                text("GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO docwise_rls")
            )
    finally:
        engine.dispose()


def main() -> None:
    ensure_rls_runtime_role()
    run_migrations()


if __name__ == "__main__":
    main()
