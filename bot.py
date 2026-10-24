import discord
from discord.ext import commands
from discord import app_commands
import io
import time
from datetime import timedelta
from collections import defaultdict
import threading
import os
import random
import asyncio
import sqlite3
import requests
from flask import Flask, jsonify, request, redirect, session, url_for, render_template_string

# ==============================================================================
#                     إعداد قاعدة البيانات الدائمة (SQLite)
# ==============================================================================

DB_FILE = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            balance INTEGER DEFAULT 100
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id TEXT PRIMARY KEY,
            language TEXT DEFAULT 'en',
            is_premium INTEGER DEFAULT 0,
            expiry_date TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_user_data(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT xp, balance FROM users WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users (user_id, xp, balance) VALUES (?, 0, 100)", (user_id,))
        conn.commit()
        conn.close()
        return 0, 100
    conn.close()
    return row[0], row[1]

def update_user_data(user_id, xp=None, balance=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    current_xp, current_balance = get_user_data(user_id)
    new_xp = xp if xp is not None else current_xp
    new_balance = balance if balance is not None else current_balance
    c.execute("UPDATE users SET xp = ?, balance = ? WHERE user_id = ?", (new_xp, new_balance, user_id))
    conn.commit()
    conn.close()

def get_server_lang(guild_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT language FROM guild_settings WHERE guild_id = ?", (str(guild_id),))
    row = c.fetchone()
    if not row:
        conn.close()
        return "en"
    conn.close()
    return row[0]

def set_server_lang(guild_id, lang):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO guild_settings (guild_id, language) VALUES (?, ?)", (str(guild_id), lang))
    conn.commit()
    conn.close()

# ==============================================================================
#                     الإعدادات الأساسية للبوت والمتغيرات
# ==============================================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command('help')

last_daily = defaultdict(float)
user_warnings = defaultdict(list)
user_violations = defaultdict(lambda: {'suspicious_count': 0, 'link_count': 0, 'last_time': 0.0})

OWNER_IDS = [1335193543660273716]
MY_SERVER_INVITE = "discord.gg/voidcraft"

DANGEROUS_EXTENSIONS = ['.exe', '.scr', '.bat', '.cmd', '.vbs', '.js', '.msi', '.zip', '.rar', '.7z']

def is_owner_or_guild_owner(interaction: discord.Interaction):
    if interaction.user.id in OWNER_IDS or interaction.user == interaction.guild.owner:
        return True
    return False

TRANSLATIONS = {
    "en": {
        "staff_only": "❌ Error: Restricted to server staff only!",
        "owner_only": "❌ Error: Restricted to Bot Owner / Server Owner ONLY!",
        "admin_channel_err": "❌ SECURITY ALERT: Staff commands CANNOT be used in public channels!",
        "log_title": "🚨 [Punishment Log - {type}]",
        "target": "👤 Target Member",
        "executor": "🛡️ Executor",
        "duration": "⏱️ Duration",
        "reason": "📜 Reason",
        "lang_changed": "🌐 Server language successfully set to: **{lang}**"
    },
    "ar": {
        "staff_only": "❌ عذراً، هذا الأمر مخصص للإدارة فقط!",
        "owner_only": "❌ عذراً، هذا الأمر مخصص حصرياً لأونر البوت / مالك السيرفر فقط!",
        "admin_channel_err": "❌ تنبيه أمني: يمنع استخدام أوامر الإدارة في القنوات العامة!",
        "log_title": "🚨 [سجل عقوبة - {type}]",
        "target": "👤 العضو المُعاقَب",
        "executor": "🛡️ المنفذ",
        "duration": "⏱️ المدة",
        "reason": "📜 السبب",
        "lang_changed": "🌐 تم تغيير لغة السيرفر بنجاح إلى: **{lang}**"
    }
}

def get_text(guild_id, key, **kwargs):
    lang = get_server_lang(guild_id) if guild_id else "en"
    if lang not in TRANSLATIONS:
        lang = "en"
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS["en"].get(key, key))
    return text.format(**kwargs)

async def send_punishment_log(guild, member, executor, punishment_type, reason, duration="Permanent"):
    ban_channel = discord.utils.get(guild.text_channels, name="ban") or discord.utils.get(guild.text_channels, name="logs")
    embed = discord.Embed(title=get_text(guild.id, "log_title", type=punishment_type), color=discord.Color.red(), timestamp=discord.utils.utcnow())
    embed.add_field(name=get_text(guild.id, "target"), value=f"{member.mention} (`{member.id}`)", inline=True)
    embed.add_field(name=get_text(guild.id, "executor"), value=f"{executor.mention if hasattr(executor, 'mention') else executor}", inline=True)
    embed.add_field(name=get_text(guild.id, "reason"), value=f"`{reason}`", inline=False)
    if ban_channel:
        try: await ban_channel.send(embed=embed)
        except: pass

@bot.event
async def on_ready():
    print(f"✅ Bot is online and logged in as {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"⚡ Synced {len(synced)} Slash Commands.")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")

def is_staff_channel(channel):
    name = channel.name.lower()
    return any(keyword in name for keyword in ["admin", "staff", "console", "owner", "ادارة", "الإدارة", "cmd"])

async def check_admin_channel(interaction: discord.Interaction):
    if is_owner_or_guild_owner(interaction):
        return True
    if not is_staff_channel(interaction.channel):
        await interaction.response.send_message(get_text(interaction.guild.id, "admin_channel_err"), ephemeral=True)
        return False
    return True

# ==============================================================================
#                 👑 لوحة التحكم الشاملة والأوامر الأساسية
# ==============================================================================

@bot.tree.command(name="ownerhelp", description="Master Control Panel: All Bot Commands in One Place")
async def ownerhelp(interaction: discord.Interaction):
    if not is_owner_or_guild_owner(interaction):
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)

    embed = discord.Embed(
        title="👑 VoidCraft Master Control Panel (All-in-One)",
        description="📋 **جميع أوامر البوت والسيرفر مجتمعة هنا:**",
        color=discord.Color.gold()
    )
    embed.add_field(name="👑 1. الأونر والرتب", value="`/giverole`, `/removerole`, `/roleall`", inline=False)
    embed.add_field(name="🛠️ 2. القنوات والتنظيف", value="`/nuke`, `/createchannel`, `/deletechannel`, `/lock`, `/unlock`, `/slowmode`, `/clear`", inline=False)
    embed.add_field(name="🔨 3. العقوبات", value="`/mute`, `/unmute`, `/kick`, `/ban`, `/unban`, `/warn`, `/infractions`", inline=False)
    embed.add_field(name="🌐 4. الأعضاء والاقتصاد", value="`/daily`, `/balance`, `/pay`, `/quiz`, `/roll`, `/level`", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="ping", description="فحص سرعة استجابة البوت")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: `{latency}ms`", ephemeral=True)

@bot.tree.command(name="daily", description="Claim daily coins reward")
async def daily(interaction: discord.Interaction):
    user_id = interaction.user.id
    current_time = time.time()
    if current_time - last_daily[user_id] < 86400:
        remaining = int(86400 - (current_time - last_daily[user_id]))
        return await interaction.response.send_message(f"⌛ Wait **{remaining//3600}h {(remaining%3600)//60}m**.", ephemeral=True)
    
    reward = random.randint(200, 500)
    xp, bal = get_user_data(user_id)
    update_user_data(user_id, balance=bal + reward)
    last_daily[user_id] = current_time
    await interaction.response.send_message(f"🎁 Claimed **{reward} coins**! Balance: **{bal + reward}**.")

@bot.tree.command(name="balance", description="Check balance")
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    _, coins = get_user_data(target.id)
    await interaction.response.send_message(f"🪙 **{target.name}** has **{coins} coins**.", ephemeral=True)


# ==============================================================================
#       🌐 خادم الويب ونظام الدخول بـ Discord وواجهة الـ HTML (المتكامل)
# ==============================================================================

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "voidcraft_secret_key_12345")

DISCORD_CLIENT_ID = os.environ.get("DISCORD_CLIENT_ID", "1532076922241024090")
DISCORD_CLIENT_SECRET = os.environ.get("DISCORD_CLIENT_SECRET", "")
REDIRECT_URI = os.environ.get("REDIRECT_URI", "https://voidcraft-bot.onrender.com/callback")

OAUTH2_URL = f"https://discord.com/api/oauth2/authorize?client_id={DISCORD_CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=identify%20guilds"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VoidCraft - النظام الاحترافي الشامل</title>
    <style>
        body { background-color: #0b0f19; color: #ffffff; font-family: sans-serif; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; min-height: 100vh; }
        .container { text-align: center; background: rgba(17, 24, 39, 0.9); padding: 40px; border-radius: 20px; box-shadow: 0 8px 32px rgba(124, 58, 237, 0.37); max-width: 750px; width: 100%; }
        .avatar { width: 130px; height: 130px; border-radius: 50%; border: 3px solid #8b5cf6; object-fit: cover; margin-bottom: 20px; }
        h1 { color: #8b5cf6; }
        p { color: #9ca3af; }
        .btn { background-color: #7c3aed; color: white; padding: 14px 30px; border-radius: 10px; text-decoration: none; font-weight: bold; display: inline-block; margin: 10px; }
        .btn-buy { background-color: #10b981; }
        .server-card { background: #1e293b; padding: 18px; margin: 12px 0; border-radius: 12px; display: flex; justify-content: space-between; align-items: center; }
    </style>
</head>
<body>
    <div class="container">
        <img src="{{ bot_avatar }}" class="avatar" alt="VoidCraft Avatar">
        <h1>VoidCraft</h1>
        <p>النظام الاحترافي المتكامل لإدارة وتنشيط سيرفرك 24/7.</p>
        {% if not user %}
            <a href="{{ oauth_url }}" class="btn btn-buy">🔑 تسجيل الدخول بحساب Discord للشراء</a>
        {% else %}
            <h3>أهلاً بك، {{ user['username'] }} 👋</h3>
            <div>
                {% for guild in owned_guilds %}
                    <div class="server-card">
                        <span>🏰 {{ guild['name'] }}</span>
                        <button onclick="activateGuild('{{ guild['id'] }}')" class="btn btn-buy">تفعيل هذا السيرفر ($4.99)</button>
                    </div>
                {% else %}
                    <p style="color: #ef4444;">لم نجد سيرفرات تملك فيها رتبة (Owner)!</p>
                {% endfor %}
            </div>
            <br><a href="/logout" style="color: #9ca3af;">تسجيل الخروج</a>
        {% endif %}
    </div>
    <script>
        function activateGuild(guildId) {
            fetch('/api/activate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ guild_id: guildId }) })
            .then(res => res.json())
            .then(data => {
                alert("✅ تم تفعيل الاشتراك بنجاح!");
                window.location.href = "https://discord.com/oauth2/authorize?client_id={{ client_id }}&scope=bot%20applications.commands&permissions=8&guild_id=" + guildId;
            });
        }
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    bot_avatar = bot.user.display_avatar.url if bot.user else "https://cdn.discordapp.com/embed/avatars/0.png"
    user = session.get("user")
    owned_guilds = session.get("owned_guilds", [])
    return render_template_string(HTML_TEMPLATE, bot_avatar=bot_avatar, user=user, owned_guilds=owned_guilds, oauth_url=OAUTH2_URL, client_id=DISCORD_CLIENT_ID)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code: return redirect("/")
    data = {'client_id': DISCORD_CLIENT_ID, 'client_secret': DISCORD_CLIENT_SECRET, 'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI}
    r = requests.post('https://discord.com/api/v10/oauth2/token', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    if r.status_code != 200: return f"خطأ من ديسكورد: {r.text}", 400
    token_json = r.json()
    access_token = token_json.get('access_token')
    if access_token:
        headers = {'Authorization': f'Bearer {access_token}'}
        session['user'] = requests.get('https://discord.com/api/v10/users/@me', headers=headers).json()
        guilds = requests.get('https://discord.com/api/v10/users/@me/guilds', headers=headers).json()
        if isinstance(guilds, list):
            session['owned_guilds'] = [g for g in guilds if g.get('owner') == True]
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/api/activate", methods=["POST"])
def api_activate():
    data = request.json or {}
    guild_id = data.get("guild_id")
    if not guild_id: return jsonify({"error": "Missing guild_id"}), 400
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO guild_settings (guild_id, is_premium) VALUES (?, 1)", (str(guild_id),))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

def run_bot():
    token = os.environ.get("DISCORD_TOKEN")
    if token: bot.run(token)
    else: print("❌ Error: DISCORD_TOKEN not found!")

bot_thread = threading.Thread(target=run_bot)
bot_thread.daemon = True
bot_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))