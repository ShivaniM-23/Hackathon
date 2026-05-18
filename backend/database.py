"""
ShadowTrace AI — database.py
Persistent storage engine with PostgreSQL/Neo4j support 
and JSON-file fallbacks for local development resilience.
"""

import json
import os
import logging
import asyncio
import time
from typing import Optional
from dotenv import load_dotenv

# Load .env
load_dotenv()

logger = logging.getLogger(__name__)

# ── Storage Files (Persistent fallback for uvicorn reloads) ───────────────────
JOB_STORE_FILE = "job_store.json"
GRAPH_STORE_FILE = "graph_store.json"

# ── PostgreSQL Config ─────────────────────────────────────────────────────────
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "Marri@1234")
PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DB = os.getenv("POSTGRES_DB", "shadowtrace")

# ── Neo4j Config ─────────────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "Marri@1234")

# ── Drivers ──────────────────────────────────────────────────────────────────
try:
    import asyncpg
    PG_AVAILABLE = True
except ImportError:
    PG_AVAILABLE = False

try:
    from neo4j import AsyncGraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False

_pg_pool = None
_neo4j_driver = None

# ── File-Based Storage Helpers ───────────────────────────────────────────────

def _load_store_file(filename: str) -> dict:
    """Loads a JSON store from disk."""
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_store_file(filename: str, data: dict):
    """Saves a JSON store to disk."""
    try:
        with open(filename, "w") as f:
            json.dump(data, f)
    except Exception as e:
        logger.error(f"File store save failed for {filename}: {e}")

# ── Lifecycle ────────────────────────────────────────────────────────────────

async def init_db():
    """Initialize database connections."""
    global _pg_pool, _neo4j_driver

    # 1. PostgreSQL Initialization
    if PG_AVAILABLE:
        try:
            _pg_pool = await asyncpg.create_pool(
                user=PG_USER,
                password=PG_PASSWORD,
                database=PG_DB,
                host=PG_HOST,
                port=PG_PORT,
                min_size=1,
                max_size=5
            )
            async with _pg_pool.acquire() as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS investigations (
                        job_id TEXT PRIMARY KEY,
                        report JSONB NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS graph_data (
                        job_id TEXT PRIMARY KEY,
                        graph JSONB NOT NULL,
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    )
                """)
            logger.info(f"✅ PostgreSQL connected to {PG_DB} at {PG_HOST}")
        except Exception as e:
            logger.warning(f"⚠️ PostgreSQL connection failed (falling back to JSON store): {e}")

    # 2. Neo4j Initialization
    if NEO4J_AVAILABLE:
        try:
            _neo4j_driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            await _neo4j_driver.verify_connectivity()
            logger.info(f"✅ Neo4j connected to {NEO4J_URI}")
        except Exception as e:
            logger.warning(f"⚠️ Neo4j connection failed: {e}")

# ── Operations ───────────────────────────────────────────────────────────────

async def save_investigation(job_id: str, report: dict):
    """Saves report to persistent file fallback and PostgreSQL."""
    # 1. File Store
    store = _load_store_file(JOB_STORE_FILE)
    
    # User-scoped write-time deduplication for completed reports
    if report.get("status") == "complete":
        from cache import normalize_url
        user_email = report.get("user_email")
        url = report.get("url", "")
        if url:
            norm_url = normalize_url(url)
            for old_id, old_rep in list(store.items()):
                if old_id != job_id and old_rep.get("status") == "complete" and old_rep.get("user_email") == user_email:
                    old_url = old_rep.get("url", "")
                    if old_url and normalize_url(old_url) == norm_url:
                        logger.info(f"🗑️  Deduplicated old report {old_id} for URL {norm_url} and user {user_email}")
                        store.pop(old_id, None)
                        if _pg_pool:
                            try:
                                await _pg_pool.execute("DELETE FROM investigations WHERE job_id = $1", old_id)
                            except Exception as e:
                                logger.error(f"PostgreSQL delete deduplication error: {e}")

    store[job_id] = report
    _save_store_file(JOB_STORE_FILE, store)

    # 2. PostgreSQL
    if _pg_pool and report.get("status") in ["complete", "error"]:
        try:
            await _pg_pool.execute(
                "INSERT INTO investigations (job_id, report) VALUES ($1, $2) ON CONFLICT (job_id) DO UPDATE SET report = $2",
                job_id, json.dumps(report),
            )
        except Exception as e:
            logger.error(f"PostgreSQL write error: {e}")

async def get_investigation(job_id: str) -> Optional[dict]:
    """Retrieves report from file store first, then PostgreSQL."""
    # 1. File Store
    store = _load_store_file(JOB_STORE_FILE)
    if job_id in store:
        return store[job_id]

    # 2. PostgreSQL
    if _pg_pool:
        try:
            row = await _pg_pool.fetchrow("SELECT report FROM investigations WHERE job_id = $1", job_id)
            if row:
                return json.loads(row["report"])
        except Exception as e:
            logger.error(f"PostgreSQL read error: {e}")
    return None


async def get_all_investigations() -> dict:
    """Returns all investigations from file store and PostgreSQL."""
    all_reports = {}

    # 1. File Store
    all_reports.update(_load_store_file(JOB_STORE_FILE))

    # 2. PostgreSQL (merge in any that aren't in file store)
    if _pg_pool:
        try:
            rows = await _pg_pool.fetch("SELECT job_id, report FROM investigations")
            for row in rows:
                if row["job_id"] not in all_reports:
                    all_reports[row["job_id"]] = json.loads(row["report"])
        except Exception as e:
            logger.error(f"PostgreSQL read all error: {e}")

    return all_reports

async def update_investigation_status(job_id: str, status: str):
    """Quick status update helper."""
    report = await get_investigation(job_id)
    if report:
        report["status"] = status
        await save_investigation(job_id, report)

async def save_graph_data(job_id: str, graph: dict):
    """Saves graph to persistent file fallback and database."""
    # 1. File Store
    store = _load_store_file(GRAPH_STORE_FILE)
    store[job_id] = graph
    _save_store_file(GRAPH_STORE_FILE, store)

    # 2. PostgreSQL
    if _pg_pool:
        try:
            await _pg_pool.execute(
                "INSERT INTO graph_data (job_id, graph) VALUES ($1, $2) ON CONFLICT (job_id) DO UPDATE SET graph = $2",
                job_id, json.dumps(graph),
            )
        except Exception as e:
            logger.error(f"PostgreSQL graph write error: {e}")

    # 3. Neo4j
    if _neo4j_driver:
        try:
            await _persist_graph_to_neo4j(job_id, graph)
        except Exception as e:
            logger.error(f"Neo4j write error: {e}")

async def get_graph_data(job_id: str) -> Optional[dict]:
    """Retrieves graph from file store or PostgreSQL."""
    store = _load_store_file(GRAPH_STORE_FILE)
    if job_id in store:
        return store[job_id]

    if _pg_pool:
        try:
            row = await _pg_pool.fetchrow("SELECT graph FROM graph_data WHERE job_id = $1", job_id)
            if row:
                return json.loads(row["graph"])
        except Exception as e:
            logger.error(f"PostgreSQL graph read error: {e}")
    return None

async def _persist_graph_to_neo4j(job_id: str, graph: dict):
    """Writes nodes and edges to Neo4j."""
    async with _neo4j_driver.session() as session:
        for node in graph.get("nodes", []):
            await session.run(
                "MERGE (n:Entity {id: $id, job_id: $job_id}) SET n.label = $label, n.type = $type, n.risk = $risk",
                id=node["id"], job_id=job_id, label=node.get("label", ""), type=node.get("type", ""), risk=node.get("risk", "unknown")
            )
        for edge in graph.get("edges", []):
            await session.run(
                "MATCH (a:Entity {id: $source, job_id: $job_id}) MATCH (b:Entity {id: $target, job_id: $job_id}) MERGE (a)-[r:RELATED {label: $label}]->(b)",
                source=edge["source"], target=edge["target"], label=edge.get("label", "related"), job_id=job_id
            )
