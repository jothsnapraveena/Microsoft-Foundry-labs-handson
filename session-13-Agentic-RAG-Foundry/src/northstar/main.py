"""ASGI entry point: python -m uvicorn northstar.main:app --app-dir src"""
from .api import create_app

app = create_app()
