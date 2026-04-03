import discord
from discord.ext import commands
import aiosqlite
import time
import os
import torch
import torch.nn as nn
from torchvision import models
from utils.hasher import generate_phash, predict_meme
import openai
import asyncio
import io


class Relay(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # --- LOAD LOCAL NEURAL NET (The Brain) ---
        self.model = self.load_local_brain()

    def load_local_brain(self):
        """Initializes the architecture and loads the trained .pth file."""
        try:
            # Must match the architecture used in train_model.py
            model = models.mobilenet_v2(weights=None)
            num_features = model.classifier[1].in_features
            model.classifier[1] = nn.Linear(num_features, 2)

            # Load the 'baked' weights
            model.load_state_dict(torch.load("meme_brain.pth", map_location='cpu', weights_only=True))
            model.eval()
            print("🧠 MemeConnect Brain: ONLINE")
            return model
        except Exception as e:
            print(f"⚠️ Neural Net failed to load: {e}")
            return None

    async def get_badge_prefix(self, author_id):
        owner_id = int(os.getenv("ALLOWED_ADMIN_ID")) if os.getenv("ALLOWED_ADMIN_ID") else None
        if author_id == owner_id:
            return "💎 **[FOUNDER]** "

        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute("SELECT is_admin, is_staff FROM users WHERE user_id = ?",
                                  (author_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    if row[0]: return "👑 **[ADMIN]** "
                    if row[1]: return "🛡️ **[MOD]** "
        return ""

    @commands.Cog.listener()
    async def on_message(self, message):
        # 1. Basic Filters
        if message.author.bot: return

        # 2. Check if Channel is a Registered Relay (dank-memes or wholesome-memes)
        if message.channel.name not in ["dank-memes", "wholesome-memes"]:
            return
        
        category = "dank" if message.channel.name == "dank-memes" else "wholesome"

        # 3. Enforce 'Images Only' (Deletes text/spam)
        if not message.attachments or not any(
                a.content_type and a.content_type.startswith(('image/', 'video/')) for a in message.attachments):
            await message.delete()
            return await message.channel.send(f"🚫 **{message.author.name}**, only memes allowed in the relay!",
                                              delete_after=3)

        # 4. Identity & Ban Check
        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute("SELECT is_banned, is_staff FROM users WHERE user_id = ?",
                                  (message.author.id,)) as cursor:
                user_data = await cursor.fetchone()
                is_banned = user_data[0] if user_data else 0
                is_staff = user_data[1] if user_data else 0
                if is_banned: return

        # 5. Processing the Meme
        attachment = message.attachments[0]
        img_bytes = await attachment.read()

        # A. Hash Check (Free/Fast)
        img_hash = generate_phash(img_bytes)
        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute("SELECT image_hash FROM banned_hashes WHERE image_hash = ?", (img_hash,)) as cursor:
                if await cursor.fetchone():
                    await message.delete()
                    return await message.channel.send("🚫 This meme is blacklisted.", delete_after=5)

        # B. Local Neural Net Check (The Brain)
        if self.model:
            # predict_meme returns 0 (Safe) or 1 (Unsafe)
            prediction = predict_meme(img_bytes, self.model)
            if prediction == 1:  # Assuming '1' is the 'unsafe' folder index
                await message.delete()
                return await message.channel.send("🚨 My local brain flagged this content.", delete_after=5)

        # C. OpenAI Check (The $5 Backup)
        if os.getenv('USE_OPENAI_AI') == 'True':
            try:
                client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                # Note: Moderation API for images requires specific model support
                # For simplicity, we use the standard check here
                response = client.moderations.create(
                    model="omni-moderation-latest",
                    input=[{"type": "image_url", "image_url": {"url": attachment.url}}]
                )
                if response.results[0].flagged:
                    await message.delete()
                    return await message.channel.send("🚨 OpenAI flagged this content.", delete_after=5)
            except Exception as e:
                print(f"⚠️ OpenAI Moderation failed: {e}")
                # We can still proceed if the local net passed and OpenAI fails temporarily, 
                # or block it. Usually safe to proceed if local AI is fine.

        # 7. Queue the Meme for Broadcast
        await message.channel.send("Meme queued!", delete_after=5)
        await message.delete()
        self.bot.loop.create_task(self.broadcast_meme(message, category, img_bytes, badge))

    async def broadcast_meme(self, message, category, img_bytes, badge):
        # Prepare for broadcast
        embed = discord.Embed(title=f"🚀 New {category.capitalize()} Meme", color=discord.Color.gold())
        embed.set_author(name=f"{badge}{message.author.name}", icon_url=message.author.display_avatar.url)
        file = discord.File(io.BytesIO(img_bytes), filename="meme.png")
        embed.set_image(url="attachment://meme.png")
        
        # Fetch all target channels
        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute("SELECT channel_id FROM channels WHERE category = ?",
                                  (category,)) as cursor:
                channels = await cursor.fetchall()

        print(f"Broadcasting to {len(channels)} total channels for category {category}")

        sent_count = 0
        # First, send to origin channel
        try:
            m = await message.channel.send(file=file, embed=embed)
            await m.add_reaction("⬆️")
            await m.add_reaction("⬇️")
            await m.add_reaction("🚩")
            async with aiosqlite.connect("meme_connect.db") as db:
                await db.execute(
                    "INSERT INTO memes (message_id, author_id, attachment_url, category) VALUES (?, ?, ?, ?)",
                    (m.id, message.author.id, "attachment://meme.png", category)
                )
                await db.commit()
        except Exception as e:
            print(f"Error sending to origin channel: {e}")

        # Then, send to other channels with 2s delay between
        for (chan_id,) in channels:
            if chan_id == message.channel.id:
                continue
                
            chan = self.bot.get_channel(chan_id)
            if chan:
                await asyncio.sleep(2)
                try:
                    m = await chan.send(file=file, embed=embed)
                    await m.add_reaction("⬆️")
                    await m.add_reaction("⬇️")
                    await m.add_reaction("🚩")

                    # Store in Memes table for Rankings
                    async with aiosqlite.connect("meme_connect.db") as db:
                        await db.execute(
                            "INSERT INTO memes (message_id, author_id, attachment_url, category) VALUES (?, ?, ?, ?)",
                            (m.id, message.author.id, "attachment://meme.png", category)
                        )
                        await db.commit()
                    sent_count += 1
                except discord.Forbidden:
                    continue
                except Exception as e:
                    print(f"Error broadcasting to channel {chan_id}: {e}")

        # Tell the user it broadcast successfully
        try:
            info_msg = await message.channel.send(f"✨ Broadcasted to {sent_count} other servers.", delete_after=10)
        except Exception as e:
            print(f"Error sending broadcast info: {e}")


async def setup(bot):
    await bot.add_cog(Relay(bot))
