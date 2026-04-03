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
        """MemeConnect command group. Use subcommands: promote, demote, stats."""
        await ctx.send("WASA WASA! Use `promote`, `demote`, or `stats`.")

    @memeconnect.group()
    async def promote(self, ctx):
        """Promote a user to moderator or admin."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Usage: `!memeconnect promote moderator @user` or `!memeconnect promote admin @user`.")

    @promote.command(name="moderator")
    async def promote_mod(self, ctx, user: discord.User):
        """Promote a user to Global Moderator."""
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
        if ctx.author.id != self.owner_id:
            return await ctx.send("❌ Only the Founder can demote Admins.")

        async with aiosqlite.connect("meme_connect.db") as db:
            await db.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user.id,))
            await db.commit()
        await ctx.send(f"📥 {user.name} is no longer an Admin (but remains a Moderator).")

    @memeconnect.command(name="stats")
    async def stats(self, ctx):
        """Show connected servers and metrics."""
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


async def setup(bot):
    await bot.add_cog(Setup(bot))
