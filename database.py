"""
Модуль для работы с SQLite базой данных
Хранит контекст диалога (последние 30 сообщений)
"""
import aiosqlite
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

DB_PATH = "bot_database.db"


async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_stats (
                chat_id INTEGER PRIMARY KEY,
                message_count INTEGER DEFAULT 0,
                last_message_date DATE,
                last_reminder_date DATETIME,
                last_boundary_reminder_date DATE
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_chat_timestamp 
            ON messages(chat_id, timestamp DESC)
        """)
        await db.commit()
        logger.info("База данных инициализирована")


async def save_message(chat_id: int, role: str, content: str):
    """
    Сохраняет сообщение в базу данных
    
    Args:
        chat_id: ID чата
        role: Роль отправителя ('user' или 'assistant')
        content: Текст сообщения
    """
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
            (chat_id, role, content)
        )
        await db.commit()
        
        # Удаляем старые сообщения, оставляя только последние 30
        await db.execute("""
            DELETE FROM messages 
            WHERE chat_id = ? AND id NOT IN (
                SELECT id FROM messages 
                WHERE chat_id = ? 
                ORDER BY timestamp DESC 
                LIMIT 30
            )
        """, (chat_id, chat_id))
        await db.commit()


async def get_context(chat_id: int, limit: int = 30) -> List[Dict[str, str]]:
    """
    Получает контекст диалога (последние N сообщений)
    
    Args:
        chat_id: ID чата
        limit: Максимальное количество сообщений
        
    Returns:
        Список сообщений в формате [{"role": "user", "content": "..."}, ...]
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT role, content 
            FROM messages 
            WHERE chat_id = ? 
            ORDER BY timestamp ASC 
            LIMIT ?
        """, (chat_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [{"role": row["role"], "content": row["content"]} for row in rows]


async def clear_context(chat_id: int):
    """Очищает контекст диалога для указанного чата"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
        await db.commit()
        logger.info(f"Контекст очищен для chat_id: {chat_id}")


async def update_user_stats(chat_id: int, message_date: datetime):
    """Обновляет статистику пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        # Проверяем, существует ли запись
        async with db.execute(
            "SELECT message_count, last_message_date FROM user_stats WHERE chat_id = ?",
            (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            
            if row:
                # Обновляем существующую запись
                old_count = row[0] if row[0] else 0
                old_date = row[1] if row[1] else None
                
                # Если это новый день, сбрасываем счетчик
                if old_date and old_date != message_date.date().isoformat():
                    await db.execute("""
                        UPDATE user_stats 
                        SET message_count = 1, last_message_date = ?
                        WHERE chat_id = ?
                    """, (message_date.date().isoformat(), chat_id))
                else:
                    await db.execute("""
                        UPDATE user_stats 
                        SET message_count = message_count + 1, last_message_date = ?
                        WHERE chat_id = ?
                    """, (message_date.date().isoformat(), chat_id))
            else:
                # Создаем новую запись
                await db.execute("""
                    INSERT INTO user_stats (chat_id, message_count, last_message_date)
                    VALUES (?, 1, ?)
                """, (chat_id, message_date.date().isoformat()))
            
            await db.commit()


async def get_user_stats(chat_id: int) -> Dict:
    """Получает статистику пользователя"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM user_stats WHERE chat_id = ?",
            (chat_id,)
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                return {
                    "message_count": row["message_count"] or 0,
                    "last_message_date": row["last_message_date"],
                    "last_reminder_date": row["last_reminder_date"],
                    "last_boundary_reminder_date": row["last_boundary_reminder_date"]
                }
            return {
                "message_count": 0,
                "last_message_date": None,
                "last_reminder_date": None,
                "last_boundary_reminder_date": None
            }


async def update_last_reminder(chat_id: int, reminder_date: datetime):
    """Обновляет дату последнего напоминания"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO user_stats (chat_id, last_reminder_date)
            VALUES (?, ?)
        """, (chat_id, reminder_date.isoformat()))
        await db.commit()


async def update_boundary_reminder(chat_id: int, reminder_date: datetime):
    """Обновляет дату последнего напоминания о границах"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO user_stats (chat_id, last_boundary_reminder_date)
            VALUES (?, ?)
        """, (chat_id, reminder_date.date().isoformat()))
        await db.commit()


async def check_recent_trigger_words(chat_id: int, hours: int = 24) -> bool:
    """Проверяет, были ли триггерные слова за последние N часов"""
    from datetime import timedelta
    
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cutoff_time = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        trigger_words_list = ['одиноко', 'грустно', 'боюсь', 'не любит']
        
        async with db.execute("""
            SELECT content FROM messages 
            WHERE chat_id = ? AND role = 'user' AND timestamp > ?
        """, (chat_id, cutoff_time)) as cursor:
            rows = await cursor.fetchall()
            for row in rows:
                content_lower = row["content"].lower()
                if any(word in content_lower for word in trigger_words_list):
                    return True
            return False
