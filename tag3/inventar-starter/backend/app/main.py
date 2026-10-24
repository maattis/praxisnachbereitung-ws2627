from fastapi import FastAPI, Request, Query, HTTPException, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import os
import json
from datetime import datetime
import psycopg
from .db import get_conn
from .models import DeviceCreate, AssignmentCreate, AssignmentReturn
import paho.mqtt.client as mqtt

app = FastAPI(title="Inventar Starter", version="0.1.0")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

MQTT_TOPIC_ISSUED = os.getenv("MQTT_ASSIGNMENT_ISSUED_TOPIC", "inventory/assignments/issued")
MQTT_TOPIC_RETURNED = os.getenv("MQTT_ASSIGNMENT_RETURNED_TOPIC", "inventory/assignments/returned")

def mqtt_client() -> mqtt.Client:
    c = mqtt.Client()
    c.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    return c


def _publish_assignment_event(topic: str, row) -> None:
    payload = {
        "assignment_id": row["id"],
        "device_id": row["device_id"],
        "person_id": row["person_id"],
        "issued_at": row["issued_at"].isoformat(sep=" ", timespec="seconds"),
        "returned_at": row["returned_at"].isoformat(sep=" ", timespec="seconds") if row["returned_at"] else None,
    }
    try:
        c = mqtt_client()
        c.publish(topic, json.dumps(payload), qos=0, retain=False)
        c.disconnect()
    except Exception as exc:
        print(f"[MQTT] Publish auf '{topic}' fehlgeschlagen:", exc)

@app.get("/health")
async def health():
    db_state = "ok"
    mqtt_state = "ok"
    try:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("select 1")
            cur.fetchone()
    except Exception as ex:
        db_state = f"error:{type(ex).__name__}"

    try:
        c = mqtt_client()
        c.disconnect()
    except Exception as ex:
        mqtt_state = f"degraded:{type(ex).__name__}"

    return {"status": "ok" if db_state == "ok" else "degraded", "db": db_state, "mqtt": mqtt_state}

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "title": "Inventar Starter"})


# -- Fachlogik (von JSON-API und HTML-Formularen gemeinsam genutzt) --------

def _fetch_devices(cur):
    cur.execute(
        """
        select d.id, d.serial_number, d.device_type_id, dt.name as device_type_name,
               d.location_id, l.name as location_name, d.note,
               exists(
                   select 1 from assignment a
                   where a.device_id = d.id and a.returned_at is null
               ) as currently_assigned
        from device d
        join device_type dt on dt.id = d.device_type_id
        join location l on l.id = d.location_id
        order by d.id
        """
    )
    return cur.fetchall()


def _fetch_active_assignments(cur):
    cur.execute(
        """
        select a.id, a.device_id, d.serial_number, a.person_id,
               p.first_name, p.last_name, a.issued_at, a.returned_at
        from assignment a
        join device d on d.id = a.device_id
        join person p on p.id = a.person_id
        where a.returned_at is null
        order by a.issued_at desc
        """
    )
    return cur.fetchall()


def _create_device_row(cur, serial_number: str, device_type_id: int, location_id: int, note: str | None):
    try:
        cur.execute(
            """
            insert into device (serial_number, device_type_id, location_id, note)
            values (%s, %s, %s, %s)
            returning id, serial_number, device_type_id, location_id, note
            """,
            (serial_number, device_type_id, location_id, note),
        )
    except psycopg.errors.UniqueViolation:
        raise HTTPException(status_code=409, detail=f"serial_number '{serial_number}' already exists")
    except psycopg.errors.ForeignKeyViolation:
        raise HTTPException(status_code=422, detail="invalid device_type_id or location_id")
    return cur.fetchone()


def _create_assignment_row(cur, device_id: int, person_id: int, issued_at: datetime | None):
    cur.execute("select 1 from device where id = %s", (device_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="device not found")

    cur.execute("select 1 from person where id = %s", (person_id,))
    if not cur.fetchone():
        raise HTTPException(status_code=404, detail="person not found")

    cur.execute(
        "select 1 from assignment where device_id = %s and returned_at is null",
        (device_id,),
    )
    if cur.fetchone():
        raise HTTPException(status_code=409, detail="device already has an active assignment")

    cur.execute(
        """
        insert into assignment (device_id, person_id, issued_at)
        values (%s, %s, %s)
        returning id, device_id, person_id, issued_at, returned_at
        """,
        (device_id, person_id, issued_at or datetime.now()),
    )
    row = cur.fetchone()
    _publish_assignment_event(MQTT_TOPIC_ISSUED, row)
    return row


def _return_assignment_row(cur, assignment_id: int, returned_at: datetime | None):
    cur.execute(
        "select id, issued_at, returned_at from assignment where id = %s",
        (assignment_id,),
    )
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="assignment not found")
    if row["returned_at"] is not None:
        raise HTTPException(status_code=409, detail="assignment is already returned")

    returned_at = returned_at or datetime.now()
    if returned_at < row["issued_at"]:
        raise HTTPException(status_code=422, detail="returned_at must not be before issued_at")

    cur.execute(
        """
        update assignment set returned_at = %s
        where id = %s
        returning id, device_id, person_id, issued_at, returned_at
        """,
        (returned_at, assignment_id),
    )
    row = cur.fetchone()
    _publish_assignment_event(MQTT_TOPIC_RETURNED, row)
    return row


# -- JSON-API ---------------------------------------------------------------

@app.get("/devices")
async def list_devices():
    with get_conn() as conn, conn.cursor() as cur:
        return _fetch_devices(cur)


@app.post("/devices", status_code=201)
async def create_device(data: DeviceCreate):
    with get_conn() as conn, conn.cursor() as cur:
        return _create_device_row(cur, data.serial_number, data.device_type_id, data.location_id, data.note)


@app.get("/assignments/active")
async def list_active_assignments():
    with get_conn() as conn, conn.cursor() as cur:
        return _fetch_active_assignments(cur)


@app.post("/assignments", status_code=201)
async def create_assignment(data: AssignmentCreate):
    with get_conn() as conn, conn.cursor() as cur:
        return _create_assignment_row(cur, data.device_id, data.person_id, data.issued_at)


@app.post("/assignments/{assignment_id}/return")
async def return_assignment(assignment_id: int, data: AssignmentReturn):
    with get_conn() as conn, conn.cursor() as cur:
        return _return_assignment_row(cur, assignment_id, data.returned_at)


# -- HTML-Oberfläche ----------------------------------------------------------

def _inventory_context(request: Request, cur, error: str | None = None):
    devices = _fetch_devices(cur)
    active_assignments = _fetch_active_assignments(cur)

    cur.execute(
        """
        select d.id, d.serial_number, dt.name as device_type_name, l.name as location_name
        from device d
        join device_type dt on dt.id = d.device_type_id
        join location l on l.id = d.location_id
        where not exists(
            select 1 from assignment a where a.device_id = d.id and a.returned_at is null
        )
        order by d.serial_number
        """
    )
    available_devices = cur.fetchall()

    cur.execute("select id, first_name, last_name from person order by last_name, first_name")
    persons = cur.fetchall()

    cur.execute("select id, name from device_type order by name")
    device_types = cur.fetchall()

    cur.execute("select id, name from location order by name")
    locations = cur.fetchall()

    return {
        "request": request,
        "title": "Inventar",
        "devices": devices,
        "active_assignments": active_assignments,
        "available_devices": available_devices,
        "persons": persons,
        "device_types": device_types,
        "locations": locations,
        "error": error,
    }


@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    with get_conn() as conn, conn.cursor() as cur:
        context = _inventory_context(request, cur)
    return templates.TemplateResponse("inventory.html", context)


@app.post("/inventory/devices", response_class=HTMLResponse)
async def inventory_create_device(
    request: Request,
    serial_number: str = Form(...),
    device_type_id: int = Form(...),
    location_id: int = Form(...),
    note: str = Form(""),
):
    with get_conn() as conn, conn.cursor() as cur:
        try:
            _create_device_row(cur, serial_number, device_type_id, location_id, note or None)
        except HTTPException as exc:
            context = _inventory_context(request, cur, error=exc.detail)
            return templates.TemplateResponse("inventory.html", context, status_code=exc.status_code)
    return RedirectResponse("/inventory", status_code=303)


@app.post("/inventory/assignments", response_class=HTMLResponse)
async def inventory_create_assignment(
    request: Request,
    device_id: int = Form(...),
    person_id: int = Form(...),
):
    with get_conn() as conn, conn.cursor() as cur:
        try:
            _create_assignment_row(cur, device_id, person_id, None)
        except HTTPException as exc:
            context = _inventory_context(request, cur, error=exc.detail)
            return templates.TemplateResponse("inventory.html", context, status_code=exc.status_code)
    return RedirectResponse("/inventory", status_code=303)


@app.post("/inventory/assignments/{assignment_id}/return", response_class=HTMLResponse)
async def inventory_return_assignment(request: Request, assignment_id: int):
    with get_conn() as conn, conn.cursor() as cur:
        try:
            _return_assignment_row(cur, assignment_id, None)
        except HTTPException as exc:
            context = _inventory_context(request, cur, error=exc.detail)
            return templates.TemplateResponse("inventory.html", context, status_code=exc.status_code)
    return RedirectResponse("/inventory", status_code=303)


@app.post("/mqtt/publish")
async def mqtt_publish(topic: str = Query(...), payload: str = Query(...)):
    c = mqtt_client()
    c.publish(topic, payload, qos=0, retain=False)
    c.disconnect()
    return {"ok": True, "topic": topic, "payload": payload}
