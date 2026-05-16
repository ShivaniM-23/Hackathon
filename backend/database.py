"""
ShadowTrace AI — database.py
PostgreSQL (via asyncpg) for reports + audit logs.
Neo4j (via neo4j-driver) for graph data.
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

# ── PostgreSQL Config (Explicit localhost for uvicorn host access) ───────────
PG_USER = os.getenv("POSTGRES_USER", "postgres")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD", "Marri@1234")
# Force localhost because we are running outside the docker network
PG_HOST = "localhost" 
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_DB = os.getenv("POSTGRES_DB", "shadowtrace")

PG_PASSWORD_ENCODED = PG_PASSWORD.replace("@", "%40")
PG_DSN = os.getenv(
    "DATABASE_URL", 
    f"postgresql://{PG_USER}:{PG_PASSWORD_ENCODED}@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

# ── Neo4j Config ─────────────────────────────────────────────────────────────
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "Marri@1234")

# ── Async Drivers ───────────────────────────────────────────────────────────
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

# ── In-memory fallback store ────────────────────────────────────────────────
_memory_store: dict[str, dict] = {}
_graph_store: dict[str, dict] = {}

_pg_pool = None
_neo4j_driver = None


async def init_db():
    """Initialize database connections with retry logic for Neo4j."""
    global _pg_pool, _neo4j_driver

    # 1. PostgreSQL Initialization
    if PG_AVAILABLE:
        try:
            _pg_pool = await asyncpg.create_pool(PG_DSN, min_size=1, max_size=5)
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
            logger.warning(f"⚠️ PostgreSQL connection failed (getaddrinfo?): {e}")

    # 2. Neo4j Initialization with Retry Logic
    if NEO4J_AVAILABLE:
        retries = 5
        delay = 5
        for i in range(retries):
            try:
                _neo4j_driver = AsyncGraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
                await _neo4j_driver.verify_connectivity()
                logger.info(f"✅ Neo4j connected to {NEO4J_URI}")
                break
            except Exception as e:
                if i < retries - 1:
                    logger.warning(f"⏳ Neo4j not ready yet, retrying in {delay}s... ({i+1}/{retries})")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Neo4j failed after {retries} attempts: {e}")


async def save_investigation(job_id: str, report: dict):
    _memory_store[job_id] = report
    if _pg_pool and report.get("status") == "complete":
        try:
            await _pg_pool.execute(
                "INSERT INTO investigations (job_id, report) VALUES ($1, $2) ON CONFLICT (job_id) DO UPDATE SET report = $2",
                job_id, json.dumps(report),
            )
        except Exception as e:
            logger.error(f"PostgreSQL write error: {e}")


async def get_investigation(job_id: str) -> Optional[dict]:
    if job_id in _memory_store:
        return _memory_store[job_id]
    if _pg_pool:
        try:
            row = await _pg_pool.fetchrow("SELECT report FROM investigations WHERE job_id = $1", job_id)
            if row:
                return json.loads(row["report"])
        except Exception as e:
            logger.error(f"PostgreSQL read error: {e}")
    return None


async def update_investigation_status(job_id: str, status: str):
    if job_id in _memory_store:
        _memory_store[job_id]["status"] = status


async def save_graph_data(job_id: str, graph: dict):
    _graph_store[job_id] = graph
    if _pg_pool:
        try:
            await _pg_pool.execute(
                "INSERT INTO graph_data (job_id, graph) VALUES ($1, $2) ON CONFLICT (job_id) DO UPDATE SET graph = $2",
                job_id, json.dumps(graph),
            )
        except Exception as e:
            logger.error(f"PostgreSQL graph write error: {e}")

    if _neo4j_driver:
        try:
            await _persist_graph_to_neo4j(job_id, graph)
        except Exception as e:
            logger.error(f"Neo4j write error: {e}")


async def get_graph_data(job_id: str) -> Optional[dict]:
    if job_id in _graph_store:
        return _graph_store[job_id]
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
                """
                MERGE (n:Entity {id: $id, job_id: $job_id})
                SET n.label = $label, n.type = $type, n.risk = $risk
                """,
                id=node["id"], job_id=job_id,
                label=node.get("label", ""), type=node.get("type", ""),
                risk=node.get("risk", "unknown"),
            )

        for edge in graph.get("edges", []):
            await session.run(
                """
                MATCH (a:Entity {id: $source, job_id: $job_id})
                MATCH (b:Entity {id: $target, job_id: $job_id})
                MERGE (a)-[r:RELATED {label: $label}]->(b)
                """,
                source=edge["source"], target=edge["target"],
                label=edge.get("label", "related"), job_id=job_id,
            )
