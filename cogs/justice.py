import discord
from discord.ext import commands
import aiosqlite
import os
from utils.moderator import JudicialView

class Justice(commands.Cog):
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

    @commands.command()
    async def appeal(self, ctx, *, reason: str):
        """Users can DM or use this to appeal a ban/strike."""
        rug_pull = self.bot.get_channel(int(os.getenv("RUG_PULL_CHANNEL_ID")))
        embed = discord.Embed(title="⚖️ New Appeal", color=discord.Color.purple(), description=reason)
        embed.set_author(name=f"{ctx.author} ({ctx.author.id})")
        await rug_pull.send(embed=embed)
        await ctx.send("✅ Your appeal has been sent to the board.")

    @commands.group(invoke_without_command=True)
    async def strike(self, ctx, user: discord.User, *, reason: str):
        # 1. Check if issuer is staff
        rank = await self.get_role(ctx.author.id)
        if rank < 1: return

        async with aiosqlite.connect("meme_connect.db") as db:
            # 2. Log Action
            await db.execute("UPDATE users SET strikes = strikes + 1 WHERE user_id = ?", (user.id,))
            cursor = await db.execute(
                "INSERT INTO judicial_actions (target_id, reason, issuer_id, type) VALUES (?, ?, ?, 'strike')",
                (user.id, reason, ctx.author.id)
            )
            action_id = cursor.lastrowid
            await db.commit()

        # 3. Post to Rug Pull for Review
        rug_pull = self.bot.get_channel(int(os.getenv("RUG_PULL_CHANNEL_ID")))
        view = JudicialView(action_id)
        embed = discord.Embed(title="🔨 Strike Issued", color=discord.Color.orange())
        embed.add_field(name="Target", value=user.mention); embed.add_field(name="Reason", value=reason)
        embed.set_footer(text="24h to Revoke. Net +3 Revokes to pardon.")
        await rug_pull.send(embed=embed, view=view)
        await ctx.send(f"Striken {user.name}. Case logged in #rug-pull.")

    @strike.command(name="remove")
    async def remove_strike(self, ctx, user: discord.User):
        rank = await self.get_role(ctx.author.id)
        if rank < 1: 
            return await ctx.send("❌ Only moderators, admins, and the founder can remove strikes.")
            
        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute("SELECT strikes FROM users WHERE user_id = ?", (user.id,)) as cursor:
                row = await cursor.fetchone()
                if not row or row[0] <= 0:
                    return await ctx.send(f"✅ {user.name} does not have any strikes.")
            
            await db.execute("UPDATE users SET strikes = strikes - 1 WHERE user_id = ?", (user.id,))
            await db.commit()
            
        await ctx.send(f"⚖️ A strike has been successfully removed from {user.name}.")

async def setup(bot):
    await bot.add_cog(Justice(bot))
