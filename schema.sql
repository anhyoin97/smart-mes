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
    predicted_duration_h REAL,
    predicted_late      INTEGER CHECK(predicted_late IN (0, 1)),
    predicted_late_probability REAL
        CHECK(predicted_late_probability BETWEEN 0 AND 1),
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
-- 품질검사 테이블
-- ============================================================

CREATE TABLE IF NOT EXISTS quality_inspections (
    inspection_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    work_order_id       INTEGER NOT NULL,
    image_id            TEXT UNIQUE,

    copper              INTEGER NOT NULL DEFAULT 0 CHECK (copper >= 0),
    mousebite           INTEGER NOT NULL DEFAULT 0 CHECK (mousebite >= 0),
    open                INTEGER NOT NULL DEFAULT 0 CHECK (open >= 0),
    pin_hole            INTEGER NOT NULL DEFAULT 0 CHECK (pin_hole >= 0),
    short               INTEGER NOT NULL DEFAULT 0 CHECK (short >= 0),
    spur                INTEGER NOT NULL DEFAULT 0 CHECK (spur >= 0),

    result              TEXT NOT NULL CHECK (result IN ('PASS', 'FAIL')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (work_order_id)
        REFERENCES work_orders(work_order_id)
);

-- ============================================================
-- 생산라인 센서 이력 테이블
-- ============================================================

CREATE TABLE IF NOT EXISTS line_sensor_readings (
    reading_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    line_id         TEXT NOT NULL,

    temperature     REAL NOT NULL,
    vibration       REAL NOT NULL,
    current         REAL NOT NULL,
    rpm             REAL NOT NULL,

    health_status   TEXT
                    CHECK (health_status IN (
                        'normal', 'warning', 'abnormal'
                    )),

    measured_at     TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),

    FOREIGN KEY (line_id)
        REFERENCES production_lines(line_id)
);