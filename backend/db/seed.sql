-- Development-only sample data. Do not add real vehicle numbers or personal data.
INSERT INTO vehicles (
    plate_number,
    owner_label,
    access_status,
    access_expires_at
)
VALUES
    ('12가3456', '테스트 차량 A', 'active', NULL),
    ('34나5678', '테스트 차량 B', 'inactive', NULL),
    ('56다7890', '테스트 차량 C', 'active', CURRENT_TIMESTAMP - INTERVAL '1 day')
ON CONFLICT (plate_number) DO UPDATE
SET
    owner_label = EXCLUDED.owner_label,
    access_status = EXCLUDED.access_status,
    access_expires_at = EXCLUDED.access_expires_at,
    updated_at = CURRENT_TIMESTAMP;
