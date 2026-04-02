import discord
from discord.ext import commands
import aiosqlite
import datetime
import os


class Rankings(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def memeconnect(self, ctx):
        embed = discord.Embed(title="🚀 MemeConnect Commands", color=discord.Color.blue())
        embed.add_field(name="`!memeconnect bestof [all/month]`", value="Shows the top 10 most liked memes.", inline=False)
        embed.add_field(name="`!memeconnect worstof [all/month]`", value="Shows the top 10 most disliked memes.", inline=False)
        embed.add_field(name="`!memeconnect top_users`", value="Shows the 10 users with the highest net score.", inline=False)
        embed.add_field(name="`!memeconnect worst_users`", value="Shows the 10 users with the lowest net score.", inline=False)
        
        embed.add_field(name="`!strike @user [reason]`", value="Issue a strike to a user (Staff only).", inline=False)
        embed.add_field(name="`!appeal [reason]`", value="Send an appeal to the board.", inline=False)

        embed.add_field(name="`!memeconnect_setup promote/demote moderator/admin @user`", value="Manage staff roles (Admin/Founder only).", inline=False)
        
        embed.set_footer(text="WASA WASA WASA!")
        await ctx.send(embed=embed)

    @memeconnect.command()
    async def bestof(self, ctx, period: str = "all"):
        query = "SELECT attachment_url, author_id, (upvotes - downvotes) as score FROM memes "
        if period == "month":
            query += "WHERE timestamp > datetime('now', '-30 days') "
        query += "ORDER BY score DESC LIMIT 10"

        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute(query) as cursor:
                top_memes = await cursor.fetchall()

        if not top_memes:
            return await ctx.send("No memes found in the history books yet!")

        embed = discord.Embed(title=f"🏆 Top 10 Memes ({period.capitalize()})", color=discord.Color.gold())
        for i, (url, author, score) in enumerate(top_memes, 1):
            embed.add_field(name=f"#{i} - Score: {score}", value=f"By <@{author}>", inline=False)
        await ctx.send(embed=embed)
        
    @memeconnect.command()
    async def worstof(self, ctx, period: str = "all"):
        query = "SELECT attachment_url, author_id, (upvotes - downvotes) as score FROM memes "
        if period == "month":
            query += "WHERE timestamp > datetime('now', '-30 days') "
        query += "ORDER BY score ASC LIMIT 10"

        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute(query) as cursor:
                worst_memes = await cursor.fetchall()

        if not worst_memes:
            return await ctx.send("No memes found in the history books yet!")

        embed = discord.Embed(title=f"🗑️ Worst 10 Memes ({period.capitalize()})", color=discord.Color.red())
        for i, (url, author, score) in enumerate(worst_memes, 1):
            embed.add_field(name=f"#{i} - Score: {score}", value=f"By <@{author}>", inline=False)
        await ctx.send(embed=embed)

    @memeconnect.command()
    async def top_users(self, ctx):
        query = """
            SELECT author_id, SUM(upvotes - downvotes) as total_score 
            FROM memes 
            GROUP BY author_id 
            ORDER BY total_score DESC 
            LIMIT 10
        """
        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute(query) as cursor:
                top_users = await cursor.fetchall()

        if not top_users:
            return await ctx.send("No users have posted memes yet!")

        embed = discord.Embed(title="🌟 Top 10 Most Liked Users", color=discord.Color.gold())
        for i, (author, score) in enumerate(top_users, 1):
            embed.add_field(name=f"#{i}", value=f"<@{author}> - Score: {score}", inline=False)
        await ctx.send(embed=embed)

    @memeconnect.command()
    async def worst_users(self, ctx):
        query = """
            SELECT author_id, SUM(upvotes - downvotes) as total_score 
            FROM memes 
            GROUP BY author_id 
            ORDER BY total_score ASC 
            LIMIT 10
        """
        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute(query) as cursor:
                worst_users = await cursor.fetchall()

        if not worst_users:
            return await ctx.send("No users have posted memes yet!")

        embed = discord.Embed(title="👎 Top 10 Most Disliked Users", color=discord.Color.red())
        for i, (author, score) in enumerate(worst_users, 1):
            embed.add_field(name=f"#{i}", value=f"<@{author}> - Score: {score}", inline=False)
        await ctx.send(embed=embed)

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
