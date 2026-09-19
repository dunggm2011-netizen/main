import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─────────────────────────────────────────────
# TỰ ĐỘNG GIẢI NÉN modules.zip NẾU THIẾU modules/
# ─────────────────────────────────────────────
import zipfile
if not os.path.isdir("modules") and os.path.isfile("modules.zip"):
    try:
        os.makedirs("modules", exist_ok=True)
        with zipfile.ZipFile("modules.zip", "r") as _z:
            _names = _z.namelist()
            if any(n.startswith("modules/") for n in _names):
                _z.extractall(".")
            elif any(n.startswith("modul/modules/") for n in _names):
                _z.extractall(".")
                if os.path.isdir("modul/modules"):
                    os.rename("modul/modules", "modules")
            else:
                for n in _names:
                    _z.extract(n, "modules")
        print("[INIT] Đã giải nén modules.zip → modules/")
    except Exception as _e:
        print(f"[INIT] Lỗi giải nén: {_e}")

# ─────────────────────────────────────────────
# FIX EVENT LOOP CHO PYTHON 3.10+ TRÊN RENDER
# ─────────────────────────────────────────────
import asyncio
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

# ─────────────────────────────────────────────
# FLASK HEALTH SERVER CHO RENDER WEB SERVICE
# ─────────────────────────────────────────────
from flask import Flask
import threading as _threading

_flask_app = Flask(__name__)

@_flask_app.route("/")
def _health_root():
    return "OK - BOT RUNNING", 200

@_flask_app.route("/health")
def _health():
    return {"status": "alive", "bot": "UNIFIED MULTI-BOT"}, 200

def _run_flask():
    port = int(os.environ.get("PORT", 10000))
    _flask_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

_threading.Thread(target=_run_flask, daemon=True).start()
print(f"[INIT] Flask health server started on PORT {os.environ.get('PORT', 10000)}")

"""
UNIFIED MULTI-BOT — KEY SYSTEM + ADMIN + RANKING
BUMX | TDS | TTC | TTC PRO5 | XWORLD
"""
# ─────────────────────────────────────────────
#  CẤU HÌNH — SỬA Ở ĐÂY
# ─────────────────────────────────────────────
BOT_TOKEN = "8716000424:AAFBWxHpPiUPTyzEsNUGD-xa6Y2bd0n0Alw"

# Admin chính (Telegram ID số) — ID của bạn
MAIN_ADMINS = [7564889663]

# Tên admin phân phối key (hiển thị cho user)
DIST_ADMINS_NAMES = ["@tbtool88"]
# ─────────────────────────────────────────────

import functools
import logging
import threading
import time as _time
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.error import TimedOut, NetworkError, RetryAfter
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.request import HTTPXRequest
from modules import bumx, tds, ttc, ttcpro5, xworld
from modules import system_db as db
from modules import admin_handlers as adm
from modules import user_handlers as usr

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# Inject configs
for mod in (bumx, tds, ttc, ttcpro5, xworld):
    mod.BOT_TOKEN = BOT_TOKEN
adm.MAIN_ADMINS = MAIN_ADMINS
usr.MAIN_ADMINS = MAIN_ADMINS
usr.DIST_ADMINS_NAMES = DIST_ADMINS_NAMES

# Inject MAIN_ADMINS vào key_system
from modules import key_system as _ks
if MAIN_ADMINS:
    _ks.MAIN_ADMIN_ID = MAIN_ADMINS[0]

# ── Reply keyboard ────────────────────────────────────
def main_rkb():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("💸 BUMX"),       KeyboardButton("🔄 TDS")],
            [KeyboardButton("🤝 TTC"),        KeyboardButton("⚡ PRO5")],
            [KeyboardButton("🎮 XWorld"),     KeyboardButton("📊 Trạng thái")],
            [KeyboardButton("🚀 Đồng Bộ"),   KeyboardButton("❓ Help")],
            [KeyboardButton("🏆 Bảng XH"),   KeyboardButton("👛 Tài khoản")],
        ],
        resize_keyboard=True,
    )

NAV_MAP = {
    "💸 BUMX": bumx, "🔄 TDS": tds,
    "🤝 TTC": ttc, "⚡ PRO5": ttcpro5, "🎮 XWorld": xworld,
}

# ── Access guard ─────────────────────────────────────
def require_access(func):
    @functools.wraps(func)
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = update.effective_user.id
        access = db.check_access(uid, MAIN_ADMINS)
        if not access["ok"]:
            await usr.show_home(update, ctx)
            return
        return await func(update, ctx)
    return wrapper

async def _handle_as_callback(update: Update, ctx, cb_data: str):
    class _FakeQuery:
        def __init__(self):
            self.data      = cb_data
            self.from_user = update.effective_user
            self.message   = update.message
        async def answer(self, *a, **kw): pass
        async def edit_message_text(self, text="", **kw):
            try:
                await update.message.reply_text(text, **{k:v for k,v in kw.items()
                    if k in ('parse_mode','reply_markup','disable_web_page_preview')})
            except Exception: pass

    class _FakeUpdate:
        def __init__(self):
            self.callback_query = _FakeQuery()
            self.effective_user = update.effective_user
            self.message        = update.message

    await usr.handle_callback(_FakeUpdate(), ctx)

def safe(func):
    @functools.wraps(func)
    async def wrap(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        for attempt in range(2):
            try:
                return await func(update, ctx)
            except RetryAfter as e:
                await asyncio.sleep(e.retry_after)
            except (TimedOut, NetworkError) as e:
                if attempt == 0: await asyncio.sleep(2)
                else: log.warning(f"Timeout: {e}")
            except Exception as e:
                log.error(f"Handler lỗi: {e}", exc_info=True); break
    return wrap

# ── /start ────────────────────────────────────────────
@safe
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if ctx.args and ctx.args[0].startswith("REF"):
        db.register_referral(uid, ctx.args[0])
    await usr.show_home(update, ctx)

@safe
async def cmd_menu(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await usr.show_home(update, ctx)

@safe
async def cmd_huy(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await usr.cmd_huy(update, ctx)

# ── Text handler ─────────────────────────────────────
@safe
async def global_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    uid  = update.effective_user.id

    # Debounce nút bấm
    import time as _t
    _last_key = f"_last_btn_{uid}"
    _now = _t.time()
    _last_time = ctx.user_data.get(_last_key, 0)
    _MENU_BTNS = {
        "🔑 Nhập Key VIP","🔌 Dùng API Key","🔗 Lấy Key Free","💰 Giá Key",
        "💸 BUMX","🔄 TDS","🤝 TTC","⚡ PRO5","🎮 XWorld","📊 Trạng thái",
        "🚀 Đồng Bộ","❓ Help","🏆 Bảng xếp hạng","🏅 Bảng xếp hạng",
        "👛 Tài khoản","💳 Nạp tiền","🔗 Giới thiệu","🛠 Admin Panel",
    }
    if text in _MENU_BTNS:
        if _now - _last_time < 1.5:
            return
        ctx.user_data[_last_key] = _now

    NOKEY_ACTIONS = {
        "🔑 Nhập Key VIP":  "usr_enter_key",
        "🔌 Dùng API Key":  "usr_use_api",
        "🔗 Lấy Key Free":  "usr_free_key",
        "💰 Giá Key":       "usr_key_price",
    }
    if text in NOKEY_ACTIONS:
        await _handle_as_callback(update, ctx, NOKEY_ACTIONS[text]); return

    # Nút menu chính
    if text == "🛠 Admin Panel":
        await adm.show_admin_panel(update, ctx); return
    if text == "💳 Nạp tiền":
        await _handle_as_callback(update, ctx, "usr_deposit"); return
    if text == "🔗 Giới thiệu":
        await _handle_as_callback(update, ctx, "usr_referral"); return
    if text == "🏆 Bảng xếp hạng" or text == "🏅 Bảng xếp hạng":
        await usr.show_ranking_menu_msg(update, ctx); return
    if text == "👛 Tài khoản":
        await _handle_as_callback(update, ctx, "usr_account"); return
    if text == "🔑 Key & Nạp":
        await _handle_as_callback(update, ctx, "usr_account"); return

    if text in NAV_MAP:
        access = db.check_access(uid, MAIN_ADMINS)
        if not access["ok"]:
            await usr.show_home(update, ctx); return
        await NAV_MAP[text].cmd_entry(update, ctx); return

    if text == "📊 Trạng thái":
        access = db.check_access(uid, MAIN_ADMINS)
        if not access["ok"]:
            await usr.show_home(update, ctx); return
        await show_all_status(update, ctx); return

    if text == "🚀 Đồng Bộ":
        access = db.check_access(uid, MAIN_ADMINS)
        if not access["ok"]:
            await usr.show_home(update, ctx); return
        await show_dong_bo(update, ctx); return

    if text == "❓ Help":
        await show_help(update, ctx); return

    if text == "🏆 Bảng XH":
        await usr.show_ranking_menu_msg(update, ctx); return

    # ── Gọi lần lượt tất cả handlers ──
    if await adm.handle_message(update, ctx): return
    if await usr.handle_message(update, ctx): return
    if await bumx.handle_message(update, ctx): return
    if await tds.handle_message(update, ctx): return
    if await ttc.handle_message(update, ctx): return
    if await ttcpro5.handle_message(update, ctx): return
    if hasattr(xworld, 'handle_message'):
        if await xworld.handle_message(update, ctx): return

    await update.message.reply_text(
        "❓ Không rõ lệnh. Chọn từ menu 👇", reply_markup=main_rkb())

# ── Callback handler ─────────────────────────────────
@safe
async def global_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data  = query.data
    uid   = query.from_user.id

    if data == "back_home":
        await query.answer()
        await usr.show_home(update, ctx); return

    if data in ("nav_bumx","nav_tds","nav_ttc","nav_pro5","nav_xworld"):
        await query.answer()
        access = db.check_access(uid, MAIN_ADMINS)
        if not access["ok"]:
            await usr.show_home(update, ctx); return
        mod_map = {"nav_bumx":bumx,"nav_tds":tds,"nav_ttc":ttc,"nav_pro5":ttcpro5,"nav_xworld":xworld}
        await mod_map[data].cmd_entry(update, ctx); return

    if data == "nav_status":
        await query.answer()
        await show_all_status_cb(query, ctx); return

    if data == "nav_dongbo":
        await query.answer()
        await show_dong_bo_cb(query, ctx); return

    if data == "nav_help":
        await query.answer()
        await show_help_cb(query); return

    if data in ("dongbo_start_all","dongbo_stop_all") or \
       data.startswith("dongbo_start_") or data.startswith("dongbo_stop_"):
        await query.answer()
        await handle_dongbo_callback(update, ctx, data); return

    if data.startswith("adm_"):
        result = await adm.handle_callback(update, ctx)
        if result: return

    if await usr.handle_callback(update, ctx): return

    for mod in (bumx, tds, ttc, ttcpro5, xworld):
        try:
            if await mod.handle_callback(update, ctx): return
        except (TimedOut, NetworkError) as e:
            try: await query.answer("⚠️ Mạng chậm!")
            except: pass
            return
        except Exception as e:
            log.error(f"Callback {data}: {e}", exc_info=True); return

    try: await query.answer()
    except: pass

# ── Photo handler ─────────────────────────────────────
@safe
async def global_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    state = ctx.user_data.get("usr_state")
    if state in (usr.ST_DEP_IMG, usr.ST_CANCEL_IMG):
        await usr.handle_message(update, ctx)

# ══════════════════════════════════════════════════════
#  TRẠNG THÁI & ĐỒNG BỘ
# ══════════════════════════════════════════════════════
async def show_all_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    lines = ["📊 <b>TRẠNG THÁI TẤT CẢ BOT</b>\n"]
    b_run = uid in bumx.running_tasks and not bumx.running_tasks[uid].done()
    b_st  = bumx.load_stats(uid); b_cfg = bumx.load_config(uid)
    lines.append(f"{'🟢' if b_run else '🔴'} <b>BUMX</b> — {'✅' if b_cfg.get('authorization') else '❌'} Auth | 🍪 {len(bumx.load_cookies(uid))}\n   " + (f"✅ {b_st.get('job_done',0)} job | 💵 {b_st.get('earned',0)}₫" if b_st else "Chưa chạy"))
    ts = tds.get_session(uid); t_run = ts.get("running",False)
    lines.append(f"{'🟢' if t_run else '🔴'} <b>TDS</b> — 👥 {len(ts.get('accounts',[]))} acc")
    tc = ttc.get_state(uid); tc_run = tc.get("running",False)
    lines.append(f"{'🟢' if tc_run else '🔴'} <b>TTC</b> — 👥 {len(ttc.load_accounts(uid))} acc")
    pu = ttcpro5.get_user(uid); p_run = pu.get("running",False)
    lines.append(f"{'🟢' if p_run else '🔴'} <b>TTC PRO5</b> — 🍪 {len(pu.get('cookies',[]))} page")
    xs = xworld.get_sess(uid)
    lines.append(f"{'🟢' if xs['vtd'].get('running') or xs['vth'].get('running') else '🔴'} <b>XWorld</b> — VTD:{'🟢' if xs['vtd'].get('running') else '🔴'} VTH:{'🟢' if xs['vth'].get('running') else '🔴'}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=main_rkb())

async def show_all_status_cb(query, ctx): pass

def _can_start(uid):
    b_cfg = bumx.load_config(uid)
    b_ck  = [c for c in bumx.load_cookies(uid) if c.get("enabled",True)]
    ts    = tds.get_session(uid)
    t_act = [a for a in ts.get("accounts",[]) if a.get("enabled",True)]
    tc_ac = ttc.get_active_accounts(uid); tc_cf = ttc.load_config(uid)
    pu    = ttcpro5.get_user(uid)
    ck_en = pu.get("cookie_enabled",[])
    p_cks = pu.get("cookies",[])
    p_act = [ck for i,ck in enumerate(p_cks) if (ck_en[i] if i<len(ck_en) else True)]
    return {
        "bumx":  bool(b_cfg.get("authorization")) and bool(b_ck),
        "tds":   bool(t_act) and bool(ts.get("settings")),
        "ttc":   bool(tc_ac) and bool(tc_cf),
        "pro5":  bool(pu.get("ttc_token")) and bool(p_act),
        "xworld": False,
    }

def _get_bot_status(uid):
    return {
        "bumx":   uid in bumx.running_tasks and not bumx.running_tasks[uid].done(),
        "tds":    tds.get_session(uid).get("running",False),
        "ttc":    ttc.get_state(uid).get("running",False),
        "pro5":   ttcpro5.get_user(uid).get("running",False),
        "xworld": False,
    }

BOT_LABELS = {"bumx":"💸 BUMX","tds":"🔄 TDS","ttc":"🤝 TTC","pro5":"⚡ PRO5"}

async def show_dong_bo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    status = _get_bot_status(uid); can = _can_start(uid)
    lines = ["🚀 <b>ĐỒNG BỘ</b>\n"]
    for key, label in BOT_LABELS.items():
        st = "🟢 Đang chạy" if status[key] else "🔴 Dừng"
        lines.append(f"{label}: {st} | {'✅' if can[key] else '⚠️ Chưa cấu hình'}")
    rows = [
        [InlineKeyboardButton("▶️ Chạy TẤT CẢ", callback_data="dongbo_start_all"),
         InlineKeyboardButton("⏹ Dừng TẤT CẢ",  callback_data="dongbo_stop_all")],
        [InlineKeyboardButton("──────────────", callback_data="noop")],
    ]
    for key, label in BOT_LABELS.items():
        if status[key]:
            rows.append([InlineKeyboardButton(f"⏹ Dừng {label}", callback_data=f"dongbo_stop_{key}")])
        elif can[key]:
            rows.append([InlineKeyboardButton(f"▶️ Chạy {label}", callback_data=f"dongbo_start_{key}")])
        else:
            rows.append([InlineKeyboardButton(f"⚠️ {label} chưa cấu hình", callback_data="noop")])
    rows.append([InlineKeyboardButton("🔙 Quay lại", callback_data="back_home")])
    await update.message.reply_text("\n".join(lines), parse_mode="HTML", reply_markup=InlineKeyboardMarkup(rows))

async def show_dong_bo_cb(query, ctx): pass

async def handle_dongbo_callback(update, ctx, data):
    query = update.callback_query
    uid = query.from_user.id
    loop = asyncio.get_event_loop()
    results = []

    async def _start(key):
        can = _can_start(uid); status = _get_bot_status(uid)
        if status.get(key): return f"⚠️ {BOT_LABELS.get(key,key)} đang chạy"
        if not can.get(key): return f"⚠️ {BOT_LABELS.get(key,key)} chưa cấu hình"
        if key == "bumx":
            stop_ev = threading.Event(); bumx.stop_flags[uid] = stop_ev
            task = asyncio.create_task(bumx.worker(uid, ctx.application))
            bumx.running_tasks[uid] = task
            return f"✅ BUMX khởi động"
        elif key == "tds":
            sess = tds.get_session(uid); sess["stop_event"] = threading.Event()
            sess["running"] = True; sess["logs"] = []
            def _sfn(u,m): asyncio.run_coroutine_threadsafe(ctx.application.bot.send_message(chat_id=u,text=m,parse_mode="HTML"),loop)
            t = threading.Thread(target=tds.worker,args=(uid,_sfn),daemon=True); sess["thread"]=t; t.start()
            return f"✅ TDS khởi động ({len([a for a in sess.get('accounts',[]) if a.get('enabled',True)])} luồng)"
        elif key == "ttc":
            state = ttc.get_state(uid); state["running"]=True; state["stop_flag"]=False
            accs = ttc.get_active_accounts(uid); cfg = ttc.load_config(uid); proxies = ttc.load_proxies(uid)
            def _sfn2(u,m): asyncio.run_coroutine_threadsafe(ctx.application.bot.send_message(chat_id=u,text=m,parse_mode="HTML"),loop)
            t = threading.Thread(target=ttc.run_worker,args=(uid,[(a["token"],a["cookie"]) for a in accs],cfg,proxies,_sfn2),daemon=True)
            state["thread"]=t; t.start()
            return f"✅ TTC khởi động ({len(accs)} luồng)"
        elif key == "pro5":
            stop_ev = threading.Event(); ttcpro5.stop_flags_pro5[uid] = stop_ev
            user = ttcpro5.get_user(uid); user["running"]=True; ttcpro5.save_user(uid,user)
            async def _sm(txt):
                try: await ctx.application.bot.send_message(chat_id=uid,text=txt)
                except: pass
            task = asyncio.create_task(ttcpro5.run_tool_for_user(uid,_sm,stop_ev))
            ttcpro5.running_tasks[uid]=task
            def _od(t):
                u=ttcpro5.get_user(uid); u["running"]=False; ttcpro5.save_user(uid,u)
                ttcpro5.stop_flags_pro5.pop(uid,None)
            task.add_done_callback(_od)
            return "✅ PRO5 khởi động"
        return "❌ Không rõ"

    def _stop(key):
        if key == "bumx":
            if uid in bumx.stop_flags: bumx.stop_flags[uid].set()
            if uid in bumx.running_tasks:
                t = bumx.running_tasks[uid]
                if not t.done(): t.cancel()
                bumx.running_tasks.pop(uid,None)
            bumx.stop_flags.pop(uid,None)
            return "⏹ BUMX dừng"
        elif key == "tds":
            sess = tds.get_session(uid)
            sess["stop_event"].set(); sess["running"]=False
            return "⏹ TDS dừng"
        elif key == "ttc":
            state = ttc.get_state(uid); state["stop_flag"]=True; state["running"]=False
            return "⏹ TTC dừng"
        elif key == "pro5":
            if uid in ttcpro5.stop_flags_pro5: ttcpro5.stop_flags_pro5[uid].set()
            u = ttcpro5.get_user(uid); u["running"]=False; ttcpro5.save_user(uid,u)
            if uid in ttcpro5.running_tasks:
                t=ttcpro5.running_tasks[uid]
                if not t.done(): t.cancel()
                ttcpro5.running_tasks.pop(uid,None)
            ttcpro5.stop_flags_pro5.pop(uid,None)
            return "⏹ PRO5 dừng"
        return "❌ Không rõ"

    if data == "dongbo_start_all":
        for key in BOT_LABELS:
            try: results.append(await _start(key))
            except Exception as e: results.append(f"❌ {key}: {e}")
    elif data == "dongbo_stop_all":
        for key in BOT_LABELS:
            try: results.append(_stop(key))
            except Exception as e: results.append(f"❌ {key}: {e}")
    elif data.startswith("dongbo_start_"):
        key = data.replace("dongbo_start_","")
        try: results.append(await _start(key))
        except Exception as e: results.append(f"❌ {e}")
    elif data.startswith("dongbo_stop_"):
        key = data.replace("dongbo_stop_","")
        try: results.append(_stop(key))
        except Exception as e: results.append(f"❌ {e}")

    head = "🚀" if "start" in data else "⏹"
    await query.message.reply_text(
        f"{head} <b>KẾT QUẢ ĐỒNG BỘ</b>\n\n" + "\n".join(results),
        parse_mode="HTML", reply_markup=main_rkb())

# ── Help ──────────────────────────────────────────────
ADMIN_1 = "@tbtool88"; ADMIN_2 = "@bomaylatop1"
async def show_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = (
        "❓ <b>HƯỚNG DẪN SỬ DỤNG</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "🗝 <b>Loại key:</b>\n"
        "• VIP: 1 ngày 1k | 1 tháng 25k | 1 năm 250k\n"
        "• API Key: Trả 10% thu nhập\n"
        "• Free: 4 giờ miễn phí\n\n"
        "🤖 <b>Các bot:</b>\n"
        "💸 BUMX | 🔄 TDS | 🤝 TTC | ⚡ PRO5 | 🎮 XWorld\n\n"
        "🚀 <b>Đồng Bộ:</b> Chạy tất cả bot 1 lần\n"
        "🏆 <b>Bảng XH:</b> Đua top nhận thưởng\n"
        "💳 <b>Nạp tiền:</b> QR tự động, duyệt 1-24h\n"
        "🔗 <b>Giới thiệu:</b> Nhận 10% hoa hồng\n\n"
        "/huy — Huỷ bước hiện tại\n\n"
        f"👨‍💼 <b>Admin:</b> {ADMIN_1} | {ADMIN_2}"
    )
    await update.message.reply_text(text, parse_mode="HTML", reply_markup=main_rkb(), disable_web_page_preview=True)

async def show_help_cb(query): pass

# ── Error handler ─────────────────────────────────────
async def error_handler(update, context):
    from telegram.error import NetworkError, TimedOut, RetryAfter, Conflict, BadRequest, Forbidden
    err = context.error

    if isinstance(err, Forbidden):
        uid = update.effective_user.id if update and update.effective_user else "?"
        log.warning(f"[BOT] User {uid} đã block bot — bỏ qua")
        return

    if isinstance(err, Conflict):
        log.error("[BOT] ❌ CONFLICT — Có 2 instance đang chạy!")
        print("\n❌ LỖI CONFLICT: Đang có 2 bot chạy cùng lúc!")
        print("👉 Tắt tất cả cửa sổ CMD/Termux đang chạy bot, rồi chạy lại 1 lần duy nhất!")
        import os; os._exit(1)

    if isinstance(err, (NetworkError, TimedOut)):
        err_str = str(err)
        if "Bad Gateway" in err_str:
            log.warning("[BOT] Telegram 502 Bad Gateway — đang chờ server phục hồi...")
        elif "TimedOut" in err_str or "timed out" in err_str.lower():
            log.warning("[BOT] Timeout — mạng chậm, đang retry...")
        else:
            log.warning(f"[BOT] Mạng lỗi: {err_str[:80]}")
        return

    if isinstance(err, RetryAfter):
        wait = err.retry_after + 1
        log.warning(f"[BOT] Flood control — chờ {wait}s rồi tiếp tục")
        await asyncio.sleep(wait)
        return

    if update:
        log.error(f"[BOT] Handler lỗi (update={update.update_id if hasattr(update,'update_id') else '?'}): {err}")
    else:
        log.error(f"[BOT] Lỗi: {err}")

# ── Main ──────────────────────────────────────────────
def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ Chưa cấu hình BOT_TOKEN!"); sys.exit(1)
    if MAIN_ADMINS == [123456789]:
        print("⚠️  Chưa cấu hình MAIN_ADMINS! Sửa trong main.py")

    try:
        request = HTTPXRequest(connect_timeout=30.0,read_timeout=30.0,write_timeout=30.0,pool_timeout=30.0)
        app = Application.builder().token(BOT_TOKEN).request(request).build()
    except TypeError:
        app = Application.builder().token(BOT_TOKEN).build()

    xworld._bot_ref_setter(app)
    xworld.cfg_load_all()

    app.add_handler(CommandHandler("start",     cmd_start))
    app.add_handler(CommandHandler("menu",      cmd_menu))
    app.add_handler(CommandHandler("huy",       cmd_huy))
    app.add_handler(CommandHandler("vthsetup",  xworld.vth_cmd_setup))
    app.add_handler(CommandHandler("vthstart",  xworld.vth_cmd_start_bot))
    app.add_handler(CommandHandler("vthstop",   xworld.vth_cmd_stop_bot))
    app.add_handler(CommandHandler("vthstatus", xworld.vth_cmd_status))
    app.add_handler(CommandHandler("vthlogs",   xworld.vth_cmd_logs))
    app.add_handler(CommandHandler("vthreset",  xworld.vth_cmd_reset))
    app.add_handler(CommandHandler("vthcancel", xworld.vth_cmd_cancel))
    app.add_handler(CommandHandler("mycfg",     xworld.cmd_mycfg))
    app.add_handler(CallbackQueryHandler(global_callback))
    app.add_handler(MessageHandler(filters.PHOTO, global_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, global_text))
    app.add_error_handler(error_handler)

    print("=" * 55)
    print("   🤖  UNIFIED MULTI-BOT + KEY SYSTEM")
    print(f"   Admin: {ADMIN_1} | {ADMIN_2}")
    print("=" * 55)

    _retry_delay = 5
    _fail_count  = 0

    while True:
        try:
            log.warning("[BOT] Đang kết nối Telegram...")
            app.run_polling(
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
            )
            break

        except KeyboardInterrupt:
            print("\n[BOT] Đã dừng bởi người dùng.")
            break

        except Exception as e:
            err_str = str(e)

            if "Conflict" in err_str or "terminated by other getUpdates" in err_str:
                print("\n❌ LỖI: Đang có 2 bot chạy cùng lúc!")
                print("👉 Tắt tất cả cửa sổ bot, chỉ chạy 1 lần duy nhất!")
                import sys; sys.exit(1)

            if "no current event loop" in err_str.lower():
                try:
                    asyncio.set_event_loop(asyncio.new_event_loop())
                    log.warning("[BOT] Đã tạo lại event loop — thử lại sau 2s...")
                except Exception as _e:
                    log.error(f"[BOT] Không tạo được event loop: {_e}")
                _time.sleep(2)
                continue

            _fail_count += 1
            if "Bad Gateway" in err_str or "502" in err_str:
                wait = min(_retry_delay * _fail_count, 60)
                log.warning(f"[BOT] 502 Bad Gateway — thử lại sau {wait}s... (lần {_fail_count})")
                _time.sleep(wait)
            elif "timed out" in err_str.lower() or "TimedOut" in err_str:
                log.warning(f"[BOT] Timeout — thử lại sau {_retry_delay}s...")
                _time.sleep(_retry_delay)
            elif "NetworkError" in err_str or "ConnectionError" in err_str:
                wait = min(_retry_delay * _fail_count, 30)
                log.warning(f"[BOT] Mạng lỗi — thử lại sau {wait}s... (lần {_fail_count})")
                _time.sleep(wait)
            else:
                log.error(f"[BOT] Lỗi không xác định: {err_str[:120]} — thử lại sau {_retry_delay}s...")
                _time.sleep(_retry_delay)

if __name__ == "__main__":
    main()
