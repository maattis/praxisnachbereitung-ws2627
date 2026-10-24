from fastapi import FastAPI, Request, Query, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import os
from datetime import datetime
import psycopg
from .db import get_conn
from .models import DeviceCreate, AssignmentCreate, AssignmentReturn
import paho.mqtt.client as mqtt

app = FastAPI(title="Inventar Starter", version="0.1.0")
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

MQTT_HOST = os.getenv("MQTT_HOST", "mqtt")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

def mqtt_client() -> mqtt.Client:
    c = mqtt.Client()
    c.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    return c

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

@app.get("/inventory", response_class=HTMLResponse)
async def inventory_page(request: Request):
    return templates.TemplateResponse("inventory.html", {"request": request, "title": "Inventar Starter"})

@app.get("/devices")
async def list_devices():
    with get_conn() as conn, conn.cursor() as cur:
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


@app.post("/devices", status_code=201)
async def create_device(data: DeviceCreate):
    with get_conn() as conn, conn.cursor() as cur:
        try:
            cur.execute(
                """
                insert into device (serial_number, device_type_id, location_id, note)
                values (%s, %s, %s, %s)
                returning id, serial_number, device_type_id, location_id, note
                """,
                (data.serial_number, data.device_type_id, data.location_id, data.note),
            )
        except psycopg.errors.UniqueViolation:
            raise HTTPException(status_code=409, detail=f"serial_number '{data.serial_number}' already exists")
        except psycopg.errors.ForeignKeyViolation:
            raise HTTPException(status_code=422, detail="invalid device_type_id or location_id")
        return cur.fetchone()


@app.get("/assignments/active")
async def list_active_assignments():
    with get_conn() as conn, conn.cursor() as cur:
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


@app.post("/assignments", status_code=201)
async def create_assignment(data: AssignmentCreate):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute("select 1 from device where id = %s", (data.device_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="device not found")

        cur.execute("select 1 from person where id = %s", (data.person_id,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="person not found")

        cur.execute(
            "select 1 from assignment where device_id = %s and returned_at is null",
            (data.device_id,),
        )
        if cur.fetchone():
            raise HTTPException(status_code=409, detail="device already has an active assignment")

        issued_at = data.issued_at or datetime.now()
        cur.execute(
            """
            insert into assignment (device_id, person_id, issued_at)
            values (%s, %s, %s)
            returning id, device_id, person_id, issued_at, returned_at
            """,
            (data.device_id, data.person_id, issued_at),
        )
        return cur.fetchone()


@app.post("/assignments/{assignment_id}/return")
async def return_assignment(assignment_id: int, data: AssignmentReturn):
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "select id, issued_at, returned_at from assignment where id = %s",
            (assignment_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="assignment not found")
        if row["returned_at"] is not None:
            raise HTTPException(status_code=409, detail="assignment is already returned")

        returned_at = data.returned_at or datetime.now()
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
        return cur.fetchone()


@app.post("/mqtt/publish")
async def mqtt_publish(topic: str = Query(...), payload: str = Query(...)):
    c = mqtt_client()
    c.publish(topic, payload, qos=0, retain=False)
    c.disconnect()
    return {"ok": True, "topic": topic, "payload": payload}
