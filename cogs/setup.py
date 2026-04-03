import os
import discord
from discord.ext import commands
import aiosqlite


class Setup(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.owner_id = int(os.getenv("ALLOWED_ADMIN_ID")) if os.getenv("ALLOWED_ADMIN_ID") else None

    async def get_role(self, user_id):
        """Helper to check rank: 0=User, 1=Mod, 2=Admin, 3=Founder"""
        if user_id == self.owner_id: return 3
        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute("SELECT is_admin, is_staff FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
                if not row: return 0
                if row[0]: return 2  # Admin
                if row[1]: return 1  # Mod
        return 0

    @commands.group(invoke_without_command=True, name="memeconnect")
    async def memeconnect(self, ctx):
        """MemeConnect command group."""
        print(f"📝 MemeConnect group invoked in {ctx.guild.name if ctx.guild else 'DM'} by {ctx.author}")
        embed = discord.Embed(title="🚀 MemeConnect Commands", color=discord.Color.blue())
        embed.add_field(name="`!memeconnect bestof [all/month]`", value="Shows the top 10 most liked memes.", inline=False)
        embed.add_field(name="`!memeconnect worstof [all/month]`", value="Shows the top 10 most disliked memes.", inline=False)
        embed.add_field(name="`!memeconnect top_users`", value="Shows the 10 users with the highest net score.", inline=False)
        embed.add_field(name="`!memeconnect worst_users`", value="Shows the 10 users with the lowest net score.", inline=False)
        embed.add_field(name="`!memeconnect stats`", value="Shows connected servers and metrics.", inline=False)
        embed.add_field(name="`!memeconnect promote moderator/admin @user`", value="Manage staff roles (Admin/Founder only).", inline=False)
        embed.add_field(name="`!memeconnect demote moderator/admin @user`", value="Remove staff roles (Admin/Founder only).", inline=False)
        embed.add_field(name="`!strike @user [reason]`", value="Issue a strike to a user (Staff only).", inline=False)
        embed.add_field(name="`!appeal [reason]`", value="Send an appeal to the board.", inline=False)
        
        embed.set_footer(text="WASA WASA WASA!")
        await ctx.send(embed=embed)

    @memeconnect.group()
    async def promote(self, ctx):
        """Promote a user to moderator or admin."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Usage: `!memeconnect promote moderator @user` or `!memeconnect promote admin @user`.")

    @promote.command(name="moderator")
    async def promote_mod(self, ctx, user: discord.User):
        """Promote a user to Global Moderator."""
        print(f"📝 Promote moderator invoked in {ctx.guild.name if ctx.guild else 'DM'} by {ctx.author}")
        rank = await self.get_role(ctx.author.id)
        if rank < 2:  # Must be Admin or Founder
            return await ctx.send("❌ Only Admins or the Founder can hire moderators!")

        async with aiosqlite.connect("meme_connect.db") as db:
            await db.execute(
                "INSERT INTO users (user_id, is_staff) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET is_staff=1",
                (user.id,))
            await db.commit()
        await ctx.send(f"🛡️ {user.name} has been appointed as a **Global Moderator**.")

    @promote.command(name="admin")
    async def promote_admin(self, ctx, user: discord.User):
        """Appoint a user as Global Admin."""
        print(f"📝 Promote admin invoked in {ctx.guild.name if ctx.guild else 'DM'} by {ctx.author}")
        rank = await self.get_role(ctx.author.id)
        if rank < 3:  # Only Founder
            return await ctx.send("❌ Only the Founder can appoint Admins!")

        async with aiosqlite.connect("meme_connect.db") as db:
            # Admins are automatically Staff too
            await db.execute(
                "INSERT INTO users (user_id, is_admin, is_staff) VALUES (?, 1, 1) ON CONFLICT(user_id) DO UPDATE SET is_admin=1, is_staff=1",
                (user.id,))
            await db.commit()
        await ctx.send(f"👑 {user.name} is now a **Global Admin**.")

    @memeconnect.group()
    async def demote(self, ctx):
        """Demote a user from moderator or admin."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Usage: `!memeconnect demote moderator @user` or `!memeconnect demote admin @user`.")

    @demote.command(name="moderator")
    async def demote_mod(self, ctx, user: discord.User):
        """Remove moderator privileges from a user."""
        print(f"📝 Demote moderator invoked in {ctx.guild.name if ctx.guild else 'DM'} by {ctx.author}")
        rank = await self.get_role(ctx.author.id)
        if rank < 2:
            return await ctx.send("❌ You don't have the authority to fire moderators.")

        async with aiosqlite.connect("meme_connect.db") as db:
            await db.execute("UPDATE users SET is_staff = 0, is_admin = 0 WHERE user_id = ?", (user.id,))
            await db.commit()
        await ctx.send(f"📥 {user.name} has been removed from the staff team.")

    @demote.command(name="admin")
    async def demote_admin(self, ctx, user: discord.User):
        """Demote an admin, retaining moderator status."""
        print(f"📝 Demote admin invoked in {ctx.guild.name if ctx.guild else 'DM'} by {ctx.author}")
        if ctx.author.id != self.owner_id:
            return await ctx.send("❌ Only the Founder can demote Admins.")

        async with aiosqlite.connect("meme_connect.db") as db:
            await db.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user.id,))
            await db.commit()
        await ctx.send(f"📥 {user.name} is no longer an Admin (but remains a Moderator).")

    @memeconnect.command(name="stats")
    async def stats(self, ctx):
        """Show connected servers and metrics."""
        print(f"📝 Stats command invoked in {ctx.guild.name if ctx.guild else 'DM'} by {ctx.author}")
        # Get connected servers sorted by population
        guilds = sorted(self.bot.guilds, key=lambda g: g.member_count, reverse=True)
        server_list = "\n".join([f"• {g.name} ({g.member_count} members)" for g in guilds[:10]])  # Top 10

        # Get metrics from database
        async with aiosqlite.connect("meme_connect.db") as db:
            # Most posts by server
            async with db.execute("""
                SELECT guild_id, COUNT(message_id) as post_count
                FROM memes
                GROUP BY guild_id
                ORDER BY post_count DESC
                LIMIT 5
            """) as cursor:
                top_posts_raw = await cursor.fetchall()

            # Most liked server (upvotes - downvotes)
            async with db.execute("""
                SELECT guild_id, SUM(upvotes - downvotes) as net_likes
                FROM memes
                GROUP BY guild_id
                ORDER BY net_likes DESC
                LIMIT 5
            """) as cursor:
                top_liked_raw = await cursor.fetchall()

        # Get guild names
        def get_guild_name(guild_id):
            guild = self.bot.get_guild(guild_id)
            return guild.name if guild else f"Unknown ({guild_id})"

        top_posts = [(get_guild_name(gid), count) for gid, count in top_posts_raw]
        top_liked = [(get_guild_name(gid), likes) for gid, likes in top_liked_raw]

        posts_str = "\n".join([f"• {name}: {count} posts" for name, count in top_posts])
        likes_str = "\n".join([f"• {name}: {likes} net likes" for name, likes in top_liked])

        embed = discord.Embed(title="📊 MemeConnect Stats", color=discord.Color.blue())
        embed.add_field(name="🌐 Connected Servers (by population)", value=server_list or "None", inline=False)
        embed.add_field(name="📈 Most Posts by Server", value=posts_str or "No data", inline=False)
        embed.add_field(name="❤️ Most Liked Server", value=likes_str or "No data", inline=False)

        await ctx.send(embed=embed)

    @memeconnect.command()
    async def bestof(self, ctx, period: str = "all"):
        """Show the top 10 most liked memes."""
        print(f"📝 Bestof command invoked in {ctx.guild.name if ctx.guild else 'DM'} by {ctx.author}")
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
        """Show the top 10 most disliked memes."""
        print(f"📝 Worstof command invoked in {ctx.guild.name if ctx.guild else 'DM'} by {ctx.author}")
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
        """Show the 10 users with the highest net score."""
        print(f"📝 Top users command invoked in {ctx.guild.name if ctx.guild else 'DM'} by {ctx.author}")
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
        """Show the 10 users with the lowest net score."""
        print(f"📝 Worst users command invoked in {ctx.guild.name if ctx.guild else 'DM'} by {ctx.author}")
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


async def setup(bot):
    await bot.add_cog(Setup(bot))
