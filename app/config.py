import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-ikke-bruk-i-produksjon")
    STORAGE_BACKEND = os.environ.get("STORAGE_BACKEND", "sqlite")
    DATABASE_PATH = os.environ.get(
        "DATABASE_PATH", os.path.join(BASE_DIR, "instance", "ektemat.sqlite3")
    )
    PENDING_IMAGE_DIR = os.path.join(BASE_DIR, "instance", "pending_images")
    # Maks antall gjester kjøkkenet kan levere til på én dag (kapasitetssjekk)
    DAILY_GUEST_CAPACITY = int(os.environ.get("DAILY_GUEST_CAPACITY", "400"))
    ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    IMAGE_MODEL = os.environ.get("IMAGE_MODEL", "claude-opus-5-5")
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    TESTING = False
