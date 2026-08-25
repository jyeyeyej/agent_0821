-- Parking database schema. This script runs only when the Docker volume is new.
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plate_number VARCHAR(20) NOT NULL,
    owner_label VARCHAR(100) NOT NULL,
    access_status VARCHAR(20) NOT NULL,
    access_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT vehicles_plate_number_unique UNIQUE (plate_number),
    CONSTRAINT vehicles_access_status_check
        CHECK (access_status IN ('active', 'inactive'))
);

CREATE TABLE IF NOT EXISTS entry_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id UUID NOT NULL,
    vehicle_id UUID REFERENCES vehicles(vehicle_id) ON DELETE SET NULL,
    recognized_plate_number VARCHAR(20),
    recognition_confidence NUMERIC(5, 4),
    approved BOOLEAN NOT NULL,
    gate_command VARCHAR(20) NOT NULL,
    reason TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT entry_events_request_id_unique UNIQUE (request_id),
    CONSTRAINT entry_events_gate_command_check
        CHECK (gate_command IN ('open', 'keep_closed')),
    CONSTRAINT entry_events_confidence_check
        CHECK (recognition_confidence IS NULL OR recognition_confidence BETWEEN 0 AND 1)
);

CREATE INDEX IF NOT EXISTS entry_events_created_at_idx
    ON entry_events (created_at DESC);

CREATE INDEX IF NOT EXISTS entry_events_recognized_plate_number_idx
    ON entry_events (recognized_plate_number);

-- Voice kiosk knowledge and order schema. Existing parking tables above are
-- intentionally kept independent so each domain can be merged safely.
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY,
    collection_name VARCHAR(100) NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    source VARCHAR(200) NOT NULL,
    chunk_index INTEGER NOT NULL DEFAULT 0,
    embedding_provider VARCHAR(50) NOT NULL DEFAULT 'ollama',
    embedding_model VARCHAR(100) NOT NULL DEFAULT 'embeddinggemma',
    embedding_dimension INTEGER NOT NULL DEFAULT 768,
    embedding vector(768),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT documents_source_chunk_unique
        UNIQUE (collection_name, source, chunk_index),
    CONSTRAINT documents_chunk_index_check CHECK (chunk_index >= 0),
    CONSTRAINT documents_embedding_dimension_check CHECK (embedding_dimension = 768)
);

CREATE TABLE IF NOT EXISTS menu_catalog (
    menu_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(200) NOT NULL,
    category VARCHAR(50) NOT NULL,
    price INTEGER NOT NULL,
    description TEXT NOT NULL,
    available BOOLEAN NOT NULL DEFAULT TRUE,
    allergens TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    available_options JSONB NOT NULL DEFAULT '{}'::jsonb,
    alternative_menu_id VARCHAR(100) REFERENCES menu_catalog(menu_id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT menu_catalog_price_check CHECK (price >= 0)
);

CREATE TABLE IF NOT EXISTS order_sessions (
    session_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(30) NOT NULL DEFAULT 'active',
    order_type VARCHAR(20) NOT NULL DEFAULT 'takeout',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT order_sessions_status_check
        CHECK (status IN ('active', 'ready_for_payment', 'cancelled')),
    CONSTRAINT order_sessions_order_type_check
        CHECK (order_type IN ('dine_in', 'takeout'))
);

CREATE TABLE IF NOT EXISTS order_cart_items (
    item_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES order_sessions(session_id) ON DELETE CASCADE,
    menu_id VARCHAR(100) NOT NULL REFERENCES menu_catalog(menu_id),
    quantity INTEGER NOT NULL,
    order_form VARCHAR(20) NOT NULL DEFAULT 'single',
    selected_options JSONB NOT NULL DEFAULT '{}'::jsonb,
    unit_price INTEGER NOT NULL,
    option_price INTEGER NOT NULL DEFAULT 0,
    line_total INTEGER NOT NULL,
    allergen_snapshot TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT order_cart_items_quantity_check CHECK (quantity BETWEEN 1 AND 10),
    CONSTRAINT order_cart_items_order_form_check CHECK (order_form IN ('single', 'set')),
    CONSTRAINT order_cart_items_price_check
        CHECK (unit_price >= 0 AND option_price >= 0 AND line_total >= 0)
);

CREATE TABLE IF NOT EXISTS conversation_turns (
    turn_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES order_sessions(session_id) ON DELETE CASCADE,
    transcript TEXT NOT NULL,
    confidence DOUBLE PRECISION NOT NULL,
    document_ids UUID[] NOT NULL DEFAULT ARRAY[]::UUID[],
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT conversation_turns_transcript_check CHECK (length(btrim(transcript)) > 0),
    CONSTRAINT conversation_turns_confidence_check CHECK (confidence BETWEEN 0.0 AND 1.0)
);

CREATE INDEX IF NOT EXISTS documents_retrieval_filter_idx
    ON documents (collection_name, embedding_provider, embedding_model, embedding_dimension);

CREATE INDEX IF NOT EXISTS documents_metadata_idx
    ON documents USING gin (metadata);

CREATE INDEX IF NOT EXISTS documents_embedding_cosine_idx
    ON documents USING hnsw (embedding vector_cosine_ops)
    WHERE embedding IS NOT NULL;

CREATE INDEX IF NOT EXISTS menu_catalog_category_available_idx
    ON menu_catalog (category, available);

CREATE INDEX IF NOT EXISTS order_cart_items_session_id_idx
    ON order_cart_items (session_id);

CREATE INDEX IF NOT EXISTS conversation_turns_session_created_at_idx
    ON conversation_turns (session_id, created_at);
