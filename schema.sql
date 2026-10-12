-- ============================================================
-- 생산라인
-- ============================================================

CREATE TABLE IF NOT EXISTS production_lines (
    line_id     TEXT PRIMARY KEY,
    line_name   TEXT NOT NULL,
    status      TEXT NOT NULL
);


-- ============================================================
-- 제품
-- ============================================================

CREATE TABLE IF NOT EXISTS products (
    product_id      TEXT PRIMARY KEY,
    product_name    TEXT NOT NULL
);


-- ============================================================
-- 작업지시
-- ============================================================

CREATE TABLE IF NOT EXISTS work_orders (

    work_order_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id             TEXT    NOT NULL,
    product_id          TEXT    NOT NULL,
    target_qty          INTEGER NOT NULL CHECK (target_qty > 0),
    status              TEXT    NOT NULL DEFAULT 'planned'
                        CHECK (status IN ('planned', 'running', 'completed')),
    planned_start_at    TEXT    NOT NULL,
    due_at              TEXT    NOT NULL,
    actual_start_at     TEXT,
    actual_end_at       TEXT,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (line_id)
        REFERENCES production_lines(line_id),

    FOREIGN KEY (product_id)
        REFERENCES products(product_id)
    
);

-- ============================================================
-- 생산실적
-- ============================================================

CREATE TABLE IF NOT EXISTS production_records (
    production_record_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id           INTEGER NOT NULL,
    production_date         TEXT    NOT NULL,
    produced_qty            INTEGER NOT NULL CHECK (produced_qty >= 0),
    
    FOREIGN KEY (work_order_id)
        REFERENCES work_orders(work_order_id)
);


-- ============================================================
-- 기초 데이터
-- ============================================================

INSERT OR IGNORE INTO production_lines
(line_id, line_name, status)
VALUES
('LINE-01', '조립라인 1', 'running'),
('LINE-02', '조립라인 2', 'running'),
('LINE-03', '포장라인 1', 'stopped');


INSERT OR IGNORE INTO products
(product_id, product_name)
VALUES
('PROD-A', '스마트 센서'),
('PROD-B', '제어 모듈'),
('PROD-C', 'IoT Gateway');

-- ============================================================
-- 예시 데이터
-- - 번호를 직접 지정해서 여러 번 실행해도 중복되지 않게 함
-- ============================================================

INSERT OR IGNORE INTO work_orders
(
    work_order_id,
    line_id,
    product_id,
    target_qty,
    status,
    planned_start_at,
    due_at,
    actual_start_at,
    actual_end_at
)
VALUES
(1, 'LINE-01', 'PROD-A', 1000, 'completed',
    '2026-09-26 08:00:00', '2026-09-26 18:00:00',
    '2026-09-26 08:05:00', '2026-09-26 17:40:00'),
 
(2, 'LINE-02', 'PROD-B',  800, 'completed',
    '2026-09-26 08:00:00', '2026-09-26 18:00:00',
    '2026-09-26 08:10:00', '2026-09-26 17:50:00'),
 
(3, 'LINE-01', 'PROD-A', 1000, 'completed',
    '2026-09-27 08:00:00', '2026-09-27 18:00:00',
    '2026-09-27 08:00:00', '2026-09-27 18:20:00'),
 
(4, 'LINE-02', 'PROD-B',  800, 'completed',
    '2026-09-27 08:00:00', '2026-09-27 18:00:00',
    '2026-09-27 08:15:00', '2026-09-27 18:05:00'),
 
(5, 'LINE-03', 'PROD-C',  500, 'completed',
    '2026-09-27 09:00:00', '2026-09-27 17:00:00',
    '2026-09-27 09:30:00', '2026-09-27 17:30:00'),
 
(6, 'LINE-01', 'PROD-A', 1000, 'planned',
    '2026-10-12 08:00:00', '2026-10-12 18:00:00',
    NULL, NULL);
 
 
INSERT OR IGNORE INTO production_records
(
    production_record_id,
    work_order_id,
    production_date,
    produced_qty
)
VALUES
(1, 1, '2026-09-26', 980),
(2, 2, '2026-09-26', 790),
(3, 3, '2026-09-27', 930),
(4, 4, '2026-09-27', 760),
(5, 5, '2026-09-27', 420);