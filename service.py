from database import get_db_connection
import uuid
from pathlib import Path
import ai_service

# ============================================================
# 생산라인 조회
# ============================================================

def list_lines(status: str | None = None):

    conn = get_db_connection()

    if status is None:

        rows = conn.execute("""
            SELECT
                line_id,
                line_name,
                status
            FROM production_lines
            ORDER BY line_id
        """).fetchall()

    else:

        rows = conn.execute("""
            SELECT
                line_id,
                line_name,
                status
            FROM production_lines
            WHERE status = ?
            ORDER BY line_id
        """, (status,)).fetchall()

    conn.close()

    result = []

    for row in rows:
        result.append(dict(row))

    return result


# ============================================================
# 생산라인 등록
# ============================================================

def create_line(
    line_id,
    line_name,
    status
):

    with get_db_connection() as conn:

        conn.execute(
            """
            INSERT INTO production_lines
            (
                line_id,
                line_name,
                status
            )
            VALUES (?, ?, ?)
            """,
            (
                line_id,
                line_name,
                status
            )
        )

        conn.commit()

        return line_id


# ============================================================
# 생산라인 수정
# ============================================================

def update_line(
    line_id,
    line_name,
    status
):

    with get_db_connection() as conn:

        cursor = conn.execute(
            """
            UPDATE production_lines

            SET line_name = ?,
                status = ?

            WHERE line_id = ?
            """,
            (
                line_name,
                status,
                line_id
            )
        )

        conn.commit()

        return cursor.rowcount


# ============================================================
# 제품 조회
# ============================================================

def list_products():

    conn = get_db_connection()

    rows = conn.execute("""
        SELECT
            product_id,
            product_name
        FROM products
        ORDER BY product_id
    """).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


# ============================================================
# 제품 등록
# ============================================================

def create_product(
    product_id,
    product_name
):

    with get_db_connection() as conn:

        conn.execute(
            """
            INSERT INTO products
            (
                product_id,
                product_name
            )
            VALUES (?, ?)
            """,
            (
                product_id,
                product_name
            )
        )

        conn.commit()

        return product_id


# ============================================================
# 제품 수정
# ============================================================

def update_product(
    product_id,
    product_name
):

    with get_db_connection() as conn:

        cursor = conn.execute(
            """
            UPDATE products

            SET product_name = ?

            WHERE product_id = ?
            """,
            (
                product_name,
                product_id
            )
        )

        conn.commit()

        return cursor.rowcount


# ============================================================
# 생산실적 조회
# - 라인, 제품, 목표수량은 작업지시를 통해 가져온다
# ============================================================

def list_production_records(limit: int = 100):

    conn = get_db_connection()

    rows = conn.execute("""
        SELECT
            r.production_record_id,
            r.work_order_id,
            r.production_date,

            o.line_id,
            l.line_name,

            o.product_id,
            p.product_name,

            o.target_qty,
            r.produced_qty

        FROM production_records r

        JOIN work_orders o
            ON r.work_order_id = o.work_order_id

        JOIN production_lines l
            ON o.line_id = l.line_id

        JOIN products p
            ON o.product_id = p.product_id

        ORDER BY
            r.production_date DESC,
            r.production_record_id DESC
        LIMIT ?
    """, (limit,)).fetchall()

    conn.close()

    result = []

    for row in rows:
        result.append(dict(row))

    return result


# ============================================================
# 생산실적 등록
# - 작업지시가 없으면 None 반환
# ============================================================

def create_production_record(
    work_order_id,
    production_date,
    produced_qty
):

    with get_db_connection() as conn:

        order = conn.execute(
            """
            SELECT work_order_id
            FROM work_orders
            WHERE work_order_id = ?
            """,
            (work_order_id,)
        ).fetchone()

        if order is None:
            return None

        cursor = conn.execute(
            """
            INSERT INTO production_records
            (
                work_order_id,
                production_date,
                produced_qty
            )
            VALUES (?, ?, ?)
            """,
            (
                work_order_id,
                production_date,
                produced_qty
            )
        )

        conn.commit()

        return cursor.lastrowid


# ============================================================
# 생산실적 수정
# ============================================================

def update_production_record(
    production_record_id,
    produced_qty
):

    with get_db_connection() as conn:

        cursor = conn.execute(
            """
            UPDATE production_records

            SET produced_qty = ?

            WHERE production_record_id = ?
            """,
            (
                produced_qty,
                production_record_id
            )
        )

        conn.commit()

        return cursor.rowcount


# ============================================================
# 생산실적 삭제
# ============================================================

def delete_production_record(production_record_id):

    with get_db_connection() as conn:

        cursor = conn.execute(
            """
            DELETE
            FROM production_records
            WHERE production_record_id = ?
            """,
            (production_record_id,)
        )

        conn.commit()

        return cursor.rowcount


# ============================================================
# 작업지시 조회
# ============================================================

def list_work_orders(limit: int = 100):

    with get_db_connection() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM work_orders
            ORDER BY work_order_id DESC
            LIMIT ?
            """,
            (limit,)
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]


# ============================================================
# 작업지시 등록
# ============================================================

def create_work_order(
    line_id,
    product_id,
    target_qty,
    planned_start_at,
    due_at
):

    # 1. 입력값 검증
    if target_qty <= 0:
        raise ValueError("목표 생산수량은 0보다 커야 합니다.")

    if planned_start_at >= due_at:
        raise ValueError("납기는 계획 시작시각보다 늦어야 합니다.")

    # 2. DNN 모델로 생산 소요시간 예측
    predicted_duration_h = ai_service.predict_duration(
        line_id,
        product_id,
        target_qty,
        planned_start_at
    )

    with get_db_connection() as conn:

        cursor = conn.execute(
            """
            INSERT INTO work_orders
            (
                line_id,
                product_id,
                target_qty,
                planned_start_at,
                due_at,
                predicted_duration_h
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                line_id,
                product_id,
                target_qty,
                planned_start_at,
                due_at,
                predicted_duration_h
            )
        )

        work_order_id = cursor.lastrowid
        
        conn.commit()

        return {
            "work_order_id": work_order_id,
            "predicted_duration_h": predicted_duration_h
        }


# ============================================================
# 작업지시 착수
# ============================================================

def start_work_order(work_order_id):

    with get_db_connection() as conn:

        cursor = conn.execute(
            """
            UPDATE work_orders

            SET status = 'running',
                actual_start_at = datetime('now', 'localtime')

            WHERE work_order_id = ?
            """,
            (work_order_id,)
        )

        conn.commit()

        return cursor.rowcount


# ============================================================
# 작업지시 완료
# ============================================================

def complete_work_order(work_order_id):

    with get_db_connection() as conn:

        cursor = conn.execute(
            """
            UPDATE work_orders

            SET status = 'completed',
                actual_end_at = datetime('now', 'localtime')

            WHERE work_order_id = ?
            """,
            (work_order_id,)
        )

        conn.commit()

        return cursor.rowcount


# ============================================================
# 품질검사 조회
# ============================================================

def list_quality_inspections(limit: int = 100):

    with get_db_connection() as conn:
    
        rows = conn.execute(
		        """
            SELECT
                q.*,
                w.line_id,
                w.product_id,
                l.line_name,
                p.product_name
            FROM quality_inspections q
            JOIN work_orders w
                ON q.work_order_id = w.work_order_id
            JOIN production_lines l
                ON w.line_id = l.line_id
            JOIN products p
                ON w.product_id = p.product_id
            ORDER BY q.inspection_id DESC
            LIMIT ?
        """, (limit,)).fetchall()

    return [dict(row) for row in rows]


# ============================================================
# 품질검사 등록
# ============================================================

def create_quality_inspection(
    work_order_id,
    copper, mousebite, open, pin_hole, short, spur,
    raw_image=None,
    det_image=None
):

    # 1. 결함 개수 검증
    defect_counts = [
        copper, mousebite, open, pin_hole, short, spur
    ]

    if any(count < 0 for count in defect_counts):
        raise ValueError("결함 개수는 0 이상이어야 합니다.")

    # 2. 검사 결과 판정
    result = "FAIL" if sum(defect_counts) > 0 else "PASS"

    # 3. 이미지 확인
    if (raw_image is None) != (det_image is None):
        raise ValueError("원본과 결과 이미지를 모두 전달해야 합니다.")

    # 4. 이미지가 있으면 UUID 생성
    image_id = uuid.uuid4().hex if raw_image is not None else None

    with get_db_connection() as conn:

        # 5. 작업지시 존재 여부 확인
        order = conn.execute("""
            SELECT work_order_id
            FROM work_orders
            WHERE work_order_id = ?
        """, (work_order_id,)).fetchone()

        if order is None:
            return None

        raw_path = None
        det_path = None

        try:
            # 6. 이미지가 있으면 파일 저장
            if image_id is not None:

                upload_dir = (
                    Path(__file__).resolve().parent
                    / "static" / "inspections"
                )
                upload_dir.mkdir(parents=True, exist_ok=True)

                raw_path = upload_dir / f"{image_id}_raw.jpg"
                det_path = upload_dir / f"{image_id}_det.png"

                raw_path.write_bytes(raw_image)
                det_path.write_bytes(det_image)

            # 7. 품질검사 DB 등록
            cursor = conn.execute("""
                INSERT INTO quality_inspections (
                    work_order_id,
                    image_id,
                    copper, mousebite, open, pin_hole, short, spur,
                    result
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                work_order_id,
                image_id,
                copper, mousebite, open, pin_hole, short, spur,
                result
            ))

            conn.commit()

            return cursor.lastrowid

        except Exception:
            conn.rollback()

            # 저장 중 오류가 발생했다면 이미지 삭제
            if raw_path is not None:
                raw_path.unlink(missing_ok=True)

            if det_path is not None:
                det_path.unlink(missing_ok=True)

            raise


# ============================================================
# 생산라인 센서 이력 조회
# ============================================================

def list_line_sensor_readings(line_id=None):

    with get_db_connection() as conn:

        rows = conn.execute("""
            SELECT
                s.*,
                l.line_name
            FROM line_sensor_readings s
            JOIN production_lines l
                ON s.line_id = l.line_id
            WHERE (? IS NULL OR s.line_id = ?)
            ORDER BY s.measured_at DESC, s.reading_id DESC
            LIMIT 100
        """, (line_id, line_id)).fetchall()

    return [dict(row) for row in rows]
    
    
# ============================================================
# 생산라인 센서 데이터 등록
# ============================================================

def create_line_sensor_reading(
    line_id,
    temperature,
    vibration,
    current,
    rpm,
    health_status
):

    # 건전성 상태 검증
    if health_status is not None and health_status not in ("normal", "warning", "abnormal"):
        raise ValueError("올바르지 않은 건전성 상태입니다.")

    with get_db_connection() as conn:

        # 생산라인 존재 여부 확인
        line = conn.execute("""
            SELECT line_id
            FROM production_lines
            WHERE line_id = ?
        """, (line_id,)).fetchone()

        if line is None:
            return None

        # 센서 데이터 등록
        cursor = conn.execute("""
            INSERT INTO line_sensor_readings (
                line_id,
                temperature,
                vibration,
                current,
                rpm,
                health_status
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            line_id,
            temperature,
            vibration,
            current,
            rpm,
            health_status
        ))

        conn.commit()

        return cursor.lastrowid    