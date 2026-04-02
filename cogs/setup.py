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

    @commands.group(invoke_without_command=True, name="memeconnect_setup")
    async def memeconnect_setup(self, ctx):
        await ctx.send("WASA WASA! Use `promote`, `demote`, or `connect`.")

    @memeconnect_setup.group()
    async def promote(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Usage: `!memeconnect_setup promote moderator @user` or `admin @user`.")

    @promote.command(name="moderator")
    async def promote_mod(self, ctx, user: discord.User):
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

    @memeconnect_setup.group()
    async def demote(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Usage: `!memeconnect_setup demote moderator @user` or `admin @user`.")

    @demote.command(name="moderator")
    async def demote_mod(self, ctx, user: discord.User):
        rank = await self.get_role(ctx.author.id)
        if rank < 2:
            return await ctx.send("❌ You don't have the authority to fire moderators.")

        async with aiosqlite.connect("meme_connect.db") as db:
            await db.execute("UPDATE users SET is_staff = 0, is_admin = 0 WHERE user_id = ?", (user.id,))
            await db.commit()
        await ctx.send(f"📥 {user.name} has been removed from the staff team.")

    @demote.command(name="admin")
    async def demote_admin(self, ctx, user: discord.User):
        if ctx.author.id != self.owner_id:
            return await ctx.send("❌ Only the Founder can demote Admins.")

        async with aiosqlite.connect("meme_connect.db") as db:
            await db.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (user.id,))
            await db.commit()
        await ctx.send(f"📥 {user.name} is no longer an Admin (but remains a Moderator).")


async def setup(bot):
    await bot.add_cog(Setup(bot))
