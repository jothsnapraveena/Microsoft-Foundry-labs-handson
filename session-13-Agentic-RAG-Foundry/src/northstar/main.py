"""ASGI entry point: python -m uvicorn northstar.main:app"""
from .api import create_app

app = create_app()
