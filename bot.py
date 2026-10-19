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
from flask import Flask

# ==================== الإعدادات الأساسية ====================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.remove_command('help')

user_xp = defaultdict(int)
last_message_time = defaultdict(float)
last_message_content = defaultdict(str)
user_spam_count = defaultdict(int)
user_warnings = defaultdict(list)

# 🕒 تخزين سجل المخالفات والعقوبات المتصاعدة مع التصفير بعد 24 ساعة
user_violations = defaultdict(lambda: {'suspicious_count': 0, 'link_count': 0, 'last_time': 0.0})

# 🌐 تخزين لغة كل سيرفر (الافتراضي: الإنجليزية en)
server_languages = defaultdict(lambda: "en")

# 🛡️ آيدي حساب الأونر الخاص بك (جون)
OWNER_IDS = [1335193543660273716]

# 🔗 رابط سيرفر ديسكورد المستثنى من الحذف
MY_SERVER_INVITE = "discord.gg/voidcraft"

# 🎥 المنصات المسموح بنشر روابطها
ALLOWED_PLATFORMS = [
    "youtube.com", "youtu.be", 
    "tiktok.com", 
    "instagram.com", 
    "snapchat.com", 
    "facebook.com", "fb.watch", 
    "twitch.tv", 
    "twitter.com", "x.com"
]

# ⚠️ الامتدادات الممنوعة لحماية أجهزة الأعضاء
DANGEROUS_EXTENSIONS = [
    '.exe', '.scr', '.bat', '.cmd', '.vbs', '.js', '.jse', '.wsf', '.wsh',
    '.ps1', '.msi', '.com', '.pif', '.reg', '.dll', '.iso', '.dmg',
    '.apk', '.zip', '.rar', '.7z', '.tar', '.gz'
]

# ==================== قاموس الترجمة الشامل ====================

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
    lang = server_languages[guild_id]
    if lang not in TRANSLATIONS:
        lang = "en"
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

# ==================== لوحة أوامر الأونر الـ VIP الفاخرة (Owner Commands) ====================

@bot.tree.command(name="ownerhelp", description="Ultimate VIP Command Panel (Bot Owner Only)")
async def ownerhelp(interaction: discord.Interaction):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
        return

    embed = discord.Embed(title=get_text(interaction.guild.id, "owner_help_title"), color=discord.Color.gold())
    
    roles_cmd = (
        "👑 `/giverole [member] [role]` - Give a role to a member\n"
        "👑 `/removerole [member] [role]` - Remove a role from a member\n"
        "👑 `/roleall [role]` - Mass assign a role to ALL members"
    )
    embed.add_field(name="🎭 Role Management System", value=roles_cmd, inline=False)

    channels_cmd = (
        "⚡ `/nuke` - Duplicate & purge channel history completely\n"
        "⚡ `/createchannel [name] [type]` - Instantly create text/voice channel\n"
        "⚡ `/deletechannel [channel]` - Delete a channel instantly\n"
        "⚡ `/lock` / `/unlock` - Instantly lock/unlock channel\n"
        "⚡ `/slowmode [seconds]` - Control channel slowmode"
    )
    embed.add_field(name="🛠️ Advanced Channel Management", value=channels_cmd, inline=False)

    voice_cmd = (
        "🎙️ `/vmute [member]` - Mute member in voice channel\n"
        "🎙️ `/vunmute [member]` - Unmute member in voice channel\n"
        "🎙️ `/vkick [member]` - Disconnect member from voice channel"
    )
    embed.add_field(name="🎙️ Voice Control System", value=voice_cmd, inline=False)

    broad_cmd = (
        "📢 `/embed [title] [description] [color]` - Broadcast rich custom embed\n"
        "📢 `/say [message]` - Make the bot talk in channel\n"
        "📢 `/nick [member] [nickname]` - Change any member's server nickname"
    )
    embed.add_field(name="📢 Announcements & Utility Tools", value=broad_cmd, inline=False)

    setup_cmd = (
        "🎫 `/setup_tickets` - Deploy interactive support tickets\n"
        "🎁 `/giveaway [prize] [duration]` - Host automated giveaway\n"
        "🌐 `/setlanguage [code]` - Switch server language dropdown"
    )
    embed.add_field(name="⚙️ Configuration & Setup", value=setup_cmd, inline=False)

    embed.set_footer(text="VoidCraft VIP Suite - Premium Monthly Edition")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== أوامر الأونر الـ VIP ====================

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
    if is_voice:
        c = await interaction.guild.create_voice_channel(name)
    else:
        c = await interaction.guild.create_text_channel(name)
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
    else:
        await interaction.response.send_message("❌ Member is not in a voice channel!", ephemeral=True)

@bot.tree.command(name="vunmute", description="Voice Unmute member (Owner Only)")
@app_commands.describe(member="Member")
async def vunmute(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    if member.voice:
        await member.edit(mute=False)
        await interaction.response.send_message(f"🔊 Voice unmuted {member.mention}.")
    else:
        await interaction.response.send_message("❌ Member is not in a voice channel!", ephemeral=True)

@bot.tree.command(name="vkick", description="Kick member from voice (Owner Only)")
@app_commands.describe(member="Member")
async def vkick(interaction: discord.Interaction, member: discord.Member):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(get_text(interaction.guild.id, "owner_only"), ephemeral=True)
    if member.voice:
        await member.move_to(None)
        await interaction.response.send_message(f"👢 Kicked {member.mention} from voice channel.")
    else:
        await interaction.response.send_message("❌ Member is not in a voice channel!", ephemeral=True)

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
    server_languages[interaction.guild.id] = code
    await interaction.response.send_message(get_text(interaction.guild.id, "lang_changed", lang=language_code.name))

# ==================== أوامر المساعدة العامة والأدمن ====================

@bot.tree.command(name="help", description="General member command list")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title=get_text(interaction.guild.id, "help_title"), color=discord.Color.blurple())
    embed.add_field(name="📊 `/level`", value="Check current level & XP stats.", inline=False)
    embed.add_field(name="👤 `/userinfo`", value="Display user account info.", inline=False)
    embed.add_field(name="🖼️ `/avatar`", value="Display user avatar image.", inline=False)
    embed.add_field(name="🏰 `/serverinfo`", value="Display server stats & info.", inline=False)
    embed.add_field(name="🏓 `/ping`", value="Check bot latency.", inline=False)
    embed.add_field(name="🤖 `/botinfo`", value="Display bot ecosystem stats.", inline=False)
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
        "🔇 `/mute [member] [minutes] [reason]` - Timeout a member\n"
        "🔊 `/unmute [member]` - Remove timeout\n"
        "👢 `/kick [member] [reason]` - Kick a member\n"
        "🔨 `/ban [member] [reason]` - Ban a member permanently\n"
        "🔓 `/unban [user_id]` - Unban a user by ID\n"
        "⚠️ `/warn [member] [reason]` - Add warning\n"
        "🧹 `/remove_warning [member] [index]` - Remove a specific warning\n"
        "🗑️ `/clear_warnings [member]` - Clear all warnings for member\n"
        "📋 `/infractions [member]` - View member warning history\n"
        "🧹 `/clear [amount]` - Purge chat messages (1-100)"
    )
    embed.add_field(name=get_text(interaction.guild.id, "mod_title"), value=mod_text, inline=False)

    sec_text = (
        "⚡ **Anti-Exe / Anti-Malware:** Auto-mutes & kicks suspicious file uploads\n"
        "⚡ **Anti-Discord Invite:** Auto-mutes external Discord server invite spam\n"
        "⚡ **Anti-Spam:** Auto-mutes repeated fast messaging\n"
        "⚡ **Public Channel Shield:** Auto-logs any staff attempting commands in public channels"
    )
    embed.add_field(name=get_text(interaction.guild.id, "sec_title"), value=sec_text, inline=False)

    embed.set_footer(text="VoidCraft Ecosystem - Staff Edition")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== نظام المسابقات والسحوبات ====================

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

# ==================== الأوامر العامة الإضافية ====================

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

# ==================== أوامر الإدارة والعقوبات ====================

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

@bot.tree.command(name="remove_warning", description="Remove a specific warning from a member")
@app_commands.describe(member="Target member", index="Warning number (1, 2, 3...)")
async def remove_warning(interaction: discord.Interaction, member: discord.Member, index: int):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return

    warns = user_warnings[member.id]
    if 1 <= index <= len(warns):
        removed_reason = warns.pop(index - 1)
        await interaction.response.send_message(get_text(interaction.guild.id, "warn_removed", index=index, member=member.mention))
        await send_punishment_log(interaction.guild, member, interaction.user, "REMOVE_WARN 🧹", f"Removed warning #{index}: {removed_reason}", "None")
    else:
        await interaction.response.send_message("❌ Invalid warning index number!", ephemeral=True)

@bot.tree.command(name="clear_warnings", description="Clear all warnings for a member")
@app_commands.describe(member="Target member")
async def clear_warnings(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message(get_text(interaction.guild.id, "staff_only"), ephemeral=True)
        return
    if not await check_admin_channel(interaction): return

    user_warnings[member.id].clear()
    await interaction.response.send_message(get_text(interaction.guild.id, "warn_cleared", member=member.mention))
    await send_punishment_log(interaction.guild, member, interaction.user, "REMOVE_WARN 🧹", "Cleared all warnings", "None")

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

# ==================== نظام التكتات والترحيب ====================

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

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome") or discord.utils.get(member.guild.text_channels, name="👋-welcome-👋")
    if channel:
        embed = discord.Embed(title="✨ Welcome to VoidCraft!", description=f"Welcome {member.mention}! 🎮", color=discord.Color.blurple())
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await channel.send(embed=embed)
    role = discord.utils.get(member.guild.roles, name="Player")
    if role:
        try: await member.add_roles(role)
        except: pass

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
    elif has_any_link and not is_allowed:
        try:
            await message.delete()
            msg = await message.channel.send(f"⚠️ {message.author.mention} Unauthorized links are not allowed!")
            await discord.utils.sleep_until(time.time() + 4)
            await msg.delete()
        except: pass
        return

    if current_time - last_message_time[author_id] < 2.5 and content_lower == last_message_content[author_id]:
        try:
            await message.delete()
            user_spam_count[author_id] += 1
            p_min = user_spam_count[author_id] * 2
            await message.author.timeout(timedelta(minutes=p_min), reason="Spamming")
            await send_punishment_log(message.guild, message.author, bot.user, "MUTE 🔇", "Spamming chat", f"{p_min} mins")
        except: pass
        return

    last_message_time[author_id] = current_time
    last_message_content[author_id] = content_lower

    user_xp[author_id] += 10
    current_xp = user_xp[author_id]
    level = current_xp // 100

    if current_xp > 0 and current_xp % 100 == 0:
        levels_channel = (discord.utils.get(message.guild.text_channels, name="levels") or 
                          discord.utils.get(message.guild.text_channels, name="المستويات") or 
                          discord.utils.get(message.guild.text_channels, name="level-up"))
        if levels_channel:
            try: await levels_channel.send(f"🎉 Congrats {message.author.mention}! Level **{level}**! 🚀")
            except: pass

        if level == 5:
            active_role = discord.utils.get(message.guild.roles, name="Active Player")
            if active_role:
                try: await message.author.add_roles(active_role)
                except: pass

    await bot.process_commands(message)

# ==================== أمر المستوى ====================

@bot.tree.command(name="level", description="Check current level")
@app_commands.describe(member="Target member")
async def slash_level(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    xp = user_xp[target.id]
    lvl = xp // 100
    embed = discord.Embed(title=f"📊 Stats for {target.name}", color=discord.Color.blue())
    embed.add_field(name="XP", value=f"**{xp}**", inline=True)
    embed.add_field(name="Level", value=f"**{lvl}**", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== خادم الويب وتشغيل البوت 24/7 ====================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 24/7!"

def run_bot():
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("❌ Error: DISCORD_TOKEN not found!")

bot_thread = threading.Thread(target=run_bot)
bot_thread.daemon = True
bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)