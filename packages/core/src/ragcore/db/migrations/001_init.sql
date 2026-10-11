-- meta: Versions and provenance
CREATE TABLE meta (
    schema_version INT PRIMARY KEY,
    text_model_name TEXT NOT NULL,
    text_model_dim INT NOT NULL,
    image_model_name TEXT NOT NULL,
    image_model_dim INT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- documents: One row per book
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    slug TEXT UNIQUE NOT NULL,
    title TEXT,
    source_hash TEXT NOT NULL,
    page_count INT NOT NULL,
    root_path TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- pages: One row per page
CREATE TABLE pages (
    id SERIAL PRIMARY KEY,
    document_id INT REFERENCES documents(id) ON DELETE CASCADE,
    page_number INT NOT NULL,
    page_hash TEXT NOT NULL,
    folder_path TEXT NOT NULL,
    image_path TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(document_id, page_number)
);

-- regions: Detected regions on a page
CREATE TABLE regions (
    id SERIAL PRIMARY KEY,
    page_id INT REFERENCES pages(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    bbox JSONB NOT NULL,
    image_path TEXT NOT NULL,
    reading_order INT NOT NULL,
    flags JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- chunks: Searchable units (text, tables, formulas)
CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    region_id INT REFERENCES regions(id) ON DELETE CASCADE,
    document_id INT REFERENCES documents(id) ON DELETE CASCADE,
    page_number INT NOT NULL,
    content_type TEXT NOT NULL,
    content TEXT NOT NULL,
    search_text TEXT NOT NULL,
    section TEXT,
    embedding vector(1024),
    tsv tsvector,
    is_deleted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- figures: Searchable figures with their own embedding space
CREATE TABLE figures (
    id SERIAL PRIMARY KEY,
    region_id INT REFERENCES regions(id) ON DELETE CASCADE,
    caption TEXT,
    description TEXT,
    image_path TEXT NOT NULL,
    embedding vector(1152),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- run_log: Per-page ingestion status
CREATE TABLE run_log (
    id SERIAL PRIMARY KEY,
    run_id TEXT NOT NULL,
    page_id INT REFERENCES pages(id) ON DELETE CASCADE,
    step TEXT NOT NULL,
    status TEXT NOT NULL,
    error_code TEXT,
    timings JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- HNSW Indexes for Vector Search
CREATE INDEX chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX figures_embedding_idx ON figures USING hnsw (embedding vector_cosine_ops);

-- Full-text and Trigram Indexes
CREATE INDEX chunks_tsv_idx ON chunks USING gin (tsv);
CREATE INDEX chunks_search_text_trgm_idx ON chunks USING gin (search_text gin_trgm_ops);

-- Regular Indexes for filtering
CREATE INDEX chunks_doc_page_idx ON chunks (document_id, page_number);
CREATE INDEX chunks_content_type_idx ON chunks (content_type);

-- Permissions for the 'ingest' role
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO ingest;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO ingest;

-- Permissions for the 'mcp_ro' read-only role
GRANT SELECT ON ALL TABLES IN SCHEMA public TO mcp_ro;
