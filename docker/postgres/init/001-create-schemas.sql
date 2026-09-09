-- Bootstraps one PostgreSQL schema per module.
-- Runs only on an empty data directory; Alembic keeps the objects inside each
-- schema up to date afterwards.

CREATE SCHEMA IF NOT EXISTS shipment;
CREATE SCHEMA IF NOT EXISTS customs;
CREATE SCHEMA IF NOT EXISTS files;

COMMENT ON SCHEMA shipment IS 'Shipment Management bounded context.';
COMMENT ON SCHEMA customs IS 'Customs Clearance bounded context.';
COMMENT ON SCHEMA files IS 'Files: shared storage-class-agnostic file service.';
