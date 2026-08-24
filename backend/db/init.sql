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
