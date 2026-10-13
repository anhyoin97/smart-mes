from fastapi import FastAPI, Body, Request, Form
import service

from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

app = FastAPI(
    swagger_ui_parameters={
        "operationsSorter": "alpha"
    }
)

templates = Jinja2Templates(
    directory="templates"
)

# ============================================================
# 기본
# ============================================================

@app.get("/")
def home():
    return "MES Server 실행 성공"


# ============================================================
# 생산라인 조회
# ============================================================

@app.get("/api/lines")
def list_lines(status: str | None = None):

    result = service.list_lines(status)

    return result


# ============================================================
# 생산라인 등록
# ============================================================

@app.post("/api/lines")
def create_line(data: dict = Body(...)):

    line_id = service.create_line(
        data["line_id"],
        data["line_name"],
        data.get("status", "stopped")
    )

    return {
        "success": True,
        "line_id": line_id
    }


# ============================================================
# 생산라인 수정
# ============================================================

@app.put("/api/lines/{line_id}")
def update_line(
    line_id: str,
    data: dict = Body(...)
):

    affected = service.update_line(
        line_id,
        data["line_name"],
        data["status"]
    )

    if affected == 0:
        return {
            "success": False,
            "message": "해당 생산라인을 찾을 수 없습니다."
        }

    return {
        "success": True,
        "line_id": line_id
    }


# ============================================================
# 제품 조회
# ============================================================

@app.get("/api/products")
def list_products():
    result = service.list_products()
    return result


# ============================================================
# 제품 등록
# ============================================================

@app.post("/api/products")
def create_product(data: dict = Body(...)):

    product_id = service.create_product(
        data["product_id"],
        data["product_name"]
    )

    return {
        "success": True,
        "product_id": product_id
    }


# ============================================================
# 제품 수정
# ============================================================

@app.put("/api/products/{product_id}")
def update_product(
    product_id: str,
    data: dict = Body(...)
):

    affected = service.update_product(
        product_id,
        data["product_name"]
    )

    if affected == 0:
        return {
            "success": False,
            "message": "해당 제품을 찾을 수 없습니다."
        }

    return {
        "success": True,
        "product_id": product_id
    }


# ============================================================
# 생산실적 조회
# ============================================================

@app.get("/api/production-records")
def list_production_records():

    result = service.list_production_records()

    return result


# ============================================================
# 생산실적 등록
# - 라인, 제품, 목표수량은 작업지시에서 가져온다
# ============================================================

@app.post("/api/production-records")
def create_production_record(data: dict = Body(...)):

    production_record_id = service.create_production_record(
        data["work_order_id"],
        data["production_date"],
        data["produced_qty"]
    )

    if production_record_id is None:
        return {
            "success": False,
            "message": "해당 작업지시를 찾을 수 없습니다."
        }

    return {
        "success": True,
        "production_record_id": production_record_id
    }


# ============================================================
# 생산실적 수정
# ============================================================

@app.put("/api/production-records/{production_record_id}")
def update_production_record(
    production_record_id: int,
    data: dict = Body(...)
):
    affected = service.update_production_record(
        production_record_id,
        data["produced_qty"]
    )

    if affected == 0:
        return {
            "success": False,
            "message": "해당 생산실적을 찾을 수 없습니다."
        }

    return {
        "success": True,
        "production_record_id": production_record_id
    }


# ============================================================
# 생산실적 삭제
# ============================================================

@app.delete("/api/production-records/{production_record_id}")
def delete_production_record(production_record_id: int):

    affected = service.delete_production_record(production_record_id)

    if affected == 0:
        return {
            "success": False,
            "message": "해당 생산실적을 찾을 수 없습니다."
        }

    return {
        "success": True,
        "production_record_id": production_record_id
    }


# ============================================================
# 작업지시 조회
# ============================================================

@app.get("/api/work-orders")
def list_work_orders():

    return service.list_work_orders()


# ============================================================
# 작업지시 등록
# ============================================================

@app.post("/api/work-orders")
def create_work_order(data: dict = Body(...)):

    work_order_id = service.create_work_order(
        data["line_id"],
        data["product_id"],
        data["target_qty"],
        data["planned_start_at"],
        data["due_at"]
    )

    return {
        "success": True,
        "work_order_id": work_order_id,
        "status": "planned"
    }


# ============================================================
# 작업지시 착수
# ============================================================

@app.post("/api/work-orders/{work_order_id}/start")
def start_work_order(work_order_id: int):

    affected = service.start_work_order(work_order_id)

    if affected == 0:
        return {
            "success": False,
            "message": "작업지시를 찾을 수 없습니다."
        }

    return {
        "success": True,
        "work_order_id": work_order_id,
        "status": "running"
    }


# ============================================================
# 작업지시 완료
# ============================================================

@app.post("/api/work-orders/{work_order_id}/complete")
def complete_work_order(work_order_id: int):

    affected = service.complete_work_order(work_order_id)

    if affected == 0:
        return {
            "success": False,
            "message": "작업지시를 찾을 수 없습니다."
        }

    return {
        "success": True,
        "work_order_id": work_order_id,
        "status": "completed"
    }

@app.get("/test", response_class=HTMLResponse)
def test_page(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="test.html",
        context={
            "title": "MES",
            "message": "Web MES",
            "url": "http://kmu.ac.kr"
        }
    )

# ============================================================
# HTML용 제품 조회
# ============================================================

@app.get("/products", response_class=HTMLResponse)
def products_page(request: Request):

    result = service.list_products()

    return templates.TemplateResponse(
        request=request,
        name="products.html",
        context={
            "products": result
        }
    )

# ============================================================
# HTML용 제품 추가
# ============================================================

@app.post("/products")
def create_product_page(
    product_id: str = Form(...),
    product_name: str = Form(...)
):
    service.create_product(product_id, product_name)

    return RedirectResponse(
        url="/products",
        status_code=303
    )

# ============================================================
# HTML용 생산실적 조회
# ============================================================

@app.get("/production-records", response_class=HTMLResponse)
def production_records_page(request: Request):
    
    # 생산실적 데이터 조회
    production = service.list_production_records()
    
    # 작업지시 데이터 조회
    orders = service.list_work_orders()

    return templates.TemplateResponse(
        request=request,
        name="production.html",
        context={
            "production": production,
            "orders": orders
        }
    )

# ============================================================
# HTML용 생산실적 등록
# ============================================================

@app.post("/production-records")
def create_production_record_page(
    work_order_id: int = Form(...),
    production_date: str = Form(...),
    produced_qty: int = Form(...)
):
    production_record_id = service.create_production_record(
        work_order_id,
        production_date,
        produced_qty
    )

    if production_record_id is None:
        return RedirectResponse(
            url="/production-records",
            status_code=303
        )

    return RedirectResponse(
        url="/production-records",
        status_code=303
    )

# ============================================================
# HTML용 생산라인 조회
# ============================================================

@app.get("/lines", response_class=HTMLResponse)
def lines_page(request: Request):

    # 생산라인 데이터 조회
    lines = service.list_lines()

    return templates.TemplateResponse(
        request=request,
        name="lines.html",
        context={
            "lines": lines
        }
    )

# ============================================================
# HTML용 생산라인 등록
# ============================================================
    
@app.post("/lines")
def create_line_page(
    line_id: str = Form(...),
    line_name: str = Form(...),
    status: str = Form(...)
):
    service.create_line(line_id, line_name, status)

    return RedirectResponse(
        url="/lines",
        status_code=303
    )

# ============================================================
# HTML용 생산라인 수정
# ============================================================
@app.patch("/lines/{line_id}")
def update_line_page(
    line_id: str,
    line_name: str = Body(...),
    status: str = Body(...)
):
    result = service.update_line(
        line_id,
        line_name,
        status
    )

    return {
        "message": "생산라인 수정 완료",
        "line_id": line_id
    }