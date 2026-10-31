-- Idempotent schema: safe to re-run (must apply nothing on second run).
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS loans (
    id BIGSERIAL PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    principal_kop BIGINT NOT NULL CHECK (principal_kop > 0),
    rate_bp INT NOT NULL CHECK (rate_bp > 0),
    months INT NOT NULL CHECK (months > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO schema_migrations (version)
SELECT '0001_loans'
WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version = '0001_loans');

-- Seed: 5 test credits, only on first application of 0001.
INSERT INTO loans (code, principal_kop, rate_bp, months)
SELECT *
FROM (VALUES
    ('T-001', 6_000_000, 1200, 12),
    ('T-002', 12_000_000, 1200, 24),
    ('T-003', 5_000_000, 900, 18),
    ('T-004', 8_500_000, 1500, 36),
    ('T-005', 3_000_000, 1100, 60)
) AS seed(code, principal_kop, rate_bp, months)
WHERE EXISTS (SELECT 1 FROM schema_migrations WHERE version = '0001_loans' AND applied_at::date = now()::date)
  AND NOT EXISTS (SELECT 1 FROM loans);
