import discord
from discord.ext import commands
from discord import app_commands
import io
import time
from datetime import timedelta
from collections import defaultdict
import threading
import os
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

# 🛡️ آيدي حساب الأونر الخاص بك
OWNER_IDS = [1335193543660273716]

# 🔗 رابط سيرفر ديسكورد المستثنى من الحذف
MY_SERVER_INVITE = "discord.gg/voidcraft"

# 🎥 المنصات المسموح بنشر روابطها وفيديوهاتها ورسائلها القصيرة (Reels/Shorts)
ALLOWED_PLATFORMS = [
    "youtube.com", "youtu.be", 
    "tiktok.com", 
    "instagram.com", 
    "snapchat.com", 
    "facebook.com", "fb.watch", 
    "twitch.tv", 
    "twitter.com", "x.com"
]

# ⚠️ الامتدادات والملفات المشبوهة والممنوعة نهائياً لحماية أجهزة الأعضاء
DANGEROUS_EXTENSIONS = [
    '.exe', '.scr', '.bat', '.cmd', '.vbs', '.js', '.jse', '.wsf', '.wsh',
    '.ps1', '.msi', '.com', '.pif', '.reg', '.dll', '.iso', '.dmg',
    '.apk', '.zip', '.rar', '.7z', '.tar', '.gz'
]

# ==================== دالة مساعدة لإرسال سجل العقوبات في قناة ban و logs ====================

async def send_punishment_log(guild, member, executor, punishment_type, reason, duration="دائم"):
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
        "SECURITY 🚨": discord.Color.dark_red()
    }

    embed = discord.Embed(
        title=f"🚨 [سجل عقوبة - {punishment_type}]",
        color=color_map.get(punishment_type, discord.Color.dark_gray()),
        timestamp=discord.utils.utcnow()
    )
    embed.add_field(name="👤 العضو المُعاقَب", value=f"{member.mention} (`{member.id}`)", inline=True)
    embed.add_field(name="🛡️ المنفذ", value=f"{executor.mention if hasattr(executor, 'mention') else executor}", inline=True)
    embed.add_field(name="⏱️ المدة", value=f"**{duration}**", inline=True)
    embed.add_field(name="📜 السبب", value=f"`{reason}`", inline=False)
    if hasattr(member, 'avatar') and member.avatar:
        embed.set_thumbnail(url=member.avatar.url)

    if ban_channel:
        try:
            await ban_channel.send(embed=embed)
        except Exception as e:
            print(f"خطأ في إرسال اللوج بقناة ban: {e}")

    if logs_channel and logs_channel != ban_channel:
        try:
            await logs_channel.send(embed=embed)
        except Exception as e:
            print(f"خطأ في إرسال اللوج بقناة logs: {e}")

# ==================== أحداث البوت المباشرة ====================

@bot.event
async def on_ready():
    print(f"✅ تم تسجيل الدخول بنجاح باسم: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🚀 تم مزامنة {len(synced)} أمر (Slash Command) عالمياً بنجاح.")
    except Exception as e:
        print(f"❌ خطأ في مزامنة الأوامر: {e}")

# ==================== سجلات التعديل والحذف للرسائل (Audit Logs) ====================

@bot.event
async def on_message_delete(message):
    if message.author.bot or message.guild is None:
        return
    logs_channel = discord.utils.get(message.guild.text_channels, name="logs")
    if logs_channel:
        embed = discord.Embed(
            title="🗑️ تم حذف رسالة",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 صاحب الرسالة", value=message.author.mention, inline=True)
        embed.add_field(name="💬 القناة", value=message.channel.mention, inline=True)
        embed.add_field(name="📜 المحتوى", value=message.content or "[ملف/مرفق]", inline=False)
        await logs_channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    if before.author.bot or before.guild is None or before.content == after.content:
        return
    logs_channel = discord.utils.get(before.guild.text_channels, name="logs")
    if logs_channel:
        embed = discord.Embed(
            title="✏️ تم تعديل رسالة",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 العضو", value=before.author.mention, inline=True)
        embed.add_field(name="💬 القناة", value=before.channel.mention, inline=True)
        embed.add_field(name="🔴 النص القديم", value=before.content or "لا يوجد", inline=False)
        embed.add_field(name="🟢 النص الجديد", value=after.content or "لا يوجد", inline=False)
        await logs_channel.send(embed=embed)

# ==================== نظام التحقق من قنوات الإدارة (Anti-Public Admin Commands) ====================

def is_staff_channel(channel):
    name = channel.name.lower()
    return any(keyword in name for keyword in ["admin", "staff", "console", "owner", "ادارة", "الإدارة"])

async def check_admin_channel(interaction: discord.Interaction):
    if interaction.user.id in OWNER_IDS:
        return True
    if not is_staff_channel(interaction.channel):
        logs_channel = (discord.utils.get(interaction.guild.text_channels, name="logs") or 
                        discord.utils.get(interaction.guild.text_channels, name="سجل-المراقبة"))
        if logs_channel:
            embed = discord.Embed(
                title="🚨 [محاولة استخدام أمر إداري في شات عام]",
                color=discord.Color.orange(),
                timestamp=discord.utils.utcnow()
            )
            embed.add_field(name="🛡️ الإداري المخالف", value=interaction.user.mention, inline=True)
            embed.add_field(name="💬 القناة العامة", value=interaction.channel.mention, inline=True)
            embed.add_field(name="⚙️ الأمر المستخدم", value=f"`/{interaction.command.name}`", inline=False)
            await logs_channel.send(embed=embed)
        
        await interaction.response.send_message(
            f"❌ عذراً يا {interaction.user.mention}، لا يمكنك تنفيذ الأوامر الإدارية في القنوات العامة! يرجى التوجه لقنوات الإدارة المخصصة.", 
            ephemeral=True
        )
        return False
    return True

# ==================== أوامر المساعدة المزدوجة ====================

@bot.tree.command(name="help", description="عرض قائمة الأوامر والمساعدة العامة للاعضاء")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 مساعدة الأعضاء - VoidCraft Bot",
        description="مرحباً بك! إليك قائمة الأوامر والميزات المتاحة لك في السيرفر:",
        color=discord.Color.blurple()
    )
    embed.add_field(name="📊 `/level`", value="لعرض مستواك الحالي ونقاط الخبرة (XP).", inline=False)
    embed.add_field(name="👤 `/userinfo`", value="عرض معلومات تفصيلية عن حسابك أو حساب عضو آخر.", inline=False)
    embed.add_field(name="🖼️ `/avatar`", value="عرض الصورة الشخصية لك أو لعضو آخر.", inline=False)
    embed.add_field(name="🏰 `/serverinfo`", value="عرض معلومات وإحصائيات سيرفر VoidCraft.", inline=False)
    embed.add_field(name="🏓 `/ping`", value="فحص سرعة استجابة البوت الحالية.", inline=False)
    embed.add_field(name="🎫 نظام التكتات", value="توجه إلى قناة التكتات واضغط على زر فتح تكت للتحدث مع الإدارة.", inline=False)
    embed.set_footer(text="VoidCraft Ecosystem - جميع الحقوق محفوظة")
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="adminhelp", description="قائمة أوامر الإدارة الكاملة (لقنوات الإدارة فقط)")
async def adminhelp(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة فقط!", ephemeral=True)
        return
    
    if not await check_admin_channel(interaction):
        return

    embed = discord.Embed(
        title="🛠️ لوحة أوامر إدارة VoidCraft Bot",
        description="إليك قائمة جميع أوامر الإدارة والحماية المتاحة:",
        color=discord.Color.dark_red()
    )
    embed.add_field(name="🔇 `/mute`", value="إعطاء ميوت موقت لعضو (المدة والسبب إجباري).", inline=False)
    embed.add_field(name="🔊 `/unmute`", value="رفع الميوت عن العضو.", inline=False)
    embed.add_field(name="👢 `/kick`", value="طرد عضو من السيرفر (السبب إجباري).", inline=False)
    embed.add_field(name="🔨 `/ban`", value="حظر عضو نهائياً (السبب إجباري).", inline=False)
    embed.add_field(name="🔓 `/unban`", value="فك الحظر عن آيدي العضو.", inline=False)
    embed.add_field(name="🧹 `/clear`", value="مسح عدد محدد من الرسائل (1-100).", inline=False)
    embed.add_field(name="⚠️ `/warn`", value="إضافة تحذير إداري لعضو (السبب إجباري).", inline=False)
    embed.add_field(name="📋 `/infractions`", value="عرض سجل عقوبات ومخالفات عضو.", inline=False)
    embed.add_field(name="🔒 `/lock` / `/unlock`", value="قفل أو فتح القناة الحالية (للأونر).", inline=False)
    embed.add_field(name="⏱️ `/slowmode`", value="تحديد الوضع البطيء للقناة (للأونر).", inline=False)
    embed.add_field(name="🎫 `/setup_tickets`", value="إرسال قائمة تكتات الدعم الفني.", inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== أوامر الفحص والمعلومات العامة ====================

@bot.tree.command(name="ping", description="فحص سرعة استجابة البوت")
async def ping(interaction: discord.Interaction):
    latency = round(bot.latency * 1000)
    embed = discord.Embed(
        title="🏓 Pong!",
        description=f"سرعة استجابة البوت الحالية: **{latency}ms**",
        color=discord.Color.green() if latency < 150 else discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="botinfo", description="عرض معلومات وإحصائيات البوت")
async def botinfo(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 معلومات VoidCraft Bot", color=discord.Color.purple())
    embed.add_field(name="🌐 السيرفرات", value=f"**{len(bot.guilds)}** سيرفر", inline=True)
    embed.add_field(name="👥 المستخدمين", value=f"**{sum(g.member_count for g in bot.guilds)}** عضو", inline=True)
    embed.add_field(name="⚙️ الاستجابة", value=f"**{round(bot.latency * 1000)}ms**", inline=True)
    embed.set_footer(text="Developed for VoidCraft Ecosystem")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="serverinfo", description="عرض إحصائيات ومعلومات السيرفر")
async def serverinfo(interaction: discord.Interaction):
    guild = interaction.guild
    embed = discord.Embed(title=f"🏰 معلومات {guild.name}", color=discord.Color.gold())
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    embed.add_field(name="👑 صاحب السيرفر", value=f"{guild.owner.mention}", inline=True)
    embed.add_field(name="👥 الأعضاء", value=f"**{guild.member_count}** عضو", inline=True)
    embed.add_field(name="💬 القنوات", value=f"**{len(guild.channels)}** قناة", inline=True)
    embed.add_field(name="🛡️ الرتب", value=f"**{len(guild.roles)}** رتبة", inline=True)
    embed.add_field(name="📅 تاريخ الإنشاء", value=f"{guild.created_at.strftime('%Y-%m-%d')}", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="userinfo", description="عرض تفاصيل حسابك أو حساب عضو آخر")
@app_commands.describe(member="العضو المراد استعراض بياناته")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    embed = discord.Embed(title=f"👤 معلومات {target.name}", color=target.color)
    avatar_url = target.avatar.url if target.avatar else target.default_avatar.url
    embed.set_thumbnail(url=avatar_url)
    embed.add_field(name="🆔 ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="📅 انضم للديسكورد", value=f"{target.created_at.strftime('%Y-%m-%d')}", inline=True)
    embed.add_field(name="📥 انضم للسيرفر", value=f"{target.joined_at.strftime('%Y-%m-%d')}", inline=True)
    embed.add_field(name="🎖️ أعلى رتبة", value=f"{target.top_role.mention}", inline=True)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="avatar", description="عرض صورة الحساب الشخصية")
@app_commands.describe(member="العضو المراد جلب صورته")
async def avatar(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    avatar_url = target.avatar.url if target.avatar else target.default_avatar.url
    embed = discord.Embed(title=f"🖼️ صورة {target.name}", color=discord.Color.blue())
    embed.set_image(url=avatar_url)
    await interaction.response.send_message(embed=embed)

# ==================== أوامر الإدارة والعقوبات (مع السبب الإجباري وقنوات الإدارة) ====================

@bot.tree.command(name="mute", description="إعطاء ميوت موقت لعضو (للإدارة فقط)")
@app_commands.describe(member="العضو", minutes="مدة الميوت بالدقائق", reason="سبب العقوبة (إجباري)")
async def slash_mute(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، هذا الأمر مخصص للإدارة فقط!", ephemeral=True)
        return
    if not await check_admin_channel(interaction):
        return

    if member.id in OWNER_IDS or member.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك إعطاء ميوت لهذا الشخص!", ephemeral=True)
        return

    if minutes <= 0:
        await interaction.response.send_message("❌ يجب تحديد وقت أكبر من 0!", ephemeral=True)
        return

    try:
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"🔇 تم إعطاء ميوت للعضو {member.mention} لمدة **{minutes}** دقيقة. السبب: **{reason}**")
        await send_punishment_log(interaction.guild, member, interaction.user, "MUTE 🔇", reason, f"{minutes} دقيقة")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="unmute", description="رفع الميوت عن العضو")
@app_commands.describe(member="العضو")
async def slash_unmute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ مخصص للإدارة فقط!", ephemeral=True)
        return
    if not await check_admin_channel(interaction):
        return

    try:
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 تم رفع الميوت عن {member.mention}.")
        await send_punishment_log(interaction.guild, member, interaction.user, "UNMUTE 🔊", "فك الميوت", "ملغى")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="kick", description="طرد عضو من السيرفر")
@app_commands.describe(member="العضو", reason="السبب (إجباري)")
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not interaction.user.guild_permissions.kick_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ مخصص للإدارة فقط!", ephemeral=True)
        return
    if not await check_admin_channel(interaction):
        return

    if member.id in OWNER_IDS or member.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك طرد هذا الشخص!", ephemeral=True)
        return

    try:
        await send_punishment_log(interaction.guild, member, interaction.user, "KICK 👢", reason, "طرد")
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 تم طرد {member.mention}. السبب: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="حظر عضو نهائياً")
@app_commands.describe(member="العضو", reason="السبب (إجباري)")
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not interaction.user.guild_permissions.ban_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ مخصص للإدارة فقط!", ephemeral=True)
        return
    if not await check_admin_channel(interaction):
        return

    if member.id in OWNER_IDS or member.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك حظر هذا الشخص!", ephemeral=True)
        return

    try:
        await send_punishment_log(interaction.guild, member, interaction.user, "BAN 🔨", reason, "حظر دائم")
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 تم حظر {member.mention}. السبب: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="unban", description="فك الحظر عن آيدي عضو")
@app_commands.describe(user_id="آيدي العضو")
async def slash_unban(interaction: discord.Interaction, user_id: str):
    if not interaction.user.guild_permissions.ban_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ مخصص للإدارة فقط!", ephemeral=True)
        return
    if not await check_admin_channel(interaction):
        return
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"🔓 تم فك الحظر عن **{user.name}**.")
        await send_punishment_log(interaction.guild, user, interaction.user, "UNBAN 🔓", "فك الحظر", "ملغى")
    except Exception as e:
        await interaction.response.send_message(f"❌ خطأ: {e}", ephemeral=True)

@bot.tree.command(name="clear", description="مسح الرسائل")
@app_commands.describe(amount="عدد الرسائل (1-100)")
async def slash_clear(interaction: discord.Interaction, amount: int = 10):
    if not interaction.user.guild_permissions.manage_messages and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ مخصص للإدارة فقط!", ephemeral=True)
        return
    if not await check_admin_channel(interaction):
        return

    amount = min(amount, 100)
    try:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 تم مسح **{len(deleted)}** رسالة.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ خطأ: {e}", ephemeral=True)

@bot.tree.command(name="warn", description="إضافة تحذير لعضو")
@app_commands.describe(member="العضو", reason="السبب (إجباري)")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ مخصص للإدارة فقط!", ephemeral=True)
        return
    if not await check_admin_channel(interaction):
        return

    user_warnings[member.id].append(reason)
    total_warns = len(user_warnings[member.id])
    await interaction.response.send_message(f"⚠️ تم تحذير {member.mention}. السبب: {reason} (الإجمالي: {total_warns})")
    await send_punishment_log(interaction.guild, member, interaction.user, "WARN ⚠️", reason, f"تحذير #{total_warns}")

@bot.tree.command(name="infractions", description="سجل عقوبات عضو")
@app_commands.describe(member="العضو")
async def infractions(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ مخصص للإدارة فقط!", ephemeral=True)
        return
    if not await check_admin_channel(interaction):
        return

    data = user_violations[member.id]
    warns = user_warnings[member.id]

    embed = discord.Embed(title=f"📋 سجل عقوبات {member.name}", color=discord.Color.dark_purple())
    embed.add_field(name="⚠️ التحذيرات", value=f"**{len(warns)}**", inline=True)
    embed.add_field(name="🚨 مخالفات الملغومات", value=f"**{data['suspicious_count']}**", inline=True)
    embed.add_field(name="🔗 مخالفات الروابط", value=f"**{data['link_count']}**", inline=True)
    if warns:
        embed.add_field(name="📜 التفاصيل", value="\n".join([f"• {w}" for w in warns]), inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="lock", description="قفل القناة (للأونر فقط)")
async def lock(interaction: discord.Interaction):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ مخصص للأونر فقط!", ephemeral=True)
        return
    if not await check_admin_channel(interaction):
        return

    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 تم قفل القناة.")

@bot.tree.command(name="unlock", description="فتح القناة (للأونر فقط)")
async def unlock(interaction: discord.Interaction):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ مخصص للأونر فقط!", ephemeral=True)
        return
    if not await check_admin_channel(interaction):
        return

    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 تم فتح القناة.")

@bot.tree.command(name="slowmode", description="الوضع البطئ (للأونر فقط)")
@app_commands.describe(seconds="الثواني")
async def slowmode(interaction: discord.Interaction, seconds: int):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ مخصص للأونر فقط!", ephemeral=True)
        return
    if not await check_admin_channel(interaction):
        return

    await interaction.channel.edit(slowmode_delay=seconds)
    await interaction.response.send_message(f"⏱️ تم تحديد الوضع البطئ بـ {seconds} ثواني.")

# ==================== نظام التكتات والترحيب ====================

class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="إغلاق التكت", style=discord.ButtonStyle.danger, custom_id="confirm_close_btn")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        channel = interaction.channel
        embed = discord.Embed(title=f"🔒 تم إغلاق التكت بواسطة {interaction.user.name}", color=discord.Color.gold())
        for target, overwrite in channel.overwrites.items():
            if target != guild.me and isinstance(target, discord.Member):
                overwrite.view_channel = False
                await channel.set_permissions(target, overwrite=overwrite)
        await interaction.response.edit_message(content="🔒 تم إغلاق القناة.", embed=embed, view=TicketControlView())

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="تنزيل المحادثة", style=discord.ButtonStyle.secondary, custom_id="transcript_btn", emoji="📄")
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        messages = [f"{msg.author}: {msg.content}" async for msg in interaction.channel.history(limit=200, oldest_first=True)]
        file = discord.File(io.BytesIO("\n".join(messages).encode('utf-8')), filename="transcript.txt")
        await interaction.followup.send("📄 ملف المحادثة:", file=file, ephemeral=True)
    @discord.ui.button(label="إعادة فتح", style=discord.ButtonStyle.success, custom_id="reopen_btn", emoji="🔓")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        for target, overwrite in interaction.channel.overwrites.items():
            if isinstance(target, discord.Member):
                overwrite.view_channel = True
                await interaction.channel.set_permissions(target, overwrite=overwrite)
        await interaction.response.send_message("🔓 تم إعادة الفتح.")
    @discord.ui.button(label="حذف", style=discord.ButtonStyle.danger, custom_id="delete_btn", emoji="⛔")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⛔ جاري الحذف...")
        await interaction.channel.delete()

class CloseButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="طلب إغلاق التكت", style=discord.ButtonStyle.danger, custom_id="initial_close_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("هل أنت متأكد من الإغلاق؟", view=ConfirmCloseView(), ephemeral=True)

class TicketModal(discord.ui.Modal, title="إنشاء تكت دعم فني"):
    minecraft_name = discord.ui.TextInput(label="اسمك في ماينكرافت", placeholder="اكتب اسمك...", required=True, max_length=50)
    problem_desc = discord.ui.TextInput(label="وصف المشكلة", placeholder="اشرح مشكلتك...", style=discord.TextStyle.paragraph, required=True, max_length=500)
    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }
        category = discord.utils.get(guild.categories, name="TICKETS") or await guild.create_category("TICKETS")
        ticket_channel = await guild.create_text_channel(f"ticket-{member.name}", overwrites=overwrites, category=category)
        embed = discord.Embed(title="🎟️ تكت جديدة", color=discord.Color.green())
        embed.add_field(name="الماينكرافت", value=self.minecraft_name.value, inline=False)
        embed.add_field(name="المشكلة", value=self.problem_desc.value, inline=False)
        await ticket_channel.send(content=f"{member.mention}", embed=embed, view=CloseButtonView())
        await interaction.response.send_message(f"✅ تم إنشاء تكتك: {ticket_channel.mention}", ephemeral=True)

class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="فتح تكت دعم فني", style=discord.ButtonStyle.primary, custom_id="create_ticket_btn", emoji="📩")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal())

@bot.tree.command(name="setup_tickets", description="إرسال لوحة التكتات (للأونر فقط)")
async def setup_tickets(interaction: discord.Interaction):
    if interaction.user.id not in OWNER_IDS and interaction.user != interaction.guild.owner:
        await interaction.response.send_message("❌ مخصص للأونر فقط!", ephemeral=True)
        return
    embed = discord.Embed(title="🎫 VoidCraft Support", description="اضغط الزر أدناه لفتح تكت دعم فني.", color=discord.Color.blurple())
    await interaction.channel.send(embed=embed, view=TicketButtonView())
    await interaction.response.send_message("✅ تم إرسال اللوحة.", ephemeral=True)

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="welcome") or discord.utils.get(member.guild.text_channels, name="👋-welcome-👋")
    if channel:
        embed = discord.Embed(title="✨ منور سيرفر VoidCraft!", description=f"أهلاً بك يا {member.mention} معنا! 🎮", color=discord.Color.blurple())
        embed.set_thumbnail(url=member.avatar.url if member.avatar else member.default_avatar.url)
        await channel.send(embed=embed)
    role = discord.utils.get(member.guild.roles, name="Player")
    if role:
        try: await member.add_roles(role)
        except: pass

# ==================== الحماية الشاملة ====================

@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        return

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
            await message.author.timeout(timedelta(minutes=mute_mins), reason="ملف مشبوه")
            await send_punishment_log(message.guild, message.author, bot.user, "SECURITY 🚨", "إرسال ملف خبيث/تنفيذي", f"ميوت {mute_mins}د + طرد")
            await message.author.kick(reason="ملف مشبوه")
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
            await message.author.timeout(timedelta(minutes=mute_m), reason="نشر روابط ديسكورد")
            await send_punishment_log(message.guild, message.author, bot.user, "MUTE 🔇", "إعلان ديسكورد خارجي", f"{mute_m} دقيقة")
        except: pass
        return
    elif has_any_link and not is_allowed:
        try:
            await message.delete()
            msg = await message.channel.send(f"⚠️ {message.author.mention} ممنوع نشر الروابط غير المصرح بها!")
            await discord.utils.sleep_until(time.time() + 4)
            await msg.delete()
        except: pass
        return

    if current_time - last_message_time[author_id] < 2.5 and content_lower == last_message_content[author_id]:
        try:
            await message.delete()
            user_spam_count[author_id] += 1
            p_min = user_spam_count[author_id] * 2
            await message.author.timeout(timedelta(minutes=p_min), reason="سبام")
            await send_punishment_log(message.guild, message.author, bot.user, "MUTE 🔇", "تكرار رسائل/سبام", f"{p_min} دقيقة")
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
            try:
                await levels_channel.send(f"🎉 مبروك {message.author.mention}! لقد وصلت إلى **Level {level}**! 🚀")
            except Exception as e:
                print(f"خطأ في إرسال رسالة الترقية: {e}")

    await bot.process_commands(message)

# ==================== أمر المستوى ====================

@bot.tree.command(name="level", description="عرض مستواك الحالي ونقاط الخبرة (XP)")
@app_commands.describe(member="العضو (اختياري)")
async def slash_level(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    xp = user_xp[target.id]
    lvl = xp // 100
    embed = discord.Embed(title=f"📊 إحصائيات مستوى {target.name}", color=discord.Color.blue())
    embed.add_field(name="✨ الخبرة (XP)", value=f"**{xp}**", inline=True)
    embed.add_field(name="🏆 المستوى (Level)", value=f"**{lvl}**", inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

# ==================== خادم الويب وتشغيل البوت ====================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running 24/7!"

def run_bot():
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("❌ خطأ: لم يتم العثور على المتغير DISCORD_TOKEN في البيئة!")

bot_thread = threading.Thread(target=run_bot)
bot_thread.daemon = True
bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)