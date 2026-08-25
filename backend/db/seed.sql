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

-- Voice kiosk menu facts. Options are server-owned data; clients must never
-- submit prices or infer compatibility from the RAG documents.
INSERT INTO menu_catalog (
    menu_id,
    name,
    category,
    price,
    description,
    available,
    allergens,
    available_options,
    alternative_menu_id
)
VALUES
    (
        'burger_bulgogi',
        '불고기 버거',
        'burger',
        6500,
        '달콤한 불고기 소스와 소고기 패티가 들어간 버거',
        TRUE,
        ARRAY['밀', '대두', '계란'],
        '{"order_forms":{"single":0,"set":2500},"size_up":700,"extra_patty":1800,"extra_cheese":600,"allowed_drinks":["drink_cola","drink_cola_zero"]}'::jsonb,
        NULL
    ),
    (
        'burger_spicy_chicken',
        '매운 치킨 버거',
        'burger',
        7000,
        '매콤한 소스와 바삭한 치킨 패티가 들어간 든든한 버거',
        TRUE,
        ARRAY['밀', '대두', '계란', '우유'],
        '{"order_forms":{"single":0,"set":2500},"size_up":700,"extra_patty":2000,"extra_cheese":600,"allowed_drinks":["drink_cola","drink_cola_zero"]}'::jsonb,
        NULL
    ),
    (
        'burger_classic',
        '클래식 비프 버거',
        'burger',
        6200,
        '소고기 패티와 신선한 채소가 들어간 기본 버거',
        TRUE,
        ARRAY['밀', '대두', '계란'],
        '{"order_forms":{"single":0,"set":2500},"size_up":700,"extra_patty":1800,"extra_cheese":600,"allowed_drinks":["drink_cola","drink_cola_zero"]}'::jsonb,
        NULL
    ),
    (
        'burger_shrimp',
        '새우 버거',
        'burger',
        6800,
        '새우 패티와 타르타르 소스가 들어간 버거',
        FALSE,
        ARRAY['새우', '밀', '대두', '계란', '우유'],
        '{"order_forms":{"single":0,"set":2500},"size_up":700,"extra_patty":0,"extra_cheese":600,"allowed_drinks":["drink_cola","drink_cola_zero"]}'::jsonb,
        'burger_classic'
    ),
    (
        'side_fries',
        '감자튀김',
        'side',
        2500,
        '바삭하게 튀긴 감자튀김',
        TRUE,
        ARRAY[]::TEXT[],
        '{"sizes":{"regular":0,"large":700}}'::jsonb,
        NULL
    ),
    (
        'drink_cola',
        '콜라',
        'drink',
        2200,
        '탄산음료 콜라',
        TRUE,
        ARRAY[]::TEXT[],
        '{"sizes":{"regular":0,"large":500}}'::jsonb,
        NULL
    ),
    (
        'drink_cola_zero',
        '제로 콜라',
        'drink',
        2200,
        '설탕을 넣지 않은 탄산음료 콜라',
        TRUE,
        ARRAY[]::TEXT[],
        '{"sizes":{"regular":0,"large":500}}'::jsonb,
        NULL
    )
ON CONFLICT (menu_id) DO UPDATE
SET
    name = EXCLUDED.name,
    category = EXCLUDED.category,
    price = EXCLUDED.price,
    description = EXCLUDED.description,
    available = EXCLUDED.available,
    allergens = EXCLUDED.allergens,
    available_options = EXCLUDED.available_options,
    alternative_menu_id = EXCLUDED.alternative_menu_id,
    updated_at = CURRENT_TIMESTAMP;

-- Approved RAG source documents. Embeddings stay NULL until the Backend A
-- ingestion function calls Ollama, preventing fake or stale vectors in SQL.
INSERT INTO documents (
    id,
    collection_name,
    title,
    content,
    source,
    chunk_index,
    embedding_provider,
    embedding_model,
    embedding_dimension,
    embedding,
    metadata
)
VALUES
    (
        'fc4d7a86-2e60-50ab-ae78-f69cd42a0762', 'kiosk_menu', '불고기 버거',
        '불고기 버거는 달콤한 불고기 소스와 소고기 패티, 양상추, 피클로 구성된 단품 메뉴입니다. 가격은 6,500원이며 세트 변경이 가능합니다.',
        'menu_bulgogi', 0, 'ollama', 'embeddinggemma', 768, NULL,
        '{"type":"menu","menu_id":"burger_bulgogi","category":"burger","available":true,"allergens":["밀","대두","계란"],"intent":"menu_lookup","updated_at":"2026-08-25"}'::jsonb
    ),
    (
        '7eb53c00-b312-5ef6-91db-302c1b0c50d4', 'kiosk_menu', '매운 치킨 버거',
        '매운 치킨 버거는 매콤한 소스와 바삭한 치킨 패티로 만든 든든한 메뉴입니다. 단품은 7,000원이며 세트, 치즈 추가, 제로 콜라 변경이 가능합니다.',
        'menu_spicy_chicken', 0, 'ollama', 'embeddinggemma', 768, NULL,
        '{"type":"menu","menu_id":"burger_spicy_chicken","category":"burger","available":true,"allergens":["밀","대두","계란","우유"],"intent":"menu_lookup","updated_at":"2026-08-25"}'::jsonb
    ),
    (
        'd4b7dab9-7c4a-5708-8069-3a0c246f703a', 'kiosk_menu', '새우 버거',
        '새우 버거는 현재 품절입니다. 새우 알레르겐을 포함하며 대체 메뉴로 클래식 비프 버거를 안내할 수 있습니다.',
        'menu_shrimp', 0, 'ollama', 'embeddinggemma', 768, NULL,
        '{"type":"menu","menu_id":"burger_shrimp","category":"burger","available":false,"allergens":["새우","밀","대두","계란","우유"],"intent":"availability","updated_at":"2026-08-25"}'::jsonb
    ),
    (
        '5b436fc7-45f7-5a6d-a62e-85960ea0db59', 'kiosk_menu', '버거 세트 옵션 규칙',
        '버거는 세트로 변경할 수 있습니다. 기본 세트는 감자튀김과 음료로 구성되며 사이즈업과 허용된 음료 변경은 카탈로그 옵션을 확인해야 합니다.',
        'option_set', 0, 'ollama', 'embeddinggemma', 768, NULL,
        '{"type":"option","menu_id":null,"category":"policy","available":true,"allergens":[],"intent":"option_rule","updated_at":"2026-08-25"}'::jsonb
    ),
    (
        '01dd1fe6-9216-5dab-bbfb-019a652f50b4', 'kiosk_menu', '알레르기 안내',
        '알레르기 정보는 안내용입니다. 고객이 알레르기를 말하면 카탈로그의 알레르겐을 확인하고 교차오염 가능성이 있으므로 매장 성분표 확인을 함께 안내합니다.',
        'allergy_notice', 0, 'ollama', 'embeddinggemma', 768, NULL,
        '{"type":"allergen","menu_id":null,"category":"policy","available":true,"allergens":[],"intent":"allergy_notice","updated_at":"2026-08-25"}'::jsonb
    ),
    (
        'd8789839-8023-5fa8-962b-e4c8fe58c494', 'kiosk_menu', '품절 메뉴 안내 규칙',
        '품절 메뉴는 검색 결과에서 숨기지 않습니다. 현재 판매 불가 상태와 함께 카탈로그에 등록된 대체 메뉴를 고객에게 안내합니다.',
        'sold_out', 0, 'ollama', 'embeddinggemma', 768, NULL,
        '{"type":"availability","menu_id":null,"category":"policy","available":true,"allergens":[],"intent":"sold_out_policy","updated_at":"2026-08-25"}'::jsonb
    ),
    (
        '3ec7215b-14f9-52a5-a023-9ff2bb8bffe3', 'kiosk_menu', '매운 메뉴 추천',
        '매운맛과 든든한 구성을 원하는 고객에게는 매운 치킨 버거 세트를 추천할 수 있습니다. 주문 전 현재 판매 여부와 옵션은 카탈로그에서 다시 확인합니다.',
        'recommendation_spicy', 0, 'ollama', 'embeddinggemma', 768, NULL,
        '{"type":"recommendation","menu_id":"burger_spicy_chicken","category":"burger","available":true,"allergens":["밀","대두","계란","우유"],"intent":"recommendation","updated_at":"2026-08-25"}'::jsonb
    ),
    (
        '2f3d6a08-638a-5ba9-a471-a11d12b9e744', 'kiosk_menu', '매장 주문 정책',
        '매장 식사와 포장을 선택할 수 있으며 주문 완료 전에는 장바구니를 변경할 수 있습니다. 주문 완료 뒤에는 결제 대기 상태로 전환됩니다.',
        'store_policy', 0, 'ollama', 'embeddinggemma', 768, NULL,
        '{"type":"policy","menu_id":null,"category":"policy","available":true,"allergens":[],"intent":"store_policy","updated_at":"2026-08-25"}'::jsonb
    )
ON CONFLICT (id) DO UPDATE
SET
    collection_name = EXCLUDED.collection_name,
    title = EXCLUDED.title,
    content = EXCLUDED.content,
    source = EXCLUDED.source,
    chunk_index = EXCLUDED.chunk_index,
    metadata = EXCLUDED.metadata,
    embedding = CASE
        WHEN documents.content IS DISTINCT FROM EXCLUDED.content THEN NULL
        ELSE documents.embedding
    END;
