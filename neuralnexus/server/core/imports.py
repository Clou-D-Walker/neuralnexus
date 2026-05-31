"""
core/imports.py
---------------
Centralised stdlib and third-party imports shared across the NeuralNexus server.
Import with:  from core.imports import *
"""

import os
import sys
import grpc
import json
import logging
from typing import List, Literal, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
from concurrent import futures
from io import BytesIO
import sqlite3
import hashlib
import uuid
import zipfile
import random

# ---------------------------------------------------------------------------
# Database path  (override with DB_PATH env var to run multiple nodes)
# ---------------------------------------------------------------------------
DB_PATH: str = os.environ.get("DB_PATH", "lms.db")

try:
    from llama_cpp import Llama
except ImportError:
    Llama = None  # type: ignore[assignment,misc]
except ImportError:
    Llama = None  # type: ignore[assignment,misc]

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
