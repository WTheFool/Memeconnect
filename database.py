import aiosqlite

DB_PATH = "meme_connect.db"


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # User Hierarchy & Stats
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                is_admin BOOLEAN DEFAULT 0,
                is_staff BOOLEAN DEFAULT 0,
                strikes INTEGER DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0,
                total_points INTEGER DEFAULT 0
            )
        """)

        # Relay Mapping (Connecting servers to categories)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                guild_id INTEGER,
                channel_id INTEGER,
                category TEXT,
                PRIMARY KEY (guild_id, category)
            )
        """)

        # Archive of Broadcasted Memes (For !bestof rankings)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS memes (
                message_id INTEGER PRIMARY KEY,
                author_id INTEGER,
                attachment_url TEXT,
                category TEXT,
                upvotes INTEGER DEFAULT 0,
                downvotes INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Blacklist of Image Hashes
        await db.execute("""
            CREATE TABLE IF NOT EXISTS banned_hashes (
                image_hash TEXT PRIMARY KEY,
                added_by INTEGER
            )
        """)

        # Judicial System (The Courtroom / Rug Pull)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS judicial_actions (
                action_id INTEGER PRIMARY KEY AUTOINCREMENT,
                target_id INTEGER,
                reason TEXT,
                issuer_id INTEGER,
                type TEXT, -- 'strike' or 'ban'
                status TEXT DEFAULT 'pending',
                approve_votes INTEGER DEFAULT 0,
                revoke_votes INTEGER DEFAULT 0,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Training Data (Logged from Mod decisions)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS training_samples (
                url TEXT,
                label TEXT, -- 'safe' or 'unsafe'
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        await db.commit()
    print("📂 FULL MemeConnect Database Initialized.")
