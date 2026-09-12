CREATE TABLE filings (
    doc_id VARCHAR PRIMARY KEY,
    company VARCHAR NOT NULL,
    ticker VARCHAR NOT NULL,
    cik VARCHAR NOT NULL,
    filing_type VARCHAR NOT NULL,
    fiscal_year INT NOT NULL,
    filing_date DATE,
    accession_number VARCHAR,
    source_url TEXT
);

CREATE TABLE chunks (
    chunk_id VARCHAR PRIMARY KEY,
    doc_id VARCHAR REFERENCES filings(doc_id),
    section VARCHAR NOT NULL,
    chunk_index INT NOT NULL,
    text TEXT NOT NULL,
    token_count INT,
    page_number INT
);

CREATE TABLE query_logs (
    query_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMP DEFAULT now(),
    raw_query TEXT NOT NULL,
    classified_persona VARCHAR,
    classified_query_type VARCHAR,
    retrieved_chunk_ids TEXT[],
    langsmith_trace_id VARCHAR,
    latency_ms INT,
    tokens_in INT,
    tokens_out INT,
    cost_usd NUMERIC(10, 6),
    final_answer TEXT,
    status VARCHAR
);

CREATE TABLE document_uploads (
    document_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id VARCHAR,
    original_filename VARCHAR NOT NULL,
    status VARCHAR NOT NULL DEFAULT 'processing',
    company VARCHAR,
    ticker VARCHAR,
    fiscal_year INT,
    filing_type VARCHAR,
    sections_found INT,
    chunks_indexed INT,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

CREATE TABLE eval_set (
    eval_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question TEXT NOT NULL,
    expected_answer TEXT,
    expected_chunk_ids TEXT[],
    actual_answer TEXT,
    recall_at_k NUMERIC(5, 4),
    mrr NUMERIC(5, 4),
    judge_score NUMERIC(5, 4)
);
