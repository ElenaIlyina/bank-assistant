CREATE TABLE jobs (
    id              text PRIMARY KEY,
    kind            text NOT NULL,
    loan_id         bigint NOT NULL REFERENCES loans(id),
    status          text NOT NULL,
    payload         jsonb NOT NULL,
    result          jsonb,
    idempotency_key text UNIQUE,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX jobs_loan_kind_status ON jobs (loan_id, kind, status);

