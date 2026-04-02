import discord
from discord.ext import commands, tasks
import os
import aiosqlite
from dotenv import load_dotenv
from flask import Flask
from threading import Thread

import database

# 1. Load Environment Variables (.env)
load_dotenv()


def _get_id(key):
    val = os.getenv(key)
    try:
        return int(val) if val else None
    except ValueError:
        return None

# --- DUMMY WEB SERVER FOR RENDER FREE TIER ---
app = Flask('')

@app.route('/')
def home():
    return "MemeConnect is Online! WASA WASA!"

def run_flask():
    # Render looks for port 10000 by default, or uses the PORT environment variable
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()


class MemeConnect(commands.Bot):
    def __init__(self):
        # We only enable default intents here to avoid privileged intent errors.
        # If you need Server Members or Message Content later, enable them in the
        # Discord Developer Portal first, then add them back here.
        intents = discord.Intents.default()
        intents.message_content = True  # Usually needed for commands
        
        super().__init__(command_prefix="!", intents=intents)

        # Global Config for easy access in Cogs
        self.config = {
            'QUARANTINE_ID': _get_id('QUARANTINE_CHANNEL_ID'),
            'RUG_PULL_ID': _get_id('RUG_PULL_CHANNEL_ID'),
            'ADMIN_ID': _get_id('ALLOWED_ADMIN_ID'),
            'DB_PATH': "meme_connect.db"
        }

    async def setup_hook(self):
        """Runs once when the bot starts up."""
        # A. Initialize Database (Ensures tables exist)
        await database.init_db()

        # B. Load Cogs (Features)
        # We use 'setup' instead of 'admin' as per your architecture
        cogs = ["cogs.relay", "cogs.rankings", "cogs.justice", "cogs.setup"]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                print(f"✅ Loaded Cog: {cog}")
            except Exception as e:
                print(f"❌ Failed to load {cog}: {e}")

        # C. Populate Channels Table for Existing Guilds (Fix for Render's ephemeral storage)
        async with aiosqlite.connect(self.config['DB_PATH']) as db:
            for guild in self.guilds:
                dank_channel = discord.utils.get(guild.text_channels, name="dank-memes")
                wholesome_channel = discord.utils.get(guild.text_channels, name="wholesome-memes")
                
                if dank_channel:
                    await db.execute(
                        "INSERT OR IGNORE INTO channels (guild_id, channel_id, category) VALUES (?, ?, ?)",
                        (guild.id, dank_channel.id, "dank")
                    )
                if wholesome_channel:
                    await db.execute(
                        "INSERT OR IGNORE INTO channels (guild_id, channel_id, category) VALUES (?, ?, ?)",
                        (guild.id, wholesome_channel.id, "wholesome")
                    )
            await db.commit()
        print("✅ Populated channels table for existing guilds.")

        # D. Start Background Tasks
        self.check_judicial_trials.start()

    # --- THE JUDICIAL LOOP (THE 24H CLOCK) ---
    @tasks.loop(hours=1)
    async def check_judicial_trials(self):
        """Checks for trials older than 24h and applies the final verdict."""
        async with aiosqlite.connect(self.config['DB_PATH']) as db:
            # Select pending trials older than 1 day
            async with db.execute(
                    "SELECT action_id, target_id, type, approve_votes, revoke_votes FROM judicial_actions "
                    "WHERE timestamp < datetime('now', '-1 day') AND status = 'pending'"
            ) as cursor:
                expired_trials = await cursor.fetchall()

            for action_id, target_id, a_type, approves, revokes in expired_trials:
                # The '3-vote lead' Rule
                if revokes - approves >= 3:
                    if a_type == 'strike':
                        await db.execute("UPDATE users SET strikes = strikes - 1 WHERE user_id = ?", (target_id,))
                    elif a_type == 'ban':
                        await db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (target_id,))

                # Close the case regardless of the outcome
                await db.execute("UPDATE judicial_actions SET status = 'closed' WHERE action_id = ?", (action_id,))

            await db.commit()
            if expired_trials:
                print(f"⚖️ Processed {len(expired_trials)} expired judicial trials.")

    @check_judicial_trials.before_loop
    async def before_check(self):
        await self.wait_until_ready()


# 2. Instantiate and Run
bot = MemeConnect()

@bot.event
async def on_guild_join(guild):
    """Called when the bot joins a new server."""
    # Create the text channels if they don't exist
    dank_channel = discord.utils.get(guild.text_channels, name="dank-memes")
    wholesome_channel = discord.utils.get(guild.text_channels, name="wholesome-memes")
    
    try:
        if not dank_channel:
            dank_channel = await guild.create_text_channel('dank-memes')
        if not wholesome_channel:
            wholesome_channel = await guild.create_text_channel('wholesome-memes')
            
        # Register the new channels in the database
        async with aiosqlite.connect(bot.config['DB_PATH']) as db:
            await db.execute(
                "INSERT OR IGNORE INTO channels (guild_id, channel_id, category) VALUES (?, ?, ?)",
                (guild.id, dank_channel.id, "dank")
            )
            await db.execute(
                "INSERT OR IGNORE INTO channels (guild_id, channel_id, category) VALUES (?, ?, ?)",
                (guild.id, wholesome_channel.id, "wholesome")
            )
            await db.commit()
            
    except discord.Forbidden:
        print(f"❌ Missing permissions to create channels in {guild.name}")
    except Exception as e:
        print(f"❌ Error creating channels in {guild.name}: {e}")

@bot.event
async def on_ready():
    print("-" * 30)
    print(f"🚀 WASA WASA WASA! {bot.user.name} IS LIVE ON RENDER!")
    print(f"🛡️ Admin ID: {bot.config.get('ADMIN_ID')}")
    print("-" * 30)


# Start Carlos Matos
if __name__ == "__main__":
    token = os.getenv('DISCORD_TOKEN')
    if token:
        # Start the Flask web server in a separate thread so Render sees a port listening
        keep_alive()
        # Start the Discord bot
        bot.run(token)
    else:
        print("❌ ERROR: DISCORD_TOKEN is not set in the environment.")
