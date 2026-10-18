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
user_violation_count = defaultdict(int)
user_warnings = defaultdict(list)

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

# ==================== أحداث البوت المباشرة ====================

@bot.event
async def on_ready():
    print(f"✅ تم تسجيل الدخول بنجاح باسم: {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"🚀 تم مزامنة {len(synced)} أمر (Slash Command) عالمياً بنجاح.")
    except Exception as e:
        print(f"❌ خطأ في مزامنة الأوامر: {e}")

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

# ==================== أوامر الإدارة والحماية والتحكم ====================

@bot.tree.command(name="mute", description="إعطاء ميوت (تقييد) لعضو معين")
@app_commands.describe(member="العضو المراد تقييده", minutes="المدة بالدقائق", reason="السبب")
async def slash_mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 60, reason: str = "لم يُذكر سبب"):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية إدارة الأعضاء!", ephemeral=True)
        return

    if member.id in OWNER_IDS or member.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك إعطاء ميوت لهذا الشخص!", ephemeral=True)
        return

    try:
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"🔇 تم إعطاء ميوت للعضو {member.mention} لمدة **{minutes}** دقيقة. السبب: **{reason}**")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="unmute", description="رفع الميوت عن العضو")
@app_commands.describe(member="العضو المراد فك الميوت عنه")
async def slash_unmute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، لا تمتلك الصلاحية المطلوبة!", ephemeral=True)
        return

    try:
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 تم رفع الميوت عن العضو {member.mention} بنجاح.")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="kick", description="طرد عضو من السيرفر")
@app_commands.describe(member="العضو المراد طرده", reason="سبب الطرد")
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "لم يُذكر سبب"):
    if not interaction.user.guild_permissions.kick_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية طرد الأعضاء!", ephemeral=True)
        return

    if member.id in OWNER_IDS or member.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك طرد هذا العضو!", ephemeral=True)
        return

    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 تم طرد العضو {member.mention}. السبب: **{reason}**")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="حظر عضو من السيرفر نهائياً")
@app_commands.describe(member="العضو المراد حظره", reason="سبب الحظر")
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "لم يُذكر سبب"):
    if not interaction.user.guild_permissions.ban_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية الحظر!", ephemeral=True)
        return

    if member.id in OWNER_IDS or member.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك حظر هذا العضو!", ephemeral=True)
        return

    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 تم حظر العضو {member.mention} نهائياً. السبب: **{reason}**")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="unban", description="فك الحظر عن آيدي عضو حظر سابقاً")
@app_commands.describe(user_id="آيدي العضو المراد فك حظره")
async def slash_unban(interaction: discord.Interaction, user_id: str):
    if not interaction.user.guild_permissions.ban_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية التعامل مع البان!", ephemeral=True)
        return
    try:
        user = await bot.fetch_user(int(user_id))
        await interaction.guild.unban(user)
        await interaction.response.send_message(f"🔓 تم فك الحظر عن العضو **{user.name}** بنجاح.")
    except Exception as e:
        await interaction.response.send_message(f"❌ لم يتم العثور على العضو أو لم يتم حظره سابقاً: {e}", ephemeral=True)

@bot.tree.command(name="clear", description="مسح عدد محدد من الرسائل في القناة")
@app_commands.describe(amount="عدد الرسائل المراد مسحها (1-100)")
async def slash_clear(interaction: discord.Interaction, amount: int = 10):
    if not interaction.user.guild_permissions.manage_messages and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية إدارة الرسائل!", ephemeral=True)
        return

    amount = min(amount, 100)
    try:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 تم مسح **{len(deleted)}** رسالة بنجاح.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="warn", description="إضافة تحذير إداري لعضو")
@app_commands.describe(member="العضو", reason="سبب التحذير")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "تخطي القوانين"):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ لا تمتلك صلاحية إعطاء تحذيرات!", ephemeral=True)
        return

    user_warnings[member.id].append(reason)
    total_warns = len(user_warnings[member.id])
    await interaction.response.send_message(f"⚠️ تم تحذير {member.mention}. السبب: **{reason}** (إجمالي التحذيرات: **{total_warns}**)")

@bot.tree.command(name="warnings", description="عرض تحذيرات عضو معين")
@app_commands.describe(member="العضو المراد فحص تحذيراته")
async def warnings(interaction: discord.Interaction, member: discord.Member):
    warns = user_warnings[member.id]
    if not warns:
        await interaction.response.send_message(f"✅ العضو {member.mention} ليس لديه أي تحذيرات.", ephemeral=True)
        return

    warn_list = "\n".join([f"**{i+1}.** {w}" for i, w in enumerate(warns)])
    embed = discord.Embed(title=f"⚠️ تحذيرات {member.name}", description=warn_list, color=discord.Color.red())
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="clear_warnings", description="مسح تحذيرات عضو بالكامل")
@app_commands.describe(member="العضو")
async def clear_warnings(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.administrator and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ مخصص للإدارة فقط!", ephemeral=True)
        return

    user_warnings[member.id].clear()
    await interaction.response.send_message(f"🧹 تم مسح جميع تحذيرات العضو {member.mention} بنجاح.")

@bot.tree.command(name="lock", description="قفل القناة الحالية وإغلاق إمكانية الكتابة")
async def lock(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ لا تمتلك صلاحية إدارة القنوات!", ephemeral=True)
        return

    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=False)
    await interaction.response.send_message("🔒 تم قفل القناة بنجاح.")

@bot.tree.command(name="unlock", description="إعادة فتح القناة والسماح بالكتابة")
async def unlock(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_channels and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ لا تمتلك صلاحية إدارة القنوات!", ephemeral=True)
        return

    await interaction.channel.set_permissions(interaction.guild.default_role, send_messages=True)
    await interaction.response.send_message("🔓 تم إعادة فتح القناة بنجاح.")

@bot.tree.command(name="slowmode", description="تحديد الوضع البطئ للكتابة في القناة (بالثواني)")
@app_commands.describe(seconds="المدة بالثواني (0 لإلغائه)")
async def slowmode(interaction: discord.Interaction, seconds: int):
    if not interaction.user.guild_permissions.manage_channels and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ لا تمتلك الصلاحية المطلوبة!", ephemeral=True)
        return

    await interaction.channel.edit(slowmode_delay=seconds)
    if seconds == 0:
        await interaction.response.send_message("🚀 تم إلغاء الوضع البطئ بالقناة.")
    else:
        await interaction.response.send_message(f"⏱️ تم تحديد الوضع البطئ بـ **{seconds}** ثواني.")

# ==================== نظام التكتات الاحترافي (Tickets System) ====================

class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="إغلاق التكت", style=discord.ButtonStyle.danger, custom_id="confirm_close_btn")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        channel = interaction.channel

        embed = discord.Embed(
            title=f"🔒 تم إغلاق التكت بواسطة {interaction.user.name}",
            description="يمكنك الآن استخراج المحادثة أو فتح/حذف التكت عبر الخيارات التالية:",
            color=discord.Color.gold()
        )

        for target, overwrite in channel.overwrites.items():
            if target != guild.me and isinstance(target, discord.Member):
                overwrite.view_channel = False
                await channel.set_permissions(target, overwrite=overwrite)

        await interaction.response.edit_message(content="🔒 تم إغلاق القناة وتجريد العضو من صلاحية الرؤية.", embed=embed, view=TicketControlView())

    @discord.ui.button(label="إلغاء", style=discord.ButtonStyle.secondary, custom_id="cancel_close_btn")
    async def cancel_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id in OWNER_IDS or interaction.user.guild_permissions.manage_channels or any(role.name == "Admin" for role in interaction.user.roles):
            return True
        await interaction.response.send_message("❌ عذراً، هذه الأزرار مخصصة للإدارة فقط!", ephemeral=True)
        return False

    @discord.ui.button(label="تنزيل المحادثة (Transcript)", style=discord.ButtonStyle.secondary, custom_id="transcript_btn", emoji="📄")
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        messages = [f"[{msg.created_at.strftime('%Y-%m-%d %H:%M')}] {msg.author}: {msg.content}" async for msg in interaction.channel.history(limit=200, oldest_first=True)]
        file_content = "\n".join(messages)
        file = discord.File(io.BytesIO(file_content.encode('utf-8')), filename=f"{interaction.channel.name}-transcript.txt")
        await interaction.followup.send("📄 تفاصيل ومستند محادثة التكت:", file=file, ephemeral=True)

    @discord.ui.button(label="إعادة فتح", style=discord.ButtonStyle.success, custom_id="reopen_btn", emoji="🔓")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = interaction.channel
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Member):
                overwrite.view_channel = True
                await channel.set_permissions(target, overwrite=overwrite)
        await interaction.response.send_message("🔓 تم إعادة فتح التكت للعضو.")

    @discord.ui.button(label="حذف القناة", style=discord.ButtonStyle.danger, custom_id="delete_btn", emoji="⛔")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⛔ جاري حذف التكت والبيانات خلال ثوانٍ...")
        await interaction.channel.delete()

class CloseButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="طلب إغلاق التكت", style=discord.ButtonStyle.danger, custom_id="initial_close_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("هل أنت تأكد من رغبتك في إغلاق التكت؟", view=ConfirmCloseView(), ephemeral=True)

class TicketModal(discord.ui.Modal, title="إنشاء تكت دعم فني"):
    minecraft_name = discord.ui.TextInput(
        label="اسمك في ماينكرافت",
        placeholder="اكتب اسمك الخطي بالمود...",
        required=True,
        max_length=50
    )
    problem_desc = discord.ui.TextInput(
        label="تفاصيل المشكلة أو الاستفسار",
        placeholder="اشرح مشكلتك بالتفصيل هنا...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        member = interaction.user

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True)
        }

        admin_role = discord.utils.get(guild.roles, name="Admin")
        if admin_role:
            overwrites[admin_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        category = discord.utils.get(guild.categories, name="TICKETS")
        if not category:
            category = await guild.create_category("TICKETS")

        channel_name = f"ticket-{member.name}"
        ticket_channel = await guild.create_text_channel(channel_name, overwrites=overwrites, category=category)

        embed = discord.Embed(title="🎟️ تكت جديدة - الدعم الفني", color=discord.Color.green())
        embed.add_field(name="مرحباً بك", value=f"أهلاً {member.mention}، سيقوم فريق الدعم بالرد عليك قريباً.\nلإغلاق التكت اضغط على الزر بالأسفل.", inline=False)
        embed.add_field(name="اسم ماينكرافت", value=f"`{self.minecraft_name.value}`", inline=False)
        embed.add_field(name="وصف المشكلة", value=self.problem_desc.value, inline=False)
        
        await ticket_channel.send(content=f"{member.mention}", embed=embed, view=CloseButtonView())
        await interaction.response.send_message(f"✅ تم إنشاء التكت الخاص بك بنجاح: {ticket_channel.mention}", ephemeral=True)

class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="فتح تكت دعم فني", style=discord.ButtonStyle.primary, custom_id="create_ticket_btn", emoji="📩")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal())

@bot.tree.command(name="setup_tickets", description="إرسال قائمة ولوحة فتح التكتات (للإدارة فقط)")
async def setup_tickets(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة أو مالك البوت فقط!", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="🎫 VoidCraft Support Tickets",
        description="لفتح تكت جديدة والحصول على الدعم الفني المباشر، اضغط على الزر أدناه ملء البيانات المطلوبة.",
        color=discord.Color.blurple()
    )
    await interaction.channel.send(embed=embed, view=TicketButtonView())
    await interaction.response.send_message("✅ تم إرسال قائمة التكتات بنجاح!", ephemeral=True)

# ==================== الترحيب واختبار الرسائل ====================

@bot.tree.command(name="testwelcome", description="تجربة إرسال رسالة الترحيب")
async def testwelcome(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ هذا الأمر مخصص للإدارة فقط!", ephemeral=True)
        return

    member = interaction.user
    channel = discord.utils.get(interaction.guild.text_channels, name="👋-welcome-👋") or discord.utils.get(interaction.guild.text_channels, name="welcome")
    if not channel:
        await interaction.response.send_message("❌ لم أجد قناة باسم `welcome` أو `👋-welcome-👋`!", ephemeral=True)
        return

    member_number = interaction.guild.member_count
    embed = discord.Embed(
        title="✨ أهلاً بك في سيرفر VoidCraft! ✨",
        description=f"أنرت السيرفر يا {member.mention}!\nنتمنى لك أوقاتاً ممتعة معنا 🎮🔥",
        color=discord.Color.blurple()
    )
    avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
    embed.set_thumbnail(url=avatar_url)
    embed.set_footer(text=f"العضو رقم #{member_number}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    
    await channel.send(embed=embed)
    await interaction.response.send_message("✅ تم تجربة إرسال رسالة الترحيب بنجاح!", ephemeral=True)

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="👋-welcome-👋") or discord.utils.get(member.guild.text_channels, name="welcome")
    if channel:
        member_number = member.guild.member_count
        embed = discord.Embed(
            title="✨ أهلاً بك في سيرفر VoidCraft! ✨",
            description=f"أنرت السيرفر يا {member.mention}!\nنتمنى لك أوقاتاً ممتعة معنا 🎮🔥",
            color=discord.Color.blurple()
        )
        avatar_url = member.avatar.url if member.avatar else member.default_avatar.url
        embed.set_thumbnail(url=avatar_url)
        embed.set_footer(text=f"العضو رقم #{member_number}", icon_url=member.guild.icon.url if member.guild.icon else None)
        await channel.send(embed=embed)

    role = discord.utils.get(member.guild.roles, name="Player") or discord.utils.get(member.guild.roles, name="Member")
    if role:
        try:
            await member.add_roles(role)
        except Exception as e:
            print(f"خطأ في إعطاء الرتبة التلقائية: {e}")

# ==================== نظام الحماية الشامل وفحص المرفقات والروابط ====================

@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        return

    # استثناء الأونر والإداريين صاحب صلاحية Administrator من القيود
    if message.author.id in OWNER_IDS or message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    author_id = message.author.id
    current_time = time.time()
    content_lower = message.content.lower()

    ban_channel = (discord.utils.get(message.guild.text_channels, name="ban") or 
                   discord.utils.get(message.guild.text_channels, name="البان") or 
                   discord.utils.get(message.guild.text_channels, name="bans"))

    # 1. فحص المرفقات الحساسة أو الملفات الملغومة للحماية الفولاذية
    has_dangerous_file = False
    detected_file_name = ""
    for attachment in message.attachments:
        filename_lower = attachment.filename.lower()
        if any(filename_lower.endswith(ext) for ext in DANGEROUS_EXTENSIONS):
            has_dangerous_file = True
            detected_file_name = attachment.filename
            break

    if has_dangerous_file:
        try:
            await message.delete()
            punishment_time = timedelta(minutes=60)
            await message.author.timeout(punishment_time, reason=f"إرسال ملفات ملغومة/مشبوهة ({detected_file_name})")

            alert_text = (
                f"🚨 **[نظام الحماية الفولاذي - منع البرمجيات الخبيثة]**\n"
                f"👤 العضو: {message.author.mention} (`{message.author}`)\n"
                f"⚠️ التنبيه: تم اكتشاف محاولة إرسال ملف تنفيذي/مشبوه (`{detected_file_name}`) لحماية أجهزة الأعضاء!\n"
                f"🔇 العقوبة: تم مسح الملف وإعطاؤه ميوت تلقائي لمدة **ساعة كاملة (60 دقيقة)**."
            )
            if ban_channel:
                await ban_channel.send(alert_text)
            else:
                msg = await message.channel.send(alert_text)
                await discord.utils.sleep_until(time.time() + 7)
                await msg.delete()
        except Exception as e:
            print(f"خطأ في معالجة الملفات الخبيثة: {e}")
        return

    # 2. فحص الروابط المشبوهة مع السماح التام بروابط الميديا والفيديوهات/الريلز والسيرفر المعتمد
    is_discord_link = "discord.gg/" in content_lower or "discord.com/invite/" in content_lower
    is_my_server = MY_SERVER_INVITE.lower() in content_lower
    has_any_link = "http://" in content_lower or "https://" in content_lower or "www." in content_lower

    is_allowed_link = any(platform in content_lower for platform in ALLOWED_PLATFORMS) or is_my_server

    is_violating_link = False
    violation_reason = ""

    if is_discord_link and not is_my_server:
        is_violating_link = True
        violation_reason = "إرسال رابط سيرفر ديسكورد خارجي غير مسموح."
    elif has_any_link and not is_allowed_link:
        is_violating_link = True
        violation_reason = "إرسال روابط خارجية مشبوهة أو غير مصرح بها."

    if is_violating_link:
        try:
            await message.delete()
            half_hour = timedelta(minutes=30)
            await message.author.timeout(half_hour, reason=violation_reason)

            alert_text = (
                f"🚨 **[نظام جدار الحماية - فلترة الروابط]**\n"
                f"👤 العضو: {message.author.mention} (`{message.author}`)\n"
                f"⚠️ التنبيه: {violation_reason}\n"
                f"💡 (ملاحظة: المسموح فقط هو روابط YouTube Shorts/Reels/TikTok/Instagram/Snapchat والسيرفر الرسمي).\n"
                f"🔇 العقوبة: تم إعطاؤه ميوت تلقائي لمدة **30 دقيقة** وحذف الرابط."
            )
            if ban_channel:
                await ban_channel.send(alert_text)
            else:
                msg = await message.channel.send(alert_text)
                await discord.utils.sleep_until(time.time() + 6)
                await msg.delete()
        except Exception as e:
            print(f"خطأ في معالجة الروابط المخالفة: {e}")
        return

    # 3. مكافحة السبام والتكرار السريع للرسائل (Anti-Spam)
    if current_time - last_message_time[author_id] < 2.5 and content_lower == last_message_content[author_id]:
        try:
            await message.delete()
            user_violation_count[author_id] += 1
            punish_minutes = user_violation_count[author_id] * 2
            
            duration = timedelta(minutes=punish_minutes)
            await message.author.timeout(duration, reason=f"مكافحة السبام وتكرار الرسائل (المخالفة #{user_violation_count[author_id]})")
            
            alert_text = (
                f"⚠️ **[نظام مكافحة السبام التلقائي]**\n"
                f"👤 العضو: {message.author.mention}\n"
                f"💬 المخالفة: تكرار إرسال الرسائل المتشابهة بوقت قصير جداً.\n"
                f"🔇 العقوبة المتصاعدة: تم إعطاؤه ميوت لمدة **{punish_minutes} دقيقة**."
            )
            if ban_channel:
                await ban_channel.send(alert_text)
            else:
                msg = await message.channel.send(alert_text)
                await discord.utils.sleep_until(time.time() + 5)
                await msg.delete()
        except Exception as e:
            print(f"خطأ في معالجة السبام: {e}")
        return

    last_message_time[author_id] = current_time
    last_message_content[author_id] = content_lower

    # 4. نظام الخبرة (XP) والتفاعل
    user_xp[author_id] += 10
    current_xp = user_xp[author_id]
    level = current_xp // 100

    if current_xp > 0 and current_xp % 100 == 0:
        levels_channel = discord.utils.get(message.guild.text_channels, name="levels") or discord.utils.get(message.guild.text_channels, name="المستويات")
        if levels_channel:
            await levels_channel.send(f"🎉 مبروك {message.author.mention}! لقد وصلت إلى **Level {level}**!")

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
    await interaction.response.send_message(embed=embed)

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