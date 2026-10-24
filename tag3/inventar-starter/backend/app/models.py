from datetime import datetime
from pydantic import BaseModel


class DeviceCreate(BaseModel):
  serial_number: str
  device_type_id: int
  location_id: int
  note: str | None = None


class AssignmentCreate(BaseModel):
  device_id: int
  person_id: int
  issued_at: datetime | None = None


class AssignmentReturn(BaseModel):
  returned_at: datetime | None = None
