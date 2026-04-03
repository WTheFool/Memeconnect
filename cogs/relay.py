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
        self.processing = set()  # Track messages being processed to prevent duplicates

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
        print(f"📨 Message in channel '{message.channel.name}' with {len(message.attachments)} attachments")
        # 1. Basic Filters
        if message.author.bot: return

        # Prevent duplicate processing of the same message
        if message.id in self.processing:
            print(f"⏭️ Skipping duplicate processing of message {message.id}")
            return
        
        self.processing.add(message.id)
        
        try:
            # 2. Check if Channel is a Registered Relay (dank-memes or wholesome-memes)
            if message.channel.name not in ["dank-memes", "wholesome-memes"]:
                return
            
            category = "dank" if message.channel.name == "dank-memes" else "wholesome"

            # 3. Enforce 'Images/Videos Only' (Deletes text/spam)
            valid_attachments = []
            for attachment in message.attachments:
                if attachment.content_type and attachment.content_type.startswith(('image/', 'video/')):
                    valid_attachments.append(attachment)

            if not valid_attachments:
                await message.delete()
                return await message.channel.send(f"🚫 **{message.author.name}**, only memes allowed in the relay!",
                                                  delete_after=3)

            if len(valid_attachments) > 10:
                await message.delete()
                return await message.channel.send("🚫 Too many memes! Max 10 at a time. Slow down!", delete_after=5)

            # 4. Identity & Ban Check
            async with aiosqlite.connect("meme_connect.db") as db:
                async with db.execute("SELECT is_banned, is_staff FROM users WHERE user_id = ?",
                                      (message.author.id,)) as cursor:
                    user_data = await cursor.fetchone()
                    is_banned = user_data[0] if user_data else 0
                    is_staff = user_data[1] if user_data else 0
                    if is_banned: return

            # 5. Process each attachment
            processed_attachments = []
            for attachment in valid_attachments:
                try:
                    img_bytes = await attachment.read()

                    # A. Hash Check (Free/Fast) - Skip for videos since PIL can't handle them
                    if attachment.content_type.startswith('image/'):
                        img_hash = generate_phash(img_bytes)
                        async with aiosqlite.connect("meme_connect.db") as db:
                            async with db.execute("SELECT image_hash FROM banned_hashes WHERE image_hash = ?", (img_hash,)) as cursor:
                                if await cursor.fetchone():
                                    continue  # Skip this one

                    # B. Local Neural Net Check (The Brain) - Only for images
                    if self.model and attachment.content_type.startswith('image/'):
                        prediction = predict_meme(img_bytes, self.model)
                        if prediction == 1:
                            continue  # Skip

                    # C. OpenAI Check (The $5 Backup)
                    if os.getenv('USE_OPENAI_AI') == 'True':
                        try:
                            client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
                            response = client.moderations.create(
                                model="omni-moderation-latest",
                                input=[{"type": "image_url", "image_url": {"url": attachment.url}}]
                            )
                            if response.results[0].flagged:
                                continue  # Skip
                        except Exception as e:
                            print(f"⚠️ OpenAI Moderation failed: {e}")

                    # If passed all checks, add to processed
                    processed_attachments.append((attachment, img_bytes))
                except Exception as e:
                    print(f"⚠️ Failed to process attachment {attachment.filename}: {e}")
                    continue  # Skip this attachment

            if not processed_attachments:
                await message.delete()
                return await message.channel.send("🚫 No valid memes passed the checks.", delete_after=5)

            # 6. Queue the batch
            badge = await self.get_badge_prefix(message.author.id)
            await message.channel.send(f"Meme(s) queued! ({len(processed_attachments)})", delete_after=5)
            await message.delete()
            self.bot.loop.create_task(self.broadcast_batch(message, processed_attachments, category, badge))
        finally:
            # Always remove from processing set
            self.processing.discard(message.id)

    async def broadcast_single(self, message, attachment, img_bytes, category, badge):
        # Prepare for broadcast
        embed = discord.Embed(title=f"🚀 New {category.capitalize()} Meme", color=discord.Color.gold())
        embed.set_author(name=f"{badge}{message.author.name}", icon_url=message.author.display_avatar.url)
        filename = attachment.filename
        
        # Set image for embeds only if it's an image
        if attachment.content_type and attachment.content_type.startswith('image/'):
            embed.set_image(url=f"attachment://{filename}")
        
        # Fetch all target channels
        async with aiosqlite.connect("meme_connect.db") as db:
            async with db.execute("SELECT channel_id FROM channels WHERE category = ?",
                                  (category,)) as cursor:
                channels = await cursor.fetchall()

        print(f"Broadcasting meme {filename} to {len(channels)} channels")

        # Send to all channels with 2s delay between
        for i, (chan_id,) in enumerate(channels):
            if i > 0:
                await asyncio.sleep(2)
                
            chan = self.bot.get_channel(chan_id)
            if chan:
                try:
                    # IMPORTANT: Recreate the file object for each send!
                    # Discord.File can only be sent once, so we must create a fresh copy
                    file = discord.File(io.BytesIO(img_bytes), filename=filename)
                    m = await chan.send(file=file, embed=embed)
                    await m.add_reaction("⬆️")
                    await m.add_reaction("⬇️")
                    await m.add_reaction("🚩")

                    # Store in Memes table for Rankings
                    async with aiosqlite.connect("meme_connect.db") as db:
                        await db.execute(
                            "INSERT INTO memes (message_id, author_id, attachment_url, category, guild_id) VALUES (?, ?, ?, ?, ?)",
                            (m.id, message.author.id, f"attachment://{filename}", category, chan.guild.id)
                        )
                        await db.commit()
                    print(f"✅ Posted to channel {chan_id}")
                except discord.Forbidden:
                    print(f"❌ No permission to post in channel {chan_id}")
                    continue
                except Exception as e:
                    print(f"❌ Error broadcasting to channel {chan_id}: {e}")

    async def broadcast_batch(self, message, processed_attachments, category, badge):
        for attachment, img_bytes in processed_attachments:
            await self.broadcast_single(message, attachment, img_bytes, category, badge)

        # Tell the user it broadcast successfully
        try:
            total_memes = len(processed_attachments)
            async with aiosqlite.connect("meme_connect.db") as db:
                async with db.execute("SELECT COUNT(*) FROM channels WHERE category = ?", (category,)) as cursor:
                    channel_count = (await cursor.fetchone())[0]
            info_msg = await message.channel.send(f"✨ Broadcasted {total_memes} meme(s) to {channel_count} channel(s).", delete_after=10)
        except Exception as e:
            print(f"Error sending broadcast info: {e}")


async def setup(bot):
    await bot.add_cog(Relay(bot))
