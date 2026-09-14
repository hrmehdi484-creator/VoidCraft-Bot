import discord
from discord.ext import commands
import io
import time
from datetime import timedelta
from collections import defaultdict
import threading
import os
from flask import Flask

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# إزالة أمر help القديم
bot.remove_command('help')

# تخزين مؤقت للـ XP، السبام، والعقوبات المتصاعدة
user_xp = defaultdict(int)
last_message_time = defaultdict(float)
last_message_content = defaultdict(str)
user_violation_count = defaultdict(int)

# 🛡️ آيدي حسابك الخاص
OWNER_IDS = [1335193543660273716]

# 🔗 رابط سيرفر ديسكورد الخاص بك (ليُستثنى من الحذف التلقائي)
MY_SERVER_INVITE = "discord.gg/voidcraft"

@bot.event
async def on_ready():
    print(f"تم تسجيل الدخول بنجاح باسم: {bot.user} - نظام الحماية والأوامر يعمل بكفاءة! 🛡️")
    try:
        # مزامنة أوامر السلاش (Slash Commands) مع ديسكورد تلقائياً
        synced = await bot.tree.sync()
        print(f"تم مزامنة {len(synced)} أمر (Slash Command) بنجاح.")
    except Exception as e:
        print(f"خطأ في مزامنة الأوامر: {e}")

@bot.tree.command(name="ping", description="فحص سرعة استجابة البوت")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! 🏓 سرعة استجابة البوت: {round(bot.latency * 1000)}ms", ephemeral=True)


# ==================== أوامر الإدارة والحماية (Slash Commands) ====================

@bot.tree.command(name="mute", description="إعطاء ميوت (تقييد) لعضو معين في السيرفر")
@discord.app_commands.describe(member="العضو المراد إعطاؤه ميوت", minutes="مدة الميوت بالدقائق (الافتراضي 60)", reason="سبب الميوت")
async def slash_mute(interaction: discord.Interaction, member: discord.Member, minutes: int = 60, reason: str = "لم يُذكر سبب"):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية استخدام هذا الأمر!", ephemeral=True)
        return

    if member.id in OWNER_IDS or member.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك إعطاء ميوت لهذا الشخص!", ephemeral=True)
        return

    try:
        duration = timedelta(minutes=minutes)
        await member.timeout(duration, reason=reason)
        await interaction.response.send_message(f"🔇 تم إعطاء ميوت للعضو {member.mention} لمدة {minutes} دقيقة. السبب: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="unmute", description="رفع الميوت عن العضو")
@discord.app_commands.describe(member="العضو المراد رفع الميوت عنه")
async def slash_unmute(interaction: discord.Interaction, member: discord.Member):
    if not interaction.user.guild_permissions.moderate_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية استخدام هذا الأمر!", ephemeral=True)
        return

    try:
        await member.timeout(None)
        await interaction.response.send_message(f"🔊 تم رفع الميوت عن العضو {member.mention} بنجاح.")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="kick", description="طرد عضو من السيرفر")
@discord.app_commands.describe(member="العضو المراد طرده", reason="السبب")
async def slash_kick(interaction: discord.Interaction, member: discord.Member, reason: str = "لم يُذكر سبب"):
    if not interaction.user.guild_permissions.kick_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية طرد الأعضاء!", ephemeral=True)
        return

    if member.id in OWNER_IDS or member.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك طرد هذا الشخص!", ephemeral=True)
        return

    try:
        await member.kick(reason=reason)
        await interaction.response.send_message(f"👢 تم طرد العضو {member.mention}. السبب: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="ban", description="حظر عضو من السيرفر نهائياً")
@discord.app_commands.describe(member="العضو المراد حظره", reason="السبب")
async def slash_ban(interaction: discord.Interaction, member: discord.Member, reason: str = "لم يُذكر سبب"):
    if not interaction.user.guild_permissions.ban_members and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية حظر الأعضاء!", ephemeral=True)
        return

    if member.id in OWNER_IDS or member.guild_permissions.administrator:
        await interaction.response.send_message("❌ لا يمكنك حظر هذا الشخص!", ephemeral=True)
        return

    try:
        await member.ban(reason=reason)
        await interaction.response.send_message(f"🔨 تم حظر العضو {member.mention} نهائياً. السبب: {reason}")
    except Exception as e:
        await interaction.response.send_message(f"❌ حدث خطأ: {e}", ephemeral=True)

@bot.tree.command(name="clear", description="مسح عدد من الرسائل في الشات (بحد أقصى 100)")
@discord.app_commands.describe(amount="عدد الرسائل المراد مسحها")
async def slash_clear(interaction: discord.Interaction, amount: int = 10):
    if not interaction.user.guild_permissions.manage_messages and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ عذراً، لا تمتلك صلاحية إدارة الرسائل!", ephemeral=True)
        return

    if amount > 100:
        amount = 100

    try:
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amount)
        await interaction.followup.send(f"🧹 تم مسح **{len(deleted)}** رسالة بنجاح.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ حدث خطأ: {e}", ephemeral=True)


# ==================== نظام التكتات (Tickets) ====================

class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="confirm_close_btn")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        channel = interaction.channel

        embed = discord.Embed(
            title=f"Ticket Closed by {interaction.user.name}",
            description="Support team ticket controls",
            color=discord.Color.yellow()
        )
        
        for target, overwrite in channel.overwrites.items():
            if target != guild.me and isinstance(target, discord.Member):
                overwrite.view_channel = False
                await channel.set_permissions(target, overwrite=overwrite)

        await interaction.response.edit_message(content="🔒 تم إغلاق التكت بنجاح.", embed=embed, view=TicketControlView())

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id="cancel_close_btn")
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

    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, custom_id="transcript_btn", emoji="📄")
    async def transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        messages = [f"{msg.author}: {msg.content}" async for msg in interaction.channel.history(limit=100, oldest_first=True)]
        file_content = "\n".join(messages)
        file = discord.File(io.BytesIO(file_content.encode('utf-8')), filename=f"{interaction.channel.name}-transcript.txt")
        await interaction.followup.send("📄 ملف محادثة التكت:", file=file, ephemeral=True)

    @discord.ui.button(label="Open", style=discord.ButtonStyle.success, custom_id="reopen_btn", emoji="🔓")
    async def reopen(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        channel = interaction.channel
        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Member):
                overwrite.view_channel = True
                await channel.set_permissions(target, overwrite=overwrite)
        await interaction.response.send_message("🔓 تم إعادة فتح التكت.")

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, custom_id="delete_btn", emoji="⛔")
    async def delete_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⛔ جاري حذف التكت نهائياً...")
        await interaction.channel.delete()

class CloseButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, custom_id="initial_close_btn", emoji="🔒")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Are you sure you would like to close this ticket?", view=ConfirmCloseView(), ephemeral=True)

class TicketModal(discord.ui.Modal, title="إنشاء تكت دعم فني"):
    minecraft_name = discord.ui.TextInput(
        label="اسمك في ماينكرافت",
        placeholder="اكتب اسمك هنا...",
        required=True,
        max_length=50
    )
    
    problem_desc = discord.ui.TextInput(
        label="ما هي مشكلتك؟",
        placeholder="اشرح مشكلتك هنا...",
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

        embed = discord.Embed(title="🎟️ تكت جديدة", color=discord.Color.green())
        embed.add_field(name="Welcome", value=f"Support will be with you shortly.\nTo close this press the close button", inline=False)
        embed.add_field(name="اسم ماينكرافت", value=self.minecraft_name.value, inline=False)
        embed.add_field(name="المشكلة", value=self.problem_desc.value, inline=False)
        
        await ticket_channel.send(content=f"{member.mention}", embed=embed, view=CloseButtonView())
        await interaction.response.send_message(f"✅ تم إنشاء التكت الخاص بك: {ticket_channel.mention}", ephemeral=True)

class TicketButtonView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Create ticket", style=discord.ButtonStyle.primary, custom_id="create_ticket_btn", emoji="📩")
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketModal())

@bot.tree.command(name="setup_tickets", description="إرسال لوحة أزرار إنشاء التكتات (للإدارة فقط)")
async def setup_tickets(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.administrator and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ هذا الأمر مخصص للأونر أو الإدارة فقط!", ephemeral=True)
        return
        
    embed = discord.Embed(
        title="ticketsVoidCraft.",
        description="To create a ticket use the Create ticket button",
        color=discord.Color.blurple()
    )
    await interaction.channel.send(embed=embed, view=TicketButtonView())
    await interaction.response.send_message("✅ تم إرسال قائمة التكتات بنجاح!", ephemeral=True)


# ==================== نظام الترحيب التجريبي ====================

@bot.tree.command(name="testwelcome", description="تجربة إرسال رسالة الترحيب في القناة المخصصة")
async def testwelcome(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild and interaction.user.id not in OWNER_IDS:
        await interaction.response.send_message("❌ هذا الأمر مخصص للأونر أو الإدارة فقط!", ephemeral=True)
        return

    member = interaction.user
    channel = discord.utils.get(interaction.guild.text_channels, name="👋-welcome-👋")
    if not channel:
        channel = discord.utils.get(interaction.guild.text_channels, name="welcome")
        if not channel:
            await interaction.response.send_message("❌ لم أجد قناة ترحيب باسم مناسب!", ephemeral=True)
            return

    member_number = interaction.guild.member_count
    embed = discord.Embed(
        title="✨ منور سيرفر VoidCraft! ✨",
        description=f"أهلاً بك يا {member.mention} في سيرفرنا!\nنحن سعداء جداً بانضمامك إلينا. 🎮🔥",
        color=discord.Color.blurple()
    )
    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)
    else:
        embed.set_thumbnail(url=member.default_avatar.url)
        
    embed.set_footer(text=f"Member #{member_number}", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
    
    await channel.send(embed=embed)
    await interaction.response.send_message("✅ تم إرسال رسالة الترحيب التجريبية بنجاح!", ephemeral=True)


# ==================== الأحداث التلقائية (الترحيب والحماية) ====================

@bot.event
async def on_member_join(member):
    channel = discord.utils.get(member.guild.text_channels, name="👋-welcome-👋")
    if not channel:
        channel = discord.utils.get(member.guild.text_channels, name="welcome")
        
    if channel:
        member_number = member.guild.member_count
        embed = discord.Embed(
            title="✨ منور سيرفر VoidCraft! ✨",
            description=f"أهلاً بك يا {member.mention} في سيرفرنا!\nنحن سعداء جداً بانضمامك إلينا. 🎮🔥",
            color=discord.Color.blurple()
        )
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)
        else:
            embed.set_thumbnail(url=member.default_avatar.url)
            
        embed.set_footer(text=f"Member #{member_number}", icon_url=member.guild.icon.url if member.guild.icon else None)
        await channel.send(embed=embed)

    role = discord.utils.get(member.guild.roles, name="Player")
    if role:
        try:
            await member.add_roles(role)
        except Exception as e:
            print(f"خطأ في إعطاء الرتبة: {e}")


# ==================== نظام الحماية والروابط والسبام ====================

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

    ban_channel = discord.utils.get(message.guild.text_channels, name="ban")
    if not ban_channel:
        ban_channel = discord.utils.get(message.guild.text_channels, name="البان")
    if not ban_channel:
        ban_channel = discord.utils.get(message.guild.text_channels, name="bans")

    allowed_platforms = ["youtube.com", "youtu.be", "tiktok.com", "instagram.com", "snapchat.com"]
    is_allowed_platform = any(platform in content_lower for platform in allowed_platforms)

    is_discord_link = "discord.gg/" in content_lower or "discord.com/invite/" in content_lower
    is_my_server = MY_SERVER_INVITE.lower() in content_lower
    has_links = "http://" in content_lower or "https://" in content_lower or "www." in content_lower

    is_violating_link = False
    violation_reason = ""

    if is_discord_link and not is_my_server:
        is_violating_link = True
        violation_reason = "إرسال رابط ديسكورد خارجي غير مسموح."
    elif has_links and not is_allowed_platform and not is_my_server:
        is_violating_link = True
        violation_reason = "إرسال روابط مشبوهة أو منصات غير مصرح بها."

    has_suspicious_attachments = False
    for attachment in message.attachments:
        if any(attachment.filename.lower().endswith(ext) for ext in ['.exe', '.scr', '.bat', '.cmd', '.zip', '.rar']):
            has_suspicious_attachments = True
            break

    if is_violating_link or has_suspicious_attachments:
        try:
            await message.delete()
            half_hour = timedelta(minutes=30)
            await message.author.timeout(half_hour, reason=violation_reason or "إرسال ملفات أو صور مشبوهة/مهكرة.")
            
            alert_text = (
                f"🚨 **[نظام الحماية والروابط]**\n"
                f"👤 العضو: {message.author.mention} (`{message.author}`)\n"
                f"⚠️ التنبيه: ممنوع إرسال روابط ديسكورد خارجية أو روابط مشبوهة أو صور/ملفات مهكرة!\n"
                f"🔇 العقوبة: تم إعطاؤه ميوت لمدة **نصف ساعة (30 دقيقة)** وحذف المخالفة."
            )
            
            if ban_channel:
                await ban_channel.send(alert_text)
            else:
                fallback_msg = await message.channel.send(alert_text)
                await discord.utils.sleep_until(time.time() + 6)
                await fallback_msg.delete()
                
        except Exception as e:
            print(f"خطأ في معالجة الروابط المخالفة: {e}")
        return

    if current_time - last_message_time[author_id] < 3.0 and content_lower == last_message_content[author_id]:
        try:
            await message.delete()
            
            user_violation_count[author_id] += 1
            punish_minutes = user_violation_count[author_id]
            
            duration = timedelta(minutes=punish_minutes)
            await message.author.timeout(duration, reason=f"سبام وتكرار رسائل (المخالفة رقم {punish_minutes})")
            
            alert_text = (
                f"⚠️ **[نظام مكافحة السبام التلقائي]**\n"
                f"👤 العضو: {message.author.mention}\n"
                f"💬 المخالفة: تكرار السبام والرسائل المتلاحقة.\n"
                f"🔇 العقوبة المتصاعدة: تم إعطاؤه ميوت لمدة **{punish_minutes} دقيقة**."
            )
            
            if ban_channel:
                await ban_channel.send(alert_text)
            else:
                fallback_msg = await message.channel.send(alert_text)
                await discord.utils.sleep_until(time.time() + 5)
                await fallback_msg.delete()
                
        except Exception as e:
            print(f"خطأ في معالجة السبام: {e}")
        return

    last_message_time[author_id] = current_time
    last_message_content[author_id] = content_lower

    user_xp[author_id] += 10  
    current_xp = user_xp[author_id]
    level = current_xp // 100

    if current_xp % 100 == 0:
        levels_channel = discord.utils.get(message.guild.text_channels, name="levels")
        if levels_channel:
            await levels_channel.send(f"🎉 Congratulations {message.author.mention}! You've reached **Level {level}**!")
        else:
            await message.channel.send(f"🎉 Congratulations {message.author.mention}! You've reached **Level {level}**!")

    await bot.process_commands(message)


# ==================== أمر المستوى للأعضاء ====================

@bot.tree.command(name="level", description="عرض مستواك الحالي ونقاط الخبرة (XP)")
@discord.app_commands.describe(member="العضو المراد عرض مستواه (اختياري)")
async def slash_level(interaction: discord.Interaction, member: discord.Member = None):
    target = member or interaction.user
    xp = user_xp[target.id]
    lvl = xp // 100
    await interaction.response.send_message(f"📊 العضو {target.mention} لديه **{xp} XP** ويقع في **Level {lvl}**!")


# ==================== خادم الويب وتشغيل البوت ====================

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_bot():
    token = os.environ.get("DISCORD_TOKEN")
    if token:
        bot.run(token)
    else:
        print("❌ خطأ: لم يتم العثور على المتغير DISCORD_TOKEN في البيئة!")

bot_thread = threading.Thread(target=run_bot)
bot_thread.daemon = Timeouts = True
bot_thread.daemon = True
bot_thread.start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)