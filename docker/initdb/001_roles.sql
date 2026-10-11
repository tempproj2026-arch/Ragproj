-- Create the roles with passwords matching the .env.example defaults
CREATE ROLE ingest WITH LOGIN PASSWORD 'secret_ingest_password';
CREATE ROLE mcp_ro WITH LOGIN PASSWORD 'secret_mcp_password';

-- Grant schema creation privileges for PostgreSQL 15+
GRANT ALL ON SCHEMA public TO ingest;
