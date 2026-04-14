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
        embed.add_field(name="`!memeconnect stats`", value="Shows server leaderboard statistics.", inline=False)
        
        embed.add_field(name="`!strike @user [reason]`", value="Issue a strike to a user (Staff only).", inline=False)
        embed.add_field(name="`!appeal [reason]`", value="Send an appeal to the board.", inline=False)

        embed.add_field(name="`!memeconnect_setup promote/demote moderator/admin @user`", value="Manage staff roles (Admin/Founder only).", inline=False)
        
        embed.set_footer(text="WASA WASA WASA!")
        await ctx.send(embed=embed)

    @memeconnect.command()
    async def stats(self, ctx):
        async with aiosqlite.connect("meme_connect.db") as db:
            # Server with the most posts originated
            async with db.execute("""
                SELECT guild_id, COUNT(DISTINCT attachment_url) as posts 
                FROM memes 
                WHERE guild_id IS NOT NULL 
                GROUP BY guild_id 
                ORDER BY posts DESC 
                LIMIT 5
            """) as cursor:
                top_post_servers = await cursor.fetchall()
                
            # Server with the most likes on their originated posts
            async with db.execute("""
                SELECT guild_id, SUM(upvotes - downvotes) as score 
                FROM (
                    SELECT guild_id, attachment_url, MAX(upvotes) as upvotes, MAX(downvotes) as downvotes
                    FROM memes
                    WHERE guild_id IS NOT NULL
                    GROUP BY attachment_url, guild_id
                )
                GROUP BY guild_id 
                ORDER BY score DESC 
                LIMIT 5
            """) as cursor:
                top_liked_servers = await cursor.fetchall()

        embed = discord.Embed(title="📊 MemeConnect Server Stats", color=discord.Color.purple())
        
        posts_text = ""
        for i, (g_id, posts) in enumerate(top_post_servers, 1):
            guild = self.bot.get_guild(g_id)
            g_name = guild.name if guild else f"Unknown Server ({g_id})"
            posts_text += f"**#{i} {g_name}**: {posts} posts\n"
            
        embed.add_field(name="🏆 Most Active Servers (Posts)", value=posts_text or "No data yet.", inline=False)
        
        likes_text = ""
        for i, (g_id, score) in enumerate(top_liked_servers, 1):
            guild = self.bot.get_guild(g_id)
            g_name = guild.name if guild else f"Unknown Server ({g_id})"
            likes_text += f"**#{i} {g_name}**: {score} net score\n"
            
        embed.add_field(name="⭐ Most Liked Servers", value=likes_text or "No data yet.", inline=False)
        
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
            # 1. Fetch the unified meme URL/Hash group based on the message ID
            async with db.execute("SELECT attachment_url, author_id, guild_id FROM memes WHERE message_id = ?", (payload.message_id,)) as cursor:
                row = await cursor.fetchone()
                if not row: return
                attachment_url, author_id, origin_guild_id = row

            # 2. Check if this specific user has ALREADY voted on THIS meme across ANY server
            # We need a new table to track individual votes to prevent cross-server double dipping.
            await db.execute("""
                CREATE TABLE IF NOT EXISTS votes (
                    user_id INTEGER,
                    attachment_url TEXT,
                    vote_type TEXT,
                    PRIMARY KEY (user_id, attachment_url, vote_type)
                )
            """)
            
            # Check if vote exists
            async with db.execute("SELECT 1 FROM votes WHERE user_id = ? AND attachment_url = ? AND vote_type = ?", (payload.user_id, attachment_url, emoji)) as cursor:
                if await cursor.fetchone():
                    # They already voted this emoji on this meme in another server. Remove the duplicate reaction if possible.
                    channel = self.bot.get_channel(payload.channel_id)
                    if channel:
                        try:
                            msg = await channel.fetch_message(payload.message_id)
                            await msg.remove_reaction(emoji, payload.member or discord.Object(id=payload.user_id))
                        except: pass
                    return

            # 3. Log the vote so they can't do it again elsewhere
            await db.execute("INSERT INTO votes (user_id, attachment_url, vote_type) VALUES (?, ?, ?)", (payload.user_id, attachment_url, emoji))

            # 4. Apply the vote to ALL instances of this meme
            if emoji == "⬆️":
                await db.execute("UPDATE memes SET upvotes = upvotes + 1 WHERE attachment_url = ?", (attachment_url,))
            elif emoji == "⬇️":
                await db.execute("UPDATE memes SET downvotes = downvotes + 1 WHERE attachment_url = ?", (attachment_url,))
            elif emoji == "🚩":
                # We count flags globally using the votes table we just made
                async with db.execute("SELECT COUNT(*) FROM votes WHERE attachment_url = ? AND vote_type = '🚩'", (attachment_url,)) as cursor:
                    flag_count = (await cursor.fetchone())[0]

                # Calculate threshold: Max(3, 0.9% of total users)
                total_users = sum(g.member_count for g in self.bot.guilds)
                threshold = max(3, int(total_users * 0.009))

                if flag_count >= threshold:
                    # Time to quarantine!
                    # A. Delete it from ALL servers
                    async with db.execute("SELECT message_id, guild_id FROM memes WHERE attachment_url = ?", (attachment_url,)) as cursor:
                        meme_instances = await cursor.fetchall()
                        
                    for m_id, g_id in meme_instances:
                        if not g_id: continue
                        guild = self.bot.get_guild(g_id)
                        if not guild: continue
                        
                        # Find the channel (dank or wholesome) in that guild
                        async with db.execute("SELECT channel_id FROM channels WHERE guild_id = ?", (g_id,)) as ch_cursor:
                            channels = await ch_cursor.fetchall()
                            for (c_id,) in channels:
                                chan = guild.get_channel(c_id)
                                if chan:
                                    try:
                                        msg = await chan.fetch_message(m_id)
                                        await msg.delete()
                                    except: pass

                    # B. Send to Quarantine Channel for staff review
                    staff_chan = self.bot.get_channel(int(os.getenv("QUARANTINE_CHANNEL_ID")))
                    if staff_chan:
                        from utils.moderator import QuarantineView
                        embed = discord.Embed(title="🚨 COMMUNITY FLAGGED MEME", color=discord.Color.red())
                        
                        origin_server_name = "Unknown Server"
                        if origin_guild_id:
                            origin_guild = self.bot.get_guild(origin_guild_id)
                            if origin_guild:
                                origin_server_name = origin_guild.name
                                
                        embed.set_image(url=attachment_url)
                        embed.set_footer(text=f"Flagged {flag_count} times. Threshold was {threshold}. Author: {author_id} | 🌐 Origin: {origin_server_name}")
                        
                        # We pass a dummy hash and category since we just need the staff to review it
                        view = QuarantineView(discord.Object(id=author_id), "flagged_hash", attachment_url, "flagged")
                        await staff_chan.send(embed=embed, view=view)

            await db.commit()


async def setup(bot):
    await bot.add_cog(Rankings(bot))
