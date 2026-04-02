import aiosqlite
import aiohttp
import os
import asyncio

async def harvest():
    if not os.path.exists("training_data"):
        os.makedirs("training_data/safe")
        os.makedirs("training_data/unsafe")

    async with aiosqlite.connect("meme_connect.db") as db:
        async with db.execute("SELECT url, label FROM training_samples") as cursor:
            samples = await cursor.fetchall()

    async with aiohttp.ClientSession() as session:
        for i, (url, label) in enumerate(samples):
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        content = await resp.read()
                        ext = url.split('.')[-1].split('?')[0] # Get file extension
                        filename = f"training_data/{label}/harvested_{i}.{ext}"
                        with open(filename, "wb") as f:
                            f.write(content)
                        print(f"✅ Downloaded {label} sample: {i}")
            except Exception as e:
                print(f"❌ Failed {url}: {e}")

if __name__ == "__main__":
    asyncio.run(harvest())
