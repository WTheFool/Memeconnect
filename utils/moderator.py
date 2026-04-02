import discord
import aiosqlite
import os

class JudicialView(discord.ui.View):
    def __init__(self, action_id):
        super().__init__(timeout=None)
        self.action_id = action_id

    @discord.ui.button(label="✅ Approve (Leave Penalty)", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect("meme_connect.db") as db:
            await db.execute("UPDATE judicial_actions SET approve_votes = approve_votes + 1 WHERE action_id = ?", (self.action_id,))
            await db.commit()
        await interaction.response.send_message("Vote to keep penalty counted.", ephemeral=True)

    @discord.ui.button(label="❌ Revoke (Lift Penalty)", style=discord.ButtonStyle.red)
    async def revoke(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect("meme_connect.db") as db:
            await db.execute("UPDATE judicial_actions SET revoke_votes = revoke_votes + 1 WHERE action_id = ?", (self.action_id,))
            await db.commit()
        await interaction.response.send_message("Vote to revoke penalty counted.", ephemeral=True)


class QuarantineView(discord.ui.View):
    def __init__(self, author, img_hash, img_url, category):
        super().__init__(timeout=None)
        self.author = author
        self.img_hash = img_hash
        self.img_url = img_url
        self.category = category
        self.owner_id = int(os.getenv("ALLOWED_ADMIN_ID"))

    async def get_badge_prefix(self):
        """Calculates the badge based on user hierarchy."""
        if self.author.id == self.owner_id:
            return "💎 **[FOUNDER]** "

        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute("SELECT is_admin, is_staff FROM users WHERE user_id = ?",
                                  (self.author.id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    if row[0]: return "👑 **[ADMIN]** "  # is_admin
                    if row[1]: return "🛡️ **[MOD]** "  # is_staff
        return ""

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.green)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Log for AI Training
        async with aiosqlite.connect("meme_connect.db") as db:
            await db.execute("INSERT INTO training_samples (url, label) VALUES (?, 'safe')", (self.img_url,))
            await db.commit()

        # 2. Get the Badge
        badge = await self.get_badge_prefix()

        # 3. Fetch all target channels
        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute("SELECT channel_id FROM channels WHERE category = ?",
                                  (self.category.lower(),)) as cursor:
                channels = await cursor.fetchall()

        # 4. Prepare Embed
        embed = discord.Embed(title=f"🚀 New {self.category.capitalize()} Meme", color=discord.Color.gold())
        embed.set_author(name=f"{badge}{self.author.name}", icon_url=self.author.display_avatar.url)
        embed.set_image(url=self.img_url)
        embed.set_footer(text="✅ VERIFIED BY STAFF | WASA WASA!")

        # 5. Broadcast Loop
        sent_count = 0
        for (chan_id,) in channels:
            chan = interaction.client.get_channel(chan_id)
            if chan:
                try:
                    m = await chan.send(embed=embed)
                    await m.add_reaction("⬆️")
                    await m.add_reaction("⬇️")
                    await m.add_reaction("🚩")

                    # Store in Memes table for Rankings
                    async with aiosqlite.connect("meme_connect.db") as db:
                        await db.execute(
                            "INSERT INTO memes (message_id, author_id, attachment_url, category) VALUES (?, ?, ?, ?)",
                            (m.id, self.author.id, self.img_url, self.category.lower())
                        )
                        await db.commit()
                    sent_count += 1
                except:
                    continue

        await interaction.response.edit_message(content=f"✨ **Approved!** Broadcasted to {sent_count} servers.",
                                                view=None, embed=None)

    @discord.ui.button(label="🗑️ Reject", style=discord.ButtonStyle.gray)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect("meme_connect.db") as db:
            await db.execute("INSERT INTO training_samples (url, label) VALUES (?, 'unsafe')", (self.img_url,))
            await db.commit()
        await interaction.response.edit_message(content="❌ **Rejected.** Meme logged as Unsafe.", view=None, embed=None)

    @discord.ui.button(label="🔨 Global Ban", style=discord.ButtonStyle.red)
    async def ban(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with aiosqlite.connect("meme_connect.db") as db:
            await db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (self.author.id,))
            await db.execute("INSERT OR IGNORE INTO banned_hashes (image_hash) VALUES (?)", (self.img_hash,))
            await db.execute("INSERT INTO training_samples (url, label) VALUES (?, 'unsafe')", (self.img_url,))
            await db.commit()
        await interaction.response.edit_message(content=f"🚨 **Banned.** User {self.author.id} blacklisted.", view=None,
                                                embed=None)
