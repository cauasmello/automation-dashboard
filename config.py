import os

def _get_required(name):
    val = os.getenv(name)
    if not val:
        raise RuntimeError("Missing required env var: " + name)
    return val

API_ID = int(_get_required("API_ID"))
API_HASH = _get_required("API_HASH")
CHANNEL = int(_get_required("CHANNEL"))

SHEET_ID = _get_required("SHEET_ID")
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME", "Página1")

GOOGLE_SERVICE_ACCOUNT_JSON = _get_required("GOOGLE_SERVICE_ACCOUNT_JSON")

TELETHON_SESSION = os.getenv("TELETHON_SESSION", "")