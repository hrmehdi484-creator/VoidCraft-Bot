import os
import sqlite3
import threading
import requests
from flask import Flask, render_template, request, redirect, jsonify, session
import discord
from discord.ext import commands

# --- CONFIGURATION ---
DB_FILE = "bot_data.db"
CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "1532076922241024090")
CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://voidcraft-bot.onrender.com/callback")
BOT_TOKEN = os.environ.get("DISCORD_TOKEN", "")

# Database Setup
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS guild_settings 
                 (guild_id TEXT PRIMARY KEY, is_premium INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

init_db()

# --- DISCORD BOT SETUP ---
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot is online and logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"⚡ Synced {len(synced)} Slash Commands.")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

@bot.tree.command(name="ping", description="فحص سرعة استجابة البوت")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: `{latency}ms`")

@bot.tree.command(name="ownerhelp", description="عرض لوحة التحكم المتقدمة للأونر")
async def ownerhelp(interaction: discord.Interaction):
    embed = discord.Embed(
        title="⚡ VoidCraft Owner & Admin Dashboard",
        description="جميع الأوامر وإعدادات السيرفر متاحة لك هنا بنجاح!",
        color=0x7289da
    )
    embed.add_field(name="🛡️ Moderation", value="`/ban`, `/kick`, `/mute`, `/clear`", inline=False)
    embed.add_field(name="⚙️ Setup", value="`/setup_tickets`, `/testwelcome`", inline=False)
    await interaction.response.send_message(embed=embed)

# --- FLASK WEB SERVER SETUP ---
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "voidcraft_super_secret_key_123")

@app.route("/")
def home():
    return """
    <html>
        <head><title>VoidCraft Bot</title></head>
        <body style='background:#0f0f15; color:white; font-family:sans-serif; text-align:center; padding-top:50px;'>
            <h1>🚀 VoidCraft Bot is Live & Running 24/7</h1>
            <p>الموقع والبوت يعملان معاً بنجاح!</p>
            <a href='/login' style='color:#7289da; text-decoration:none; font-size:20px;'>👉 تسجيل الدخول عبر Discord</a>
        </body>
    </html>
    """

@app.route("/api/activate", methods=["POST"])
def api_activate():
    data = request.json or {}
    guild_id = data.get("guild_id")
    if not guild_id:
        return jsonify({"error": "Missing guild_id"}), 400

    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO guild_settings (guild_id, is_premium) VALUES (?, 1)", (guild_id,))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": f"Guild {guild_id} activated successfully!"})

# --- DUAL RUNNER (BOT + WEB SERVER) ---
def run_bot():
    if BOT_TOKEN:
        bot.run(BOT_TOKEN)
    else:
        print("❌ Error: DISCORD_TOKEN is missing in Environment Variables!")

# تشغيل البوت في Thread منفصل عند بدء التشغيل
bot_thread = threading.Thread(target=run_bot)
bot_thread.daemon = True
bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)