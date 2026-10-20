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

# ==============================================================================
#                      إعداد قاعدة البيانات الدائمة (SQLite)
# ==============================================================================

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

# ==============================================================================
#                       الإعدادات الأساسية للبوت والمتغيرات
# ==============================================================================

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

# 🛡️ آيدي حساب الأونر الرئيسي الخاص بك (جون)
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

# ==============================================================================
#          دالة التحقق الذكية للأونر ومالك السيرفر المشتري تلقائياً
# ==============================================================================

def is_owner_or_guild_owner(interaction: discord.Interaction):
    if interaction.user.id in OWNER_IDS or interaction.user == interaction.guild.owner:
        return True
    return False

# ==============================================================================
#                      قاموس الترجمة الشامل لكافة اللغات
# ==============================================================================

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
        "owner_help_title": "👑 Ultimate Master Owner Control Panel - VoidCraft",
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
        "owner_help_title": "👑 لوحة التحكم الشاملة لمالك السيرفر - VoidCraft",
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

# ==============================================================================
#                       دالة إرسال سجل العقوبات واللوغات
# ==============================================================================

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

# ==============================================================================
#                      أحداث البوت الأساسية وتسجيل الدخول
# ==============================================================================

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
        try: await logs_channel.send(embed=embed)
        except: pass

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
        try: await logs_channel.send(embed=embed)
        except: pass

# ==============================================================================
#                     التحقق من قنوات الإدارة والتحصين الأمني
# ==============================================================================

def is_staff_channel(channel):
    name = channel.name.lower()
    return any(keyword in name for keyword in ["admin", "staff", "console", "owner", "ادارة", "الإدارة", "cmd"])

async def check_admin_channel(interaction: discord.Interaction):
    if is_owner_or_guild_owner(interaction): return True
    
    if not is_staff_channel(interaction.channel):
        logs_channel = (discord.utils.get(interaction.guild.text_channels, name="logs") or 
                        discord.utils.get(interaction.guild.text_channels, name="سجل-المراقبة"))
        if logs_channel:
            embed = discord.Embed(
                title="🚨 [SECURITY VIOLATION - Public Channel Command Usage]", 
                description=f"⚠️ **Staff member attempted to run an admin command in a public channel!**",
                color=discord.Color.dark_red(), timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="Violator", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
            embed.add_field(name="Channel", value=interaction.channel.mention, inline=True)
            embed.add_field(name="Command", value=f"`/{interaction.command.name}`", inline=False)
            try: await logs_channel.send(embed=embed)
            except: pass
        
        await interaction.response.send_message(get_text(interaction.guild.id, "admin_channel_err"), ephemeral=True)
        return False
    return True

# ==============================================================================
#            👑 لوحة التحكم الشاملة (تحتوي على كل أوامر السيرفر في مكان واحد)
# ==============================================================================

@bot.tree.command(name="ownerhelp", description="Master Control Panel: All Bot Commands in One Place")
async def ownerhelp(interaction: discord.Interaction):
    if not is_owner_or_guild_owner(interaction):
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)

    embed = discord.Embed(
        title="👑 VoidCraft Master Control Panel (All-in-One)",
        description="📋 **جميع أوامر البوت والسيرفر مجتمعة هنا لتسهيل التحكم الكامل:**",
        color=discord.Color.gold()
    )
    
    owner_cmds = (
        "• `/giverole [member] [role]` - منح رتبة لعضو\n"
        "• `/removerole [member] [role]` - سحب رتبة من عضو\n"
        "• `/roleall [role]` - منح رتبة لجميع الأعضاء دفعة واحدة"
    )
    embed.add_field(name="👑 1. أدوات الأونر والرتب", value=owner_cmds, inline=False)

    channel_cmds = (
        "• `/nuke` - نسخ القناة ومسح كامل تاريخ الرسائل\n"
        "• `/createchannel [name] [is_voice]` - إنشاء قناة نصية أو صوتية\n"
        "• `/deletechannel [channel]` - حذف قناة معينة فوراً\n"
        "• `/lock` / `/unlock` - قفل أو فتح القناة الحالية\n"
        "• `/slowmode [seconds]` - ضبط الوضع البطئ للقناة\n"
        "• `/clear [amount]` - مسح رسائل الشات (1-100)\n"
        "• `/clear_bots [amount]` - مسح رسائل البوتات فقط\n"
        "• `/clear_user [member] [amount]` - مسح رسائل عضو محدد"
    )
    embed.add_field(name="🛠️ 2. التحكم بالقنوات والتنظيف الشامل", value=channel_cmds, inline=False)

    mod_cmds = (
        "• `/mute [member] [minutes] [reason]` - إسكات وتيم آوت عضو\n"
        "• `/unmute [member]` - فك الكتم عن العضو\n"
        "• `/kick [member] [reason]` - طرد عضو من السيرفر\n"
        "• `/ban [member] [reason]` - حظر عضو نهائياً\n"
        "• `/unban [user_id]` - فك الحظر عن آيدي حساب\n"
        "• `/warn [member] [reason]` - إعطاء تحذير مسجل لعضو\n"
        "• `/infractions [member]` - عرض سجل التحذيرات والمخالفات"
    )
    embed.add_field(name="🔨 3. إدارة العقوبات والتحذيرات", value=mod_cmds, inline=False)

    voice_broadcast = (
        "• `/vmute` / `/vunmute` / `/vkick` - التحكم بالأعضاء في الرومات الصوتية\n"
        "• `/embed [title] [description]` - إرسال برودكاست مظلل (Embed)\n"
        "• `/say [message]` - جعل البوت يتحدث ويكتب باسمه في الشات\n"
        "• `/nick [member] [nickname]` - تغيير اسم/لقب أي عضو\n"
        "• `/setup_tickets` - نشر لوحة الدعم الفني والتكتات\n"
        "• `/giveaway [prize] [duration]` - بدء مسابقة وسحب آلي\n"
        "• `/setlanguage` - تغيير لغة السيرفر والبوت"
    )
    embed.add_field(name="🎙️ 4. الصوت، الفعاليات، والإعدادات", value=voice_broadcast, inline=False)

    member_cmds = (
        "• `/level [member]` - فحص مستوى العضو ونقاط خبرته (XP)\n"
        "• `/daily` - استلام المكافأة اليومية من العملات\n"
        "• `/balance [member]` - فحص الرصيد المالي للحساب\n"
        "• `/pay [member] [amount]` - تحويل وإهداء الأموال للأعضاء\n"
        "• `/quiz` - لعب مسابقة الأسئلة الثقافية التفاعلية\n"
        "• `/roll` - رمي النرد العشوائي (1-6)\n"
        "• `/userinfo` / `/avatar` - عرض معلومات البروفايل والصورة\n"
        "• `/serverinfo` / `/botinfo` / `/ping` - إحصائيات السيرفر والبوت"
    )
    embed.add_field(name="🌐 5. الأعضاء والاقتصاد والتسلية", value=member_cmds, inline=False)

    embed.set_footer(text="VoidCraft Master Suite • Licensed for Server Owner")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==============================================================================
#                       أوامر الاقتصاد والتسلية الحلال
# ==============================================================================

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
@app_commands.describe(member="Target member")
async def balance(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    _, coins = get_user_data(target.id)
    await interaction.response.send_message(f"🪙 **{target.name}** has **{coins} coins**.", ephemeral=True)

@bot.tree.command(name="pay", description="Gift coins")
@app_commands.describe(member="Target member", amount="Amount")
async def pay(interaction: discord.Interaction, member: discord.Member, amount: int):
    if amount <= 0: return await interaction.response.send_message("❌ Invalid amount!", ephemeral=True)
    _, sender_bal = get_user_data(interaction.user.id)
    if sender_bal < amount: return await interaction.response.send_message("❌ Insufficient funds!", ephemeral=True)
    
    update_user_data(interaction.user.id, balance=sender_bal - amount)
    _, target_bal = get_user_data(member.id)
    update_user_data(member.id, balance=target_bal + amount)
    await interaction.response.send_message(f"💸 Gifted **{amount} coins** to {member.mention}!")

QUIZ_QUESTIONS = [
    {"q": "What is the capital of Saudi Arabia?", "a": "Riyadh"},
    {"q": "Which planet is known as the Red Planet?", "a": "Mars"},
    {"q": "What is the hardest natural substance on Earth?", "a": "Diamond"}
]

@bot.tree.command(name="quiz", description="Play trivia quiz game")
async def quiz(interaction: discord.Interaction):
    item = random.choice(QUIZ_QUESTIONS)
    embed = discord.Embed(title="🧠 Trivia Quiz", description=f"**Question:** {item['q']}\n\n*Type answer in 15s!*", color=discord.Color.teal())
    await interaction.response.send_message(embed=embed)
    def check(m): return m.channel == interaction.channel and m.content.lower() == item['a'].lower()
    try:
        msg = await bot.wait_for('message', timeout=15.0, check=check)
        await interaction.channel.send(f"🎉 Correct {msg.author.mention}! Answer: **{item['a']}**.")
    except asyncio.TimeoutError:
        await interaction.channel.send(f"⏱️ Time's up! Answer was **{item['a']}**.")

@bot.tree.command(name="roll", description="Roll a dice (1-6)")
async def roll(interaction: discord.Interaction):
    await interaction.response.send_message(f"🎲 You rolled a **{random.randint(1, 6)}**!")

# ==============================================================================
#                       أوامر الأونر الفردية المتقدمة
# ==============================================================================

@bot.tree.command(name="giverole", description="Give role to member")
async def giverole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await member.add_roles(role)
    await interaction.response.send_message(f"✅ Added {role.mention} to {member.mention}.")

@bot.tree.command(name="removerole", description="Remove role from member")
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await member.remove_roles(role)
    await interaction.response.send_message(f"✅ Removed {role.mention} from {member.mention}.")

@bot.tree.command(name="roleall", description="Assign role to ALL members")
async def roleall(interaction: discord.Interaction, role: discord.Role):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await interaction.response.send_message("⏳ Assigning role to all members...")
    for member in interaction.guild.members:
        try: await member.add_roles(role)
        except: pass
    await interaction.followup.send(f"✅ Added {role.mention} to all members!")

@bot.tree.command(name="nuke", description="Clone and clear channel history")
async def nuke(interaction: discord.Interaction):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    channel = interaction.channel
    pos = channel.position
    new_c = await channel.clone(reason="Nuke channel")
    await channel.delete()
    await new_c.edit(position=pos)
    await new_c.send("💥 Channel Nuked!")

@bot.tree.command(name="createchannel", description="Create new channel")
async def createchannel(interaction: discord.Interaction, name: str, is_voice: bool = False):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    c = await interaction.guild.create_voice_channel(name) if is_voice else await interaction.guild.create_text_channel(name)
    await interaction.response.send_message(f"✅ Created {c.mention}.")

@bot.tree.command(name="deletechannel", description="Delete a channel")
async def deletechannel(interaction: discord.Interaction, channel: discord.abc.GuildChannel):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await channel.delete()
    await interaction.response.send_message("✅ Channel deleted.")

@bot.tree.command(name="vmute", description="Voice Mute member")
async def vmute(interaction: discord.Interaction, member: discord.Member):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    if member.voice:
        await member.edit(mute=True)
        await interaction.response.send_message(f"🔇 Voice muted {member.mention}.")
    else: await interaction.response.send_message("❌ Not in voice!", ephemeral=True)

@bot.tree.command(name="vunmute", description="Voice Unmute member")
async def vunmute(interaction: discord.Interaction, member: discord.Member):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    if member.voice:
        await member.edit(mute=False)
        await interaction.response.send_message(f"🔊 Voice unmuted {member.mention}.")
    else: await interaction.response.send_message("❌ Not in voice!", ephemeral=True)

@bot.tree.command(name="vkick", description="Kick member from voice")
async def vkick(interaction: discord.Interaction, member: discord.Member):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    if member.voice:
        await member.move_to(None)
        await interaction.response.send_message(f"👢 Kicked {member.mention} from voice.")
    else: await interaction.response.send_message("❌ Not in voice!", ephemeral=True)

@bot.tree.command(name="embed", description="Send custom embed")
async def embed_cmd(interaction: discord.Interaction, title: str, description: str):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    emb = discord.Embed(title=title, description=description, color=discord.Color.blue())
    await interaction.channel.send(embed=emb)
    await interaction.response.send_message("✅ Sent!", ephemeral=True)

@bot.tree.command(name="say", description="Make bot talk")
async def say(interaction: discord.Interaction, message: str):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await interaction.channel.send(message)
    await interaction.response.send_message("✅ Sent!", ephemeral=True)

@bot.tree.command(name="nick", description="Change nickname")
async def nick(interaction: discord.Interaction, member: discord.Member, nickname: str):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    await member.edit(nick=nickname)
    await interaction.response.send_message(f"✅ Changed nickname to `{nickname}`.")

@bot.tree.command(name="setlanguage", description="Change server language")
@app_commands.choices(language_code=[app_commands.Choice(name="🇺🇸 English", value="en"), app_commands.Choice(name="🇸🇦 العربية", value="ar")])
async def setlanguage(interaction: discord.Interaction, language_code: app_commands.Choice[str]):
    if not is_owner_or_guild_owner(interaction): return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    set_server_lang(interaction.guild.id, language_code.value)
    await interaction.response.send_message(get_text(interaction.guild.id, "lang_changed", lang=language_code.name))

# ==============================================================================
#                      أوامر الإدارة والعقوبات والتنظيف
# ==============================================================================

@bot.tree.command(name="mute", description="Timeout member")
async def slash_mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str):
    if not interaction.user.guild_permissions.moderate_members and not is_owner_or_guild_owner(interaction):
        return await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
    if not await check_admin_channel(interaction): return
    try:
        await member.timeout(timedelta(minutes=minutes), reason=reason)
        await interaction.response.send_message(f"🔇 Muted {member.mention} for **{minutes}m**. Reason: `{reason}`")
        await send_punishment_log(interaction.guild, member, interaction.user, "MUTE 🔇", reason, f"{minutes}m")
    except Exception as e: await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="unmute", description="Unmute member")
async def slash_unmute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members and not is_owner_or_guild_owner(interaction):
        return await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
    if not await check_admin_channel(interaction): return
    try:
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 Unmuted {member.mention}.")
        await send_punishment_log(interaction.guild, member, interaction.user, "UNMUTE 🔊", "Unmuted", "None")
    except Exception as e: await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="kick", description="Kick member")
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not interaction.user.guild_permissions.kick_members and not is_owner_or_guild_owner(interaction):
        return await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
    if not await check_admin_channel(interaction): return
    try:
        await send_punishment_log(interaction.guild, member, interaction.user, "KICK 👢", reason, "Kicked")
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 Kicked {member.mention}.")
    except Exception as e: await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="Ban member")
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not interaction.user.guild_permissions.ban_members and not is_owner_or_guild_owner(interaction):
        return await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
    if not await check_admin_channel(interaction): return
    try:
        await send_punishment_log(interaction.guild, member, interaction.user, "BAN 🔨", reason, "Permanent")
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 Banned {member.mention}.")
    except Exception as e: await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="unban", description="Unban ID")
async def slash_unban(interaction: discord.Interaction, user_id: str):
    if not interaction.user.guild_permissions.ban_members and not is_owner_or_guild_owner(interaction):
        return await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
    if not await check_admin_channel(interaction): return
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"🔓 Unbanned **{user.name}**.")
    except Exception as e: await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="clear", description="Clear chat messages")
async def slash_clear(interaction: discord.Interaction, amount: int = 10):
    if not interaction.user.guild_permissions.manage_messages and not is_owner_or_guild_owner(interaction):
        return await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
    if not await check_admin_channel(interaction): return
    try:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=min(amount, 100))
        await interaction.followup.send(f"🧹 Cleared **{len(deleted)}** messages.", ephemeral=True)
    except Exception as e: await interaction.followup.send(f"❌ Error: {e}", ephemeral=True)

@bot.tree.command(name="clear_bots", description="Purge bot messages")
async def clear_bots(interaction: discord.Interaction, amount: int = 20):
    if not interaction.user.guild_permissions.manage_messages and not is_owner_or_guild_owner(interaction): return
    if not await check_admin_channel(interaction): return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=min(amount, 100), check=lambda m: m.author.bot)
    await interaction.followup.send(f"🧹 Cleared **{len(deleted)}** bot messages.", ephemeral=True)

@bot.tree.command(name="clear_user", description="Purge user messages")
async def clear_user(interaction: discord.Interaction, member: discord.Member, amount: int = 20):
    if not interaction.user.guild_permissions.manage_messages and not is_owner_or_guild_owner(interaction): return
    if not await check_admin_channel(interaction): return
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=min(amount, 100), check=lambda m: m.author == member)
    await interaction.followup.send(f"🧹 Cleared **{len(deleted)}** messages.", ephemeral=True)

@bot.tree.command(name="warn", description="Warn member")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not interaction.user.guild_permissions.moderate_members and not is_owner_or_guild_owner(interaction): return
    if not await check_admin_channel(interaction): return
    user_warnings[member.id].append(reason)
    await interaction.response.send_message(f"⚠️ Warned {member.mention}. Reason: `{reason}`")
    await send_punishment_log(interaction.guild, member, interaction.user, "WARN ⚠️", reason, f"Warn #{len(user_warnings[member.id])}")

@bot.tree.command(name="infractions", description="Check warnings")
async def infractions(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members and not is_owner_or_guild_owner(interaction): return
    if not await check_admin_channel(interaction): return
    warns = user_warnings[member.id]
    embed = discord.Embed(title=f"📋 Infractions for {member.name}", color=discord.Color.dark_purple())
    embed.add_field(name="Warnings Count", value=f"**{len(warns)}**", inline=True)
    if warns:
        embed.add_field(name="Details", value="\n".join([f"`#{i+1}` - {w}" for i, w in enumerate(warns)]), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="lock", description="Lock channel")
async def lock(interaction: discord.Interaction):
    if not is_owner_or_guild_owner(interaction): return
    if not await check_admin_channel(interaction): return
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 Channel locked.")

@bot.tree.command(name="unlock", description="Unlock channel")
async def unlock(interaction: discord.Interaction):
    if not is_owner_or_guild_owner(interaction): return
    if not await check_admin_channel(interaction): return
    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 Channel unlocked.")

@bot.tree.command(name="slowmode", description="Set slowmode")
async def slowmode(interaction: discord.Interaction, seconds: int):
    if not is_owner_or_guild_owner(interaction): return
    if not await check_admin_channel(interaction): return
    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"⏱️ Slowmode set to {seconds}s.")

# ==============================================================================
#                      نظام التكتات والمسابقات التفاعلية
# ==============================================================================

class ConfirmCloseView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, custom_id="confirm_close_btn")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild, channel = interaction.guild, interaction.channel
        embed = discord.Embed(title=f"🔒 Ticket Closed", color=discord.Color.gold())
        for target, overwrite in channel.overwrites.items():
            if target != guild.me and isinstance(target, discord.Member):
                overwrite.view_channel = False
                await channel.set_permissions(target, overwrite=overwrite)
        await interaction.response.edit_message(content="🔒 Ticket closed.", embed=embed)

class TicketButtonView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Create Ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket_btn", emoji="📩")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild, member = interaction.guild, interaction.user
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        category = discord.utils.get(guild.categories, name="TICKETS") or await guild.create_category("TICKETS")
        ticket_channel = await guild.create_text_channel(f"ticket-{member.name}", overwrites=overwrites, category=category)
        embed = discord.Embed(title="🎟️ Support Ticket", description="Staff will be with you shortly.", color=discord.Color.green())
        await ticket_channel.send(content=f"{member.mention}", embed=embed, view=ConfirmCloseView())
        await interaction.response.send_message(f"✅ Ticket created: {ticket_channel.mention}", ephemeral=True)

@bot.tree.command(name="setup_tickets", description="Setup tickets panel")
async def setup_tickets(interaction: discord.Interaction):
    if not is_owner_or_guild_owner(interaction): return
    embed = discord.Embed(title="🎫 VoidCraft Support", description="Click below to open a ticket.", color=discord.Color.blurple())
    await interaction.channel.send(embed=embed, view=TicketButtonView())
    await interaction.response.send_message("✅ Panel sent.", ephemeral=True)

class GiveawayView(discord.ui.View):
    def __init__(self, prize):
        super().__init__(timeout=None)
        self.prize = prize
        self.participants = set()
    @discord.ui.button(label="🎉 Enter Giveaway", style=discord.ButtonStyle.success, custom_id="enter_giveaway_btn")
    async def enter_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in self.participants:
            await interaction.response.send_message("❌ Already entered!", ephemeral=True)
        else:
            self.participants.add(interaction.user.id)
            await interaction.response.send_message(f"🎉 Entered giveaway for **{self.prize}**!", ephemeral=True)

@bot.tree.command(name="giveaway", description="Start automated giveaway")
async def giveaway(interaction: discord.Interaction, prize: str, duration_minutes: int):
    if not is_owner_or_guild_owner(interaction): return
    embed = discord.Embed(title="🎁 GIVEAWAY STARTED!", description=f"Prize: **{prize}**\nDuration: **{duration_minutes}m**", color=discord.Color.gold())
    view = GiveawayView(prize)
    await interaction.response.send_message(embed=embed, view=view)
    await asyncio.sleep(duration_minutes * 60)
    if view.participants:
        winner = interaction.guild.get_member(random.choice(list(view.participants)))
        await interaction.channel.send(f"🎉 Congratulations {winner.mention}! You won **{prize}**!")
    else:
        await interaction.channel.send(f"🎁 Giveaway ended. No participants.")

# ==============================================================================
#                  الإحصائيات والمعلومات الشخصية والعامة
# ==============================================================================

@bot.tree.command(name="ping", description="Check latency")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"🏓 Pong! **{round(bot.latency * 1000)}ms**", ephemeral=True)

@bot.tree.command(name="botinfo", description="Bot statistics")
async def botinfo(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 VoidCraft Stats", color=discord.Color.purple())
    embed.add_field(name="Servers", value=f"**{len(bot.guilds)}**", inline=True)
    embed.add_field(name="Users", value=f"**{sum(g.member_count for g in bot.guilds)}**", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="Server info")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"🏰 {guild.name}", color=discord.Color.gold())
    if guild.icon: embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="Owner", value=f"{guild.owner.mention}", inline=True)
    embed.add_field(name="Members", value=f"**{guild.member_count}**", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="User info")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(title=f"👤 {target.name}", color=target.color)
    if target.avatar: embed.set_thumbnail(url=target.avatar.url)
    embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="User avatar")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(title=f"🖼️ {target.name}'s Avatar", color=discord.Color.blue())
    if target.avatar: embed.set_image(url=target.avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="level", description="Check level")
async def slash_level(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    xp, _ = get_user_data(target.id)
    embed = discord.Embed(title=f"📊 Stats for {target.name}", color=discord.Color.blue())
    embed.add_field(name="XP", value=f"**{xp}**", inline=True)
    embed.add_field(name="Level", value=f"**{xp // 100}**", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==============================================================================
#                    نظام الحماية والأمان التلقائي 24/7
# ==============================================================================

@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None: return
    if message.author.id in OWNER_IDS or message.author == message.guild.owner or message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    author_id = message.author.id
    current_time = time.time()
    content_lower = message.content.lower()

    user_data = user_violations[author_id]
    if current_time - user_data['last_time'] > 86400:
        user_data['suspicious_count'], user_data['link_count'] = 0, 0

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
            await send_punishment_log(message.guild, message.author, bot.user, "MUTE 🔇", "External Discord invite", f"{mute_m}m")
        except: pass
        return

    xp, bal = get_user_data(author_id)
    update_user_data(author_id, xp=xp + 10)

    await bot.process_commands(message)

# ==============================================================================
#            خادم الويب وواجهة الموقع الإلكتروني (Flask & Frontend)
# ==============================================================================

from flask import render_template_string

app = Flask(__name__)

# 🌐 يمكنك استبدال الرابط أدناه برابط صورة البوت الخاصة بك (Avatar)
BOT_AVATAR_URL = "https://cdn.discordapp.com/embed/avatars/0.png" 

# 🔗 رابط دعوة البوت الخاص بك من Discord Developer Portal
CLIENT_ID = "YOUR_BOT_CLIENT_ID" # ضع هنا Client ID الخاص ببوتك
DISCORD_INVITE_URL = f"https://discord.com/oauth2/authorize?client_id={CLIENT_ID}&scope=bot&permissions=8"

HTML_HOME_PAGE = f"""
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>VoidCraft - النظام الاحترافي الشامل</title>
    <style>
        body {{
            background-color: #0b0f19;
            color: #ffffff;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            align-items: center;
            min-height: 100vh;
        }}
        .container {{
            text-align: center;
            background: rgba(17, 24, 39, 0.85);
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 8px 32px 0 rgba(124, 58, 237, 0.37);
            border: 1px solid rgba(255, 255, 255, 0.1);
            max-width: 750px;
            width: 100%;
        }}
        .bot-avatar {{
            width: 120px;
            height: 120px;
            border-radius: 50%;
            border: 3px solid #8b5cf6;
            box-shadow: 0 0 20px rgba(139, 92, 246, 0.5);
            margin-bottom: 15px;
        }}
        h1 {{
            font-size: 2.5rem;
            color: #8b5cf6;
            margin-bottom: 10px;
        }}
        .description {{
            color: #9ca3af;
            font-size: 1.1rem;
            margin-bottom: 25px;
            line-height: 1.6;
        }}
        .features {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
            text-align: right;
        }}
        .feature-card {{
            background: rgba(31, 41, 55, 0.5);
            padding: 15px;
            border-radius: 10px;
            border-right: 4px solid #7c3aed;
        }}
        .feature-card h4 {{ margin: 0 0 5px 0; color: #f3f4f6; }}
        .feature-card p {{ margin: 0; font-size: 0.85rem; color: #9ca3af; }}
        .stats {{
            display: flex;
            justify-content: space-around;
            margin-bottom: 30px;
            background: rgba(31, 41, 55, 0.5);
            padding: 15px;
            border-radius: 10px;
        }}
        .stat-item h3 {{ margin: 0; color: #f3f4f6; font-size: 1.6rem; }}
        .stat-item span {{ font-size: 0.9rem; color: #9ca3af; }}
        .btn-group {{
            display: flex;
            gap: 15px;
            justify-content: center;
            flex-wrap: wrap;
        }}
        .btn {{
            background-color: #7c3aed;
            color: white;
            padding: 12px 25px;
            border-radius: 8px;
            text-decoration: none;
            font-weight: bold;
            transition: 0.3s;
            cursor: pointer;
            border: none;
            font-size: 1rem;
            box-shadow: 0 4px 12px rgba(124, 58, 237, 0.4);
        }}
        .btn:hover {{ background-color: #6d28d9; transform: translateY(-2px); }}
        .btn-buy {{ background-color: #10b981; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.4); }}
        .btn-buy:hover {{ background-color: #059669; }}
        
        /* شاشة اختيار السيرفر بعد الدفع */
        #server-selection-modal {{
            display: none;
            margin-top: 25px;
            background: rgba(15, 23, 42, 0.95);
            padding: 20px;
            border-radius: 15px;
            border: 1px solid #10b981;
        }}
        .server-list {{
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-top: 15px;
        }}
        .server-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: #1e293b;
            padding: 10px 15px;
            border-radius: 8px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- صورة البوت -->
        <img src="{BOT_AVATAR_URL}" alt="VoidCraft Logo" class="bot-avatar">
        
        <h1>VoidCraft</h1>
        <p class="description">البوت الآمن الشامل لحماية وإدارة وتنشيط سيرفرك 24/7 بدعم كامل للغة العربية والإنجليزية وبدون أي خيارات غير حلال.</p>

        <!-- ماذا يقدم البوت -->
        <div class="features">
            <div class="feature-card">
                <h4>🛡️ حماية حقيقية</h4>
                <p>منع الملفات الملغومة، روابط السبام، وحظر الأوامر في الشات العام.</p>
            </div>
            <div class="feature-card">
                <h4>🪙 اقتصاد حلال</h4>
                <p>مكافآت يومية، تحويل أموال، ونظام مستويات تفاعلي بدون قمار.</p>
            </div>
            <div class="feature-card">
                <h4>🎫 دعم ومسابقات</h4>
                <p>تكتات دعم فني تفاعلية وسحوبات Giveaway آلية.</p>
            </div>
        </div>

        <!-- الإحصائيات -->
        <div class="stats">
            <div class="stat-item">
                <h3 id="server-count">...</h3>
                <span>السيرفرات المفعّلة</span>
            </div>
            <div class="stat-item">
                <h3 id="user-count">...</h3>
                <span>الأعضاء المحميون</span>
            </div>
        </div>

        <!-- أزرار العمليات -->
        <div class="btn-group">
            <a href="{DISCORD_INVITE_URL}" target="_blank" class="btn">إضافة البوت (Invite Bot)</a>
            <button onclick="startPurchaseFlow()" class="btn btn-buy">تسجيل الدخول والاشتراك ($4.99 / شهرياً)</button>
        </div>

        <!-- منطقة اختيار سيرفر واحد بعد تسجيل الدخول والدفع -->
        <div id="server-selection-modal">
            <h3 style="color: #10b981;">🎉 تم الدفع بنجاح! اختر سيرفر واحد فقط لتفعيله:</h3>
            <p style="font-size: 0.9rem; color: #9ca3af;">(يظهر هنا السيرفرات التي تملك فيها رتبة Owner)</p>
            <div class="server-list" id="servers-container">
                <!-- سيتم جلب السيرفرات تلقائياً عبر Discord OAuth2 -->
            </div>
        </div>
    </div>

    <script>
        fetch('/api/stats')
            .then(res => res.json())
            .then(data => {{
                document.getElementById('server-count').innerText = data.servers;
                document.getElementById('user-count').innerText = data.users;
            }});

        function startPurchaseFlow() {{
            // 1. تسجيل الدخول بحساب ديسكورد وجلب السيرفرات
            alert("سيتم الآن تحويلك لتسجيل الدخول بحساب الديسكورد للتحقق من سيرفراتك ثم إتمام الدفع!");
            
            // محاكاة إظهار قائمة السيرفرات بعد إتمام الدفع (اختيار سيرفر واحد فقط)
            document.getElementById('server-selection-modal').style.display = 'block';
            const container = document.getElementById('servers-container');
            
            // تجربة العرض: سيرفرين يملكهما العميل مع إمكانية اختيار واحد فقط
            container.innerHTML = `
                <div class="server-item">
                    <span>🏰 سيرفر التجربة الأول (أنت الأونر)</span>
                    <button class="btn btn-buy" onclick="activateSingleServer('123456789')">تفعيل هذا السيرفر</button>
                </div>
                <div class="server-item">
                    <span>🏰 سيرفر المجتمعات الثاني (أنت الأونر)</span>
                    <button class="btn btn-buy" onclick="activateSingleServer('987654321')">تفعيل هذا السيرفر</button>
                </div>
            `;
        }}

        function activateSingleServer(guildId) {{
            fetch('/api/activate', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ guild_id: guildId }})
            }})
            .then(res => res.json())
            .then(data => {{
                alert("✅ تم تفعيل الاشتراك بنجاح للسيرفر المختار! يمكنك الآن استخدام البوت بكامل الصلاحيات.");
                window.location.href = "{DISCORD_INVITE_URL}&guild_id=" + guildId;
            }});
        }}
    </script>
</body>
</html>
"""

@app.route("/")
def home():
    return render_template_string(HTML_HOME_PAGE)

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
    if not guild_id: return jsonify({"error": "Missing guild_id"}), 400
    
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