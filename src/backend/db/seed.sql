-- source concepts table
CREATE TABLE IF NOT EXISTS source_concepts (
    source_id SERIAL PRIMARY KEY,
    source_value TEXT NOT NULL,
    source_concept_name TEXT NOT NULL,
    source_vocabulary_id INTEGER NOT NULL,
    freq INTEGER DEFAULT 1,
    mapped BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_source_value ON source_concepts (source_value);
CREATE INDEX IF NOT EXISTS idx_freq ON source_concepts (freq);
CREATE INDEX IF NOT EXISTS idx_source_vocabulary ON source_concepts (source_vocabulary_id);
-- OMOP vocabulary tables
CREATE TABLE IF NOT EXISTS concept (
    concept_id INTEGER PRIMARY KEY,
    concept_name TEXT NOT NULL,
    domain_id TEXT NOT NULL,
    vocabulary_id TEXT NOT NULL,
    concept_class_id TEXT NOT NULL,
    standard_concept TEXT,
    concept_code TEXT NOT NULL,
    valid_start_date DATE NOT NULL,
    valid_end_date DATE NOT NULL,
    invalid_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_concept_id ON concept (concept_id);
CREATE INDEX IF NOT EXISTS idx_domain_id ON concept (domain_id);
CREATE INDEX IF NOT EXISTS idx_vocabulary_id ON concept (vocabulary_id);
CREATE INDEX IF NOT EXISTS idx_standard_concept ON concept (standard_concept);
CREATE INDEX IF NOT EXISTS idx_concept_code ON concept (concept_code);
CREATE OR REPLACE VIEW standard_concepts AS
SELECT concept_id,
    concept_name,
    domain_id,
    vocabulary_id,
    concept_class_id,
    standard_concept,
    concept_code
FROM concept
WHERE standard_concept = 'S';
CREATE TABLE IF NOT EXISTS concept_relationship (
    concept_id_1 INTEGER NOT NULL,
    concept_id_2 INTEGER NOT NULL,
    relationship_id TEXT NOT NULL,
    valid_start_date DATE NOT NULL,
    valid_end_date DATE NOT NULL,
    invalid_reason TEXT NULL,
    CONSTRAINT fpk_concept_relationship_concept_id_1 FOREIGN KEY (concept_id_1) REFERENCES concept (concept_id),
    CONSTRAINT fpk_concept_relationship_concept_id_2 FOREIGN KEY (concept_id_2) REFERENCES concept (concept_id)
);
CREATE INDEX IF NOT EXISTS idx_concept_relationship_id_1 ON concept_relationship (concept_id_1);
CREATE INDEX IF NOT EXISTS idx_concept_relationship_id_2 ON concept_relationship (concept_id_2);
CREATE INDEX IF NOT EXISTS idx_concept_relationship_id_3 ON concept_relationship (relationship_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_concept_relationship ON concept_relationship (concept_id_1, concept_id_2, relationship_id);
CREATE TABLE IF NOT EXISTS concept_ancestor (
    ancestor_concept_id INTEGER NOT NULL,
    descendant_concept_id INTEGER NOT NULL,
    min_levels_of_separation INTEGER NOT NULL,
    max_levels_of_separation INTEGER NOT NULL,
    CONSTRAINT fpk_concept_ancestor_ancestor_concept_id FOREIGN KEY (ancestor_concept_id) REFERENCES concept (concept_id),
    CONSTRAINT fpk_concept_ancestor_descendant_concept_id FOREIGN KEY (descendant_concept_id) REFERENCES concept (concept_id)
);
CREATE INDEX IF NOT EXISTS idx_concept_ancestor_id_1 ON concept_ancestor (ancestor_concept_id);
CREATE INDEX IF NOT EXISTS idx_concept_ancestor_id_2 ON concept_ancestor (descendant_concept_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_concept_ancestor ON concept_ancestor (ancestor_concept_id, descendant_concept_id);
-- table to track embedded concepts
CREATE TABLE IF NOT EXISTS embedded_concepts (
    concept_id INTEGER NOT NULL,
    collection_name TEXT NOT NULL,
    embedding_model TEXT,
    embedded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    concept_type TEXT NOT NULL DEFAULT 'standard',
    -- 'standard' or 'source'
    source_vocabulary_id INTEGER NULL,
    -- Only for source concepts
    PRIMARY KEY (concept_id, collection_name, concept_type)
);
CREATE INDEX IF NOT EXISTS idx_embedded_concepts_type ON embedded_concepts (concept_type);
CREATE INDEX IF NOT EXISTS idx_embedded_concepts_source_vocab ON embedded_concepts (source_vocabulary_id);
-- table to store ATC7 codes for drug concepts
CREATE TABLE IF NOT EXISTS concept_atc7 (
    concept_id INTEGER NOT NULL,
    atc7_codes TEXT [] NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (concept_id),
    CONSTRAINT fk_concept_atc7_concept_id FOREIGN KEY (concept_id) REFERENCES concept (concept_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_concept_atc7_concept_id ON concept_atc7 (concept_id);
-- mappings table
CREATE TABLE IF NOT EXISTS source_standard_map (
    map_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL,
    concept_id INTEGER NOT NULL,
    CONSTRAINT fk_source_id FOREIGN KEY (source_id) REFERENCES source_concepts(source_id) ON DELETE CASCADE,
    CONSTRAINT fk_concept_id FOREIGN KEY (concept_id) REFERENCES concept(concept_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_map_source_id ON source_standard_map (source_id);
CREATE INDEX IF NOT EXISTS idx_map_concept_id ON source_standard_map (concept_id);
-- Auto-mapping audit table to track mapping method and confidence
CREATE TABLE IF NOT EXISTS auto_mapping_audit (
    audit_id SERIAL PRIMARY KEY,
    source_id INTEGER NOT NULL,
    concept_id INTEGER NOT NULL,
    confidence_score DECIMAL(5, 3),
    mapping_method TEXT NOT NULL,
    -- 'auto_drug', 'auto_standard', 'manual'
    target_domains TEXT [],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_source_id FOREIGN KEY (source_id) REFERENCES source_concepts(source_id) ON DELETE CASCADE,
    CONSTRAINT fk_audit_concept_id FOREIGN KEY (concept_id) REFERENCES concept(concept_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_auto_mapping_audit_source_id ON auto_mapping_audit (source_id);
CREATE INDEX IF NOT EXISTS idx_auto_mapping_audit_concept_id ON auto_mapping_audit (concept_id);
CREATE INDEX IF NOT EXISTS idx_auto_mapping_audit_method ON auto_mapping_audit (mapping_method);
CREATE INDEX IF NOT EXISTS idx_auto_mapping_audit_created_at ON auto_mapping_audit (created_at);
-- Configuration table for app settings
CREATE TABLE IF NOT EXISTS app_config (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_app_config_key ON app_config (key);
-- Vocabulary import tracking table
CREATE TABLE IF NOT EXISTS vocabulary_imports (
    import_id SERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    records_imported INTEGER NOT NULL DEFAULT 0,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'completed',
    error_message TEXT
);
CREATE INDEX IF NOT EXISTS idx_vocabulary_imports_table ON vocabulary_imports (table_name);
CREATE INDEX IF NOT EXISTS idx_vocabulary_imports_date ON vocabulary_imports (import_date);