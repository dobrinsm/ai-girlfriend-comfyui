"""
RAG Memory management for conversation history
"""

import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import aiosqlite

logger = logging.getLogger(__name__)


class MemoryManager:
    """Manages conversation memory with SQLite backend"""

    def __init__(self, db_path: str = "./data/memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db: Optional[aiosqlite.Connection] = None

    async def initialize(self):
        """Initialize database tables"""
        self._db = await aiosqlite.connect(self.db_path)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                user_message TEXT NOT NULL,
                ai_response TEXT NOT NULL,
                metadata TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_id ON memories(user_id)
        """)
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)
        """)
        await self._db.commit()
        logger.info("Memory database initialized")

    async def add_memory(
        self,
        user_id: str,
        user_message: str,
        ai_response: str,
        metadata: Optional[Dict] = None
    ):
        """Add a conversation memory"""
        if not self._db:
            raise RuntimeError("Memory manager not initialized")

        await self._db.execute(
            """
            INSERT INTO memories (user_id, user_message, ai_response, metadata)
            VALUES (?, ?, ?, ?)
            """,
            (user_id, user_message, ai_response, json.dumps(metadata) if metadata else None)
        )
        await self._db.commit()

    async def get_memories(
        self,
        user_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[Dict]:
        """Get memories for a user"""
        if not self._db:
            raise RuntimeError("Memory manager not initialized")

        cursor = await self._db.execute(
            """
            SELECT user_message, ai_response, metadata, timestamp
            FROM memories
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (user_id, limit, offset)
        )

        rows = await cursor.fetchall()
        memories = []

        for row in rows:
            memories.append({
                "user_message": row[0],
                "ai_response": row[1],
                "metadata": json.loads(row[2]) if row[2] else {},
                "timestamp": row[3]
            })

        return memories

    async def search_memories(
        self,
        user_id: str,
        query: str,
        limit: int = 5
    ) -> List[Dict]:
        """Search memories by content (simple keyword search)"""
        if not self._db:
            raise RuntimeError("Memory manager not initialized")

        cursor = await self._db.execute(
            """
            SELECT user_message, ai_response, metadata, timestamp
            FROM memories
            WHERE user_id = ? AND (
                user_message LIKE ? OR ai_response LIKE ?
            )
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (user_id, f"%{query}%", f"%{query}%", limit)
        )

        rows = await cursor.fetchall()
        memories = []

        for row in rows:
            memories.append({
                "user_message": row[0],
                "ai_response": row[1],
                "metadata": json.loads(row[2]) if row[2] else {},
                "timestamp": row[3]
            })

        return memories

    async def clear_memories(self, user_id: str):
        """Clear all memories for a user"""
        if not self._db:
            raise RuntimeError("Memory manager not initialized")

        await self._db.execute(
            "DELETE FROM memories WHERE user_id = ?",
            (user_id,)
        )
        await self._db.commit()
        logger.info(f"Cleared memories for user: {user_id}")

    async def get_memory_stats(self, user_id: str) -> Dict:
        """Get memory statistics for a user"""
        if not self._db:
            raise RuntimeError("Memory manager not initialized")

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM memories WHERE user_id = ?",
            (user_id,)
        )
        count = (await cursor.fetchone())[0]

        cursor = await self._db.execute(
            "SELECT MIN(timestamp), MAX(timestamp) FROM memories WHERE user_id = ?",
            (user_id,)
        )
        row = await cursor.fetchone()

        return {
            "total_memories": count,
            "first_interaction": row[0],
            "last_interaction": row[1]
        }

    async def close(self):
        """Close database connection"""
        if self._db:
            await self._db.close()
            self._db = None
