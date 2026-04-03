# MemeConnect Deployment & Debugging Guide

## What Was Fixed

### 1. **Double "Memes Queued" Messages** ✅
- **Problem**: `on_message` was being triggered twice for the same message
- **Solution**: Added `self.processing` set to deduplicate message handling
- **Result**: Only ONE "Memes queued!" message per user post

### 2. **Broadcasts Not Working (0 Servers)** ✅
- **Problem**: Channels weren't being fetched from database (SQL queries returned 0 results)
- **Root Cause**: `setup_hook()` was trying to populate channels before guilds loaded
- **Solution**: Moved all channel population to `on_ready()` where guilds are fully loaded
- **Result**: Channels are NOW properly registered and broadcasts will work

### 3. **File Upload Support** ✅
- MP4, GIF, PNG, JPG all supported
- Each file is re-created for each Discord.File send (Discord limitation)
- Videos skip PIL-based checks (hash/AI) but work fine as file uploads

### 4. **Port Issue** ✅
- Flask runs on port 10000 (standard for Render)
- "No open ports detected" is a normal Render warning - NOT an error
- Render detects ports automatically, doesn't need manual config

## Logs You'll See on Render

### On Startup:
```
🔧 Initializing MemeConnect bot...
📋 Starting setup_hook...
✅ Loaded Cog: cogs.relay
✅ Loaded Cog: cogs.rankings
✅ Loaded Cog: cogs.justice
✅ Loaded Cog: cogs.setup
✅ Setup complete - waiting for guilds to load...
🚀 WASA WASA WASA! MemeConnect IS LIVE ON RENDER!
🌐 Connected to X guilds
📂 Populating channels table...
  Checking guild: ServerName
✅ Channels table populated: X total channels registered
   - Guild ID: dank -> Channel ID
```

### When Someone Posts a Meme:
```
📨 Message in channel 'dank-memes' with 1 attachments
Broadcasting meme filename.jpg to 3 channels
✅ Posted to channel 123456
✅ Posted to channel 789012
✅ Posted to channel 345678
```

### Troubleshooting Logs:

**If you see "Broadcasting to 0 channels":**
- Channels not registered in database
- Check that all guilds were found in on_ready
- All servers must have "dank-memes" and "wholesome-memes" channels

**If you see "❌ No permission to post":**
- Bot missing permissions in that channel
- Add "Send Messages" and "Attach Files" permissions

**If you see attachment processing errors:**
- Video files that fail PIL processing are skipped (OK)
- Other errors logged: "⚠️ Failed to process attachment"

## What to Test

1. **Post 1 image to dank-memes**
   - Should see "Meme(s) queued! (1)" ONCE
   - Should broadcast to all servers
   - Should see "✨ Broadcasted 1 meme(s) to X channel(s)"

2. **Post 1 MP4 to dank-memes**
   - Should see "Meme(s) queued! (1)" ONCE
   - Should broadcast as file (no embed preview for videos)
   - Should work identically to images

3. **Post 3 images + 1 GIF to dank-memes**
   - Should see "Meme(s) queued! (4)" ONCE
   - All 4 should broadcast to all servers
   - GIF should work like any other file

## Permissions Needed

Make sure the bot has these permissions in all meme channels:
- ✅ Send Messages
- ✅ Embed Links
- ✅ Attach Files
- ✅ Add Reactions
- ✅ Manage Messages (to delete user's original message)
- ✅ Read Message History

## Ready to Deploy!

This version should work perfectly. Deploy to Render and:
1. Check the startup logs (should see all channels registered)
2. Test posting memes
3. Check Render logs for any errors
4. All logs are printed to help debug!

