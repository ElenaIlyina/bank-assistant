CREATE TABLE documents (
    id          text PRIMARY KEY,
    filename    text NOT NULL,
    sha256      text NOT NULL UNIQUE,
    content     bytea NOT NULL,
    status      text NOT NULL DEFAULT 'uploaded'
                CHECK (status IN (
                    'uploaded', 'parsing', 'embedding',
                    'indexed', 'rejected', 'failed'
                )),
    error       text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX documents_filename_idx ON documents (filename);

CREATE TABLE chunks (
    id              bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    document_id     text NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal         integer NOT NULL CHECK (ordinal >= 0),
    text            text NOT NULL,
    kind            text NOT NULL,
    section         text NOT NULL DEFAULT '',
    page            integer CHECK (page >= 1),
    sheet           text,
    row_number      integer CHECK (row_number >= 1),
    program_code    text,
    embedding       vector(768),
    embedding_model text,
    search_vector   tsvector GENERATED ALWAYS AS (
        to_tsvector('russian'::regconfig, section || ' ' || text)
    ) STORED,
    UNIQUE (document_id, ordinal)
);

CREATE INDEX chunks_search_vector_idx
    ON chunks USING gin (search_vector);

CREATE INDEX chunks_program_code_idx
    ON chunks (program_code);

