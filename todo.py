import os
import sys
import requests # pyright: ignore[reportMissingModuleSource]
from datetime import datetime, timedelta, date
import time
import smtplib
from email.mime.text import MIMEText
import logging
# For dokuments with a given CUSTOM_FIELD_NAME (Type: Date) the TODO_TAG will be set some days ahead of the given date.

# ----------------------
# Setup Logging:
# ----------------------
class FlushStreamHandler(logging.StreamHandler):
  def emit(self, record):
    super().emit(record)
    self.flush()  # erzwingt sofortigen Flush

class ScriptFilter(logging.Filter):
  def filter(self, record):
    if not hasattr(record, "script"):
      record.script = "external"
    return True

handler = FlushStreamHandler(sys.stdout)
handler.addFilter(ScriptFilter())

scriptName = os.path.basename(__file__)
level = os.getenv("LOGLEVEL", "INFO")

logging.basicConfig(
  level=level
  , format="%(asctime)s - %(module)s:%(lineno)d [%(levelname)s] %(message)s"
#  , format="%(asctime)s - %(script)s:%(lineno)d [%(levelname)s] %(message)s"
  , datefmt="%Y-%m-%d %H:%M:%S"
  , handlers=[handler]
  )

logger = logging.LoggerAdapter(
  logging.getLogger(),
  {"script": scriptName}
  )

# ----------------------
# Configuration from Environment
# ----------------------
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
  logger.error(f"File {env_path} not found")
  exit(2)   

PAPERLESS_URL = os.environ.get("PAPERLESS_URL")
API_TOKEN = os.environ.get("API_TOKEN")
DAYS_AHEAD = int(os.environ.get("DAYS_AHEAD") or "3")
TODO_TAG_NAME = os.environ.get("TODO_TAG", "")
DONE_TAG_NAME =  os.environ.get("DONE_TAG", "")
DUE_FIELD_NAME = os.environ.get("DUE_FIELD", "")
HEADERS = {"Authorization": f"Token {API_TOKEN}"}
OVERDUE_UNSET_DAYS = int(os.environ.get("OVERDUE_UNSET_DAYS") or "99999")
# ensure no OverflowError: date value out of range at limit_unset_date = today - timedelta(days=OVERDUE_UNSET_DAYS):
OVERDUE_UNSET_DAYS = min (OVERDUE_UNSET_DAYS, (datetime.today().date() - date.min).days) # date.min is 0001-01-01

# ----------------------------
# Function: Send eMail
# ----------------------------
def send_email(message, subject=""):
  smtp_server = os.environ.get("EMAIL_SMTP_SERVER").strip()
  smtp_port = int(os.environ.get("EMAIL_SMTP_PORT") or "587")
  timeout = int(os.environ.get("EMAIL_TIMEOUT_S") or "40")
  user = os.environ.get("EMAIL_USER").strip()
  password = os.environ.get("EMAIL_PASSWORD").strip().strip('"')
  #### logger.debug(f"MAIL_PASSWORD={password}")  # ❌ HARD NO
  if subject=="":
    subject = os.environ.get("EMAIL_SUBJECT", "Paperless ToDo Update")
  to_addr = os.environ.get("EMAIL_TO")
  use_starttls = os.environ.get("EMAIL_USE_STARTTLS", "true").lower().strip() == "true"

  if not smtp_server or not user or not password or not to_addr:
    # no E-Mail configured
    logger.debug(f"eMail sending skipped as eMail is not or not fully configured!")
    return
  try:
    msg = MIMEText(message) # convert e.g. \n to \r\n
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    # logger.debug(f"Readback of logger.level 'DEBUG' = {logger.isEnabledFor(logging.DEBUG)}")
    logger.debug(f"Sending eMail to {to_addr} via {smtp_server}:{smtp_port}, use_starttls={use_starttls}, account={user}, timeout={timeout}s ...")
    if (not use_starttls) and (smtp_port==465):
      logger.debug(f"using smtplib.SMTP_SSL, (not smtplib.SMTP)")
      server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=timeout)
      if logger.isEnabledFor(logging.DEBUG):
        server.set_debuglevel(1) # 1: debug active, 2: with additionally timestamps
      logger.debug(f"eMail using SMTP_SSL with port {smtp_port} and {timeout}s timeout")
    else: 
      logger.debug(f"using smtplib.SMTP, (not smtplib.SMTP_SSL)") 
      server = smtplib.SMTP(smtp_server, smtp_port, timeout=timeout)
      if logger.isEnabledFor(logging.DEBUG):
        server.set_debuglevel(1)
      logger.debug(f"eMail using SMTP with port={smtp_port}, use_starttls={'true' if use_starttls else 'false'} and {timeout}s timeout")
      server.ehlo()
      if use_starttls:
        server.starttls()          
      server.ehlo()
    server.login(user, password)
    server.send_message(msg)    
  except Exception as e:
    logger.error(f"🐞 E-Mail-Error: {e}")


# ----------------------------
########## Main ##########
# ----------------------------
messagesSet = []
messagesUnset = []

today = datetime.today().date()
start = time.time()
limit_set_date = today + timedelta(days=DAYS_AHEAD) # e.g. 3 days ahead from today
limit_unset_date = today - timedelta(days=OVERDUE_UNSET_DAYS) # e.g 3 days in the past
logger.debug(f"DAYS_AHEAD={DAYS_AHEAD}, limit_set_date={limit_set_date}, OVERDUE_UNSET_DAYS={OVERDUE_UNSET_DAYS}, limit_unset_date={limit_unset_date}")

if DUE_FIELD_NAME == "":
  logger.error(f"DUE_FIELD is not set in the .env file!")
  exit(1)   

if TODO_TAG_NAME == "":
  logger.error(f"TODO_TAG is not set in the .env file!")
  exit(1)   

logger.info(f"Starting {__file__}, DUE_FIELD_NAME: {DUE_FIELD_NAME}, TODO_TAG_NAME: {TODO_TAG_NAME}")
logger.debug(f"PAPERLESS_URL: {PAPERLESS_URL}")

# ----------------------
# 1. Get the ID of the custom field CUSTOM_FIELD_NAME:
# ----------------------
try:
  cf_list = requests.get(f"{PAPERLESS_URL}/api/custom_fields/", headers=HEADERS).json()["results"]
  field = next(f for f in cf_list if f["name"] == DUE_FIELD_NAME)
  if not field:
    logger.error(f"DUE_FIELD '{DUE_FIELD_NAME}' is not configured in your paperless instance!")
    exit(1)
except Exception as e:
  logger.error(f"{repr(e)}")
  exit(2)
field_id = field["id"]

# ----------------------
# Search / create Tag ID
# ----------------------
tags = requests.get(f"{PAPERLESS_URL}/api/tags/", headers=HEADERS).json()["results"]
tag = next((t for t in tags if t["name"] == TODO_TAG_NAME), None)
if not tag: # create tag
  logger.debug(f"The tag '{TODO_TAG_NAME}' needs to be created ...")
  tag = requests.post(f"{PAPERLESS_URL}/api/tags/", headers=HEADERS, json={"name": TODO_TAG_NAME}).json()
  logger.info(f"The tag {TODO_TAG_NAME} was not found in paperless and was now created.")
todo_tag_id = tag["id"]

if (DONE_TAG_NAME != ""):
  logger.debug(f"DONE_TAG '{DONE_TAG_NAME}' is defined in environment setup!")
  tag = next((t for t in tags if t["name"] == DONE_TAG_NAME), None)
  if not tag:
    logger.debug(f"The tag '{DONE_TAG_NAME}' needs to be created ...")
    tag = requests.post(f"{PAPERLESS_URL}/api/tags/", headers=HEADERS, json={"name": DONE_TAG_NAME}).json()
    logger.info(f"The tag {DONE_TAG_NAME} was not found in paperless and was now created.")
  else:
    logger.info(f"DONE_TAG_NAME: {DONE_TAG_NAME}")  
  done_tag_id = tag["id"]
else:
  logger.debug("No DONE_TAG_NAME configured")
  
# ------------------------------
# 3. Scan all documents
# without a given page_size only 100 documents will be returned
# possibly use:
'''
docs = requests.get( f"{PAPERLESS_URL}/api/documents/?page_size=1000000", headers=HEADERS ).json()["results"]
'''
# or alternative solution:
# ------------------------------
docs = []
url = f"{PAPERLESS_URL}/api/documents/?page_size=1000"
while url:
  resp = requests.get(url, headers=HEADERS).json()
  docs.extend(resp["results"])
  url = resp["next"]

# ----------------------
# Check that documents:
# ----------------------
logger.debug(f"Starting to check {len(docs)} documents ...")
chgCount = 0
docCount = 0
docWithFieldCount = 0
for doc in docs: # Enum for alle docs
  # extract custom field from list:
  value = None
  docCount += 1
  for f in doc.get("custom_fields", []):
    if f.get("field") == field_id:
      value = f.get("value")
      break
  if value is None:
    continue
  docWithFieldCount += 1

  due_date = datetime.strptime(value, "%Y-%m-%d").date()
  logger.debug(f"Doc with field {DUE_FIELD_NAME} at {value}: {doc['title']}")
  tags_set = set(doc["tags"])

    # ✅ Document has due date and is due in the next days (or, if done_tag is used, possibly already overdue)
  if ((due_date == limit_set_date) or ((due_date <= limit_set_date) and ("done_tag_id" in locals()))): 
    if todo_tag_id not in tags_set:
      tags_set.add(todo_tag_id)
      requests.patch( f"{PAPERLESS_URL}/api/documents/{doc['id']}/", headers=HEADERS, json={"tags": list(tags_set)} )
      logger.info(f"✅ Tag '{TODO_TAG_NAME}' assigned: {doc['title']} (due date {due_date})")
      messagesSet.append(f"{due_date} {doc['title']}")
      chgCount += 1
    else:
      logger.debug(f"Tag {TODO_TAG_NAME} was already assigned to {doc['title']} with due date {due_date}")
  
  # ✖ remove ToDo if overdue
  elif due_date < limit_unset_date:
    if todo_tag_id in tags_set:
      tags_set.remove(todo_tag_id)
      requests.patch( f"{PAPERLESS_URL}/api/documents/{doc['id']}/", headers=HEADERS, json={"tags": list(tags_set)} )
      logger.info(f"✖ Tag '{TODO_TAG_NAME}' removed: {doc['title']}")
      messagesUnset.append(f"{due_date} {doc['title']}")
    else:
      logger.debug(f"Tag {TODO_TAG_NAME} has not been assigned to {doc['title']}")
  else:
    logger.debug(f"Unchanged document with {DUE_FIELD_NAME}={due_date}: {doc['title']}")

runtime = time.time() - start
runtime_Unit="s"
if (runtime > 180):
  runtime = int(runtime // 60) 
  runtime_Unit="min"
logger.info(f"{docCount} docs scanned in {runtime:.1f}{runtime_Unit}, {docWithFieldCount} with Tag {DUE_FIELD_NAME} found, Tag {TODO_TAG_NAME} set for {chgCount} files")
# if eMail configured and any change: Send an eMail:
message=""
if messagesSet:
  message=f"✅ Tag {TODO_TAG_NAME} set:\r\n"
  message += "\r\n".join(messagesSet)
if messagesUnset:
  message="\r\n✖ Tag {TODO_TAG_NAME} removed:\r\n"
  message += "\r\n".join(messagesUnset)
if message != "":
  send_email(message)    # send eMail
exit (0)