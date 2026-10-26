#!/bin/sh
set -eu
# Runs only when the DB volume is first initialized. Passwords passed as environment variables.
for setting in "siteforge:$SITEFORGE_DB_PASSWORD" "commandcenter:$COMMAND_CENTER_DB_PASSWORD"; do
 user=${setting%%:*}; pw=${setting#*:}
 PGPASSWORD="$POSTGRES_PASSWORD" psql -v ON_ERROR_STOP=1 -U postgres -d postgres -v username="$user" -v password="$pw" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'username', :'password') WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'username') \gexec
SQL
done
PGPASSWORD="$POSTGRES_PASSWORD" psql -v ON_ERROR_STOP=1 -U postgres -d postgres <<'SQL'
SELECT 'CREATE DATABASE siteforge OWNER siteforge' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'siteforge') \gexec

SQL

PGPASSWORD="$POSTGRES_PASSWORD" psql -v ON_ERROR_STOP=1 -U postgres -d siteforge <<'SQL'
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
CREATE SCHEMA IF NOT EXISTS command_center AUTHORIZATION commandcenter;
GRANT CONNECT ON DATABASE siteforge TO commandcenter;
GRANT USAGE, CREATE ON SCHEMA command_center TO commandcenter;
REVOKE ALL ON SCHEMA public FROM commandcenter;
SQL
