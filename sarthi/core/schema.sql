CREATE TABLE IF NOT EXISTS source (
    source_id VARCHAR PRIMARY KEY,
    url VARCHAR,
    publisher VARCHAR,
    title VARCHAR,
    doc_type VARCHAR,
    published_on DATE,
    retrieved_at TIMESTAMP,
    sha256 VARCHAR,
    licence_note VARCHAR
);

CREATE TABLE IF NOT EXISTS document_page (
    sha256 VARCHAR,
    page_no INTEGER,
    text VARCHAR,
    char_count INTEGER,
    has_text_layer BOOLEAN,
    image_path VARCHAR,
    PRIMARY KEY (sha256, page_no)
);

CREATE TABLE IF NOT EXISTS rule_card (
    rule_id VARCHAR,
    version INTEGER,
    "group" VARCHAR,
    title_en VARCHAR,
    title_hi VARCHAR,
    source_sha256 VARCHAR,
    page_no INTEGER,
    quote VARCHAR,
    in_force_from DATE,
    in_force_to DATE,
    applies_by VARCHAR,
    triggers JSON,
    inputs JSON,
    params JSON,
    condition VARCHAR,
    if_true VARCHAR,
    if_false VARCHAR,
    question_en VARCHAR,
    question_hi VARCHAR,
    action_en VARCHAR,
    action_hi VARCHAR,
    status VARCHAR,
    approved_by VARCHAR,
    approved_at TIMESTAMP,
    status_note VARCHAR,
    PRIMARY KEY (rule_id, version)
);
ALTER TABLE rule_card ADD COLUMN IF NOT EXISTS status_note VARCHAR;

CREATE TABLE IF NOT EXISTS policy_product (
    product_id VARCHAR PRIMARY KEY,
    insurer VARCHAR,
    product_name VARCHAR,
    uin VARCHAR,
    wording_sha256 VARCHAR,
    cis_sha256 VARCHAR,
    is_standard_product BOOLEAN
);

CREATE TABLE IF NOT EXISTS policy_clause (
    product_id VARCHAR,
    clause_no VARCHAR,
    heading VARCHAR,
    text VARCHAR,
    page_no INTEGER,
    normalised_hash VARCHAR,
    PRIMARY KEY (product_id, clause_no)
);

CREATE TABLE IF NOT EXISTS "case" (
    case_id VARCHAR PRIMARY KEY,
    source_sha256 VARCHAR,
    forum VARCHAR,
    case_number VARCHAR,
    decided_on DATE,
    insurer VARCHAR,
    product_id VARCHAR,
    outcome VARCHAR,
    relief_amount DOUBLE
);

ALTER TABLE "case" ADD COLUMN IF NOT EXISTS appellant VARCHAR;
ALTER TABLE "case" ADD COLUMN IF NOT EXISTS policyholder_prevailed BOOLEAN;

CREATE TABLE IF NOT EXISTS case_issue (
    case_id VARCHAR,
    issue VARCHAR,
    holding VARCHAR,
    holding_quote VARCHAR,
    page_no INTEGER,
    status VARCHAR,
    reviewer_note VARCHAR,
    PRIMARY KEY (case_id, issue)
);

CREATE TABLE IF NOT EXISTS case_fact (
    case_id VARCHAR,
    field VARCHAR,
    value VARCHAR,
    quote VARCHAR,
    page_no INTEGER,
    confidence DOUBLE,
    status VARCHAR,
    reviewer_note VARCHAR,
    PRIMARY KEY (case_id, field)
);

CREATE TABLE IF NOT EXISTS insurer_stat (
    insurer VARCHAR,
    year VARCHAR,
    metric VARCHAR,
    value DOUBLE,
    unit VARCHAR,
    source_sha256 VARCHAR,
    page_no INTEGER,
    PRIMARY KEY (insurer, year, metric)
);

CREATE TABLE IF NOT EXISTS eval_result (
    run_id VARCHAR,
    case_id VARCHAR,
    method VARCHAR,
    repeat INTEGER,
    backend VARCHAR,
    verdicts JSON,
    agrees_with_outcome BOOLEAN,
    false_hope BOOLEAN,
    latency_ms INTEGER,
    tokens INTEGER,
    PRIMARY KEY (run_id, case_id, method, repeat)
);

CREATE TABLE IF NOT EXISTS freshness_alert (
    alert_id VARCHAR PRIMARY KEY,
    rule_id VARCHAR,
    found_url VARCHAR,
    found_title VARCHAR,
    found_on DATE,
    status VARCHAR
);
