import discord
from discord.ext import commands
import aiosqlite
import datetime
import os


class Rankings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.user_id == self.bot.user.id: return

        emoji = str(payload.emoji)
        async with aiosqlite.connect("meme_connect.db") as db:
            if emoji == "⬆️":
                await db.execute("UPDATE memes SET upvotes = upvotes + 1 WHERE message_id = ?", (payload.message_id,))
            elif emoji == "⬇️":
                await db.execute("UPDATE memes SET downvotes = downvotes + 1 WHERE message_id = ?",
                                 (payload.message_id,))
            elif emoji == "🚩":
                # Auto-Quarantine Logic: Check if flag count >= 3
                channel = self.bot.get_channel(payload.channel_id)
                msg = await channel.fetch_message(payload.message_id)
                flag_count = next((r.count for r in msg.reactions if str(r.emoji) == "🚩"), 0)

                if flag_count >= 3:
                    await msg.delete()
                    # Re-send to Quarantine (Simplified)
                    staff_chan = self.bot.get_channel(int(os.getenv("QUARANTINE_CHANNEL_ID")))
                    await staff_chan.send(f"🚨 **COMMUNITY FLAGGED:** Meme by <@{payload.user_id}> removed from public.")
            await db.commit()


async def setup(bot):
    await bot.add_cog(Rankings(bot))
