import os
import sys
import requests # pyright: ignore[reportMissingModuleSource]
from datetime import datetime, timedelta
import time
import smtplib
from email.mime.text import MIMEText
import logging
# Bei Dokumenten mit CUSTOM_FIELD_NAME="Fälligkeit" gesetzt auf in den nächsten 3 Tagen das Tag TODO_TAG_NAME="ToDoHorst" setzen

# ToDo:
# eMail mit den Docs sortiert nach Fälligkeit

# docker run --rm -d --network paperless_default -v /volume1/docker/paperless-overdue/todo.py:/app/todo.py:ro -v /volume1/docker/paperless-overdue/.env:/app/.env:ro -v /volume1/docker/paperless-overdue/logs:/app/logs paperless-todo:latest

class FlushStreamHandler(logging.StreamHandler):
  def emit(self, record):
    super().emit(record)
    self.flush()  # erzwingt sofortigen Flush

logging.basicConfig(
  level=logging.INFO
  , format="%(asctime)s - %{script}s [%(levelname)s] %(message)s"
  , datefmt="%Y-%m-%d %H:%M:%S"
  , handlers=[FlushStreamHandler(sys.stdout)]
  )


# ----------------------
# Konfiguration aus Env
# ----------------------
# load_dotenv()  # sollte beim Start von Shell automatisch alle Variablen aus .env laden, aber import load_dotenv # pyright: ignore[reportMissingImports]
# apt und apk fehlen im Slim-Container, um pip zu installieren !

# ----------------------------
# ToDo.env Datei zu Fuß einlesen (kein pip):
# ----------------------------
envFileName=".env"
env_path = os.path.join(os.path.dirname(__file__), envFileName)
if os.path.exists(env_path):
  with open(env_path) as f:
    for line in f:
      line = line.strip()
      if not line or line.startswith("#"):
        continue
      key, value = line.split("=", 1)
      os.environ[key] = value
else :
  logging.error(f"File {env_path} not found")
  exit()   

PAPERLESS_URL = os.environ.get("PAPERLESS_URL")
API_TOKEN = os.environ.get("API_TOKEN")
DAYS_AHEAD = int(os.environ.get("DAYS_AHEAD", 3))
TODO_TAG_NAME = os.environ.get("TODO_TAG", "ToDo")
DUE_FIELD_NAME = os.environ.get("DUE_FIELD", "DueDate")
HEADERS = {"Authorization": f"Token {API_TOKEN}"}
OVERDUE_UNSET_DAYS = int(os.environ.get("OVERDUE_UNSET_DAYS", "99999"))

# ----------------------------
# Funktion: E-Mail senden
# ----------------------------
def send_email(message, subject="Paperless ToDo Update"):
  smtp_server = os.environ.get("EMAIL_SMTP_SERVER")
  smtp_port = int(os.environ.get("EMAIL_SMTP_PORT", 587))
  user = os.environ.get("EMAIL_USER")
  password = os.environ.get("EMAIL_PASSWORD")
  to_addr = os.environ.get("EMAIL_TO")
  use_tls = os.environ.get("EMAIL_USE_TLS", "true").lower() == "true"

  if not smtp_server or not user or not password or not to_addr:
    # kein E-Mail konfiguriert
    return
  try:
    msg = MIMEText(message)
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr

    with smtplib.SMTP(smtp_server, smtp_port) as server:
      if use_tls:
        server.starttls()
      server.login(user, password)
      server.send_message(msg)
  except Exception as e:
    logging.error(f"E-Mail-Fehler: {e}")


logging.info(f"Starting {__file__} ...")
messagesSet = []
messagesUnset = []

today = datetime.today().date()
start = time.time()
limit_set_date = today + timedelta(days=DAYS_AHEAD) # z.B. heute in 3 Tagen
limit_unset_date = today - timedelta(days=OVERDUE_UNSET_DAYS) # z.B. heute vor 3 Tagen

logging.info(f"Starting {__file__}, DUE_FIELD_NAME:  {DUE_FIELD_NAME} ")
logging.debug(f"PAPERLESS_URL: {PAPERLESS_URL}")
# ----------------------
# 1. Custom Field ID von CUSTOM_FIELD_NAME finden:
# ----------------------
cf_list = requests.get(f"{PAPERLESS_URL}/api/custom_fields/", headers=HEADERS).json()["results"]
field = next(f for f in cf_list if f["name"] == DUE_FIELD_NAME)
field_id = field["id"]

# cf = requests.get(f"{PAPERLESS_URL}/api/custom_fields/", headers=HEADERS).json()
# field_id = next(f["id"] for f in cf["results"] if f["name"] == {DUE_FIELD_NAME})

# ----------------------
# Tag ID finden / erstellen
# ----------------------
tags = requests.get(f"{PAPERLESS_URL}/api/tags/", headers=HEADERS).json()["results"]
tag = next((t for t in tags if t["name"] == TODO_TAG_NAME), None)
if not tag:
    tag = requests.post(f"{PAPERLESS_URL}/api/tags/", headers=HEADERS, json={"name": TODO_TAG_NAME}).json()
tag_id = tag["id"]

# ------------------------------
# 3. Alle Dokumente abrufen
# Ganz ohne page_size-Angabe werden nur ca. 100 Dokumente geliefert
# Eventuell:
'''
docs = requests.get( f"{PAPERLESS_URL}/api/documents/?page_size=1000000", headers=HEADERS ).json()["results"]
'''
# ------------------------------
docs = []
url = f"{PAPERLESS_URL}/api/documents/?page_size=100"
while url:
    resp = requests.get(url, headers=HEADERS).json()
    docs.extend(resp["results"])
    url = resp["next"]

# ----------------------
# Dokumente bearbeiten
# ----------------------
chgCount = 0
docCount = 0
docWithTagCount = 0
for doc in docs: # Enum für alle docs
  # Custom Field aus Liste extrahieren
  value = None
  docCount += 1
  for f in doc.get("custom_fields", []):
    if f.get("field") == field_id:
      value = f.get("value")
      break
  if not value:
    continue
  docWithTagCount += 1
  due_date = datetime.strptime(value, "%Y-%m-%d").date()
  logging.info(f"Doc mit Fälligkeit: {doc['title']} am {value}")
  tags_set = set(doc["tags"])

  # log_entries = []

  # ✅ Document hat Fälligkeitsdatum und ist (demnächst) fällig (oder überfällig)
  if due_date <= limit_set_date: # ohne überfällig: today <= due_date <= limit_set_date:
    if tag_id not in tags_set:
      tags_set.add(tag_id)
      requests.patch( f"{PAPERLESS_URL}/api/documents/{doc['id']}/", headers=HEADERS, json={"tags": list(tags_set)} )
      logging.info(f"✅ Tag {TODO_TAG_NAME} set: {doc['title']}")
      # messages.append(f"✅ Tag {TODO_TAG_NAME} set: {doc['title']} (due date {due_date})")
      messagesSet.append(f"{due_date} doc['title']")
      chgCount += 1

  # ❌ ToDo entfernen für überfällige Dokumente
  elif due_date < limit_unset_date:
    if tag_id in tags_set:
      tags_set.remove(tag_id)
      requests.patch( f"{PAPERLESS_URL}/api/documents/{doc['id']}/", headers=HEADERS, json={"tags": list(tags_set)} )
      logging.info(f"❌ Tag {TODO_TAG_NAME} unset: {doc['title']}")
      messagesUnset.append(f"{due_date} {doc['title']}")

runtime = time.time() - start
runtime_Unit="s"
if (runtime > 180) :
  runtime = int(runtime // 60) 
  runtime_Unit="min"
logging.info(f"{docCount} docs scanned in {runtime:.1f}{runtime_Unit}, {docWithTagCount} with Tag {DUE_FIELD_NAME} found, Tag {TODO_TAG_NAME} set for {chgCount} files")
    # Log schreiben
message=""
if messagesSet:
  message="Tag {TODO_TAG_NAME} set:"
  message += "\n".join(messagesSet)
if messagesUnset:
  message="Tag {TODO_TAG_NAME} removed:"
  message += "\n".join(messagesUnset)
if message != "":
  send_email(message)    # sendet die Nachricht als E-Mail
