from database import get_db_connection


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

def list_production_records():

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
    """).fetchall()

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

def list_work_orders():

    with get_db_connection() as conn:

        rows = conn.execute(
            """
            SELECT *
            FROM work_orders
            ORDER BY work_order_id DESC
            """
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

    with get_db_connection() as conn:

        cursor = conn.execute(
            """
            INSERT INTO work_orders
            (
                line_id,
                product_id,
                target_qty,
                planned_start_at,
                due_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                line_id,
                product_id,
                target_qty,
                planned_start_at,
                due_at
            )
        )

        conn.commit()

        return cursor.lastrowid


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