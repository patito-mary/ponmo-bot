import aiosqlite

DB_PATH = "ponmo_bot.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                guild_id    INTEGER PRIMARY KEY,
                user_id     INTEGER,
                channel_id  INTEGER,
                duration    INTEGER DEFAULT 25,
                break_time  INTEGER DEFAULT 5,
                playlist_id TEXT    DEFAULT 'lofi_girl',
                unmutes_left INTEGER DEFAULT 3,
                phase       TEXT    DEFAULT 'work',
                is_active   INTEGER DEFAULT 1
            )
        """)
        await db.commit()    
        
async def create_session(guild_id, user_id, channel_id, duration, break_time, playlist_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO sessions
            (guild_id, user_id, channel_id, duration, break_time, playlist_id, unmutes_left, phase, is_active)
            VALUES (?, ?, ?, ?, ?, ?, 3, 'work', 1)
        """, (guild_id, user_id, channel_id, duration, break_time, playlist_id))
        await db.commit()
        
async def get_session(guild_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM sessions WHERE guild_id = ? AND is_active = 1", (guild_id,)
        ) as cursor:
            return await cursor.fetchone()
        
async def use_unmute(guild_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT unmutes_left FROM sessions WHERE guild_id = ? AND is_active = 1", (guild_id,)
        ) as cursor:
            row = await cursor.fetchone()
        if not row or row[0] <= 0:
            return 0  # sin créditos
        new_count = row[0] - 1
        await db.execute(
            "UPDATE sessions SET unmutes_left = ? WHERE guild_id = ?", (new_count, guild_id)
        )
        await db.commit()
        return new_count  # retorna cuántos quedan
    
async def set_phase(guild_id, phase):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET phase = ? WHERE guild_id = ?", (phase, guild_id)
        )
        await db.commit()

async def end_session(guild_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE sessions SET is_active = 0 WHERE guild_id = ?", (guild_id,)
        )
        await db.commit()                                