## Wie ist das Projekt strukturiert?
- Das Backend basiert auf FastAPI und PostgreSQL, es wird MQTT für asynchrone Events genutzt.
- Das Programm läuft über Docker Compose.
- Die Code-Struktur im backend/app/ Verzeichnis ist logisch getrennt:
  - main.py Enthält alle API-Routen und die Kernlogik
  - db.py Verwaltet den Datenbankaufbau
  - models.py Definiert Datenstrukturen
  - templates/ Beinhaltet die Jinja2-HTML-Templates für das Frontend
- Die Datenbank wird beim ersten Start initialisiert.

## Wie werden Formulare verarbeitet?
- Die HTML-Formulare senden POST-Requests an die entsprechenden FastAPI-Routen
- FastAPI liest die gesendeten Formulardaten aus
- Für die Noteneingabe wird HTMX verwendet. Das Formular sendet die Daten im Hintergrund, der Server antwortet mit dem neu zu rendernden HTML-Teilstück, welches direkt ins DOM eingefügt wird.

## Wie werden Templates eingebunden?
- Das Projekt nutzt Jinja2Templates von FastAPI.
- Die API-Endpunkte geben eine TemplateResponse zurück. Dabei wird der Name der HTML-Datei und ein Dictionary übergeben.

## Wie sehen einfache CRUD-Flows aus?
- Create: Ein POST-Request wird empfangen und über INSERT-SQL-Befehle in der Datenbank gespeichert, und danach erfolgt ein Redirect zur Listenansicht.
- Read: Ein GET-Request führt ein SELECT in der Datenbank aus, übergibt die Daten an das Template, das diese dann darstellt.
- Update: Ein GET lädt das Formular mit den bestehenden Daten. Beim Speichern sendet das Formular einen POST-Request, der ein UPDATE in der DB ausführt, es folgt ein Redirect.
- Delete: Wird über ein simples POST-Formular mit einer Bestätigung gelöst. Der Endpunkt führt das DELETE in der DB aus und leitet den Nutzer.
