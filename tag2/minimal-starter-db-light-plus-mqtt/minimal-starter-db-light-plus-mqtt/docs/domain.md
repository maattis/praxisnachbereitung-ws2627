# Domain Model: 

## Fachregeln
* **R1 Geräte-Lebenszyklus:** Ein physisches Gerät `Device` hat einen Status z. B. 'AVAILABLE', 'IN_USE', 'MAINTENANCE', 'LOST'. Eine Zuweisung Ausleihe darf nur erstellt werden, wenn der Status des Geräts auf 'AVAILABLE' steht.
* **R2 Trennung von Typ und Instanz:** Die Entität `DeviceModel` speichert allgemeine Spezifikationen. Die Entität `Device` repräsentiert das konkrete Gerät.
* **R3 Eine aktive Zuweisung:** Ein `Device` kann zu jedem Zeitpunkt maximal eine aktive Zuweisung `Assignment` haben.
* **R4 Integrität:** 
  * **R4_1** Das Ausgabedatum `issued_at` muss vor oder auf dem Rückgabedatum `returned_at` liegen.
  * **R4_2** Ein Gerät darf nicht vor seinem Kaufdatum `purchase_date` ausgeliehen werden.
* **R5 Zustandserfassung:** Der Zustand des Geräts muss sowohl bei der Ausgabe `condition_out` als auch bei der Rücknahme `condition_in` dokumentiert werden.

## Entity-Relationship-Diagramm

```mermaid
erDiagram
    Location ||--o{ Employee : based_at
    Location ||--o{ Device : stored_at
    DeviceModel ||--o{ Device : specifies
    Employee ||--o{ Assignment : initiates
    Device ||--o{ Assignment : is_assigned_to

    Location {
        int location_id PK
        string name UK
        string address
    }

    Employee {
        int employee_id PK
        int location_id FK
        string email UK
        string first_name
        string last_name
        string department
        boolean is_active
    }

    DeviceModel {
        int model_id PK
        string device_type
        string manufacturer
        string model_name
    }

    Device {
        string device_id PK 
        int model_id FK
        int location_id FK
        string serial_number UK
        date purchase_date
        float net_price
        string status "e.g., AVAILABLE, IN_USE, MAINTENANCE"
    }

    Assignment {
        int assignment_id PK
        string device_id FK
        int employee_id FK
        datetime issued_at
        datetime expected_return_date
        datetime returned_at "nullable"
        string condition_out
        string condition_in "nullable"
    }
