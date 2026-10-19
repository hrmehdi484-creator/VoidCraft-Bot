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
from flask import Flask, jsonify, request

# ==================== إعداد قاعدة البيانات الدائمة (SQLite) ====================

DB_FILE = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    xp INTEGER DEFAULT 0,
                    balance INTEGER DEFAULT 100
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS guild_settings (
                    guild_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'en',
                    is_premium INTEGER DEFAULT 0,
                    expiry_date TEXT
                )''')
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
    c.execute("SELECT language FROM guild_settings WHERE guild_id = ?", (guild_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return "en"
    conn.close()
    return row[0]

def set_server_lang(guild_id, lang):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO guild_settings (guild_id, language) VALUES (?, ?)", (guild_id, lang))
    conn.commit()
    conn.close()

# ==================== الإعدادات الأساسية للبوت ====================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command('help')

last_daily = defaultdict(float)
last_message_time = defaultdict(float)
last_message_content = defaultdict(str)
user_spam_count = defaultdict(int)
user_warnings = defaultdict(list)
user_violations = defaultdict(lambda: {'suspicious_count': 0, 'link_count': 0, 'last_time': 0.0})

# 🛡️ آيدي حساب الأونر الخاص بك (جون)
OWNER_IDS = [1335193543660273716]

# 🔗 رابط سيرفر ديسكورد المستثنى من الحذف
MY_SERVER_INVITE = "discord.gg/voidcraft"

ALLOWED_PLATFORMS = [
    "youtube.com", "youtu.be", 
    "tiktok.com", 
    "instagram.com", 
    "snapchat.com", 
    "facebook.com", "fb.watch", 
    "twitch.tv", 
    "twitter.com", "x.com"
]

DANGEROUS_EXTENSIONS = [
    '.exe', '.scr', '.bat', '.cmd', '.vbs', '.js', '.jse', '.wsf', '.wsh',
    '.ps1', '.msi', '.com', '.pif', '.reg', '.dll', '.iso', '.dmg',
    '.apk', '.zip', '.rar', '.7z', '.tar', '.gz'
]

# ==================== قاموس الترجمة العالمي لكافة اللغات ====================

TRANSLATIONS = {
    "en": {
        "staff_only": "❌ Error: Restricted to server staff only!",
        "owner_only": "❌ Error: Restricted to Bot Owner / Server Owner ONLY!",
        "admin_channel_err": "❌ SECURITY ALERT: Staff commands CANNOT be used in public channels! Incident logged.",
        "log_title": "🚨 [Punishment Log - {type}]",
        "target": "👤 Target Member",
        "executor": "🛡️ Executor",
        "duration": "⏱️ Duration",
        "reason": "📜 Reason",
        "help_title": "🤖 Member Command Panel - VoidCraft",
        "admin_help_title": "🛠️ Staff Command Panel - VoidCraft",
        "owner_help_title": "👑 Ultimate Owner VIP Command Panel - VoidCraft",
        "sec_title": "🛡️ Security & Auto-Protection Systems",
        "mod_title": "🔨 Moderation & Punishments System",
        "ctrl_title": "⚙️ Channel & Server Control",
        "setup_title": "🎫 Setup, Tickets & Giveaways",
        "lang_changed": "🌐 Server language successfully set to: **{lang}**",
        "warn_removed": "✅ Removed warning index **{index}** from {member}.",
        "warn_cleared": "🧹 Cleared all warnings for {member}."
    },
    "ar": {
        "staff_only": "❌ عذراً، هذا الأمر مخصص للإدارة فقط!",
        "owner_only": "❌ عذراً، هذا الأمر مخصص حصرياً لأونر البوت / مالك السيرفر فقط!",
        "admin_channel_err": "❌ تنبيه أمني: يمنع استخدام أوامر الإدارة في القنوات العامة! تم توثيق المحاولة.",
        "log_title": "🚨 [سجل عقوبة - {type}]",
        "target": "👤 العضو المُعاقَب",
        "executor": "🛡️ المنفذ",
        "duration": "⏱️ المدة",
        "reason": "📜 السبب",
        "help_title": "🤖 لوحة أوامر الأعضاء - VoidCraft",
        "admin_help_title": "🛠️ لوحة أوامر الإدارة - VoidCraft",
        "owner_help_title": "👑 لوحة أوامر الأونر الVIP الفاخرة - VoidCraft",
        "sec_title": "🛡️ أنظمة الأمان والحماية التلقائية",
        "mod_title": "🔨 نظام العقوبات وإدارة الأعضاء",
        "ctrl_title": "⚙️ التحكم بالقنوات والسيرفر",
        "setup_title": "🎫 الإعدادات والمسابقات والتكتات",
        "lang_changed": "🌐 تم تغيير لغة السيرفر بنجاح إلى: **{lang}**",
        "warn_removed": "✅ تم حذف التحذير رقم **{index}** من العضو {member}.",
        "warn_cleared": "🧹 تم مسح جميع التحذيرات المسجلة بحق العضو {member}."
    }
}

def get_text(guild_id, key, **kwargs):
    lang = get_server_lang(guild_id) if guild_id else "en"
    if lang not in TRANSLATIONS: lang = "en"
    text = TRANSLATIONS[lang].get(key, TRANSLATIONS["en"].get(key, key))
    return text.format(**kwargs)

# ==================== دالة إرسال سجل العقوبات ====================

async def send_punishment_log(guild, member, executor, punishment_type, reason, duration="Permanent"):
    ban_channel = (discord.utils.get(guild.text_channels, name="ban") or 
                   discord.utils.get(guild.text_channels, name="البان") or 
                   discord.utils.get(guild.text_channels, name="bans"))

    logs_channel = (discord.utils.get(guild.text_channels, name="logs") or 
                    discord.utils.get(guild.text_channels, name="سجل-المراقبة"))

    color_map = {
        "MUTE 🔇": discord.Color.orange(),
        "KICK 👢": discord.Color.gold(),
        "BAN 🔨": discord.Color.red(),
        "WARN ⚠️": discord.Color.yellow(),
        "UNMUTE 🔊": discord.Color.green(),
        "UNBAN 🔓": discord.Color.blue(),
        "REMOVE_WARN 🧹": discord.Color.teal(),
        "SECURITY 🚨": discord.Color.dark_red()
    }

    embed = discord.Embed(
        title=get_text(guild.id, "log_title", type=punishment_type),
        color=color_map.get(punishment_type, discord.Color.dark_gray()),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name=get_text(guild.id, "target"), value=f"{member.mention} (`{member.id}`)", inline=True)
    embed.add_field(name=get_text(guild.id, "executor"), value=f"{executor.mention if hasattr(executor, 'mention') else executor}", inline=True)
    embed.add_field(name=get_text(guild.id, "duration"), value=f"**{duration}**", inline=True)
    embed.add_field(name=get_text(guild.id, "reason"), value=f"`{reason}`", inline=False)
    if hasattr(member, 'avatar') and member.avatar:
        embed.set_thumbnail(url=member.avatar.url)

    if ban_channel:
        try: await ban_channel.send(embed=embed)
        except Exception as e: print(f"Error ban log: {e}")

    if logs_channel and logs_channel != ban_channel:
        try: await logs_channel.send(embed=embed)
        except Exception as e: print(f"Error audit log: {e}")

# ==================== أحداث البوت المباشرة ====================

@bot.event
async def on_ready():
    print(f"✅ Logged in successfully as: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🚀 Synced {len(synced)} slash commands globally.")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

@bot.event
async def on_message_delete(message):
    if message.author.bot or message.guild is None: return
    logs_channel = discord.utils.get(message.guild.text_channels, name="logs")
    if logs_channel:
        embed = discord.Embed(title="🗑️ Message Deleted", color=discord.Color.red(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Author", value=message.author.mention, inline=True)
        embed.add_field(name="Channel", value=message.channel.mention, inline=True)
        embed.add_field(name="Content", value=message.content or "[Attachment]", inline=False)
        await logs_channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.guild is None or before.content == after.content: return
    logs_channel = discord.utils.get(before.guild.text_channels, name="logs")
    if logs_channel:
        embed = discord.Embed(title="✏️ Message Edited", color=discord.Color.blue(), timestamp=discord.utils.utcnow())
        embed.add_field(name="Author", value=before.author.mention, inline=True)
        embed.add_field(name="Channel", value=before.channel.mention, inline=True)
        embed.add_field(name="Before", value=before.content or "None", inline=False)
        embed.add_field(name="After", value=after.content or "None", inline=False)
        await logs_channel.send(embed=embed)

# ==================== التحقق من قنوات الإدارة والتحصين ====================

def is_staff_channel(channel):
    name = channel.name.lower()
    return any(keyword in name for keyword in ["admin", "staff", "console", "owner", "ادارة", "الإدارة", "cmd"])

async def check_admin_channel(interaction: discord.Interaction):
    if interaction.user.id in OWNER_IDS: return True
    
    if not is_staff_channel(interaction.channel):
        logs_channel = (discord.utils.get(interaction.guild.text_channels, name="logs") or 
                        discord.utils.get(interaction.guild.text_channels, name="سجل-المراقبة"))
        if logs_channel:
            embed = discord.Embed(
                title="🚨 [SECURITY VIOLATION - Public Channel Command Usage]", 
                description=f"⚠️ **Staff member attempted to run an admin command in a public channel!**",
                color=discord.Color.dark_red(), 
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Violator", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
            embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
            embed.add_field(name="Command", value=f"`/{interaction.command.name}`", inline=False)
            await logs_channel.send(embed=embed)
        
        await interaction.response.send_message(get_text(interaction.guild.id, "admin_channel_err"), ephemeral=True)
        return False
    return True

# ==================== 🪙 نظام الاقتصاد والمالية الحلال ====================

@bot.tree.command(name="daily", description="Claim your daily interactive coins reward")
async def daily(interaction: discord.Interaction):
    user_id = interaction.user.id
    current_time = time.time()
    
    if current_time - last_daily[user_id] < 86400:
        remaining = int(86400 - (current_time - last_daily[user_id]))
        hours, mins = remaining // 3600, (remaining % 3600) // 60
        return await interaction.response.send_message(f"⌛ You already claimed your daily reward! Wait **{hours}h {mins}m**.", ephemeral=True)
    
    reward = random.randint(200, 500)
    xp, bal = get_user_data(user_id)
    update_user_data(user_id, balance=bal + reward)
    last_daily[user_id] = current_time
    await interaction.response.send_message(f"🎁 You claimed your daily interaction reward of **{reward} coins**! Balance: **{bal + reward}**.")

@bot.tree.command(name="balance", description="Check your or another member's balance")
@app_commands.describe(member="Target member")
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    _, coins = get_user_data(target.id)
    await interaction.response.send_message(f"🪙 **{target.name}** has **{coins} coins**.", ephemeral=True)

@bot.tree.command(name="pay", description="Gift coins to another member")
@app_commands.describe(member="Target member", amount="Amount to send")
async def pay(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0:
        return await interaction.response.send_message("❌ Amount must be greater than 0!", ephemeral=True)
    _, sender_bal = get_user_data(interaction.user.id)
    if sender_bal < amount:
        return await interaction.response.send_message("❌ You don't have enough coins!", ephemeral=True)
    
    update_user_data(interaction.user.id, balance=sender_bal - amount)
    _, target_bal = get_user_data(member.id)
    update_user_data(member.id, balance=target_bal + amount)
    await interaction.response.send_message(f"💸 Successfully gifted **{amount} coins** to {member.mention}!")

# ==================== 🎲 نظام ألعاب التحدي الثقافية الحلال ====================

QUIZ_QUESTIONS = [
    {"q": "What is the capital of Saudi Arabia?", "a": "Riyadh"},
    {"q": "Which planet is known as the Red Planet?", "a": "Mars"},
    {"q": "What is the hardest natural substance on Earth?", "a": "Diamond"},
    {"q": "Which gas do plants absorb from the atmosphere?", "a": "Carbon Dioxide"}
]

@bot.tree.command(name="quiz", description="Play a quick trivia question game for fun")
async def quiz(interaction: discord.Interaction):
    item = random.choice(QUIZ_QUESTIONS)
    embed = discord.Embed(title="🧠 Trivia Quiz Game", description=f"**Question:** {item['q']}\n\n*Type your answer in the chat within 15 seconds!*", color=discord.Color.teal())
    await interaction.response.send_message(embed=embed)

    def check(m):
        return m.channel == interaction.channel and m.content.lower() == item['a'].lower()

    try:
        msg = await bot.wait_for('message', timeout=15.0, check=check)
        await interaction.channel.send(f"🎉 Correct answer {msg.author.mention}! The answer was **{item['a']}**.")
    except asyncio.TimeoutError:
        await interaction.channel.send(f"⏱️ Time's up! The correct answer was **{item['a']}**.")

@bot.tree.command(name="roll", description="Roll a dice for fun (1-6)")
async def roll(interaction: discord.Interaction):
    dice_result = random.randint(1, 6)
    await interaction.response.send_message(f"🎲 You rolled a **{dice_result}**!")

# ==================== 🧹 أوامر التنظيف المتقدمة ====================

@bot.tree.command(name="clear_bots", description="Purge messages sent by bots only")
@app_commands.describe(amount="Number of messages to scan (1-100)")
async def clear_bots(interaction: discord.Interaction, amount: int = 20):
    if not interaction.user.guild_permissions.manage_messages and interaction.user.id not in OWNER_IDS:
        return await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
    if not await check_admin_channel(interaction): return

    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=min(amount, 100), check=lambda m: m.author.bot)
    await interaction.followup.send(f"🧹 Cleared **{len(deleted)}** bot messages.", ephemeral=True)

@bot.tree.command(name="clear_user", description="Purge messages sent by a specific user")
@app_commands.describe(member="Target member", amount="Number of messages to scan")
async def clear_user(interaction: discord.Interaction, member: discord.Member, amount: int = 20):
    if not interaction.user.guild_permissions.manage_messages and interaction.user.id not in OWNER_IDS:
        return await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
    if not await check_admin_channel(interaction): return

    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=min(amount, 100), check=lambda m: m.author == member)
    await interaction.followup.send(f"🧹 Cleared **{len(deleted)}** messages from {member.mention}.", ephemeral=True)

# ==================== 👑 لوحة الأونر الشاملة لكل أوامر البوت ====================

@bot.tree.command(name="ownerhelp", description="Full Master Control Panel for Bot Owner (All Commands Included)")
async def ownerhelp(interaction: discord.Interaction):
    # 🔒 التحقق المشدد: مخصص حصرياً لأونر البوت أو مالك السيرفر
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)

    embed = discord.Embed(
        title="👑 Master Owner Control Panel - VoidCraft",
        description="جميع أوامر البوت والسيرفر المتاحة تحت تصرفك الكامل في مكان واحد:",
        color=discord.Color.gold()
    )
    
    # 👑 1. قسم إدارة الأدوار والصلاحيات (Role Management)
    roles_cmd = (
        "• `/giverole [member] [role]` - منح رتبة لعضو معّين\n"
        "• `/removerole [member] [role]` - سحب رتبة من عضو معّين\n"
        "• `/roleall [role]` - منح رتبة لجميع أعضاء السيرفر دفعة واحدة"
    )
    embed.add_field(name="🎭 1. إدارة الرتب والأدوار", value=roles_cmd, inline=False)

    # 🛠️ 2. قسم التحكم بالقنوات والتطهير (Channel Control & Purge)
    channels_cmd = (
        "• `/nuke` - نسخ القناة وإعادة إنشائها لمسح كل الرسائل بلمسة واحدة\n"
        "• `/createchannel [name] [is_voice]` - إنشاء قناة نصية أو صوتية فوراً\n"
        "• `/deletechannel [channel]` - حذف القناة المحددة فوراً\n"
        "• `/lock` / `/unlock` - قفل أو فتح الكتابة في القناة الحالية\n"
        "• `/slowmode [seconds]` - ضبط وتحديد زمن الوضع البطئ بالثواني\n"
        "• `/clear [amount]` - مسح عدد محدد من الرسائل (1-100)\n"
        "• `/clear_bots [amount]` - تنظيف ومسح رسائل البوتات فقط\n"
        "• `/clear_user [member] [amount]` - مسح رسائل عضو محدد فقط"
    )
    embed.add_field(name="🛠️ 2. التحكم بالقنوات والتنظيف الشامل", value=channels_cmd, inline=False)

    # 🔨 3. قسم العقوبات والإدارة (Moderation & Punishments)
    mod_cmd = (
        "• `/mute [member] [minutes] [reason]` - إسكات عضو لمدة محددة بالدقائق\n"
        "• `/unmute [member]` - فك الإسكات والكتم عن العضو\n"
        "• `/kick [member] [reason]` - طرد عضو خارج السيرفر\n"
        "• `/ban [member] [reason]` - حظر عضو نهائياً من السيرفر\n"
        "• `/unban [user_id]` - فك الحظر عن آيدي حساب محدد\n"
        "• `/warn [member] [reason]` - إعطاء تحذير مسجل بحق عضو\n"
        "• `/infractions [member]` - عرض سجل التحذيرات والمخالفات المسجلة"
    )
    embed.add_field(name="🔨 3. إدارة العقوبات والأعضاء", value=mod_cmd, inline=False)

    # 🎙️ 4. قسم التحكم بالرومات الصوتية (Voice Control System)
    voice_cmd = (
        "• `/vmute [member]` - كتم صوت عضو داخل الرومات الصوتية\n"
        "• `/vunmute [member]` - فك الكتم الصوتي عن العضو\n"
        "• `/vkick [member]` - إخراج وطرد عضو من القناة الصوتية"
    )
    embed.add_field(name="🎙️ 4. التحكم الصوتي (Voice)", value=voice_cmd, inline=False)

    # 📢 5. قسم البرودكاست والإعدادات والتعديل (Broadcast & Settings)
    broad_cmd = (
        "• `/embed [title] [description]` - إرسال برودكاست مظلل ومصمم (Embed)\n"
        "• `/say [message]` - جعل البوت يتحدث ويكتب باسمه في الشات\n"
        "• `/nick [member] [nickname]` - تغيير اسم/لقب أي عضو داخل السيرفر\n"
        "• `/setlanguage` - تغيير لغة السيرفر والبوت بقائمة منسدلة"
    )
    embed.add_field(name="📢 5. الإعلانات والتعديل واللغة", value=broad_cmd, inline=False)

    # 🎫 6. قسم الأنظمة التفاعلية والمسابقات (Tickets & Giveaways)
    setup_cmd = (
        "• `/setup_tickets` - نشر لوحة الدعم الفني والتكتات التفاعلية\n"
        "• `/giveaway [prize] [duration]` - بدء مسابقة وسحب تفاعلي مع مؤقت"
    )
    embed.add_field(name="🎫 6. التكتات والمسابقات التلقائية", value=setup_cmd, inline=False)

    # 🪙 7. قسم الاقتصاد والألعاب والمعلومات العامة (Economy, Fun & Stats)
    general_cmd = (
        "• `/level [member]` - فحص مستوى العضو ونقاط خبرته (XP)\n"
        "• `/daily` - استلام المكافأة اليومية المجانية\n"
        "• `/balance [member]` - فحص الرصيد المالي للحساب\n"
        "• `/pay [member] [amount]` - تحويل وإهداء الأموال بين الأعضاء\n"
        "• `/quiz` / `/roll` - ألعاب مسابقات ثنائية وتسلية حلال\n"
        "• `/userinfo` / `/avatar` - عرض معلومات البروفايل والصورة الشخصية\n"
        "• `/serverinfo` / `/botinfo` / `/ping` - عرض إحصائيات السيرفر والبوت وسرعة الاتصال"
    )
    embed.add_field(name="🌐 7. الاقتصاد، التسلية، والإحصائيات العامة", value=general_cmd, inline=False)

    embed.set_footer(text="VoidCraft Master Control Panel • Reserved for Owner Only")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== أوامر الأونر الـ VIP الفردية ====================

@bot.tree.command(name="giverole", description="Give role to member (Owner Only)")
@app_commands.describe(member="Member", role="Role")
async def giverole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await member.add_roles(role)
    await interaction.response.send_message(f"✅ Added {role.mention} to {member.mention}.")

@bot.tree.command(name="removerole", description="Remove role from member (Owner Only)")
@app_commands.describe(member="Member", role="Role")
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await member.remove_roles(role)
    await interaction.response.send_message(f"✅ Removed {role.mention} from {member.mention}.")

@bot.tree.command(name="roleall", description="Assign role to ALL members (Owner Only)")
@app_commands.describe(role="Role")
async def roleall(interaction: discord.Interaction, role: discord.Role):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await interaction.response.send_message("⏳ Assigning role to all members, please wait...")
    for member in interaction.guild.members:
        try: await member.add_roles(role)
        except: pass
    await interaction.followup.send(f"✅ Successfully added {role.mention} to all members!")

@bot.tree.command(name="nuke", description="Clone and clear channel history (Owner Only)")
async def nuke(interaction: discord.Interaction):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    channel = interaction.channel
    pos = channel.position
    new_channel = await channel.clone(reason="Nuke channel")
    await channel.delete()
    await new_channel.edit(position=pos)
    await new_channel.send("💥 Channel has been Nuked!")

@bot.tree.command(name="createchannel", description="Create new channel (Owner Only)")
@app_commands.describe(name="Channel name", is_voice="Is Voice channel?")
async def createchannel(interaction: discord.Interaction, name: str, is_voice: bool = False):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    if is_voice: c = await interaction.guild.create_voice_channel(name)
    else: c = await interaction.guild.create_text_channel(name)
    await interaction.response.send_message(f"✅ Created channel {c.mention}.")

@bot.tree.command(name="deletechannel", description="Delete a channel (Owner Only)")
@app_commands.describe(channel="Target channel")
async def deletechannel(interaction: discord.Interaction, channel: discord.abc.GuildChannel):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await channel.delete()
    await interaction.response.send_message(f"✅ Channel deleted.")

@bot.tree.command(name="vmute", description="Voice Mute member (Owner Only)")
@app_commands.describe(member="Member")
async def vmute(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    if member.voice:
        await member.edit(mute=True)
        await interaction.response.send_message(f"🔇 Voice muted {member.mention}.")
    else: await interaction.response.send_message("❌ Member is not in a voice channel!", ephemeral=True)

@bot.tree.command(name="vunmute", description="Voice Unmute member (Owner Only)")
@app_commands.describe(member="Member")
async def vunmute(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    if member.voice:
        await member.edit(mute=False)
        await interaction.response.send_message(f"🔊 Voice unmuted {member.mention}.")
    else: await interaction.response.send_message("❌ Member is not in a voice channel!", ephemeral=True)

@bot.tree.command(name="vkick", description="Kick member from voice (Owner Only)")
@app_commands.describe(member="Member")
async def vkick(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    if member.voice:
        await member.move_to(None)
        await interaction.response.send_message(f"👢 Kicked {member.mention} from voice channel.")
    else: await interaction.response.send_message("❌ Member is not in a voice channel!", ephemeral=True)

@bot.tree.command(name="embed", description="Send rich custom embed broadcast (Owner Only)")
@app_commands.describe(title="Title", description="Description")
async def embed_cmd(interaction: discord.Interaction, title: str, description: str):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    emb = discord.Embed(title=title, description=description, color=discord.Color.blue())
    await interaction.channel.send(embed=emb)
    await interaction.response.send_message("✅ Broadcast sent!", ephemeral=True)

@bot.tree.command(name="say", description="Make bot talk in channel (Owner Only)")
@app_commands.describe(message="Message content")
async def say(interaction: discord.Interaction, message: str):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await interaction.channel.send(message)
    await interaction.response.send_message("✅ Sent!", ephemeral=True)

@bot.tree.command(name="nick", description="Change member nickname (Owner Only)")
@app_commands.describe(member="Member", nickname="New Nickname")
async def nick(interaction: discord.Interaction, member: discord.Member, nickname: str):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await member.edit(nick=nickname)
    await interaction.response.send_message(f"✅ Changed nickname for {member.mention} to `{nickname}`.")

# ==================== أمر إعداد اللغة ====================

@bot.tree.command(name="setlanguage", description="Change bot language for this server (Owner Only)")
@app_commands.choices(language_code=[
    app_commands.Choice(name="🇺🇸 English", value="en"),
    app_commands.Choice(name="🇸🇦 العربية", value="ar")
])
async def setlanguage(interaction: discord.Interaction, language_code: app_commands.Choice[str]):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
        return
    
    code = language_code.value
    set_server_lang(interaction.guild.id, code)
    await interaction.response.send_message(get_text(interaction.guild.id, "lang_changed", lang=language_code.name))

# ==================== أوامر المساعدة العامة والأدمن ====================

@bot.tree.command(name="help", description="General member command list")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title=get_text(interaction.guild.id, "help_title"), color=discord.Color.blurple())
    embed.add_field(name="📊 `/level`", value="Check level & XP stats.", inline=False)
    embed.add_field(name="💰 `/daily` / `/balance` / `/pay`", value="Interactive reward & gifting tools.", inline=False)
    embed.add_field(name="🧠 `/quiz` / `/roll`", value="Fun & trivia quiz games.", inline=False)
    embed.add_field(name="👤 `/userinfo` / `/avatar`", value="Account info & profile photo.", inline=False)
    embed.add_field(name="🏰 `/serverinfo` / `/botinfo` / `/ping`", value="Ecosystem stats.", inline=False)
    embed.set_footer(text="VoidCraft Ecosystem - Global Edition")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="adminhelp", description="Complete staff command list (Staff Channels Only)")
async def adminhelp(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return

    embed = discord.Embed(title=get_text(interaction.guild.id, "admin_help_title"), color=discord.Color.dark_red())
    
    mod_text = (
        "🔇 `/mute` / `unmute` - Timeout & remove timeout\n"
        "👢 `/kick` / `ban` / `unban` - Kick, ban & unban user\n"
        "⚠️ `/warn` / `remove_warning` / `clear_warnings` - Warning system\n"
        "📋 `/infractions` - View warning logs\n"
        "🧹 `/clear` / `clear_bots` / `clear_user` - Purge chat messages"
    )
    embed.add_field(name=get_text(interaction.guild.id, "mod_title"), value=mod_text, inline=False)

    sec_text = (
        "⚡ **Anti-Exe / Anti-Malware:** Auto-mutes & kicks suspicious file uploads\n"
        "⚡ **Anti-Discord Invite:** Auto-mutes external Discord server invite spam\n"
        "⚡ **Anti-Spam:** Auto-mutes repeated fast messaging\n"
        "⚡ **Public Channel Shield:** Auto-logs staff command usage in public channels"
    )
    embed.add_field(name=get_text(interaction.guild.id, "sec_title"), value=sec_text, inline=False)

    embed.set_footer(text="VoidCraft Ecosystem - Staff Edition")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== أوامر الإدارة والعقوبات بالتفصيل ====================

@bot.tree.command(name="mute", description="Timeout member")
@app_commands.describe(member="Target", minutes="Minutes", reason="Reason (Required)")
async def slash_mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return
    if minutes <= 0: return await interaction.response.send_message("❌ Invalid duration!", ephemeral=True)

    try:
        await member.timeout(timedelta(minutes=minutes), reason=reason)
        await interaction.response.send_message(f"🔇 Muted {member.mention} for **{minutes}** mins. Reason: `{reason}`")
        await send_punishment_log(interaction.guild, member, interaction.user, "MUTE 🔇", reason, f"{minutes} mins")
    except Exception as e: await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="unmute", description="Unmute member")
@app_commands.describe(member="Target")
async def slash_unmute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return
    try:
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 Unmuted {member.mention}.")
        await send_punishment_log(interaction.guild, member, interaction.user, "UNMUTE 🔊", "Unmuted", "None")
    except Exception as e: await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="kick", description="Kick member")
@app_commands.describe(member="Target", reason="Reason (Required)")
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not interaction.user.guild_permissions.kick_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return
    try:
        await send_punishment_log(interaction.guild, member, interaction.user, "KICK 👢", reason, "Kicked")
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 Kicked {member.mention}. Reason: `{reason}`")
    except Exception as e: await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="Ban member")
@app_commands.describe(member="Target", reason="Reason (Required)")
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not interaction.user.guild_permissions.ban_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return
    try:
        await send_punishment_log(interaction.guild, member, interaction.user, "BAN 🔨", reason, "Permanent")
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 Banned {member.mention}. Reason: `{reason}`")
    except Exception as e: await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="unban", description="Unban ID")
@app_commands.describe(user_id="User ID")
async def slash_unban(interaction: discord.Interaction, user_id: str):
    if not interaction.user.guild_permissions.ban_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"🔓 Unbanned **{user.name}**.")
        await send_punishment_log(interaction.guild, user, interaction.user, "UNBAN 🔓", "Unbanned", "None")
    except Exception as e: await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="clear", description="Clear chat")
@app_commands.describe(amount="Messages (1-100)")
async def slash_clear(interaction: discord.Interaction, amount: int = 10):
    if not interaction.user.guild_permissions.manage_messages and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return
    amount = min(amount, 100)
    try:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 Cleared **{len(deleted)}** messages.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="warn", description="Warn member")
@app_commands.describe(member="Target", reason="Reason (Required)")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return
    user_warnings[member.id].append(reason)
    await interaction.response.send_message(f"⚠️ Warned {member.mention}. Reason: `{reason}`")
    await send_punishment_log(interaction.guild, member, interaction.user, "WARN ⚠️", reason, f"Warn #{len(user_warnings[member.id])}")

@bot.tree.command(name="infractions", description="Check warnings")
@app_commands.describe(member="Target")
async def infractions(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return
    data, warns = user_violations[member.id], user_warnings[member.id]
    embed = discord.Embed(title=f"📋 Infractions for {member.name}", color=discord.Color.dark_purple())
    embed.add_field(name="Warnings", value=f"**{len(warns)}**", inline=True)
    embed.add_field(name="Suspicious Files", value=f"**{data['suspicious_count']}**", inline=True)
    embed.add_field(name="External Links", value=f"**{data['link_count']}**", inline=True)
    if warns:
        embed.add_field(name="Warning Details", value="\n".join([f"`#{i+1}` - {w}" for i, w in enumerate(warns)]), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="lock", description="Lock channel (Owner Only)")
async def lock(interaction: discord.Interaction):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 Channel locked.")

@bot.tree.command(name="unlock", description="Unlock channel (Owner Only)")
async def unlock(interaction: discord.Interaction):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 Channel unlocked.")

@bot.tree.command(name="slowmode", description="Slowmode (Owner Only)")
@app_commands.describe(seconds="Seconds")
async def slowmode(interaction: discord.Interaction, seconds: int):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"⏱️ Slowmode set to {seconds}s.")

# ==================== نظام التكتات والترحيب المتكامل ====================

class ConfirmCloseView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="confirm_close_btn")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild, channel = interaction.guild, interaction.channel
        embed = discord.Embed(title=f"🔒 Ticket Closed by {interaction.user.name}", color=discord.Color.gold())
        for target, overwrite in channel.overwrites.items():
            if target != guild.me and isinstance(target, discord.Member):
                overwrite.view_channel = False
                await channel.set_permissions(target, overwrite=overwrite)
        await interaction.response.edit_message(content="🔒 Ticket closed.", embed=embed, view=TicketControlView())

class TicketControlView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, custom_id="transcript_btn", emoji="📄")
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        messages = [f"{msg.author}: {msg.content}" async for msg in interaction.channel.history(limit=200, oldest_first=True)]
        file = discord.File(io.BytesIO("\n".join(messages).encode('utf-8')), filename="transcript.txt")
        await interaction.followup.send("📄 Transcript file:", file=file, ephemeral=True)
    @discord.ui.button(label="Reopen", style=discord.ButtonStyle.success, custom_id="reopen_btn", emoji="🔓")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        for target, overwrite in interaction.channel.overwrites.items():
            if isinstance(target, discord.Member):
                overwrite.view_channel = True
                await interaction.channel.set_permissions(target, overwrite=overwrite)
        await interaction.response.send_message("🔓 Ticket reopened.")
    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="delete_btn", emoji="⛔")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⛔ Deleting ticket...")
        await interaction.channel.delete()

class CloseButtonView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="initial_close_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Are you sure?", view=ConfirmCloseView(), ephemeral=True)

class TicketModal(discord.ui.Modal, title="Support Ticket"):
    minecraft_name = discord.ui.TextInput(label="Minecraft IGN", placeholder="Your ingame name...", required=True, max_length=50)
    problem_desc = discord.ui.TextInput(label="Issue Description", placeholder="Describe your issue...", style=discord.TextStyle.paragraph, required=True, max_length=500)
    async def on_submit(self, interaction: discord.Interaction):
        guild, member = interaction.guild, interaction.user
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        category = discord.utils.get(guild.categories, name="TICKETS") or await guild.create_category("TICKETS")
        ticket_channel = await guild.create_text_channel(f"ticket-{member.name}", overwrites=overwrites, category=category)
        embed = discord.Embed(title="🎟️ New Support Ticket", color=discord.Color.green())
        embed.add_field(name="Minecraft IGN", value=self.minecraft_name.value, inline=False)
        embed.add_field(name="Issue", value=self.problem_desc.value, inline=False)
        await ticket_channel.send(content=f"{member.mention}", embed=embed, view=CloseButtonView())
        await interaction.response.send_message(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)

class TicketButtonView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket_btn", emoji="📩")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal())

@bot.tree.command(name="setup_tickets", description="Setup tickets panel (Owner Only)")
async def setup_tickets(interaction: discord.Interaction):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
        return
    embed = discord.Embed(title="🎫 VoidCraft Support", description="Click below to open a ticket.", color=discord.Color.blurple())
    await interaction.channel.send(embed=embed, view=TicketButtonView())
    await interaction.response.send_message("✅ Panel sent.", ephemeral=True)

# ==================== نظام المسابقات والسحوبات (Giveaways) ====================

class GiveawayView(discord.ui.View):
    def __init__(self, prize):
        super().__init__(timeout=None)
        self.prize = prize
        self.participants = set()

    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success, custom_id="enter_giveaway_btn")
    async def enter_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            await interaction.response.send_message("❌ You have already entered this giveaway!", ephemeral=True)
        else:
            self.participants.add(interaction.user.id)
            await interaction.response.send_message(f"🎉 You successfully entered the giveaway for **{self.prize}**!", ephemeral=True)

@bot.tree.command(name="giveaway", description="Start an automated giveaway (Owner Only)")
@app_commands.describe(prize="Prize name", duration_minutes="Duration in minutes")
async def giveaway(interaction: discord.Interaction, prize: str, duration_minutes: int):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
        return

    embed = discord.Embed(
        title="🎁 GIVEAWAY STARTED!",
        description=f"Prize: **{prize}**\nDuration: **{duration_minutes}** minutes\nHosted by: {interaction.user.mention}\n\nClick the button below to join!",
        color=discord.Color.gold()
    )
    view = GiveawayView(prize)
    await interaction.response.send_message(embed=embed, view=view)
    
    await asyncio.sleep(duration_minutes * 60)
    
    if view.participants:
        winner_id = random.choice(list(view.participants))
        winner = interaction.guild.get_member(winner_id)
        await interaction.channel.send(f"🎉 Congratulations {winner.mention}! You won **{prize}**!")
    else:
        await interaction.channel.send(f"🎁 Giveaway for **{prize}** ended. No participants joined.")

# ==================== الأوامر العامة الإضافية والمعلومات ====================

@bot.tree.command(name="ping", description="Check latency")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    await interaction.response.send_message(f"🏓 Pong! Latency: **{latency}ms**", ephemeral=True)

@bot.tree.command(name="botinfo", description="Bot statistics")
async def botinfo(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 VoidCraft Bot Statistics", color=discord.Color.purple())
    embed.add_field(name="Servers", value=f"**{len(bot.guilds)}**", inline=True)
    embed.add_field(name="Users", value=f"**{sum(g.member_count for g in bot.guilds)}**", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Server statistics")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"🏰 {guild.name}", color=discord.Color.gold())
    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Owner", value=f"{guild.owner.mention}", inline=True)
    embed.add_field(name="Members", value=f"**{guild.member_count}**", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="User info")
@app_commands.describe(member="Target member")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(title=f"👤 {target.name}", color=target.color)
    embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
    embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="User avatar")
@app_commands.describe(member="Target member")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(title=f"🖼️ {target.name}'s Avatar", color=discord.Color.blue())
    embed.set_image(url=target.avatar.url if target.avatar else target.default_avatar.url)
    await interaction.response.send_message(embed=embed)

# ==================== نظام الحماية الشامل والأوتوماتيكي ====================

@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None: return
    if message.author.id in OWNER_IDS or message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    author_id = message.author.id
    current_time = time.time()
    content_lower = message.content.lower()

    user_data = user_violations[author_id]
    if current_time - user_data['last_time'] > 86400:
        user_data['suspicious_count'] = 0
        user_data['link_count'] = 0

    has_dangerous_file = any(any(att.filename.lower().endswith(ext) for ext in DANGEROUS_EXTENSIONS) for att in message.attachments)
    if has_dangerous_file:
        try:
            await message.delete()
            user_data['suspicious_count'] += 1
            user_data['last_time'] = current_time
            mute_mins = 30 + ((user_data['suspicious_count'] - 1) * 60)
            await message.author.timeout(timedelta(minutes=mute_mins), reason="Suspicious file")
            await send_punishment_log(message.guild, message.author, bot.user, "SECURITY 🚨", "Sent malicious file", f"Mute {mute_mins}m + Kick")
            await message.author.kick(reason="Suspicious file")
        except: pass
        return

    is_discord_link = "discord.gg/" in content_lower or "discord.com/invite/" in content_lower
    is_my_server = MY_SERVER_INVITE.lower() in content_lower
    has_any_link = "http://" in content_lower or "https://" in content_lower or "www." in content_lower
    is_allowed = any(p in content_lower for p in ALLOWED_PLATFORMS) or is_my_server

    if is_discord_link and not is_my_server:
        try:
            await message.delete()
            user_data['link_count'] += 1
            user_data['last_time'] = current_time
            mutes = [1, 5, 15, 30, 60]
            mute_m = mutes[min(user_data['link_count'] - 1, len(mutes) - 1)]
            await message.author.timeout(timedelta(minutes=mute_m), reason="Discord invite spam")
            await send_punishment_log(message.guild, message.author, bot.user, "MUTE 🔇", "External Discord invite", f"{mute_m} mins")
        except: pass
        return

    xp, bal = get_user_data(author_id)
    update_user_data(author_id, xp=xp + 10)

    await bot.process_commands(message)

@bot.tree.command(name="level", description="Check current level")
@app_commands.describe(member="Target member")
async def slash_level(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    xp, _ = get_user_data(target.id)
    lvl = xp // 100
    embed = discord.Embed(title=f"📊 Stats for {target.name}", color=discord.Color.blue())
    embed.add_field(name="XP", value=f"**{xp}**", inline=True)
    embed.add_field(name="Level", value=f"**{lvl}**", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== خادم الويب (Flask API للتواصل مع الموقع) ====================

app = Flask(__name__)

@app.route("/")
def home():
    return "VoidCraft Bot & API are running 24/7!"

@app.route("/api/stats", methods=["GET"])
def api_stats():
    return jsonify({
        "servers": len(bot.guilds),
        "users": sum(g.member_count for g in bot.guilds)
    })

@app.route("/api/activate", methods=["POST"])
def api_activate():
    data = request.json
    guild_id = data.get("guild_id")
    if not guild_id:
        return jsonify({"error": "Missing guild_id"}), 400
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE guild_settings SET is_premium = 1 WHERE guild_id = ?", (guild_id,))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": f"Guild {guild_id} activated successfully!"})

def run_bot():
    token = os.environ.get("DISCORD_TOKEN")
    if token: bot.run(token)
    else: print("❌ Error: DISCORD_TOKEN not found!")

bot_thread = threading.Thread(target=run_bot)
bot_thread.daemon = True
bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)