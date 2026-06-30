#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  QuizBot Pro — v6.8  (ALWAYS-ON OPTIMIZED + FONT PATH FIXED)                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import telebot, json, re, os, random, string, html as html_mod, threading, logging, time, io, math
from ssl import SSLError as StdSSLError
from requests.exceptions import SSLError as RequestsSSLError, ReadTimeout as RequestsReadTimeout
import psycopg2
from psycopg2.extras import DictCursor, execute_batch, execute_values
from psycopg2 import pool
from datetime import datetime
from telebot.types import (ReplyKeyboardMarkup, KeyboardButton,
                           InlineKeyboardMarkup, InlineKeyboardButton, InputFile,
                           InlineQueryResultArticle, InputTextMessageContent,
                           ReplyKeyboardRemove, WebAppInfo)
from dotenv import load_dotenv

# 🚀 ANTI-CRASH & TIMEOUT CONFIG
telebot.apihelper.READ_TIMEOUT  = 60    
telebot.apihelper.RETRY_ON_ERROR = True  

load_dotenv()

# 👉 FIXED: Using Absolute Path for background execution
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

logging.basicConfig(filename=os.path.join(BASE_DIR, 'bot_activity.log'), level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logging.info("Bot script started/restarted.")

TOKEN        = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
BOT_USER     = "QuizBot_Pro_bot" # Change this to your bot username without @
OWNER_ID     = 863857194

if DATABASE_URL:
    DATABASE_URL = re.sub(r"[&?]prepare_threshold=[^&]*", "", DATABASE_URL)
    DATABASE_URL = DATABASE_URL.replace("?&", "?").replace("&&", "&")
    if DATABASE_URL.endswith("?") or DATABASE_URL.endswith("&"):
        DATABASE_URL = DATABASE_URL[:-1]

bot = telebot.TeleBot(TOKEN, parse_mode=None, num_threads=15)
_wizard = {}
_auto_timers = {}
_LETTERS = "ABCDEFGHIJ"
_CORRECT = "\u2705"

_user_cache = set()
_ban_cache = set()
_approved_cache = set()
_pending_cache = {}
_state_cache = {}
_quiz_data_cache = {}
_session_cache = {}
_rm_sent = set()
OWNER_NAME = "Sunny ☀️"
OWNER_USERNAME = "@Sunnysharmask"

# ⚡ SUPERFAST CONNECTION POOL
try:
    db_pool = pool.ThreadedConnectionPool(5, 20, DATABASE_URL)
    logging.info("Superfast DB pool created.")
except Exception as e:
    logging.error(f"Pool error: {e}")
    db_pool = None

class _PgWrapper:
    def __init__(self, conn): self._conn = conn
    def _fix(self, sql): return sql.replace("?", "%s")
    def execute(self, sql, params=()):
        cur = self._conn.cursor(cursor_factory=DictCursor)
        cur.execute(self._fix(sql), params)
        return cur
    def executemany(self, sql, params_list):
        cur = self._conn.cursor(cursor_factory=DictCursor)
        execute_batch(cur, self._fix(sql), params_list, page_size=100)
        return cur
    def __enter__(self): return self
    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type: self._conn.rollback()
        else: self._conn.commit()
        if db_pool and self._conn: db_pool.putconn(self._conn)
        elif self._conn: self._conn.close()
        return False

def get_db():
    if db_pool: return _PgWrapper(db_pool.getconn())
    return _PgWrapper(psycopg2.connect(DATABASE_URL))

def init_db():
    with get_db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id BIGINT PRIMARY KEY, username TEXT, first_name TEXT,
            html_toggle INTEGER NOT NULL DEFAULT 0, state TEXT NOT NULL DEFAULT 'idle',
            created_at INTEGER NOT NULL DEFAULT CAST(EXTRACT(EPOCH FROM NOW()) AS INTEGER),
            is_approved INTEGER NOT NULL DEFAULT 0)""")
            
        conn.execute("""CREATE TABLE IF NOT EXISTS quizzes (
            quiz_id SERIAL PRIMARY KEY, short_id TEXT NOT NULL DEFAULT '',
            creator_id BIGINT NOT NULL, title TEXT NOT NULL,
            neg_marking TEXT NOT NULL DEFAULT '0', quiz_type TEXT NOT NULL DEFAULT 'free',
            timer_seconds INTEGER NOT NULL DEFAULT 45,
            shuffle_q INTEGER NOT NULL DEFAULT 0, shuffle_o INTEGER NOT NULL DEFAULT 0,
            section_quiz INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL DEFAULT CAST(EXTRACT(EPOCH FROM NOW()) AS INTEGER))""")
            
        conn.execute("""CREATE TABLE IF NOT EXISTS questions (
            question_id SERIAL PRIMARY KEY,
            quiz_id INTEGER NOT NULL REFERENCES quizzes(quiz_id) ON DELETE CASCADE,
            ref_text TEXT NOT NULL DEFAULT '', q_text TEXT NOT NULL,
            options TEXT NOT NULL, correct_idx INTEGER NOT NULL,
            position INTEGER NOT NULL DEFAULT 0,
            explanation TEXT NOT NULL DEFAULT '',
            image_file_id TEXT NOT NULL DEFAULT '')""")
        try:
            conn.execute("ALTER TABLE questions ADD COLUMN IF NOT EXISTS image_file_id TEXT NOT NULL DEFAULT ''")
        except Exception: pass
            
        conn.execute("""CREATE TABLE IF NOT EXISTS active_sessions (
            session_id SERIAL PRIMARY KEY, user_id BIGINT NOT NULL,
            quiz_id INTEGER NOT NULL, chat_id BIGINT NOT NULL,
            current_q_idx INTEGER NOT NULL DEFAULT 0,
            is_paused INTEGER NOT NULL DEFAULT 0, is_completed INTEGER NOT NULL DEFAULT 0,
            total_q INTEGER NOT NULL DEFAULT 0, shuffled_order TEXT NOT NULL DEFAULT '[]',
            start_time INTEGER NOT NULL DEFAULT CAST(EXTRACT(EPOCH FROM NOW()) AS INTEGER),
            end_time INTEGER)""")
            
        conn.execute("""CREATE TABLE IF NOT EXISTS session_results (
            result_id SERIAL PRIMARY KEY, session_id INTEGER NOT NULL,
            user_id BIGINT NOT NULL, participant_name TEXT NOT NULL DEFAULT '',
            question_id INTEGER NOT NULL, selected_idx INTEGER,
            is_correct INTEGER NOT NULL DEFAULT 0,
            answered_at INTEGER NOT NULL DEFAULT CAST(EXTRACT(EPOCH FROM NOW()) AS INTEGER))""")
            
        conn.execute("""CREATE TABLE IF NOT EXISTS poll_map (
            poll_id TEXT PRIMARY KEY, session_id INTEGER NOT NULL,
            question_id INTEGER NOT NULL, correct_idx INTEGER NOT NULL,
            owner_id BIGINT NOT NULL)""")
            
        conn.execute("""CREATE TABLE IF NOT EXISTS banned_users (
            user_id BIGINT PRIMARY KEY, banned_by BIGINT,
            reason TEXT NOT NULL DEFAULT '',
            banned_at INTEGER NOT NULL DEFAULT CAST(EXTRACT(EPOCH FROM NOW()) AS INTEGER))""")
            
        conn.execute("""CREATE TABLE IF NOT EXISTS global_leaderboard (
            id SERIAL PRIMARY KEY,
            telegram_id BIGINT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            score REAL NOT NULL DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
            
        conn.execute("""CREATE TABLE IF NOT EXISTS tournaments (
            tournament_id SERIAL PRIMARY KEY,
            quiz_id INTEGER NOT NULL,
            chat_id BIGINT NOT NULL,
            creator_id BIGINT NOT NULL,
            status TEXT NOT NULL DEFAULT 'waiting',
            current_round INTEGER NOT NULL DEFAULT 1,
            active_players TEXT NOT NULL DEFAULT '[]',
            q_offset INTEGER NOT NULL DEFAULT 0,
            qs_per_round INTEGER NOT NULL DEFAULT 0,
            created_at INTEGER NOT NULL DEFAULT CAST(EXTRACT(EPOCH FROM NOW()) AS INTEGER))""")
        try:
            conn.execute("ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS q_offset INTEGER NOT NULL DEFAULT 0")
            conn.execute("ALTER TABLE tournaments ADD COLUMN IF NOT EXISTS qs_per_round INTEGER NOT NULL DEFAULT 0")
        except Exception: pass
            
        conn.execute("CREATE INDEX IF NOT EXISTS idx_q ON questions(quiz_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sr ON session_results(session_id, user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_as ON active_sessions(user_id, chat_id, is_completed)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_short ON quizzes(short_id)")
        
    try:
        with get_db() as conn:
            for r in conn.execute("SELECT user_id FROM banned_users").fetchall():
                _ban_cache.add(r["user_id"])
    except Exception: pass
    if OWNER_ID: _approved_cache.add(OWNER_ID)
    try:
        with get_db() as conn:
            conn.execute("UPDATE users SET is_approved=1 WHERE user_id=?", (OWNER_ID,))
            for r in conn.execute("SELECT user_id FROM users WHERE is_approved=1").fetchall():
                _approved_cache.add(r["user_id"])
    except Exception: pass

init_db()

_tournament_cache = {}
try:
    with get_db() as conn:
        active_t = conn.execute(
            "SELECT tournament_id, chat_id FROM tournaments WHERE status IN ('waiting','round_active')"
        ).fetchall()
        for row in active_t:
            _tournament_cache[row["chat_id"]] = row["tournament_id"]
    logging.info(f"Tournament cache loaded: {len(_tournament_cache)} active tournaments.")
except Exception as _te:
    logging.error(f"Tournament cache load error: {_te}")

def _bg_run(fn): threading.Thread(target=fn, daemon=True).start()
def _bg_db(sql, params=()):
    def _do():
        try:
            with get_db() as conn: conn.execute(sql, params)
        except Exception as e: logging.error(f"BG DB: {e}")
    _bg_run(_do)

def sync_global_leaderboard(user_id, username, add_score):
    def _bg():
        try:
            with get_db() as conn:
                conn.execute("""
                    INSERT INTO global_leaderboard (telegram_id, username, score, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT (telegram_id) DO UPDATE 
                    SET score = global_leaderboard.score + EXCLUDED.score,
                        username = EXCLUDED.username,
                        updated_at = CURRENT_TIMESTAMP
                """, (user_id, username, add_score))
        except Exception as e:
            logging.error(f"Global LB Sync Error: {e}")
    _bg_run(_bg)

def _cache_quiz_data(quiz_id):
    if quiz_id in _quiz_data_cache: return _quiz_data_cache[quiz_id]
    with get_db() as conn:
        quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
        questions = conn.execute("SELECT * FROM questions WHERE quiz_id=? ORDER BY position,question_id", (quiz_id,)).fetchall()
    if not quiz: return None
    data = {"quiz": dict(quiz), "questions": [dict(q) for q in questions],
            "q_map": {q["question_id"]: dict(q) for q in questions}}
    _quiz_data_cache[quiz_id] = data
    return data

def _cache_session(session_id, sess_dict=None):
    if sess_dict: _session_cache[session_id] = dict(sess_dict); return _session_cache[session_id]
    if session_id in _session_cache: return _session_cache[session_id]
    with get_db() as conn:
        sess = conn.execute("SELECT * FROM active_sessions WHERE session_id=?", (session_id,)).fetchone()
    if sess: _session_cache[session_id] = dict(sess)
    return _session_cache.get(session_id)

def _invalidate_quiz_cache(quiz_id): _quiz_data_cache.pop(quiz_id, None)

def is_owner(uid): return OWNER_ID is not None and uid == OWNER_ID
def is_banned(uid): return uid in _ban_cache

def is_approved_user(uid):
    if OWNER_ID and uid == OWNER_ID: return True
    if uid in _approved_cache: return True
    u = get_user(uid)
    if u and u.get("is_approved"): _approved_cache.add(uid); return True
    return False

def register_user(msg):
    u = msg.from_user
    if u.id in _user_cache: return
    _user_cache.add(u.id)
    _state_cache[u.id] = "idle"
    def _bg():
        try:
            with get_db() as conn:
                existing = conn.execute("SELECT user_id FROM users WHERE user_id=?", (u.id,)).fetchone()
                conn.execute("INSERT INTO users(user_id,username,first_name) VALUES(?,?,?) "
                    "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username,first_name=excluded.first_name",
                    (u.id, u.username, u.first_name))
                if not existing:
                    uname = f"@{u.username}" if u.username else "no username"
                    chat_type = msg.chat.type if hasattr(msg, 'chat') else "unknown"
                    if OWNER_ID and u.id != OWNER_ID:
                        _pending_cache[u.id] = True
                        kb = InlineKeyboardMarkup(row_width=2)
                        kb.add(
                            InlineKeyboardButton("✅ Allow", callback_data=f"approve_{u.id}"),
                            InlineKeyboardButton("❌ Deny", callback_data=f"deny_{u.id}")
                        )
                        try:
                            bot.send_message(OWNER_ID,
                                f"🆕 <b>New User Request!</b>\n👤 <b>{html_mod.escape(u.first_name or '')}</b>\n"
                                f"🔗 {uname}\n🆔 <code>{u.id}</code>\n📍 {chat_type}\n\n"
                                f"Allow this user to use the bot?",
                                parse_mode="HTML", reply_markup=kb)
                        except Exception: pass
        except Exception as e: logging.error(f"register BG: {e}")
    _bg_run(_bg)

def get_user(uid):
    with get_db() as conn: return conn.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()

def set_state(uid, state):
    _state_cache[uid] = state
    _bg_db("UPDATE users SET state=? WHERE user_id=?", (state, uid))

def get_state(uid):
    if uid in _state_cache: return _state_cache[uid]
    u = get_user(uid)
    state = u["state"] if u else "idle"
    _state_cache[uid] = state
    return state

def make_short_id(length=8): return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))

def parse_neg_value(neg_str):
    try:
        if '/' in str(neg_str):
            p = str(neg_str).split('/'); return float(p[0]) / float(p[1])
        return float(neg_str)
    except Exception: return 0.0

def quiz_card_kb(quiz_id, short_id=""):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("▶️  Start Quiz", callback_data=f"qs_{quiz_id}"))
    kb.add(InlineKeyboardButton("🚀  Add to Group", url=f"https://t.me/{BOT_USER}?startgroup=quiz_{quiz_id}"))
    kb.add(InlineKeyboardButton("🔗  Share Quiz", switch_inline_query=short_id or str(quiz_id)))
    return kb

def edit_panel_kb(quiz_id, quiz=None):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("✏️  Rename Quiz", callback_data=f"ep_name_{quiz_id}"))
    if quiz:
        type_icon  = "🔓" if quiz["quiz_type"] == "free" else "🔒"
        type_label = "FREE" if quiz["quiz_type"] == "free" else "PAID"
    else:
        type_icon, type_label = "🔓", "FREE"
    kb.add(InlineKeyboardButton(f"Quiz TYPE: {type_icon} {type_label}", callback_data=f"ep_type_{quiz_id}"))
    sq = quiz["shuffle_q"] if quiz else 0
    so = quiz["shuffle_o"] if quiz else 0
    kb.row(
        InlineKeyboardButton(f"🔀 Shuffle Qs: {'✅' if sq else '❌'}",   callback_data=f"ep_shq_{quiz_id}"),
        InlineKeyboardButton(f"🔀 Shuffle Opts: {'✅' if so else '❌'}", callback_data=f"ep_sho_{quiz_id}"),
    )
    if quiz:
        timer_val = quiz["timer_seconds"]
        neg_v     = parse_neg_value(quiz["neg_marking"])
        neg_label = f"{neg_v:.2f}".rstrip("0").rstrip(".") if neg_v else "None"
    else:
        timer_val, neg_label = "—", "—"
    kb.row(
        InlineKeyboardButton(f"⏱ Timer: {timer_val}s",    callback_data=f"ep_timer_{quiz_id}"),
        InlineKeyboardButton(f"➖ Neg Mark: {neg_label}", callback_data=f"ep_neg_{quiz_id}"),
    )
    kb.add(InlineKeyboardButton("📝  Question Management", callback_data=f"ep_qmgmt_{quiz_id}"))
    kb.add(InlineKeyboardButton("🗑  Delete Quiz",    callback_data=f"ep_delquiz_{quiz_id}"))
    kb.add(InlineKeyboardButton("✅  Done Editing",   callback_data=f"ep_done_{quiz_id}"))
    return kb

def qadd_panel_kb(quiz_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("📄 File Upload (TXT / JSON)", callback_data=f"qadd_file_{quiz_id}"),
        InlineKeyboardButton("✍️ Manual Entry",             callback_data=f"qadd_manual_{quiz_id}"),
        InlineKeyboardButton("⬅️ Back",                     callback_data=f"ep_back_{quiz_id}"),
    )
    return kb

def qdel_panel_kb(quiz_id):
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(
        InlineKeyboardButton("🔢 Number / Range se Delete", callback_data=f"qdel_num_{quiz_id}"),
        InlineKeyboardButton("☢️ Delete All Questions",   callback_data=f"qdel_all_{quiz_id}"),
        InlineKeyboardButton("⬅️ Back",                     callback_data=f"ep_back_{quiz_id}"),
    )
    return kb

def qdel_confirm_kb(quiz_id):
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✅ Yes, Delete", callback_data=f"qdel_confirm_{quiz_id}"),
        InlineKeyboardButton("❌ Cancel",             callback_data=f"ep_qdel_{quiz_id}"),
    )
    return kb

def qlist_page_kb(quiz_id, page, total_pages):
    kb = InlineKeyboardMarkup(row_width=3)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️", callback_data=f"qlist_pg_{quiz_id}_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("▶️", callback_data=f"qlist_pg_{quiz_id}_{page+1}"))
    if nav:
        kb.add(*nav)
    kb.add(InlineKeyboardButton("⬅️ Back", callback_data=f"ep_back_{quiz_id}"))

def qview_buttons_kb(quiz_id, qs, page, total_pages, per_page=10):
    kb = InlineKeyboardMarkup(row_width=3)
    offset = page * per_page
    row = []
    for i, q in enumerate(qs):
        g_idx = offset + i
        btn = InlineKeyboardButton(f"✏️ Q{g_idx+1}", callback_data=f"eq_sel_{quiz_id}_{g_idx}")
        row.append(btn)
        if len(row) == 3:
            kb.add(*row); row = []
    if row:
        kb.add(*row)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton("◀️ Prev", callback_data=f"eq_pg_{quiz_id}_{page-1}"))
    nav.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav.append(InlineKeyboardButton("Next ▶️", callback_data=f"eq_pg_{quiz_id}_{page+1}"))
    if nav:
        kb.add(*nav)
    kb.add(InlineKeyboardButton("⬅️ Back", callback_data=f"ep_qmgmt_{quiz_id}"))
    return kb

def group_ctrl_kb(session_id, is_paused=False):
    kb = InlineKeyboardMarkup(row_width=3)
    pause_btn = InlineKeyboardButton("▶️ Resume", callback_data=f"gctrl_resume_{session_id}") if is_paused else InlineKeyboardButton("⏸ Pause", callback_data=f"gctrl_pause_{session_id}")
    kb.add(
        InlineKeyboardButton("⚡ Fast", callback_data=f"gctrl_fast_{session_id}"),
        pause_btn,
        InlineKeyboardButton("🐢 Slow", callback_data=f"gctrl_slow_{session_id}")
    )
    kb.add(InlineKeyboardButton("🛑 Stop Quiz", callback_data=f"gctrl_stop_{session_id}"))
    return kb

def is_group_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ("administrator", "creator")
    except Exception: return False

def edit_ctrl_panel(chat_id, msg_id, session_id, status_text, is_paused=False):
    try:
        bot.edit_message_text(status_text, chat_id, msg_id, parse_mode="HTML",
            reply_markup=group_ctrl_kb(session_id, is_paused))
    except Exception: pass

def safe_send(chat_id, text, **kwargs):
    if not text: return
    for i in range(0, max(len(text), 1), 4096):
        try: bot.send_message(chat_id, text[i:i+4096], **kwargs)
        except Exception as e: logging.error(f"safe_send error: {e}")

def send_edit_panel(chat_id, quiz, q_count, message_id=None):
    type_icon  = "🔓" if quiz["quiz_type"] == "free" else "🔒"
    type_label = "FREE" if quiz["quiz_type"] == "free" else "PAID"
    title      = html_mod.escape(quiz["title"][:35])
    short_id   = quiz.get("short_id") or quiz["quiz_id"]

    text = (
        f"╔══ 🛠 <b>QUIZ EDITOR</b> ══╗\n"
        f"\n"
        f"  📌 <b>{title}</b>\n"
        f"  🔑 <code>{short_id}</code>  ·  {type_icon} <b>{type_label}</b>\n"
        f"  🔢 <b>{q_count}</b> Questions\n"
        f"\n"
        f"╚══════════════════════╝"
    )

    kb = edit_panel_kb(quiz["quiz_id"], quiz)
    try:
        if message_id:
            bot.edit_message_text(text, chat_id, message_id, parse_mode="HTML", reply_markup=kb)
        else:
            bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

_OPT_RE = re.compile(r"^[a-zA-Z0-9](?:[).:]|-(?=\s))\s*(.*)", re.UNICODE)

def extract_q_and_ref(question_lines):
    if not question_lines: return "", ""
    if len(question_lines) == 1:
        q = re.sub(r"^[Qq]?\d+[).\-:]\s*", "", question_lines[0], flags=re.IGNORECASE).strip()
        if len(q) > 280: return q, q[:275] + "..."
        return "", q
    full_text = "\n".join(question_lines)
    has_list = bool(re.search(r"\n\s*([1-9][.:\)]|[IVX]+\.)", full_text))
    if len(full_text) <= 250 and not has_list:
        q = re.sub(r"^[Qq]?\d+[).\-:]\s*", "", full_text, flags=re.IGNORECASE).strip()
        return "", q
    clean_first = re.sub(r"^[Qq]?\d+[).\-:]\s*", "", question_lines[0], flags=re.IGNORECASE).strip()
    last_line = question_lines[-1].strip()
    if re.match(r"^([1-9][.:\)]|[IVX]+\.)", last_line):
        q_text, ref_text = clean_first, "\n".join(question_lines[1:])
    else:
        q_text = last_line
        ref_lines = question_lines[:-1]; ref_lines[0] = clean_first
        ref_text = "\n".join(ref_lines)
    if len(q_text) > 280: ref_text = q_text + "\n\n" + ref_text; q_text = q_text[:275] + "..."
    return ref_text.strip(), q_text.strip()

def parse_manual_block(block):
    lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
    if len(lines) < 3: raise ValueError(f"Too few lines ({len(lines)})")
    
    explanation = ""
    filtered = []
    for line in lines:
        low = line.lower()
        if low.startswith("exp:") or low.startswith("explanation:") or low.startswith("व्याख्या:"):
            explanation = re.split(r":\s*", line, maxsplit=1)[-1].strip()
        else:
            filtered.append(line)
    lines = filtered
    opt_start = -1
    for i, line in enumerate(lines):
        if _OPT_RE.match(line): opt_start = i; break
    if opt_start == -1 or opt_start == 0: raise ValueError("No options detected.")
    
    ref_text, q_text = extract_q_and_ref(lines[:opt_start])
    opts, correct_idx = [], -1
    
    for line in lines[opt_start:]:
        m = _OPT_RE.match(line)
        if not m: continue
        opt = m.group(1).strip()
        if _CORRECT in opt: correct_idx = len(opts); opt = opt.replace(_CORRECT, "").strip()
        opts.append(opt[:100])
        
    if len(opts) < 2: raise ValueError(f"Only {len(opts)} opt(s)")
    if len(opts) > 10: raise ValueError(f"{len(opts)} opts > 10")
    
    return (ref_text, q_text, opts, correct_idx if correct_idx >= 0 else 0, explanation)

def bulk_parse_manual(raw):
    raw = re.sub("\\[.*?\\]", " ", raw)
    raw = re.sub("\\n\\s*✅", " ✅", raw)
    raw = re.sub("(?im)^(\\s*(?:exp|explanation|व्याख्या):.*?)$", "\\1\\n\\n\\n", raw)
    
    parsed, errors = [], []
    for i, block in enumerate(re.split("\\n\\s*\\n", raw.strip()), 1):
        block = block.strip()
        if not block: continue
        try: parsed.append(parse_manual_block(block))
        except ValueError as e: errors.append(f"Block {i}: {e}")
    return parsed, errors

def _parse_bpsc_block(block):
    paras = [p.strip() for p in re.split(r"\n\s*\n", block.strip()) if p.strip()]
    if not paras: raise ValueError("Empty")
    if len(paras) == 1:
        fl = paras[0].splitlines()
        question_lines, option_lines = fl[:1], [l.strip() for l in fl[1:] if l.strip()]
    else:
        question_lines = []
        for p in paras[:-1]: question_lines.extend(p.splitlines())
        option_lines = [l.strip() for l in paras[-1].splitlines() if l.strip() and not l.strip().startswith("👉")]
    ref_text, q_text = extract_q_and_ref(question_lines)
    opts, correct_idx = [], -1
    for line in option_lines:
        if not line: continue
        clean = line
        m = _OPT_RE.match(clean)
        if m: clean = m.group(1).strip()
        if _CORRECT in clean: correct_idx = len(opts); clean = clean.replace(_CORRECT, "").strip()
        if clean: opts.append(clean[:100])
    if len(opts) < 2: raise ValueError(f"Only {len(opts)} opt(s)")
    if len(opts) > 10: opts = opts[:10]
    return (ref_text, q_text, opts, correct_idx if correct_idx >= 0 else 0, "")

def parse_bpsc_txt(content):
    raw_blocks = re.split(r"(?=^\s*Q\d+\.)", content, flags=re.MULTILINE)
    parsed, errors = [], []
    for i, block in enumerate(raw_blocks, 1):
        block = block.strip()
        if not block or not re.match(r"Q\d+\.", block, re.IGNORECASE): continue
        try: parsed.append(_parse_bpsc_block(block))
        except ValueError as e: errors.append(f"TXT Q{i}: {e}")
    return parsed, errors

def parse_json_schema_a(items):
    parsed, errors = [], []
    for i, item in enumerate(items, 1):
        try:
            q = str(item.get("question","")).strip(); ops = item.get("options", [])
            ci = int(item.get("correct_index", 0)); exp = str(item.get("explanation","")).strip()
            if not q: raise ValueError("empty")
            if not isinstance(ops, list) or len(ops) < 2: raise ValueError("opts<2")
            if len(ops) > 10: ops = ops[:10]
            if not (0 <= ci < len(ops)): ci = 0
            parsed.append(("", q[:300], [str(o)[:100] for o in ops], ci, exp))
        except Exception as e: errors.append(f"JSON A {i}: {e}")
    return parsed, errors

def parse_json_schema_b(items):
    parsed, errors = [], []
    for i, item in enumerate(items, 1):
        try:
            ref_text = str(item.get("reference_text","")).strip()
            q_text = str(item.get("question_text","")).strip()
            ops_raw = item.get("options", [])
            corr_id = str(item.get("correct_option_id","a")).strip().lower()
            exp = str(item.get("explanation","")).strip()
            if not q_text and not ref_text: raise ValueError("empty")
            if not isinstance(ops_raw, list) or len(ops_raw) < 2: raise ValueError("opts<2")
            opts, correct_idx = [], 0
            for j, opt in enumerate(ops_raw):
                if isinstance(opt, dict):
                    oid = str(opt.get("id","")).strip().lower(); otxt = str(opt.get("text","")).strip()
                else:
                    oid = _LETTERS[j].lower() if j < 10 else str(j); otxt = str(opt).strip()
                if oid == corr_id: correct_idx = j
                opts.append(otxt[:100])
            if len(opts) > 10: opts = opts[:10]
            if len(q_text) > 300: q_text = q_text[:297] + "..."
            parsed.append((ref_text, q_text, opts, correct_idx, exp))
        except Exception as e: errors.append(f"JSON B {i}: {e}")
    return parsed, errors

def detect_and_parse(filename, content):
    fname = filename.lower()
    if fname.endswith(".json"):
        data = json.loads(content)
        if isinstance(data, dict) and "questions" in data: return parse_json_schema_b(data["questions"])
        elif isinstance(data, list):
            if data and isinstance(data[0], dict) and ("question_text" in data[0] or "reference_text" in data[0]):
                return parse_json_schema_b(data)
            return parse_json_schema_a(data)
        raise ValueError("JSON: list or {questions:[...]}\n")
    if re.search(r"^\s*Q\d+\.", content, re.MULTILINE):
        r, e = parse_bpsc_txt(content)
        if r: return r, e
    return bulk_parse_manual(content)

def save_questions(quiz_id, questions):
    with get_db() as conn:
        count = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()[0]
        query = "INSERT INTO questions(quiz_id,ref_text,q_text,options,correct_idx,position,explanation,image_file_id) VALUES %s"
        data = []
        for i, row in enumerate(questions):
            r, q, o, c, *rest = row
            exp = rest[0] if rest else ""
            img = rest[1] if len(rest) > 1 else ""
            data.append((quiz_id, r, q, json.dumps(o, ensure_ascii=False), c, count+i, exp or "", img or ""))
        execute_values(conn._conn.cursor(), query, data, page_size=500)
    _invalidate_quiz_cache(quiz_id)

def find_quiz(uid, id_str):
    with get_db() as conn:
        if id_str.isdigit(): return conn.execute("SELECT * FROM quizzes WHERE quiz_id=? AND creator_id=?", (int(id_str), uid)).fetchone()
        return conn.execute("SELECT * FROM quizzes WHERE short_id=? AND creator_id=?", (id_str.upper(), uid)).fetchone()

# ══════════════════════════════════════════════════════════════════════════════
#  QUIZ SESSION ENGINE
# ══════════════════════════════════════════════════════════════════════════════
def _cancel_auto_timer(session_id):
    t = _auto_timers.pop(session_id, None)
    if t:
        try: t.cancel()
        except Exception: pass

def _auto_advance(session_id, expected_q_idx):
    try: _auto_timers.pop(session_id, None); send_next_poll(session_id)
    except Exception as e: logging.error(f"Auto-advance: {e}")

def send_next_poll(session_id):
    _cancel_auto_timer(session_id)
    try:
        sess = _session_cache.get(session_id)
        if not sess:
            with get_db() as conn:
                sess_row = conn.execute("SELECT * FROM active_sessions WHERE session_id=?", (session_id,)).fetchone()
            if not sess_row: return
            sess = _cache_session(session_id, sess_row)
        if sess.get("is_paused") or sess.get("is_completed"): return
        quiz_id = sess["quiz_id"]
        cached = _quiz_data_cache.get(quiz_id)
        if not cached: cached = _cache_quiz_data(quiz_id)
        if not cached: return
        quiz, all_qs, q_map = cached["quiz"], cached["questions"], cached["q_map"]
        order = json.loads(sess.get("shuffled_order") or "[]")
        questions = [q_map[qid] for qid in order if qid in q_map] if order else list(all_qs)
        total = len(questions)
        q_idx = sess.get("current_q_idx", 0)
        if q_idx >= total: _finish_session(session_id); return
        q = questions[q_idx]
        opts = json.loads(q["options"])
        period = quiz.get("timer_seconds", 45)
        correct_idx = q["correct_idx"]
        if quiz.get("shuffle_o"):
            pairs = list(enumerate(opts)); random.shuffle(pairs)
            orig_correct = correct_idx; opts = []
            for new_i, (orig_i, txt) in enumerate(pairs):
                opts.append(txt)
                if orig_i == orig_correct: correct_idx = new_i
        ref = (q.get("ref_text") or "").strip()
        if ref:
            try: bot.send_message(sess["chat_id"], f"📖 *Reference* | Q{q_idx+1}/{total}\n\n{ref}", parse_mode="Markdown")
            except Exception:
                try: bot.send_message(sess["chat_id"], f"Reference Q{q_idx+1}/{total}\n\n{ref}")
                except Exception: pass
        img_fid = (q.get("image_file_id") or "").strip()
        if img_fid:
            try:
                bot.send_photo(sess["chat_id"], img_fid, caption=f"🖼 Q{q_idx+1}/{total}")
                time.sleep(0.3)
            except Exception as e:
                logging.warning(f"Quiz image send failed Q{q_idx+1}: {e}")
        prefix = f"[{q_idx+1}/{total}] "
        max_q = 290 - len(prefix)
        poll_q = prefix + (q["q_text"][:max_q] if len(q["q_text"]) > max_q else q["q_text"])
        exp_text = (q.get("explanation") or "").strip()
        exp_arg = exp_text[:200] if exp_text else None
        msg = bot.send_poll(chat_id=sess["chat_id"], question=poll_q, options=opts,
            type="quiz", correct_option_id=correct_idx, is_anonymous=False, open_period=period,
            explanation=exp_arg, explanation_parse_mode=None)
        new_idx = q_idx + 1
        sess["current_q_idx"] = new_idx
        _session_cache[session_id] = sess
        _poll_id, _q_id, _owner = msg.poll.id, q["question_id"], sess["user_id"]
        def _bg_write():
            try:
                with get_db() as conn:
                    conn.execute("INSERT INTO poll_map(poll_id,session_id,question_id,correct_idx,owner_id) VALUES(?,?,?,?,?) "
                        "ON CONFLICT(poll_id) DO UPDATE SET session_id=EXCLUDED.session_id,question_id=EXCLUDED.question_id,"
                        "correct_idx=EXCLUDED.correct_idx,owner_id=EXCLUDED.owner_id",
                        (_poll_id, session_id, _q_id, correct_idx, _owner))
                    conn.execute("UPDATE active_sessions SET current_q_idx=? WHERE session_id=?", (new_idx, session_id))
            except Exception as e: logging.error(f"BG poll: {e}")
        _bg_run(_bg_write)
        t = threading.Timer(period + 0.05, _auto_advance, args=[session_id, new_idx])
        t.daemon = True; t.start(); _auto_timers[session_id] = t
    except telebot.apihelper.ApiTelegramException as exc:
        logging.error(f"TG API: {exc}")
        try:
            if sess: bot.send_message(sess["chat_id"], f"⚠️ Poll error: {exc.description}\nSkipping...")
        except Exception: pass
        try:
            new_idx = sess.get("current_q_idx", 0) + 1
            sess["current_q_idx"] = new_idx; _session_cache[session_id] = sess
            _bg_db("UPDATE active_sessions SET current_q_idx=? WHERE session_id=?", (new_idx, session_id))
            t = threading.Timer(1.0, _auto_advance, args=[session_id, new_idx])
            t.daemon = True; t.start(); _auto_timers[session_id] = t
        except Exception: pass
    except Exception as e: logging.error(f"Poll failed: {e}")

def _finish_session(session_id):
    with get_db() as conn:
        sess = conn.execute("SELECT * FROM active_sessions WHERE session_id=?", (session_id,)).fetchone()
        if not sess: return
        conn.execute("UPDATE active_sessions SET is_completed=1,end_time=(CAST(EXTRACT(EPOCH FROM NOW()) AS INTEGER)) WHERE session_id=?", (session_id,))
        quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (sess["quiz_id"],)).fetchone()
    _session_cache.pop(session_id, None)
    qt = quiz["title"] if quiz else "Quiz"
    nv = parse_neg_value(quiz["neg_marking"]) if quiz else 0.0
    creator_name = ""
    try:
        with get_db() as conn:
            cr = conn.execute("SELECT first_name FROM users WHERE user_id=?", (sess["user_id"],)).fetchone()
            if cr and cr["first_name"]: creator_name = cr["first_name"]
    except Exception: pass
    _send_leaderboard(session_id, sess["chat_id"], qt, nv, sess["total_q"], sess["start_time"], creator_name)
    if quiz: _bg_run(lambda: _export_practice_html(sess["chat_id"], sess["quiz_id"]))

def _send_leaderboard(session_id, chat_id, quiz_title, neg_val, total_q, session_start, creator_name=""):
    with get_db() as conn:
        rows = conn.execute("""SELECT user_id, MAX(participant_name) AS name, SUM(is_correct) AS correct,
            COUNT(*) AS answered, MIN(answered_at) AS first_at, MAX(answered_at) AS last_at
            FROM session_results WHERE session_id=? GROUP BY user_id
            ORDER BY (SUM(is_correct)-(COUNT(*)-SUM(is_correct))*?) DESC, (MAX(answered_at)-MIN(answered_at)) ASC
        """, (session_id, neg_val)).fetchall()
    if not rows:
        bot.send_message(chat_id, f"🏁 Quiz '{quiz_title}' ended! No answers.", parse_mode="HTML"); return
    
    def short_name(raw):
        n = (raw or "User").strip()
        orig_parts = n.split(); first_token = orig_parts[0] if orig_parts else n
        name = re.sub(r'^[^a-zA-Z0-9]+', '', first_token)
        name = re.sub(r'[^a-zA-Z0-9]+$', '', name)
        if not name: name = first_token[:10]
        if len(name) > 10: name = name[:9] + "…"
        if len(orig_parts) > 1 and orig_parts[-1] and ord(orig_parts[-1][0]) > 127:
            name = name + " " + orig_parts[-1]
        return html_mod.escape(name)
        
    for r in rows:
        c_ans = int(r["correct"] or 0)
        w_ans = int(r["answered"] or 0) - c_ans
        user_score = round(c_ans - w_ans * neg_val, 2)
        u_name = r["name"] or f"User{r['user_id']}"
        sync_global_leaderboard(r["user_id"], u_name, user_score)

    def _pc(text, w):
        tl = len(text)
        if tl >= w: return text
        return " " * ((w - tl) // 2) + text
    def _ps(l, r, w):
        h = w // 2; return l.center(h) + r.center(h)
        
    safe_title = html_mod.escape(quiz_title)
    players = []
    for r in rows[:15]:
        correct = int(r["correct"] or 0); wrong = int(r["answered"] or 0) - correct
        score = round(correct - wrong * neg_val, 2)
        elapsed = int(r["last_at"] or 0) - int(r["first_at"] or 0)
        mins, sec = elapsed // 60, elapsed % 60
        time_str = f"{elapsed}s" if elapsed < 60 else f"{mins}m {sec:02d}s"
        pct = max(0.0, round((score / total_q * 100), 2) if total_q else 0.0)
        players.append({"name": short_name(r["name"] or f"User{r['user_id']}"), "correct": correct,
                        "wrong": wrong, "score": score, "time_str": time_str, "pct": pct})
    SEP, SEP2, W = "━━━━━━━━━━━━━━━━━━━━━━━━", "─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─", 32
    podium = ""
    if len(players) >= 1:
        r1 = players[0]
        podium += _pc("🥇", W)+"\n"+_pc(r1["name"], W)+"\n"+_pc(f"{r1['pct']}%", W)+"\n"+_pc(f"⏱ {r1['time_str']}", W)+"\n\n"
    if len(players) >= 3:
        r2, r3 = players[1], players[2]
        podium += _ps("🥈","🥉",W)+"\n"+_ps(r2["name"],r3["name"],W)+"\n"+_ps(f"{r2['pct']}%",f"{r3['pct']}%",W)+"\n"+_ps(f"⏱ {r2['time_str']}",f"⏱ {r3['time_str']}",W)+"\n"
    elif len(players) >= 2:
        r2 = players[1]
        podium += _pc("🥈",W)+"\n"+_pc(r2["name"],W)+"\n"+_pc(f"{r2['pct']}%",W)+"\n"+_pc(f"⏱ {r2['time_str']}",W)+"\n"
    ri = {1:"👑",2:"🥈",3:"🥉"}
    rl = []
    for i, p in enumerate(players):
        icon = ri.get(i+1, f"{i+1}.")
        rl.append(f"<b>{icon} {p['name']}</b>")
        rl.append(f"✅ {p['correct']} | ❌ {p['wrong']} | 🎯 {p['score']} | {p['pct']}%")
        rl.append(f"⏱ {p['time_str']}")
        if i < len(players)-1: rl.append(SEP2)
    mt = players[-1]["time_str"] if players else ""
    kb_rm = InlineKeyboardMarkup(row_width=1)
    kb_rm.add(InlineKeyboardButton("📝 Review Mistakes", callback_data=f"rm_{session_id}_0"))
    msg_text = (f"🎯 Quiz '<b>{safe_title}</b>' — Results!\n\n{SEP}\n\n<pre>{podium}</pre>\n{SEP}\n\n"
                + "\n".join(rl) + f"\n\n{SEP}\n👥 {len(rows)} | By — <b>{html_mod.escape(creator_name) if creator_name else '—'}</b>")
    try: bot.send_message(chat_id, msg_text, parse_mode="HTML", reply_markup=kb_rm)
    except Exception:
        plain = [f"🎯 '{quiz_title}' Results!\n", SEP, podium, SEP]
        for i, p in enumerate(players):
            icon = ["👑","🥈","🥉"][i] if i < 3 else f"{i+1}."
            plain.extend([f"{icon} {p['name']}", f"✅{p['correct']}|❌{p['wrong']}|🎯{p['score']}|{p['pct']}%", f"⏱{p['time_str']}"])
            if i < len(players)-1: plain.append(SEP2)
        plain.extend([SEP, f"👥 {len(rows)} | By — {creator_name}"])
        bot.send_message(chat_id, "\n".join(plain), reply_markup=kb_rm)

def send_individual_result(chat_id, uid):
    with get_db() as conn:
        sess = conn.execute("SELECT * FROM active_sessions WHERE user_id=? ORDER BY session_id DESC LIMIT 1", (uid,)).fetchone()
        if not sess: return safe_send(chat_id, "No sessions.")
        results = conn.execute("""SELECT sr.selected_idx,sr.is_correct,q.q_text,q.options,q.correct_idx
            FROM session_results sr JOIN questions q ON sr.question_id=q.question_id
            WHERE sr.session_id=? AND sr.user_id=? ORDER BY sr.result_id""", (sess["session_id"], uid)).fetchall()
        quiz = conn.execute("SELECT title,neg_marking FROM quizzes WHERE quiz_id=?", (sess["quiz_id"],)).fetchone()
    total = sess["total_q"] or len(results)
    correct = sum(1 for r in results if r["is_correct"])
    nv = parse_neg_value(quiz["neg_marking"]) if quiz else 0.0
    wrong = len(results) - correct; score = correct - wrong * nv
    pct = (correct / total * 100) if total else 0.0
    title = quiz["title"] if quiz else "Quiz"
    lines = [f"📊 *{title}*\n\n🏆 *{correct}/{total}* ({pct:.1f}%)\n🎯 *{score:.2f}*\n{'─'*36}\n"]
    for i, r in enumerate(results, 1):
        opts = json.loads(r["options"])
        sel = opts[r["selected_idx"]] if r["selected_idx"] is not None and r["selected_idx"] < len(opts) else "—"
        ans = opts[r["correct_idx"]] if r["correct_idx"] < len(opts) else "?"
        lines.append(f"{'✅' if r['is_correct'] else '❌'} *Q{i}:* {r['q_text'][:120]}")
        if not r["is_correct"]: lines.append(f"   Your: _{sel}_\n   Ans: _{ans}_")
        lines.append("")
    full = "\n".join(lines)
    for i in range(0, max(len(full),1), 4000): safe_send(chat_id, full[i:i+4000], parse_mode="Markdown")
    if sess: _bg_run(lambda: send_weak_topic_analysis(chat_id, uid, sess["session_id"]))

def send_weak_topic_analysis(chat_id, uid, session_id):
    try:
        with get_db() as conn:
            results = conn.execute("""
                SELECT sr.is_correct, q.position
                FROM session_results sr
                JOIN questions q ON sr.question_id = q.question_id
                WHERE sr.session_id=? AND sr.user_id=?
                ORDER BY q.position, sr.result_id
            """, (session_id, uid)).fetchall()
        if not results: return
        topic_stats = {}
        for i, r in enumerate(results):
            chunk_start = (i // 5) * 5
            chunk_end   = chunk_start + 5
            label = f"Q{chunk_start+1}–Q{chunk_end}"
            if label not in topic_stats:
                topic_stats[label] = {"total": 0, "wrong": 0}
            topic_stats[label]["total"] += 1
            if not r["is_correct"]:
                topic_stats[label]["wrong"] += 1
        has_wrong = any(s["wrong"] > 0 for s in topic_stats.values())
        if not has_wrong:
            safe_send(chat_id, "✅ *No weak areas! Perfect performance!* 🎉", parse_mode="Markdown")
            return
        lines = ["📊 *Weak Area Analysis:*\n"]
        weak_labels = []
        for label, s in topic_stats.items():
            pct = int(s["wrong"] / s["total"] * 100) if s["total"] else 0
            icon = "❌" if s["wrong"] > 0 else "✅"
            lines.append(f"{icon} {label:<8} → {s['wrong']}/{s['total']} wrong  ({pct}% fail)")
            if s["wrong"] > 0: weak_labels.append(label)
        if weak_labels:
            lines.append(f"\n💡 Focus more on: *{' & '.join(weak_labels[:2])}*")
        safe_send(chat_id, "\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Weak topic analysis error: {e}")

def _send_review_mistakes(session_id, user_id, dm_chat_id):
    try:
        with get_db() as conn:
            sess = conn.execute(
                "SELECT * FROM active_sessions WHERE session_id=?", (session_id,)
            ).fetchone()
            if not sess:
                bot.send_message(dm_chat_id, "⚠️ Session data not found.")
                return

            quiz = conn.execute(
                "SELECT title, neg_marking FROM quizzes WHERE quiz_id=?",
                (sess["quiz_id"],)
            ).fetchone()

            wrong_rows = conn.execute("""
                SELECT
                    sr.selected_idx,
                    sr.is_correct,
                    q.q_text,
                    q.options,
                    q.correct_idx,
                    q.explanation,
                    q.ref_text,
                    q.position
                FROM session_results sr
                JOIN questions q ON sr.question_id = q.question_id
                WHERE sr.session_id = ?
                  AND sr.user_id   = ?
                  AND sr.is_correct = 0
                ORDER BY q.position, sr.result_id
            """, (session_id, user_id)).fetchall()

        if not wrong_rows:
            bot.send_message(
                dm_chat_id,
                "🎉 *No wrong answers!* Everything was correct — well done! 🏆",
                parse_mode="Markdown"
            )
            return

        quiz_title = quiz["title"] if quiz else "Quiz"
        total_wrong = len(wrong_rows)

        bot.send_message(
            dm_chat_id,
            f"📝 *Review Mistakes*\n"
            f"Quiz: *{html_mod.escape(quiz_title)}*\n"
            f"❌ Wrong answers: *{total_wrong}*\n\n"
            f"_Each wrong question is listed below:_",
            parse_mode="Markdown"
        )

        for i, r in enumerate(wrong_rows, 1):
            try:
                opts         = json.loads(r["options"])
                correct_idx  = r["correct_idx"]
                selected_idx = r["selected_idx"]

                correct_text  = opts[correct_idx]  if correct_idx  < len(opts) else "?"
                selected_text = opts[selected_idx] if (
                    selected_idx is not None and selected_idx < len(opts)
                ) else "—"

                opt_lines = []
                for j, opt in enumerate(opts):
                    if j == correct_idx:
                        opt_lines.append(f"  ✅ {_LETTERS[j]}) {html_mod.escape(opt)}")
                    elif j == selected_idx:
                        opt_lines.append(f"  ❌ {_LETTERS[j]}) {html_mod.escape(opt)}")
                    else:
                        opt_lines.append(f"  ◻️ {_LETTERS[j]}) {html_mod.escape(opt)}")

                opts_block = "\n".join(opt_lines)

                ref = html_mod.escape((r["ref_text"] or "").strip())
                ref_line = f"\n<i>{ref}</i>\n" if ref else ""

                msg = (
                    f"<b>❌ Q{i}/{total_wrong}</b>\n"
                    f"{ref_line}"
                    f"<b>{html_mod.escape(r['q_text'])}</b>\n\n"
                    f"{opts_block}\n\n"
                    f"🙋 <i>Your answer:</i> <s>{html_mod.escape(selected_text)}</s>\n"
                    f"✅ <i>Correct answer:</i> <b>{html_mod.escape(correct_text)}</b>"
                )

                explanation = (r["explanation"] or "").strip()
                if explanation:
                    msg += f"\n\n💡 <b>Explanation:</b>\n<i>{html_mod.escape(explanation)}</i>"

                msg += "\n\n" + "─" * 30

                bot.send_message(dm_chat_id, msg, parse_mode="HTML")
                time.sleep(0.3)   

            except Exception as eq:
                logging.error(f"Review mistake Q{i} send error: {eq}")
                continue

        bot.send_message(
            dm_chat_id,
            f"✅ <b>Review complete!</b>\n"
            f"Review complete for {total_wrong} wrong question(s). Practice them more! 💪",
            parse_mode="HTML"
        )

    except Exception as e:
        logging.error(f"_send_review_mistakes error: {e}")
        try:
            bot.send_message(dm_chat_id, "⚠️ Error sending mistakes. Please try again.")
        except Exception:
            pass


def _export_html(chat_id, quiz_id):
    with get_db() as conn:
        quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
        if not quiz: return safe_send(chat_id, f"Quiz {quiz_id} not found.")
        questions = conn.execute("SELECT * FROM questions WHERE quiz_id=? ORDER BY position,question_id", (quiz_id,)).fetchall()
    if not questions: return safe_send(chat_id, "No Qs.")
    q_blocks = []
    for i, q in enumerate(questions, 1):
        opts = json.loads(q["options"]); ref = html_mod.escape(q["ref_text"] or "")
        ref_html = f'<div class="ref">{ref}</div>' if ref else ""
        lis = "".join(
            f'<li class="correct">{_LETTERS[j]}) {html_mod.escape(o)}</li>' if j == q["correct_idx"]
            else f'<li>{_LETTERS[j]}) {html_mod.escape(o)}</li>' for j, o in enumerate(opts))
        q_blocks.append(f'<div class="question"><p class="qnum">Q{i}/{len(questions)}</p>{ref_html}'
            f'<p class="qtext">{html_mod.escape(q["q_text"])}</p><ul class="opts">{lis}</ul></div>')
    html_out = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"/><title>{html_mod.escape(quiz["title"])}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0;}}body{{font-family:'Segoe UI',sans-serif;background:#f0f4f8;}}
header{{background:linear-gradient(135deg,#1a73e8,#0b3d91);color:#fff;padding:32px 48px;}}h1{{font-size:26px;}}
.container{{max-width:820px;margin:24px auto;padding:0 20px 60px;}}.question{{background:#fff;border-radius:10px;padding:22px 26px;margin-bottom:18px;box-shadow:0 2px 8px rgba(0,0,0,.08);border-left:4px solid #1a73e8;}}
.qnum{{font-size:11px;color:#1a73e8;font-weight:700;margin-bottom:4px;}}.ref{{background:#f8f9fa;border-left:3px solid #aaa;padding:10px 14px;margin-bottom:12px;white-space:pre-wrap;font-size:13.5px;color:#333;}}
.qtext{{font-size:15px;font-weight:600;line-height:1.6;margin-bottom:14px;}}.opts{{list-style:none;display:grid;gap:7px;}}.opts li{{padding:8px 14px;border-radius:6px;background:#f8f9fa;border:1px solid #e0e0e0;font-size:14px;}}
.opts li.correct{{background:#e6f4ea;border-color:#34a853;color:#1b5e20;font-weight:600;}}.opts li.correct::after{{content:" ✓";}}</style></head><body>
<header><h1>📚 {html_mod.escape(quiz["title"])}</h1><p>{quiz_id} · {len(questions)} Qs · {datetime.now().strftime("%d %b %Y")}</p></header>
<div class="container">{"".join(q_blocks)}</div></body></html>"""
    f = io.BytesIO(html_out.encode("utf-8")); f.seek(0)
    try: bot.send_document(chat_id, InputFile(f, file_name=f"quiz_{quiz_id}.html"), caption=f"HTML: {quiz['title']} ({len(questions)} Qs)")
    except Exception as e: safe_send(chat_id, f"Export failed: {e}")

def _export_txt(chat_id, quiz_id):
    with get_db() as conn:
        quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
        if not quiz: return safe_send(chat_id, f"Quiz {quiz_id} not found.")
        questions = conn.execute("SELECT * FROM questions WHERE quiz_id=? ORDER BY position,question_id", (quiz_id,)).fetchall()
    if not questions: return safe_send(chat_id, "No Qs.")
    sep = "=" * 65
    lines = [sep, f"  {quiz['title'].upper()}", f"  {len(questions)} Qs | {datetime.now().strftime('%d %b %Y')}", sep, ""]
    akey = ["", sep, "  ANSWER KEY", sep]
    for i, q in enumerate(questions, 1):
        opts = json.loads(q["options"]); corr = q["correct_idx"]
        if q["ref_text"]: lines.append(f"Q{i}. [Ref] {q['ref_text'][:150]}")
        lines.append(f"Q{i}. {q['q_text']}")
        for j, o in enumerate(opts): lines.append(f"       {_LETTERS[j]}) {o}")
        lines.append(""); akey.append(f"  Q{i:>3}.  [{_LETTERS[corr]}]  {opts[corr]}")
    akey.append(sep)
    f = io.BytesIO("\n".join(lines + akey).encode("utf-8")); f.seek(0)
    try: bot.send_document(chat_id, InputFile(f, file_name=f"quiz_{quiz_id}.txt"), caption=f"Test: {quiz['title']} ({len(questions)} Qs)")
    except Exception as e: safe_send(chat_id, f"Export failed: {e}")

def _generate_quiz_pdf(quiz, questions):
    from fpdf import FPDF
    
    # 👉 FIXED: absolute path to ensure font files are always found.
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    
    title = str(quiz.get("title","Quiz")); qid = str(quiz.get("short_id") or quiz.get("quiz_id",""))
    nv = parse_neg_value(quiz.get("neg_marking","0"))
    nd = f"{nv:.4f}".rstrip("0").rstrip(".") if nv else "0"
    total_q = len(questions); labels = ["(A)","(B)","(C)","(D)","(E)","(F)","(G)","(H)","(I)","(J)"]
    class QPDF(FPDF):
        def header(self):
            if self.page_no()==1:
                self.set_fill_color(26,35,126);self.rect(0,0,210,26,"F")
                self.set_fill_color(229,57,53);self.rect(0,26,210,1,"F")
                self.set_text_color(255,255,255);self.set_font("hindi","B",18)
                self.set_xy(10,5);self.cell(190,10,title,align="C")
                self.set_font("hindi","",9);self.set_text_color(144,202,249)
                self.set_xy(10,16);self.cell(190,6,f"Quiz ID: {qid} | {total_q} Qs",align="C");self.set_y(32)
            else:
                self.set_fill_color(26,35,126);self.rect(0,0,210,13,"F")
                self.set_fill_color(229,57,53);self.rect(0,13,210,0.7,"F")
                self.set_text_color(255,255,255);self.set_font("hindi","B",10)
                self.set_xy(15,3);self.cell(90,7,title[:40])
                self.set_font("hindi","",9);pg=f"Page {self.page_no()}";pw=self.get_string_width(pg)
                self.set_xy(195-pw,3);self.cell(pw,7,pg);self.set_y(18)
        def footer(self):
            self.set_y(-12);self.set_draw_color(224,224,224);self.set_line_width(0.3)
            self.line(15,self.get_y(),195,self.get_y());self.ln(2)
            self.set_text_color(150,150,150);self.set_font("hindi","",7)
            self.cell(60,5,title[:25],align="L");self.cell(60,5,f"ID: {qid}",align="C");self.cell(60,5,f"Page {self.page_no()}",align="R")
    pdf = QPDF(); pdf.set_auto_page_break(True, margin=14)
    
    # 👉 FIXED: Path logic to dynamically load from the bot's true directory
    fr = os.path.join(BASE_DIR, "NotoSansDevanagari-Regular.ttf")
    fb = os.path.join(BASE_DIR, "NotoSansDevanagari-Bold.ttf")
    
    # Fallback to Mukta if NotoSans is missing for some reason
    if not os.path.exists(fr):
        fr = os.path.join(BASE_DIR, "Mukta-Regular.ttf")
        fb = os.path.join(BASE_DIR, "Mukta-Bold.ttf")

    if os.path.exists(fr): 
        pdf.add_font("hindi", "", fr)
        pdf.add_font("hindi", "B", fb if os.path.exists(fb) else fr)
    else: 
        raise FileNotFoundError(f"Font not found in directory: {BASE_DIR}. Make sure TTF files are present.")
        
    try: pdf.set_text_shaping(use_shaping_engine=True, script="Deva", language="hi")
    except Exception: pass
    pdf.add_page()
    inst = [f"• Total Questions: {total_q}",f"• Negative Marking: {nd}",f"• Timer: {quiz.get('timer_seconds',45)}s per question",
            "• Each question carries equal marks","• Answer is given below each question",
            f"• Date: {datetime.now().strftime('%d %b %Y')}"]
    lh,th,pad = 5.5,7,4; by = pdf.get_y(); bh = pad+th+len(inst)*lh+pad
    pdf.set_fill_color(245,245,245);pdf.set_draw_color(224,224,224);pdf.rect(10,by,190,bh,"DF")
    pdf.set_xy(15,by+pad);pdf.set_font("hindi","B",11);pdf.set_text_color(26,35,126)
    pdf.cell(0,th,"Instructions:",new_x="LMARGIN",new_y="NEXT")
    pdf.set_font("hindi","",9.5);pdf.set_text_color(51,51,51)
    for line in inst: pdf.set_x(17);pdf.cell(0,lh,line,new_x="LMARGIN",new_y="NEXT")
    pdf.set_y(by+bh+5)

    col_w = 91; col_gap = 8; left_x = 10; right_x = left_x + col_w + col_gap
    labels_loc = ["(A)","(B)","(C)","(D)","(E)","(F)","(G)","(H)","(I)","(J)"]
    col = 0  
    col_y = [pdf.get_y(), pdf.get_y()]  

    def draw_question_in_col(q, qn, col_idx):
        cx = left_x if col_idx == 0 else right_x
        cy = col_y[col_idx]
        qt = str(q.get("q_text",""))
        ref = str(q.get("ref_text","") or "").strip()
        opts_raw = q.get("options","[]")
        opts = json.loads(opts_raw) if isinstance(opts_raw,str) else (opts_raw or [])
        cor = q.get("correct_idx",0)

        ql = max(1, len(qt)//45+1)
        eh = 8 + ql*6 + len(opts)*5.5 + 7
        if ref: eh += max(1,len(ref)//55+1)*5 + 4

        if cy + eh > 282:
            pdf.add_page()
            col_y[0] = pdf.get_y()
            col_y[1] = pdf.get_y()
            cy = col_y[col_idx]
            cx = left_x if col_idx == 0 else right_x

        ct = cy
        if ref:
            pdf.set_xy(cx+2, cy)
            pdf.set_font("hindi","",8); pdf.set_text_color(85,85,85)
            pdf.set_fill_color(248,249,250)
            pdf.multi_cell(col_w-4, 4.5, ref, fill=True, new_x="LMARGIN", new_y="NEXT")
            cy = pdf.get_y(); pdf.ln(1)

        pdf.set_font("hindi","B",9.5); pdf.set_text_color(33,33,33)
        pdf.set_xy(cx, cy)
        pdf.multi_cell(col_w, 5.5, f"Q{qn}. {qt}", new_x="LMARGIN", new_y="NEXT")
        cy = pdf.get_y(); pdf.ln(1)

        pdf.set_font("hindi","",9); pdf.set_text_color(66,66,66)
        for i, o in enumerate(opts):
            lb = labels_loc[i] if i < len(labels_loc) else f"({i+1})"
            pdf.set_xy(cx+4, pdf.get_y())
            pdf.multi_cell(col_w-4, 5, f"{lb}  {str(o)}", new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

        al = labels_loc[cor] if 0 <= cor < len(labels_loc) else "?"
        at = str(opts[cor]) if 0 <= cor < len(opts) else "N/A"
        pdf.set_fill_color(232,245,233); pdf.set_draw_color(76,175,80); pdf.set_text_color(46,125,50)
        pdf.set_font("hindi","B",9); pdf.set_xy(cx, pdf.get_y())
        pdf.multi_cell(col_w, 6, f"  Ans: {al}  {at}", border=1, fill=True, new_x="LMARGIN", new_y="NEXT")
        cy = pdf.get_y()
        pdf.set_draw_color(224,224,224); pdf.set_line_width(0.2)
        pdf.line(cx, cy+1, cx+col_w, cy+1); pdf.ln(2)
        col_y[col_idx] = pdf.get_y()

    for q in questions:
        qn = q.get("position",0)+1
        draw_question_in_col(q, qn, col)
        col = 1 - col
        if col_y[0] > col_y[1] + 3:
            col = 1
        elif col_y[1] > col_y[0] + 3:
            col = 0
        pdf.set_y(max(col_y[0], col_y[1]))
    buf=io.BytesIO(pdf.output());buf.seek(0);return buf

def _export_pdf_quizpdf(chat_id, quiz_id):
    try: from fpdf import FPDF
    except ImportError: safe_send(chat_id,"⚠️ fpdf2 missing!");_export_txt(chat_id,quiz_id);return
    with get_db() as conn:
        quiz=conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
        if not quiz: return safe_send(chat_id,f"❌ Quiz {quiz_id} not found.")
        questions=conn.execute("SELECT * FROM questions WHERE quiz_id=? ORDER BY position,question_id", (quiz_id,)).fetchall()
    if not questions: return safe_send(chat_id,"❌ No Qs.")
    try: pm=bot.send_message(chat_id,"⏳ <b>PDF...</b>",parse_mode="HTML")
    except Exception: pm=None
    try:
        pb=_generate_quiz_pdf(dict(quiz),[dict(q) for q in questions])
        t=quiz["title"];sid=quiz.get("short_id") or str(quiz_id)
        cl=re.sub(r"[^\w\s\-]","",t);cl=re.sub(r"\s+","_",cl.strip())
        cap=f"📄 <b>{html_mod.escape(t)}</b>\n📊 {len(questions)} Qs | 🆔 <code>{sid}</code>"
        pb.seek(0);bot.send_document(chat_id,InputFile(pb,file_name=f"{cl}_{sid}.pdf"),caption=cap,parse_mode="HTML")
        if pm:
            try: bot.delete_message(chat_id,pm.message_id)
            except Exception: pass
    except FileNotFoundError: safe_send(chat_id,"❌ Font missing! Please check bot directory.")
    except Exception as e: safe_send(chat_id,f"❌ PDF: {e}")

def _export_practice_html(chat_id, quiz_id):
    try:
        time.sleep(3)
        with get_db() as conn:
            quiz=conn.execute("SELECT * FROM quizzes WHERE quiz_id=?",(quiz_id,)).fetchone()
            if not quiz: return
            questions=conn.execute("SELECT * FROM questions WHERE quiz_id=? ORDER BY position,question_id",(quiz_id,)).fetchall()
        if not questions: return
        nv=parse_neg_value(quiz["neg_marking"])
        nd=f"{nv:.6f}".rstrip('0').rstrip('.') if nv else "0"
        tq=len(questions);tm=max(10,(tq+2)//3);ts=tm*60
        ji=[{"q":q["q_text"],"ref":q["ref_text"] or "","opts":json.loads(q["options"]),"ans":q["correct_idx"]} for q in questions]
        jq=json.dumps(ji,ensure_ascii=False);st=html_mod.escape(quiz["title"])
        ho=f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>{st}</title>
<style>*{{box-sizing:border-box;margin:0;padding:0;}}body{{font-family:'Segoe UI',sans-serif;background:#f0f2f5;color:#222;}}
#ss{{max-width:480px;margin:60px auto;background:#fff;border-radius:16px;padding:32px 24px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.1);}}
#ss h1{{font-size:26px;color:#3b3f9e;}}#ss p{{color:#888;font-size:14px;margin-bottom:20px;}}
.ir{{display:flex;justify-content:space-between;align-items:center;padding:11px 0;border-bottom:1px solid #eee;font-size:15px;}}.il{{color:#888;}}.iv{{font-weight:600;}}
.timer-ctrl{{display:flex;align-items:center;gap:8px;}}.tc-btn{{width:28px;height:28px;border:none;border-radius:6px;background:#3b3f9e;color:#fff;font-size:16px;cursor:pointer;font-weight:700;line-height:1;}}
#sb{{margin-top:22px;width:100%;padding:14px;background:#3b3f9e;color:#fff;border:none;border-radius:10px;font-size:17px;cursor:pointer;}}
#hd{{background:#3b3f9e;color:#fff;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;}}
#hd h2{{font-size:15px;}}#ti{{font-size:20px;font-weight:700;color:#ffd700;}}
#qs{{display:none;max-width:680px;margin:16px auto;padding:0 12px 80px;}}.qc{{background:#fff;border-radius:12px;padding:20px;box-shadow:0 2px 10px rgba(0,0,0,.08);}}
.qm{{font-size:11px;color:#3b3f9e;font-weight:700;margin-bottom:4px;}}.qr{{background:#f8f9fa;border-left:3px solid #aaa;padding:9px 13px;margin-bottom:10px;font-size:13px;color:#444;white-space:pre-wrap;}}
.qt{{font-size:15.5px;font-weight:600;line-height:1.65;margin-bottom:14px;}}.qk{{font-size:12px;color:#3b3f9e;margin-bottom:10px;}}
.op{{display:block;width:100%;text-align:left;padding:11px 15px;margin:7px 0;border:1.5px solid #ddd;border-radius:8px;background:#fff;font-size:14.5px;cursor:pointer;}}
.op.correct{{background:#e6f9ee;border-color:#27ae60;color:#1a7a42;font-weight:600;}}.op.wrong{{background:#fdecea;border-color:#e74c3c;color:#c0392b;}}
#nv{{position:fixed;bottom:0;left:0;right:0;background:#fff;padding:10px 14px;display:none;justify-content:space-between;gap:8px;box-shadow:0 -2px 10px rgba(0,0,0,.1);}}
.nb{{flex:1;padding:12px;border:none;border-radius:8px;font-size:14px;cursor:pointer;font-weight:600;}}
#pb{{background:#eee;color:#444;}}#rb{{background:#fff3cd;color:#856404;border:1.5px solid #ffc107;}}#nb{{background:#3b3f9e;color:#fff;}}
#rs{{display:none;max-width:460px;margin:40px auto;background:#fff;border-radius:16px;padding:26px 20px;text-align:center;box-shadow:0 4px 20px rgba(0,0,0,.1);}}
.rt{{font-size:22px;font-weight:700;color:#3b3f9e;margin-bottom:18px;}}.rg{{display:grid;grid-template-columns:1fr 1fr;gap:11px;margin-bottom:18px;}}
.rb{{background:#f0f2f5;border-radius:10px;padding:13px;}}.rv{{font-size:21px;font-weight:700;}}.rl{{font-size:12px;color:#777;margin-top:3px;}}
.gc{{color:#27ae60;}}.rc{{color:#e74c3c;}}.bc{{color:#3b3f9e;}}
.ab{{width:100%;padding:12px;border:none;border-radius:9px;font-size:15px;cursor:pointer;color:#fff;margin-top:7px;font-weight:600;}}
#wl{{display:none;max-width:680px;margin:16px auto;padding:0 12px 60px;}}
.wq{{background:#fff;border-radius:12px;padding:18px 20px;margin-bottom:14px;box-shadow:0 2px 8px rgba(0,0,0,.07);border-left:4px solid #e74c3c;}}
.wq-num{{font-size:11px;color:#e74c3c;font-weight:700;margin-bottom:6px;}}
.wq-ref{{background:#fff8f0;border-left:3px solid #f39c12;padding:8px 12px;margin-bottom:10px;font-size:12.5px;color:#555;white-space:pre-wrap;border-radius:4px;}}
.wq-txt{{font-size:15px;font-weight:600;line-height:1.6;margin-bottom:12px;}}
.wq-opts{{list-style:none;display:grid;gap:6px;}}
.wq-opts li{{padding:9px 13px;border-radius:7px;background:#f8f9fa;border:1.5px solid #e0e0e0;font-size:14px;}}
.wq-opts li.correct{{background:#e6f4ea;border-color:#27ae60;color:#1b5e20;font-weight:700;}}
.wq-opts li.wrong{{background:#fdecea;border-color:#e74c3c;color:#c0392b;font-weight:600;}}
#wl-hd{{background:#e74c3c;color:#fff;padding:10px 16px;display:flex;justify-content:space-between;align-items:center;position:sticky;top:0;z-index:100;}}
#wl-hd h2{{font-size:15px;}}
.back-btn{{background:rgba(255,255,255,.25);border:none;color:#fff;padding:6px 14px;border-radius:6px;font-size:13px;cursor:pointer;font-weight:600;}}
</style></head><body>
<div id="ss"><h1>📋 Practice</h1><p>Quiz</p>
<div class="ir"><span class="il">Topic</span><span class="iv">{st}</span></div>
<div class="ir"><span class="il">Qs</span><span class="iv">{tq}</span></div>
<div class="ir"><span class="il">Timer</span>
  <span class="timer-ctrl">
    <button class="tc-btn" onclick="adjTimer(-1)" title="−1 min">−</button>
    <span class="iv" id="tv">{tm}m</span>
    <button class="tc-btn" onclick="adjTimer(1)" title="+1 min">+</button>
  </span>
</div>
<div class="ir"><span class="il">Neg</span><span class="iv">-{nd}</span></div>
<button id="sb" onclick="go_start()">▶ Start</button></div>
<div id="qs"><div id="hd"><h2 id="qc">Q 1/{tq}</h2><div id="ti">--:--</div></div>
<div class="qc" style="margin-top:14px;"><div class="qm" id="qm"></div><div class="qr" id="qr" style="display:none"></div>
<div class="qt" id="qt"></div><div class="qk">+1 / -{nd}</div><div id="os"></div></div></div>
<div id="nv"><button class="nb" id="pb" onclick="mv(-1)">◀</button><button class="nb" id="rb" onclick="mr()">🔖</button>
<button class="nb" id="nb" onclick="mv(1)">▶</button></div>
<div id="rs"><div class="rt">🏆 Result</div><div class="rg">
<div class="rb"><div class="rv bc" id="r1"></div><div class="rl">Score</div></div>
<div class="rb"><div class="rv" id="r2"></div><div class="rl">Acc</div></div>
<div class="rb"><div class="rv gc" id="r3"></div><div class="rl">✅</div></div>
<div class="rb"><div class="rv rc" id="r4"></div><div class="rl">❌</div></div>
<div class="rb"><div class="rv" id="r5"></div><div class="rl">⏭</div></div>
<div class="rb"><div class="rv" id="r6"></div><div class="rl">⏱</div></div></div>
<button class="ab" style="background:#3b3f9e;" onclick="ra()">🔁 Again</button>
<button class="ab" style="background:#e74c3c;" onclick="rw()">📝 Review Mistakes</button></div>
<div id="wl">
  <div id="wl-hd"><h2 id="wl-title">📝 Review Mistakes</h2><button class="back-btn" onclick="wb()">✕ Close</button></div>
  <div id="wl-body" style="padding:12px 0;"></div>
</div>
<script>const AQ={jq};const NG={nv};let customTS={ts};
let Q=AQ.slice(),ci=0,an={{}},rv=new Set(),tl=customTS,tv=null,t0=null;
function adjTimer(d){{customTS=Math.max(60,customTS+d*60);document.getElementById('tv').textContent=Math.floor(customTS/60)+'m';}}
function go_start(){{document.getElementById('ss').style.display='none';document.getElementById('qs').style.display='block';document.getElementById('nv').style.display='flex';tl=customTS;t0=Date.now();st();sq(0);}}
function st(){{tv=setInterval(()=>{{tl--;const m=String(Math.floor(tl/60)).padStart(2,'0'),s=String(tl%60).padStart(2,'0');document.getElementById('ti').textContent=m+':'+s;if(tl<=0){{clearInterval(tv);sr();}}}},1000);}}
function sq(i){{ci=i;const q=Q[i];document.getElementById('qc').textContent='Q '+(i+1)+'/'+Q.length;document.getElementById('qm').textContent='Q '+(i+1);const r=document.getElementById('qr');if(q.ref){{r.style.display='block';r.textContent=q.ref;}}else{{r.style.display='none';}}document.getElementById('qt').textContent='Q'+(i+1)+'. '+q.q;const c=document.getElementById('os');c.innerHTML='';q.opts.forEach((o,j)=>{{const b=document.createElement('button');b.className='op';b.textContent=o;if(an[i]!==undefined){{if(j===an[i])b.classList.add(j===q.ans?'correct':'wrong');else if(j===q.ans)b.classList.add('correct');b.disabled=true;}}else{{b.onclick=()=>pk(i,j);}}c.appendChild(b);}});document.getElementById('pb').disabled=i===0;document.getElementById('nb').textContent=i===Q.length-1?'Submit ✓':'Next ▶';document.getElementById('rb').style.background=rv.has(i)?'#ffc107':'';}}
function pk(qi,oi){{an[qi]=oi;const q=Q[qi];document.querySelectorAll('.op').forEach((b,j)=>{{b.disabled=true;if(j===oi)b.classList.add(j===q.ans?'correct':'wrong');else if(j===q.ans)b.classList.add('correct');}});setTimeout(()=>mv(1),700);}}
function mv(d){{const n=ci+d;if(n<0)return;if(n>=Q.length){{clearInterval(tv);sr();return;}}sq(n);}}
function mr(){{rv.has(ci)?rv.delete(ci):rv.add(ci);sq(ci);}}
function sr(){{document.getElementById('qs').style.display='none';document.getElementById('nv').style.display='none';document.getElementById('rs').style.display='block';let c=0,w=0,sk=0;Q.forEach((q,i)=>{{if(an[i]===undefined)sk++;else if(an[i]===q.ans)c++;else w++;}});const s=c-w*NG,a=(c+w)>0?((c/(c+w))*100).toFixed(1):'0.0';const e=Math.floor((Date.now()-t0)/1000);document.getElementById('r1').textContent=s.toFixed(2);document.getElementById('r2').textContent=a+'%';document.getElementById('r3').textContent=c;document.getElementById('r4').textContent=w;document.getElementById('r5').textContent=sk;document.getElementById('r6').textContent=Math.floor(e/60)+'m '+String(e%60).padStart(2,'0')+'s';}}
function ra(){{Q=AQ.slice();an={{}};rv=new Set();tl=customTS;ci=0;document.getElementById('rs').style.display='none';document.getElementById('qs').style.display='block';document.getElementById('nv').style.display='flex';t0=Date.now();clearInterval(tv);st();sq(0);}}
function wb(){{document.getElementById('wl').style.display='none';document.getElementById('rs').style.display='block';}}
function rw(){{
  const wrongs=AQ.filter((q,i)=>an[i]!==undefined&&an[i]!==q.ans);
  if(!wrongs.length){{alert('No wrong answers! Great job! 🎉');return;}}
  const LB='ABCDEFGHIJ';
  let html='';
  wrongs.forEach((q,wi)=>{{
    let opts='';
    q.opts.forEach((o,j)=>{{
      let cls='';
      if(j===q.ans) cls='correct';
      else if(j===an[AQ.indexOf(q)]) cls='wrong';
      opts+=`<li class="${{cls}}">${{LB[j]}}) ${{o}}${{j===q.ans?' ✓ (Correct)':j===an[AQ.indexOf(q)]?' ✗ (Your answer)':''}}</li>`;
    }});
    const refHtml=q.ref?`<div class="wq-ref">📖 ${{q.ref}}</div>`:'';
    html+=`<div class="wq"><p class="wq-num">❌ Wrong Q${{wi+1}} of ${{wrongs.length}}</p>${{refHtml}}<p class="wq-txt">Q${{AQ.indexOf(q)+1}}. ${{q.q}}</p><ul class="wq-opts">${{opts}}</ul></div>`;
  }});
  document.getElementById('wl-body').innerHTML=html;
  document.getElementById('wl-title').textContent='📝 Review Mistakes ('+wrongs.length+' wrong)';
  document.getElementById('rs').style.display='none';
  document.getElementById('wl').style.display='block';
  window.scrollTo(0,0);
}}</script></body></html>"""
        f=io.BytesIO(ho.encode("utf-8"));f.seek(0)
        bot.send_document(chat_id,InputFile(f,file_name=f"practice_{quiz_id}.html"),
            caption=f"📋 {st}\n❓ {tq} Qs | ⏱ {tm}m | ➖ -{nd}\n\n💡 Tip: You can adjust the timer using − + buttons before starting!",parse_mode=None)
    except Exception as e: logging.error(f"Practice HTML: {e}")

# ══════════════════════════════════════════════════════════════════════════════
#  COMMANDS
# ══════════════════════════════════════════════════════════════════════════════
def is_group(m):
    if isinstance(m, int): return m < 0
    try: return m.chat.type in ("group","supergroup","channel")
    except AttributeError: return False

def group_only_reply(msg):
    if is_group(msg):
        bot.send_message(msg.chat.id, "ℹ️ Sent me in Dm!", reply_markup=ReplyKeyboardRemove())
        return True
    return False

@bot.message_handler(commands=["logs"])
def cmd_logs(msg):
    if not is_owner(msg.from_user.id): return bot.send_message(msg.chat.id, "🚫")
    try:
        if os.path.exists('bot_activity.log'):
            with open('bot_activity.log','rb') as f: bot.send_document(msg.chat.id, f, caption="📂 Logs")
        else: bot.send_message(msg.chat.id, "No log yet.")
    except Exception as e: bot.send_message(msg.chat.id, f"⚠️ {e}")

@bot.message_handler(commands=["start"])
def cmd_start(msg):
    register_user(msg)
    uid, parts = msg.from_user.id, msg.text.split(maxsplit=1)
    if is_banned(uid): return bot.send_message(msg.chat.id, "🚫 Banned.")
    if is_group(msg):
        if len(parts) > 1 and parts[1].startswith("quiz_"):
            if not is_group_admin(msg.chat.id, uid):
                try:
                    quiz_id_check = int(parts[1][5:])
                    with get_db() as conn:
                        qrow = conn.execute("SELECT creator_id FROM quizzes WHERE quiz_id=?", (quiz_id_check,)).fetchone()
                    if not qrow or qrow["creator_id"] != uid:
                        return safe_send(msg.chat.id, "🚫 Only the quiz creator or a group admin can start the quiz.")
                except Exception:
                    return safe_send(msg.chat.id, "🚫 Only the quiz creator or a group admin can start the quiz.")
            try: set_state(uid,"idle"); _do_start_quiz(msg.chat.id, uid, int(parts[1][5:]))
            except Exception as e: safe_send(msg.chat.id, f"⚠️ {e}")
        return
    if len(parts) > 1 and parts[1].startswith("quiz_"):
        if not is_approved_user(uid):
            return _send_pending_msg(msg.chat.id, uid)
        try: set_state(uid,"idle"); _do_start_quiz(msg.chat.id, uid, int(parts[1][5:])); return
        except Exception: pass
    set_state(uid,"idle"); _wizard.pop(uid,None)
    if not is_approved_user(uid):
        return _send_pending_msg(msg.chat.id, uid)
    
    kb = InlineKeyboardMarkup(row_width=1)
    kb.add(InlineKeyboardButton("📊 View Premium Dashboard", web_app=WebAppInfo(url="https://bpsc-premium.vercel.app")))
    kb.add(InlineKeyboardButton("📝 Create a Quiz", callback_data="help_create")) 

    msg_text = (
        f"Hello *{msg.from_user.first_name or 'there'}* 🌟!\n\n"
        f"Welcome to **LAKSHYA** 🎯\n"
        f"Your BPSC preparation dashboard is ready. "
        f"Tap the button below to view your Live Rank and Progress!"
    )
    bot.send_message(msg.chat.id, msg_text, parse_mode="Markdown", reply_markup=kb)

def _send_pending_msg(chat_id, uid):
    if uid in _pending_cache:
        bot.send_message(chat_id,
            f"⏳ <b>Approval Pending...</b>\n\nYour request has been sent to the bot owner.\n"
            f"Please wait for approval.\n\n"
            f"👤 Owner: <b>{html_mod.escape(OWNER_NAME)}</b>\n"
            f"📲 Contact: {OWNER_USERNAME}",
            parse_mode="HTML")
    else:
        _pending_cache[uid] = True
        bot.send_message(chat_id,
            f"👋 <b>Welcome!</b>\n\nThis bot requires owner approval to use.\n"
            f"Your request has been sent to the owner.\n\n"
            f"👤 Owner: <b>{html_mod.escape(OWNER_NAME)}</b>\n"
            f"📲 Contact: {OWNER_USERNAME}\n\n"
            f"⏳ Please wait for approval...",
            parse_mode="HTML")

@bot.message_handler(commands=["features", "feature"])
def cmd_features(msg):
    if group_only_reply(msg): return
    text = (
        "🤖 <b>QuizBot Pro — All Commands</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📝 <b>Creation</b>\n"
        "/create /done /cancel /edit /stopedit\n"
        "/myquizzes — list all your quizzes with IDs\n\n"
        "🎮 <b>Session</b>\n"
        "/stop — stop running quiz\n"
        "/pause /resume — pause or resume quiz\n"
        "/fast /slow — change speed (admins too)\n\n"
        "📊 <b>Results & Report Card</b>\n"
        "/result — score with per-question breakdown\n"
        "<b>Review Mistakes</b> — button after quiz: wrong Qs with correct answers\n"
        "<b>Weak Topic Analysis</b> — auto after result: shows your weakest question groups\n\n"
        "📄 <b>Export</b>\n"
        "💡 Usage: /command quiz_id — e.g. /quizpdf AB12CD34\n"
        "/createhtml — HTML file with all answers\n"
        "/quizpdf — 2-column PDF with answers\n"
        "/practice — interactive HTML: timer + explanation per question\n\n"
        "⚔️ <b>Tournament</b>\n"
        "/tournament &lt;id&gt; — create elimination tournament in group\n"
        "   Players tap Join button to enter\n"
        "/tstart — begin tournament (creator only)\n"
        "   Round-wise leaderboard sent automatically\n\n"
        "⚙️ <b>Settings</b>\n"
        "/html — toggle HTML result reports on/off\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )
    safe_send(msg.chat.id, text, parse_mode="HTML")

@bot.message_handler(commands=["stats"])
def cmd_stats(msg):
    if group_only_reply(msg): return
    with get_db() as conn:
        u=conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        q=conn.execute("SELECT COUNT(*) FROM quizzes").fetchone()[0]
        n=conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        s=conn.execute("SELECT COUNT(*) FROM active_sessions WHERE is_completed=1").fetchone()[0]
    safe_send(msg.chat.id, f"*Stats*\nUsers:`{u}` Quizzes:`{q}` Qs:`{n}` Sessions:`{s}`", parse_mode="Markdown")

@bot.message_handler(commands=["create"])
def cmd_create(msg):
    if group_only_reply(msg): return
    register_user(msg); uid = msg.from_user.id
    if not is_approved_user(uid): return _send_pending_msg(msg.chat.id, uid)
    set_state(uid,"awaiting_quiz_title")
    _wizard[uid] = {"title":None,"questions":[],"neg":"0","quiz_type":"free","timer":45,"section":0}
    safe_send(msg.chat.id, "✅ *New Quiz*\nSend *quiz name*.\n_/cancel to abort_", parse_mode="Markdown")

@bot.message_handler(commands=["cancel"])
def cmd_cancel(msg):
    if group_only_reply(msg): return
    set_state(msg.from_user.id,"idle"); _wizard.pop(msg.from_user.id,None)
    safe_send(msg.chat.id, "Cancelled.", reply_markup=ReplyKeyboardRemove())

@bot.message_handler(commands=["done"])
def cmd_done(msg):
    if group_only_reply(msg): return
    uid = msg.from_user.id; state = get_state(uid)
    if state not in ("adding_questions","awaiting_quiz_title"): return safe_send(msg.chat.id, "/create first.")
    store = _wizard.get(uid, {})
    if not store.get("questions"): return safe_send(msg.chat.id, "No questions yet.")
    set_state(uid,"awaiting_timer")
    safe_send(msg.chat.id, f"✅ *{len(store['questions'])} Question(s)*\n\n⏳ *Timer (seconds, >9):*", parse_mode="Markdown")

@bot.message_handler(commands=["edit"])
def cmd_edit(msg):
    if group_only_reply(msg): return
    register_user(msg); uid, parts = msg.from_user.id, msg.text.split(maxsplit=1)
    if len(parts) > 1:
        quiz = find_quiz(uid, parts[1].strip())
        if quiz:
            with get_db() as conn: qc = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz["quiz_id"],)).fetchone()[0]
            return send_edit_panel(msg.chat.id, quiz, qc)
        return safe_send(msg.chat.id, "Not found.")
    set_state(uid,"awaiting_edit_quiz_id")
    _wizard[uid] = {"edit_mode":True,"questions":[],"quiz_id":None}
    safe_send(msg.chat.id, "Send *Quiz ID*.", parse_mode="Markdown")

@bot.message_handler(commands=["stopedit"])
def cmd_stopedit(msg):
    if group_only_reply(msg): return
    uid = msg.from_user.id
    if get_state(uid) != "editing_questions": return safe_send(msg.chat.id, "Not editing.")
    store = _wizard.get(uid, {}); qs, qid = store.get("questions",[]), store.get("quiz_id")
    if qs and qid:
        save_questions(qid, qs); _invalidate_quiz_cache(qid)
        safe_send(msg.chat.id, f"Saved *{len(qs)}* Q(s).", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    else: safe_send(msg.chat.id, "Nothing.", reply_markup=ReplyKeyboardRemove())
    set_state(uid,"idle"); _wizard.pop(uid,None)

@bot.message_handler(commands=["myquizzes"])
def cmd_myquizzes(msg):
    if group_only_reply(msg): return
    try:
        register_user(msg); uid = msg.from_user.id
        with get_db() as conn:
            rows = conn.execute(
                "SELECT z.quiz_id, z.short_id, z.title, z.quiz_type, z.timer_seconds, "
                "COUNT(q.question_id) AS cnt "
                "FROM quizzes z LEFT JOIN questions q ON z.quiz_id=q.quiz_id "
                "WHERE z.creator_id=? "
                "GROUP BY z.quiz_id, z.short_id, z.title, z.quiz_type, z.timer_seconds, z.created_at "
                "ORDER BY z.created_at DESC",
                (uid,)).fetchall()
        if not rows:
            return safe_send(msg.chat.id, "📭 No quizzes found.\n\nUse /create to make one!")
        lines = ["📋 <b>Your Quizzes:</b>\n"]
        for r in rows:
            sid   = html_mod.escape(str(r['short_id'] or r['quiz_id']))
            title = html_mod.escape(str(r['title']))
            qtype = "🔓" if r['quiz_type'] == 'free' else "🔒"
            lines.append(f"{qtype} <code>{sid}</code> — <b>{title}</b> ({r['cnt']} Qs)")
        safe_send(msg.chat.id, "\n".join(lines), parse_mode="HTML")
    except Exception as e:
        logging.error(f"cmd_myquizzes error: {e}", exc_info=True)
        safe_send(msg.chat.id, f"⚠️ Error loading quizzes: {e}")



def _countdown_and_start(chat_id, uid, quiz_id, show_countdown=True, question_ids=None):
    cached = _cache_quiz_data(quiz_id)
    if not cached: 
        safe_send(chat_id, f"⚠️ Quiz {quiz_id} not found.")
        return None
    quiz, all_qs = cached["quiz"], cached["questions"]
    if not all_qs: 
        safe_send(chat_id, "⚠️ No Qs.")
        return None
    # Tournament round: use specific question slice
    if question_ids:
        q_map = cached["q_map"]
        selected_qs = [q_map[qid] for qid in question_ids if qid in q_map]
        if not selected_qs:
            safe_send(chat_id, "⚠️ No questions available for this round.")
            return None
    else:
        selected_qs = all_qs
    with get_db() as conn:
        if conn.execute("SELECT session_id FROM active_sessions WHERE user_id=? AND chat_id=? AND is_completed=0", (uid, chat_id)).fetchone():
            safe_send(chat_id, "⚠️ Active session. /stop first.")
            return None
        q_ids = [q["question_id"] for q in selected_qs]
        if quiz.get("shuffle_q"): random.shuffle(q_ids)
        cur = conn.execute("INSERT INTO active_sessions(user_id,quiz_id,chat_id,total_q,shuffled_order) VALUES(?,?,?,?,?) RETURNING session_id",
            (uid, quiz_id, chat_id, len(selected_qs), json.dumps(q_ids)))
        sid = cur.fetchone()[0]
    _cache_session(sid, {"session_id":sid,"user_id":uid,"quiz_id":quiz_id,"chat_id":chat_id,
        "current_q_idx":0,"is_paused":0,"is_completed":0,"total_q":len(selected_qs),
        "shuffled_order":json.dumps(q_ids),"start_time":int(time.time()),"end_time":None})
    gm = None
    if show_countdown and is_group(chat_id):
        try:
            bot.send_message(chat_id, f"🏁 *{quiz['title']}*\n📊 {len(all_qs)} Qs · ⏱ {quiz['timer_seconds']}s", parse_mode="Markdown")
            time.sleep(0.3); cd = bot.send_message(chat_id, "🟡 *Ready...*", parse_mode="Markdown")
            time.sleep(0.8); bot.edit_message_text("🟠 *Steady...*", chat_id, cd.message_id, parse_mode="Markdown")
            time.sleep(0.8); bot.edit_message_text("🟢 *GO! 🚀*", chat_id, cd.message_id, parse_mode="Markdown")
            time.sleep(0.3); gm = cd.message_id
        except Exception: pass
    else:
        try: bot.send_message(chat_id, f"🏁 *{quiz['title']}!*\n📊 {len(all_qs)} Qs · ⏱ {quiz['timer_seconds']}s", parse_mode="Markdown")
        except Exception: pass
    send_next_poll(sid)
    if gm:
        try: bot.delete_message(chat_id, gm)
        except Exception: pass
    
    return sid

def _do_start_quiz(chat_id, uid, quiz_id, question_ids=None): 
    return _countdown_and_start(chat_id, uid, quiz_id, question_ids=question_ids)

@bot.message_handler(commands=["pause"])
def cmd_pause(msg):
    uid = msg.from_user.id
    with get_db() as conn:
        s = conn.execute("SELECT session_id,user_id FROM active_sessions WHERE chat_id=? AND is_completed=0 ORDER BY session_id DESC LIMIT 1", (msg.chat.id,)).fetchone()
        if not s: return safe_send(msg.chat.id, "No session.")
        if uid != s["user_id"] and not is_group_admin(msg.chat.id, uid):
            return safe_send(msg.chat.id, "🚫 Only quiz owner or group admin can do this.")
        conn.execute("UPDATE active_sessions SET is_paused=1 WHERE session_id=?", (s["session_id"],))
    sid = s["session_id"]
    if sid in _session_cache: _session_cache[sid]["is_paused"] = 1
    _cancel_auto_timer(sid); safe_send(msg.chat.id, "⏸ Paused. /resume")

@bot.message_handler(commands=["resume"])
def cmd_resume(msg):
    uid = msg.from_user.id
    with get_db() as conn:
        s = conn.execute("SELECT session_id,user_id FROM active_sessions WHERE chat_id=? AND is_completed=0 ORDER BY session_id DESC LIMIT 1", (msg.chat.id,)).fetchone()
        if not s: return safe_send(msg.chat.id, "No session.")
        if uid != s["user_id"] and not is_group_admin(msg.chat.id, uid):
            return safe_send(msg.chat.id, "🚫 Only quiz owner or group admin can do this.")
        conn.execute("UPDATE active_sessions SET is_paused=0 WHERE session_id=?", (s["session_id"],))
    sid = s["session_id"]
    if sid in _session_cache: _session_cache[sid]["is_paused"] = 0
    safe_send(msg.chat.id, "▶️ Resumed!"); send_next_poll(sid)

@bot.message_handler(commands=["stop"])
def cmd_stop(msg):
    uid = msg.from_user.id
    with get_db() as conn:
        s = conn.execute("SELECT session_id,user_id FROM active_sessions WHERE chat_id=? AND is_completed=0 ORDER BY session_id DESC LIMIT 1", (msg.chat.id,)).fetchone()
        if not s: return safe_send(msg.chat.id, "No session.")
        if uid != s["user_id"] and not is_group_admin(msg.chat.id, uid):
            return safe_send(msg.chat.id, "🚫 Only quiz owner or group admin can do this.")
        sess = conn.execute("SELECT * FROM active_sessions WHERE session_id=?", (s["session_id"],)).fetchone()
        quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (sess["quiz_id"],)).fetchone()
        conn.execute("UPDATE active_sessions SET is_completed=1,end_time=(CAST(EXTRACT(EPOCH FROM NOW()) AS INTEGER)) WHERE session_id=?", (s["session_id"],))
    _session_cache.pop(s["session_id"], None); _cancel_auto_timer(s["session_id"])
    safe_send(msg.chat.id, "🛑 *Stopped.*", parse_mode="Markdown")
    nv = parse_neg_value(quiz["neg_marking"]) if quiz else 0.0
    sc_name = ""
    try:
        with get_db() as conn:
            cr = conn.execute("SELECT first_name FROM users WHERE user_id=?", (sess["user_id"],)).fetchone()
            if cr and cr["first_name"]: sc_name = cr["first_name"]
    except Exception: pass
    _send_leaderboard(s["session_id"], msg.chat.id, quiz["title"] if quiz else "Quiz", nv, sess["total_q"], sess["start_time"], sc_name)
    if quiz: _bg_run(lambda: _export_practice_html(msg.chat.id, sess["quiz_id"]))

@bot.message_handler(commands=["fast"])
def cmd_fast(msg):
    uid, parts = msg.from_user.id, msg.text.split()
    delta = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
    with get_db() as conn:
        s = conn.execute("SELECT session_id,quiz_id,user_id FROM active_sessions WHERE chat_id=? AND is_completed=0 ORDER BY session_id DESC LIMIT 1", (msg.chat.id,)).fetchone()
        if not s: return safe_send(msg.chat.id, "⚠️ No quiz.")
        if uid != s["user_id"] and not is_group_admin(msg.chat.id, uid):
            return safe_send(msg.chat.id, "🚫 Only quiz owner or group admin can do this.")
        quiz = conn.execute("SELECT timer_seconds FROM quizzes WHERE quiz_id=?", (s["quiz_id"],)).fetchone()
        nt = max(10, int(quiz["timer_seconds"]) - delta)
        conn.execute("UPDATE quizzes SET timer_seconds=? WHERE quiz_id=?", (nt, s["quiz_id"]))
    _invalidate_quiz_cache(s["quiz_id"]); safe_send(msg.chat.id, f"⚡ <b>{nt}s</b>", parse_mode="HTML")

@bot.message_handler(commands=["slow"])
def cmd_slow(msg):
    uid, parts = msg.from_user.id, msg.text.split()
    delta = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 5
    with get_db() as conn:
        s = conn.execute("SELECT session_id,quiz_id,user_id FROM active_sessions WHERE chat_id=? AND is_completed=0 ORDER BY session_id DESC LIMIT 1", (msg.chat.id,)).fetchone()
        if not s: return safe_send(msg.chat.id, "⚠️ No quiz.")
        if uid != s["user_id"] and not is_group_admin(msg.chat.id, uid):
            return safe_send(msg.chat.id, "🚫 Only quiz owner or group admin can do this.")
        quiz = conn.execute("SELECT timer_seconds FROM quizzes WHERE quiz_id=?", (s["quiz_id"],)).fetchone()
        nt = min(300, int(quiz["timer_seconds"]) + delta)
        conn.execute("UPDATE quizzes SET timer_seconds=? WHERE quiz_id=?", (nt, s["quiz_id"]))
    _invalidate_quiz_cache(s["quiz_id"]); safe_send(msg.chat.id, f"🐢 <b>{nt}s</b>", parse_mode="HTML")

@bot.message_handler(commands=["result"])
def cmd_result(msg):
    if group_only_reply(msg): return
    register_user(msg); send_individual_result(msg.chat.id, msg.from_user.id)

@bot.message_handler(commands=["html"])
def cmd_html(msg):
    if group_only_reply(msg): return
    register_user(msg); uid = msg.from_user.id
    with get_db() as conn:
        old = conn.execute("SELECT html_toggle FROM users WHERE user_id=?", (uid,)).fetchone()
        new = 1 - int(old["html_toggle"] or 0)
        conn.execute("UPDATE users SET html_toggle=? WHERE user_id=?", (new, uid))
    safe_send(msg.chat.id, f"HTML: *{'ON' if new else 'OFF'}*", parse_mode="Markdown")

@bot.message_handler(commands=["practice"])
def cmd_practice(msg):
    if group_only_reply(msg): return
    register_user(msg); uid, parts = msg.from_user.id, msg.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].strip().isdigit():
        safe_send(msg.chat.id, "⏳..."); _bg_run(lambda: _export_practice_html(msg.chat.id, int(parts[1].strip())))
    else:
        with get_db() as conn: last = conn.execute("SELECT quiz_id FROM active_sessions WHERE user_id=? ORDER BY session_id DESC LIMIT 1", (uid,)).fetchone()
        if last: safe_send(msg.chat.id, "⏳..."); _bg_run(lambda: _export_practice_html(msg.chat.id, last["quiz_id"]))
        else: safe_send(msg.chat.id, "`/practice <id>`", parse_mode="Markdown")

@bot.message_handler(commands=["createhtml"])
def cmd_createhtml(msg):
    if group_only_reply(msg): return
    register_user(msg); uid, parts = msg.from_user.id, msg.text.split(maxsplit=1)
    if len(parts) > 1:
        quiz = find_quiz(uid, parts[1].strip())
        if quiz: _export_html(msg.chat.id, quiz["quiz_id"])
        else: safe_send(msg.chat.id, "❌ Quiz not found.")
    else: set_state(uid,"awaiting_html_id"); safe_send(msg.chat.id, "Send *Quiz ID*.", parse_mode="Markdown")

@bot.message_handler(commands=["quizpdf"])
def cmd_quizpdf(msg):
    if group_only_reply(msg): return
    register_user(msg); uid, parts = msg.from_user.id, msg.text.split(maxsplit=1)
    if len(parts) > 1:
        sid = parts[1].strip()
        if sid.isdigit(): return safe_send(msg.chat.id, "❌ Please use Quiz ID (e.g. ZGPZIQKF), not numeric ID.")
        with get_db() as conn:
            quiz = conn.execute("SELECT * FROM quizzes WHERE short_id=? AND creator_id=?", (sid.upper(), uid)).fetchone()
        if quiz: _bg_run(lambda: _export_pdf_quizpdf(msg.chat.id, quiz['quiz_id']))
        else: safe_send(msg.chat.id, "❌ Not found.")
    else: set_state(uid,"awaiting_txt_id"); safe_send(msg.chat.id, "Send *Quiz ID*.", parse_mode="Markdown")

@bot.message_handler(content_types=["document"])
def handle_document(msg):
    register_user(msg)
    if is_group(msg): return
    uid, state = msg.from_user.id, get_state(msg.from_user.id)
    if state not in ("adding_questions","awaiting_quiz_title","editing_questions"):
        return safe_send(msg.chat.id, "Use /create first.")
    doc, fname = msg.document, msg.document.file_name or "upload"
    if doc.file_size and doc.file_size > 10*1024*1024:
        return safe_send(msg.chat.id, "Max 10 MB.")

    try:
        _pm = bot.send_message(msg.chat.id, f"⏳ `{fname}`...", parse_mode="Markdown")
    except Exception:
        _pm = None

    try:
        raw = bot.download_file(bot.get_file(doc.file_id).file_path)
        content = raw.decode("utf-8", errors="replace")
    except Exception as e:
        if _pm:
            try: bot.delete_message(msg.chat.id, _pm.message_id)
            except Exception: pass
        return safe_send(msg.chat.id, f"Download failed: {e}")

    try:
        parsed, errors = detect_and_parse(fname, content)
    except Exception as e:
        if _pm:
            try: bot.delete_message(msg.chat.id, _pm.message_id)
            except Exception: pass
        return safe_send(msg.chat.id, f"Parse error: {e}")

    seen, unique = set(), []
    for q in parsed:
        key = q[0][:80] + "|" + q[1][:80] + "|" + str(q[2])[:60]
        if key not in seen:
            seen.add(key)
            unique.append(q)

    if not unique:
        if _pm:
            try: bot.delete_message(msg.chat.id, _pm.message_id)
            except Exception: pass
        return safe_send(msg.chat.id, f"No valid Qs.\n" + "\n".join(errors[:6]))

    if True:
        if state == "awaiting_quiz_title":
            store = _wizard.setdefault(uid, {"title": fname[:50], "questions": [], "neg": "0", "quiz_type": "free", "timer": 45, "section": 0})
            if not store.get("title"):
                store["title"] = fname[:50]
        store = _wizard.setdefault(uid, {"questions": []})
        store.setdefault("questions", []).extend(unique)
        if _pm:
            try: bot.delete_message(msg.chat.id, _pm.message_id)
            except Exception: pass
        if state == "editing_questions":
            set_state(uid, "editing_questions")
            safe_send(msg.chat.id, f"✅ *{len(unique)}* questions queued!\nTotal: *{len(store['questions'])}*\n\n/stopedit to save.", parse_mode="Markdown")
        else:
            set_state(uid, "adding_questions")
            safe_send(msg.chat.id, f"✅ *{len(unique)}* added! Total: *{len(store['questions'])}*\n/done to finish.", parse_mode="Markdown")

    if errors:
        safe_send(msg.chat.id, f"*{len(errors)} skipped:*\n" + "\n".join(f"• {e}" for e in errors[:6]), parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: True)
def handle_callback(call):
    uid, data, cid, mid = call.from_user.id, call.data or "", call.message.chat.id, call.message.message_id
    if data.startswith("qs_"):
        bot.answer_callback_query(call.id, "Starting..."); _do_start_quiz(cid, uid, int(data[3:]))
    elif data.startswith("ep_"):
        parts = data.split("_"); action = parts[1]; quiz_id = int(parts[2])
        with get_db() as conn:
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            qc   = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()[0]
        if not quiz and action != "close":
            return bot.answer_callback_query(call.id, "❌ Quiz not found.", show_alert=True)
        if quiz and quiz["creator_id"] != uid:
            return bot.answer_callback_query(call.id, "🚫 Only the creator can do this.", show_alert=True)

        if action == "close":
            bot.answer_callback_query(call.id)
            try: bot.delete_message(cid, mid)
            except Exception: pass

        elif action == "done":
            bot.answer_callback_query(call.id, "✅ Done!")
            try: bot.delete_message(cid, mid)
            except Exception: pass

        elif action == "back":
            bot.answer_callback_query(call.id)
            send_edit_panel(cid, quiz, qc, mid)

        elif action == "type":
            new_type = "paid" if quiz["quiz_type"] == "free" else "free"
            with get_db() as conn:
                conn.execute("UPDATE quizzes SET quiz_type=? WHERE quiz_id=?", (new_type, quiz_id))
                quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            _invalidate_quiz_cache(quiz_id)
            bot.answer_callback_query(call.id, f"✅ Type: {new_type.upper()}")
            send_edit_panel(cid, quiz, qc, mid)

        elif action == "timer":
            bot.answer_callback_query(call.id)
            _wizard[uid] = {"quiz_id": quiz_id, "edit_panel_mid": mid, "edit_panel_cid": cid}
            set_state(uid, "awaiting_edit_timer")
            try: bot.edit_message_text(
                f"⏱ <b>Timer Edit</b>\n\nCurrent: <b>{quiz['timer_seconds']}s</b>\n\nEnter new timer (seconds, minimum 10):",
                cid, mid, parse_mode="HTML")
            except Exception: pass
            bot.send_message(cid, "👇 Send new timer value (e.g. <code>20</code>):", parse_mode="HTML")

        elif action == "neg":
            bot.answer_callback_query(call.id)
            _wizard[uid] = {"quiz_id": quiz_id, "edit_panel_mid": mid, "edit_panel_cid": cid}
            set_state(uid, "awaiting_edit_neg")
            neg_val = parse_neg_value(quiz["neg_marking"])
            cur_neg = f"{neg_val:.2f}".rstrip("0").rstrip(".") if neg_val else "None"
            try: bot.edit_message_text(
                f"➖ <b>Negative Marking Edit</b>\n\nCurrent: <b>{cur_neg}</b>\n\nEnter new value or <code>0</code> for none:",
                cid, mid, parse_mode="HTML")
            except Exception: pass
            bot.send_message(cid, "👇 Send neg mark value (e.g. <code>0.33</code> or <code>0</code>):", parse_mode="HTML")

        elif action == "shq":
            with get_db() as conn:
                conn.execute("UPDATE quizzes SET shuffle_q=? WHERE quiz_id=?", (1 - quiz["shuffle_q"], quiz_id))
                quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            _invalidate_quiz_cache(quiz_id)
            bot.answer_callback_query(call.id, f"🔀 Shuffle Qs: {'ON ✅' if quiz['shuffle_q'] else 'OFF ❌'}")
            send_edit_panel(cid, quiz, qc, mid)

        elif action == "sho":
            with get_db() as conn:
                conn.execute("UPDATE quizzes SET shuffle_o=? WHERE quiz_id=?", (1 - quiz["shuffle_o"], quiz_id))
                quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            _invalidate_quiz_cache(quiz_id)
            bot.answer_callback_query(call.id, f"🔀 Shuffle Opts: {'ON ✅' if quiz['shuffle_o'] else 'OFF ❌'}")
            send_edit_panel(cid, quiz, qc, mid)

        elif action == "delquiz":
            bot.answer_callback_query(call.id)
            kb_confirm = InlineKeyboardMarkup(row_width=2)
            kb_confirm.add(
                InlineKeyboardButton("✅ Yes, Delete", callback_data=f"ep_delquizconfirm_{quiz_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data=f"ep_back_{quiz_id}"),
            )
            txt = (f"⚠️ <b>Quiz Delete Confirm</b>\n\n"
                   f"All {qc} questions in <b>{html_mod.escape(quiz['title'])}</b> will be permanently deleted!\n\nThis action cannot be undone!")
            try: bot.edit_message_text(txt, cid, mid, parse_mode="HTML", reply_markup=kb_confirm)
            except Exception: bot.send_message(cid, txt, parse_mode="HTML", reply_markup=kb_confirm)

        elif action == "delquizconfirm":
            bot.answer_callback_query(call.id, "🗑 Deleting...")
            with get_db() as conn:
                conn.execute("DELETE FROM questions WHERE quiz_id=?", (quiz_id,))
                conn.execute("DELETE FROM quizzes WHERE quiz_id=?", (quiz_id,))
            _invalidate_quiz_cache(quiz_id)
            try: bot.delete_message(cid, mid)
            except Exception: pass
            bot.send_message(cid, f"✅ Quiz <b>{html_mod.escape(quiz['title'])}</b> has been deleted!", parse_mode="HTML")

        elif action == "shuffle":
            bot.answer_callback_query(call.id)
            send_edit_panel(cid, quiz, qc, mid)

        elif action == "qlist":
            bot.answer_callback_query(call.id)
            with get_db() as conn:
                qs = conn.execute("SELECT position, q_text FROM questions WHERE quiz_id=? ORDER BY position, question_id", (quiz_id,)).fetchall()
            if not qs:
                return bot.answer_callback_query(call.id, "❌ No questions found.", show_alert=True)
            PER_PAGE = 10; total_pages = max(1, (len(qs) + PER_PAGE - 1) // PER_PAGE)
            page_qs  = qs[:PER_PAGE]
            lines    = [f"📋 *Questions — {quiz['title'][:25]}*\n_(Page 1/{total_pages})_\n"]
            for i, q in enumerate(page_qs, 1):
                lines.append(f"`{i}.` {q['q_text'][:80]}{'…' if len(q['q_text']) > 80 else ''}")
            txt = "\n".join(lines)
            kb  = qlist_page_kb(quiz_id, 0, total_pages)
            try: bot.edit_message_text(txt, cid, mid, parse_mode="Markdown", reply_markup=kb)
            except Exception: bot.send_message(cid, txt, parse_mode="Markdown", reply_markup=kb)

        elif action == "qmgmt":
            bot.answer_callback_query(call.id)
            kb_mgmt = InlineKeyboardMarkup(row_width=2)
            kb_mgmt.row(
                InlineKeyboardButton("👀 View/Edit", callback_data=f"eq_pg_{quiz_id}_0"),
                InlineKeyboardButton("➕ Add", callback_data=f"ep_qadd_{quiz_id}"),
            )
            kb_mgmt.add(InlineKeyboardButton("🗑 Delete Range", callback_data=f"ep_qdel_{quiz_id}"))
            kb_mgmt.add(InlineKeyboardButton("⬅️ Back", callback_data=f"ep_back_{quiz_id}"))
            txt = (f"📚 <b>Question Management</b>\n\n"
                   f"📌 <b>{html_mod.escape(quiz['title'][:35])}</b>\n"
                   f"🔢 Total: <b>{qc}</b> questions")
            try: bot.edit_message_text(txt, cid, mid, parse_mode="HTML", reply_markup=kb_mgmt)
            except Exception: bot.send_message(cid, txt, parse_mode="HTML", reply_markup=kb_mgmt)

        elif action == "qadd":
            bot.answer_callback_query(call.id)
            txt = f"➕ *Add Questions*\n\n📌 {html_mod.escape(quiz['title'][:30])}\n\nSend a file or paste questions manually:"
            try: bot.edit_message_text(txt, cid, mid, parse_mode="Markdown", reply_markup=qadd_panel_kb(quiz_id))
            except Exception: bot.send_message(cid, txt, parse_mode="Markdown", reply_markup=qadd_panel_kb(quiz_id))

        elif action == "qdel":
            bot.answer_callback_query(call.id)
            txt = f"🗑️ *Delete Questions*\n\n📌 {html_mod.escape(quiz['title'][:30])}\n🔢 Total: *{qc}* questions"
            try: bot.edit_message_text(txt, cid, mid, parse_mode="Markdown", reply_markup=qdel_panel_kb(quiz_id))
            except Exception: bot.send_message(cid, txt, parse_mode="Markdown", reply_markup=qdel_panel_kb(quiz_id))

        elif action == "name":
            bot.answer_callback_query(call.id)
            _wizard[uid] = {"quiz_id": quiz_id, "edit_panel_mid": mid, "edit_panel_cid": cid}
            set_state(uid, "awaiting_quiz_rename")
            txt = f"✏️ *Quiz Name Edit*\n\nCurrent: *{html_mod.escape(quiz['title'])}*\n\nType and send the new name:"
            try: bot.edit_message_text(txt, cid, mid, parse_mode="Markdown")
            except Exception: pass
            bot.send_message(cid, "👇 Send new name:", parse_mode="Markdown")
    elif data.startswith("sh_"):
        parts = data.split("_"); action, quiz_id = parts[1], int(parts[2])
        if action == "back":
            bot.answer_callback_query(call.id)
            with get_db() as conn:
                quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
                qc = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()[0]
            return send_edit_panel(cid, quiz, qc, mid)
        with get_db() as conn:
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            if not quiz: return bot.answer_callback_query(call.id, "Not found.")
            if action == "q": conn.execute("UPDATE quizzes SET shuffle_q=? WHERE quiz_id=?", (1-quiz["shuffle_q"], quiz_id))
            elif action == "o": conn.execute("UPDATE quizzes SET shuffle_o=? WHERE quiz_id=?", (1-quiz["shuffle_o"], quiz_id))
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
        _invalidate_quiz_cache(quiz_id); bot.answer_callback_query(call.id, "✅")
        send_edit_panel(cid, quiz, qc if "qc" in dir() else 0, mid)
    elif data.startswith("qadd_"):
        parts = data.split("_"); action = parts[1]; quiz_id = int(parts[2])
        with get_db() as conn:
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
        if not quiz or quiz["creator_id"] != uid:
            return bot.answer_callback_query(call.id, "🚫", show_alert=True)
        bot.answer_callback_query(call.id)
        _wizard[uid] = {"edit_mode": True, "quiz_id": quiz_id, "questions": [], "edit_panel_mid": mid, "edit_panel_cid": cid}
        set_state(uid, "editing_questions")
        if action == "file":
            bot.send_message(cid,
                f"📄 *Send a file* (TXT or JSON)\n\n"
                f"Quiz: *{html_mod.escape(quiz['title'])}*\n\n"
                f"/stopedit when done to save.",
                parse_mode="Markdown")
        elif action == "manual":
            bot.send_message(cid,
                f"✍️ *Paste questions*\n\n"
                f"Quiz: *{html_mod.escape(quiz['title'])}*\n\n"
                f"Format:\n`Q1. Question text\na) Option A ✅\nb) Option B\nc) Option C\nd) Option D`\n\n"
                f"/stopedit to save.",
                parse_mode="Markdown")
    elif data.startswith("qdel_"):
        parts = data.split("_"); action = parts[1]; quiz_id = int(parts[2])
        with get_db() as conn:
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            qc   = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()[0]
        if not quiz or quiz["creator_id"] != uid:
            return bot.answer_callback_query(call.id, "🚫", show_alert=True)
        if action == "num":
            bot.answer_callback_query(call.id)
            _wizard[uid] = {"quiz_id": quiz_id, "edit_panel_mid": mid, "edit_panel_cid": cid}
            set_state(uid, "awaiting_del_range")
            bot.send_message(cid,
                f"🔢 *Send question number or range*\n\n"
                f"Quiz: *{html_mod.escape(quiz['title'])}* ({qc} Qs)\n\n"
                f"Examples:\n"
                f"• `5` — only delete 5th question\n"
                f"• `3-7` — delete Q3 to Q7\n"
                f"• `1,4,9` — delete specific numbers",
                parse_mode="Markdown")
        elif action == "all":
            bot.answer_callback_query(call.id)
            txt = (f"☢️ *Are you sure?*\n\n"
                   f"All *{qc}* questions in *{html_mod.escape(quiz['title'])}* will be deleted!\n\n"
                   f"⚠️ This action cannot be undone!")
            try: bot.edit_message_text(txt, cid, mid, parse_mode="Markdown", reply_markup=qdel_confirm_kb(quiz_id))
            except Exception: bot.send_message(cid, txt, parse_mode="Markdown", reply_markup=qdel_confirm_kb(quiz_id))
        elif action == "confirm":
            bot.answer_callback_query(call.id, "🗑️ Deleting...")
            with get_db() as conn:
                conn.execute("DELETE FROM questions WHERE quiz_id=?", (quiz_id,))
                quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
                qc   = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()[0]
            _invalidate_quiz_cache(quiz_id)
            send_edit_panel(cid, quiz, qc, mid)
            bot.send_message(cid, "✅ All questions have been deleted!")
    elif data.startswith("eq_pg_"):
        # View/Edit: paginated Q buttons
        parts = data.split("_"); quiz_id = int(parts[2]); page = int(parts[3])
        with get_db() as conn:
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            qs   = conn.execute("SELECT question_id, q_text FROM questions WHERE quiz_id=? ORDER BY position, question_id", (quiz_id,)).fetchall()
        if not quiz or quiz["creator_id"] != uid:
            return bot.answer_callback_query(call.id, "🚫", show_alert=True)
        bot.answer_callback_query(call.id)
        PER_PAGE = 10; total_pages = max(1, (len(qs) + PER_PAGE - 1) // PER_PAGE)
        page = max(0, min(page, total_pages - 1))
        page_qs = qs[page * PER_PAGE:(page + 1) * PER_PAGE]
        txt = (f"📚 <b>View/Edit Questions</b>\n"
               f"📌 <b>{html_mod.escape(quiz['title'][:30])}</b>\n"
               f"🔢 Total: <b>{len(qs)}</b> · Page <b>{page+1}/{total_pages}</b>\n\n"
               f"Select a question to edit:")
        kb = qview_buttons_kb(quiz_id, page_qs, page, total_pages)
        try: bot.edit_message_text(txt, cid, mid, parse_mode="HTML", reply_markup=kb)
        except Exception: bot.send_message(cid, txt, parse_mode="HTML", reply_markup=kb)

    elif data.startswith("eq_sel_"):
        # Show individual question with Replace/Delete
        parts = data.split("_"); quiz_id = int(parts[2]); g_idx = int(parts[3])
        with get_db() as conn:
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            qs   = conn.execute("SELECT * FROM questions WHERE quiz_id=? ORDER BY position, question_id", (quiz_id,)).fetchall()
        if not quiz or quiz["creator_id"] != uid:
            return bot.answer_callback_query(call.id, "🚫", show_alert=True)
        if g_idx >= len(qs):
            return bot.answer_callback_query(call.id, "❌ Question not found.", show_alert=True)
        bot.answer_callback_query(call.id)
        q = qs[g_idx]
        opts = json.loads(q["options"])
        correct = q["correct_idx"]
        opt_lines = ""
        for i, opt in enumerate(opts):
            icon = "✅" if i == correct else "❌"
            opt_lines += f"  {icon} {chr(97+i)}) {html_mod.escape(opt)}\n"
        exp = (q.get("explanation") or "").strip()
        exp_line = f"\n📖 <i>Exp: {html_mod.escape(exp[:150])}</i>" if exp else ""
        txt = (f"✏️ <b>Edit Q{g_idx+1}</b>\n\n"
               f"Q: {html_mod.escape(q['q_text'][:300])}\n\n"
               f"{opt_lines}{exp_line}")
        page = g_idx // 10
        kb = InlineKeyboardMarkup(row_width=2)
        kb.row(
            InlineKeyboardButton("🔄 Replace", callback_data=f"eq_rep_{quiz_id}_{g_idx}"),
            InlineKeyboardButton("🗑 Delete",  callback_data=f"eq_del_{quiz_id}_{g_idx}"),
        )
        kb.add(InlineKeyboardButton("⬅️ Back", callback_data=f"eq_pg_{quiz_id}_{page}"))
        has_img = (q.get("image_file_id") or "").strip()
        if has_img:
            try:
                bot.send_photo(cid, has_img, caption=txt, parse_mode="HTML", reply_markup=kb)
                try: bot.delete_message(cid, mid)
                except Exception: pass
            except Exception:
                try: bot.edit_message_text(txt, cid, mid, parse_mode="HTML", reply_markup=kb)
                except Exception: bot.send_message(cid, txt, parse_mode="HTML", reply_markup=kb)
        else:
            try: bot.edit_message_text(txt, cid, mid, parse_mode="HTML", reply_markup=kb)
            except Exception: bot.send_message(cid, txt, parse_mode="HTML", reply_markup=kb)

    elif data.startswith("eq_rep_"):
        # Replace question - set state
        parts = data.split("_"); quiz_id = int(parts[2]); g_idx = int(parts[3])
        with get_db() as conn:
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
        if not quiz or quiz["creator_id"] != uid:
            return bot.answer_callback_query(call.id, "🚫", show_alert=True)
        bot.answer_callback_query(call.id)
        _wizard[uid] = {"quiz_id": quiz_id, "q_idx": g_idx, "edit_panel_mid": mid, "edit_panel_cid": cid}
        set_state(uid, "awaiting_q_replace")
        bot.send_message(cid,
            f"🔄 <b>Replace Q{g_idx+1}</b>\n\n"
            f"Send the new question in this format:\n\n"
            f"<code>Question text\na) Option A\nb) Option B ✅\nc) Option C\nd) Option D\nEx: Explanation (optional)</code>\n\n"
            f"Or send an image first, then reply to it with the options.",
            parse_mode="HTML")

    elif data.startswith("eq_del_"):
        # Delete single question
        parts = data.split("_"); quiz_id = int(parts[2]); g_idx = int(parts[3])
        with get_db() as conn:
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            qs   = conn.execute("SELECT question_id FROM questions WHERE quiz_id=? ORDER BY position, question_id", (quiz_id,)).fetchall()
        if not quiz or quiz["creator_id"] != uid:
            return bot.answer_callback_query(call.id, "🚫", show_alert=True)
        if g_idx >= len(qs):
            return bot.answer_callback_query(call.id, "❌ Not found.", show_alert=True)
        q_id = qs[g_idx]["question_id"]
        with get_db() as conn:
            conn.execute("DELETE FROM questions WHERE question_id=?", (q_id,))
            remaining = conn.execute("SELECT question_id FROM questions WHERE quiz_id=? ORDER BY position, question_id", (quiz_id,)).fetchall()
            for i, r in enumerate(remaining):
                conn.execute("UPDATE questions SET position=? WHERE question_id=?", (i, r["question_id"]))
            qc = len(remaining)
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
        _invalidate_quiz_cache(quiz_id)
        bot.answer_callback_query(call.id, f"✅ Q{g_idx+1} deleted!")
        page = max(0, (g_idx - 1 if g_idx > 0 else 0) // 10)
        with get_db() as conn:
            qs2 = conn.execute("SELECT question_id, q_text FROM questions WHERE quiz_id=? ORDER BY position, question_id", (quiz_id,)).fetchall()
        total_pages = max(1, (len(qs2) + 9) // 10)
        page = min(page, total_pages - 1)
        page_qs = qs2[page * 10:(page + 1) * 10]
        txt = (f"📚 <b>View/Edit Questions</b>\n"
               f"📌 <b>{html_mod.escape(quiz['title'][:30])}</b>\n"
               f"🔢 Total: <b>{len(qs2)}</b> · Page <b>{page+1}/{total_pages}</b>\n\n"
               f"Select a question to edit:")
        kb = qview_buttons_kb(quiz_id, page_qs, page, total_pages)
        try: bot.edit_message_text(txt, cid, mid, parse_mode="HTML", reply_markup=kb)
        except Exception: bot.send_message(cid, txt, parse_mode="HTML", reply_markup=kb)

    elif data.startswith("qlist_pg_"):
        _, _, quiz_id_s, page_s = data.split("_", 3)
        quiz_id = int(quiz_id_s); page = int(page_s)
        with get_db() as conn:
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            qs   = conn.execute("SELECT position, q_text FROM questions WHERE quiz_id=? ORDER BY position, question_id", (quiz_id,)).fetchall()
        if not quiz or quiz["creator_id"] != uid:
            return bot.answer_callback_query(call.id, "🚫", show_alert=True)
        bot.answer_callback_query(call.id)
        PER_PAGE = 10; total_pages = max(1, (len(qs) + PER_PAGE - 1) // PER_PAGE)
        page    = max(0, min(page, total_pages - 1))
        page_qs = qs[page * PER_PAGE:(page + 1) * PER_PAGE]
        offset  = page * PER_PAGE
        lines   = [f"📋 *Questions — {quiz['title'][:25]}*\n_(Page {page+1}/{total_pages})_\n"]
        for i, q in enumerate(page_qs, offset + 1):
            lines.append(f"`{i}.` {q['q_text'][:80]}{'…' if len(q['q_text']) > 80 else ''}")
        txt = "\n".join(lines)
        kb  = qlist_page_kb(quiz_id, page, total_pages)
        try: bot.edit_message_text(txt, cid, mid, parse_mode="Markdown", reply_markup=kb)
        except Exception: bot.send_message(cid, txt, parse_mode="Markdown", reply_markup=kb)
    elif data == "noop":
        bot.answer_callback_query(call.id)
    elif data.startswith("gctrl_"):
        parts = data.split("_"); action = parts[1]; session_id = int(parts[2])
        with get_db() as conn:
            sess = conn.execute("SELECT * FROM active_sessions WHERE session_id=?", (session_id,)).fetchone()
        if not sess:
            return bot.answer_callback_query(call.id, "Session not found!", show_alert=True)
        if uid != sess["user_id"] and not is_group_admin(cid, uid):
            return bot.answer_callback_query(call.id, "🚫 Only admin or quiz creator!", show_alert=True)
        if action == "stop":
            bot.answer_callback_query(call.id, "🛑 Stopping...")
            with get_db() as conn:
                quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (sess["quiz_id"],)).fetchone()
                conn.execute("UPDATE active_sessions SET is_completed=1,end_time=(CAST(EXTRACT(EPOCH FROM NOW()) AS INTEGER)) WHERE session_id=?", (session_id,))
            _session_cache.pop(session_id, None); _cancel_auto_timer(session_id)
            try: bot.edit_message_text("🛑 <b>Quiz Stopped by Admin</b>", cid, mid, parse_mode="HTML")
            except Exception: pass
            nv = parse_neg_value(quiz["neg_marking"]) if quiz else 0.0
            gc_name = ""
            try:
                with get_db() as conn:
                    cr = conn.execute("SELECT first_name FROM users WHERE user_id=?", (sess["user_id"],)).fetchone()
                    if cr and cr["first_name"]: gc_name = cr["first_name"]
            except Exception: pass
            _send_leaderboard(session_id, cid, quiz["title"] if quiz else "Quiz", nv, sess["total_q"], sess["start_time"], gc_name)
        elif action == "pause":
            with get_db() as conn:
                conn.execute("UPDATE active_sessions SET is_paused=1 WHERE session_id=?", (session_id,))
            if session_id in _session_cache: _session_cache[session_id]["is_paused"] = 1
            _cancel_auto_timer(session_id)
            bot.answer_callback_query(call.id, "⏸ Paused!")
            edit_ctrl_panel(cid, mid, session_id, "⏸ <b>Quiz Paused</b>\nPaused by admin.", is_paused=True)
        elif action == "resume":
            with get_db() as conn:
                conn.execute("UPDATE active_sessions SET is_paused=0 WHERE session_id=?", (session_id,))
            if session_id in _session_cache: _session_cache[session_id]["is_paused"] = 0
            bot.answer_callback_query(call.id, "▶️ Resumed!")
            with get_db() as conn:
                quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (sess["quiz_id"],)).fetchone()
            ctrl_text = (f"🎮 <b>Admin Controls</b> — ▶️ Resumed\n"
                         f"⏱ {quiz['timer_seconds']}s per Q\n"
                         f"<i>Only quiz creator &amp; admins can use these buttons.</i>")
            edit_ctrl_panel(cid, mid, session_id, ctrl_text, is_paused=False)
            send_next_poll(session_id)
        elif action == "fast":
            with get_db() as conn:
                quiz = conn.execute("SELECT timer_seconds FROM quizzes WHERE quiz_id=?", (sess["quiz_id"],)).fetchone()
                nt = max(10, int(quiz["timer_seconds"]) - 5)
                conn.execute("UPDATE quizzes SET timer_seconds=? WHERE quiz_id=?", (nt, sess["quiz_id"]))
            _invalidate_quiz_cache(sess["quiz_id"])
            bot.answer_callback_query(call.id, f"⚡ Timer: {nt}s")
            edit_ctrl_panel(cid, mid, session_id,
                f"🎮 <b>Admin Controls</b>\n⚡ Timer set to <b>{nt}s</b>\n<i>Only quiz creator &amp; admins can use these buttons.</i>")
        elif action == "slow":
            with get_db() as conn:
                quiz = conn.execute("SELECT timer_seconds FROM quizzes WHERE quiz_id=?", (sess["quiz_id"],)).fetchone()
                nt = min(300, int(quiz["timer_seconds"]) + 5)
                conn.execute("UPDATE quizzes SET timer_seconds=? WHERE quiz_id=?", (nt, sess["quiz_id"]))
            _invalidate_quiz_cache(sess["quiz_id"])
            bot.answer_callback_query(call.id, f"🐢 Timer: {nt}s")
            edit_ctrl_panel(cid, mid, session_id,
                f"🎮 <b>Admin Controls</b>\n🐢 Timer set to <b>{nt}s</b>\n<i>Only quiz creator &amp; admins can use these buttons.</i>")
    elif data.startswith("approve_"):
        if not is_owner(uid): return bot.answer_callback_query(call.id, "🚫")
        tid = int(data[8:])
        with get_db() as conn:
            conn.execute("UPDATE users SET is_approved=1 WHERE user_id=?", (tid,))
            user = conn.execute("SELECT first_name FROM users WHERE user_id=?", (tid,)).fetchone()
        _approved_cache.add(tid); _pending_cache.pop(tid, None)
        name = html_mod.escape((user["first_name"] or str(tid)) if user else str(tid))
        bot.answer_callback_query(call.id, f"✅ {name} approved!")
        try: bot.edit_message_reply_markup(cid, mid, reply_markup=None)
        except Exception: pass
        try: bot.send_message(tid, f"✅ <b>Access Granted!</b>\n\nApproved by {html_mod.escape(OWNER_NAME)}.\nSend /start to begin!", parse_mode="HTML")
        except Exception: pass
    elif data.startswith("deny_"):
        if not is_owner(uid): return bot.answer_callback_query(call.id, "🚫")
        tid = int(data[5:])
        _pending_cache.pop(tid, None); _approved_cache.discard(tid)
        with get_db() as conn:
            user = conn.execute("SELECT first_name FROM users WHERE user_id=?", (tid,)).fetchone()
        name = html_mod.escape((user["first_name"] or str(tid)) if user else str(tid))
        bot.answer_callback_query(call.id, f"❌ {name} denied.")
        try: bot.edit_message_reply_markup(cid, mid, reply_markup=None)
        except Exception: pass
        try: bot.send_message(tid, f"❌ Your access request was denied.\nContact {OWNER_USERNAME} for help.")
        except Exception: pass
    elif data.startswith("rm_"):
        parts_rm = data.split("_")
        session_id_rm = int(parts_rm[1])
        req_uid = uid
        rm_key = (session_id_rm, req_uid)
        if rm_key in _rm_sent:
            return bot.answer_callback_query(call.id, "✅ Already sent to your DM!", show_alert=True)
        _rm_sent.add(rm_key)
        bot.answer_callback_query(call.id, "📨 Sending your mistakes to DM...", show_alert=False)

        def _send_dm(sid=session_id_rm, ruid=req_uid, group_cid=cid):
            try:
                bot.send_message(ruid,
                    "📝 <b>Review Mistakes</b> loading...",
                    parse_mode="HTML")
                _send_review_mistakes(sid, ruid, ruid)
            except Exception as e:
                _rm_sent.discard((sid, ruid))
                logging.error(f"DM review mistakes failed for {ruid}: {e}")
                try:
                    uname = call.from_user.username
                    mention = f"@{uname}" if uname else f"User {ruid}"
                    bot.send_message(
                        group_cid,
                        f"⚠️ {mention}: Could not send DM.\n"
                        f"Please start the bot in private first 👉 @{BOT_USER}",
                        parse_mode=None
                    )
                except Exception:
                    pass
        _bg_run(_send_dm)
    elif data.startswith("copyid_"): bot.answer_callback_query(call.id, f"ID: {data[7:]}", show_alert=True)
    elif data.startswith("tj_"):
        t_id = int(data[3:])
        with get_db() as conn:
            t = conn.execute("SELECT * FROM tournaments WHERE tournament_id=?", (t_id,)).fetchone()
        if not t or t["status"] != "waiting":
            return bot.answer_callback_query(call.id, "❌ Tournament not available.", show_alert=True)
        players = json.loads(t["active_players"] or "[]")
        if uid in players:
            return bot.answer_callback_query(call.id, "✅ Already joined!", show_alert=True)
        players.append(uid)
        with get_db() as conn:
            conn.execute("UPDATE tournaments SET active_players=? WHERE tournament_id=?",
                (json.dumps(players), t_id))
        bot.answer_callback_query(call.id, f"✅ Joined! ({len(players)} players so far)", show_alert=True)
        try:
            u = call.from_user
            name = html_mod.escape((u.first_name or "") + (" " + u.last_name if u.last_name else "")).strip()
            bot.send_message(cid, f"⚔️ *{name}* joined the tournament! ({len(players)} players)",
                parse_mode="Markdown")
        except Exception: pass
    elif data.startswith("tnext_"):
        t_id = int(data[6:])
        with get_db() as conn:
            t = conn.execute("SELECT * FROM tournaments WHERE tournament_id=?", (t_id,)).fetchone()
        if not t: return bot.answer_callback_query(call.id, "❌ Tournament not found.", show_alert=True)
        if t["creator_id"] != uid and not is_owner(uid) and not is_group_admin(cid, uid):
            return bot.answer_callback_query(call.id, "⚠️ Only the tournament creator or group admin can start the next round.", show_alert=True)
        if t["status"] != "waiting":
            return bot.answer_callback_query(call.id, "⚠️ Round already in progress.", show_alert=True)
        bot.answer_callback_query(call.id, "▶️ Starting next round...")
        _bg_run(lambda: _run_tournament_round(t_id, cid))
    else: bot.answer_callback_query(call.id)

@bot.message_handler(commands=["allow"])
def cmd_allow(msg):
    if not is_owner(msg.from_user.id): return bot.send_message(msg.chat.id, "🚫")
    parts = msg.text.split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        return bot.send_message(msg.chat.id, "<code>/allow USER_ID</code>", parse_mode="HTML")
    tid = int(parts[1])
    with get_db() as conn:
        conn.execute("UPDATE users SET is_approved=1 WHERE user_id=?", (tid,))
        user = conn.execute("SELECT first_name FROM users WHERE user_id=?", (tid,)).fetchone()
    _approved_cache.add(tid); _pending_cache.pop(tid, None)
    name = html_mod.escape((user["first_name"] or str(tid)) if user else str(tid))
    bot.send_message(msg.chat.id, f"✅ <b>{name}</b> (<code>{tid}</code>) approved.", parse_mode="HTML")
    try: bot.send_message(tid, f"✅ <b>Access Granted!</b>\n\nYou have been approved by {html_mod.escape(OWNER_NAME)}.\nSend /start to begin!", parse_mode="HTML")
    except Exception: pass

@bot.message_handler(commands=["deny"])
def cmd_deny(msg):
    if not is_owner(msg.from_user.id): return bot.send_message(msg.chat.id, "🚫")
    parts = msg.text.split()
    if len(parts) < 2 or not parts[1].lstrip("-").isdigit():
        return bot.send_message(msg.chat.id, "<code>/deny USER_ID</code>", parse_mode="HTML")
    tid = int(parts[1])
    _pending_cache.pop(tid, None)
    with get_db() as conn:
        conn.execute("UPDATE users SET is_approved=0 WHERE user_id=?", (tid,))
        user = conn.execute("SELECT first_name FROM users WHERE user_id=?", (tid,)).fetchone()
    _approved_cache.discard(tid)
    name = html_mod.escape((user["first_name"] or str(tid)) if user else str(tid))
    bot.send_message(msg.chat.id, f"❌ <b>{name}</b> (<code>{tid}</code>) denied.", parse_mode="HTML")
    try: bot.send_message(tid, f"❌ Your access request was denied. Contact {OWNER_USERNAME} for help.", parse_mode="HTML")
    except Exception: pass

@bot.message_handler(commands=["pending"])
def cmd_pending(msg):
    if not is_owner(msg.from_user.id): return bot.send_message(msg.chat.id, "🚫")
    if not _pending_cache: return bot.send_message(msg.chat.id, "✅ No pending requests.")
    with get_db() as conn:
        lines = [f"⏳ <b>Pending ({len(_pending_cache)}):</b>\n"]
        for uid in list(_pending_cache.keys()):
            u = conn.execute("SELECT first_name, username FROM users WHERE user_id=?", (uid,)).fetchone()
            uname = f"@{u['username']}" if u and u['username'] else "—"
            fname = html_mod.escape(u['first_name'] or '?') if u else "?"
            kb = InlineKeyboardMarkup(row_width=2)
            kb.add(InlineKeyboardButton("✅ Allow", callback_data=f"approve_{uid}"),
                   InlineKeyboardButton("❌ Deny", callback_data=f"deny_{uid}"))
            bot.send_message(msg.chat.id, f"👤 <b>{fname}</b> {uname}\n🆔 <code>{uid}</code>", parse_mode="HTML", reply_markup=kb)

@bot.message_handler(commands=["ban"])
def cmd_ban(msg):
    if not is_owner(msg.from_user.id): return bot.send_message(msg.chat.id, "🚫")
    parts = msg.text.split(maxsplit=2)
    if len(parts)<2 or not parts[1].lstrip("-").isdigit(): return bot.send_message(msg.chat.id, "<code>/ban ID reason</code>", parse_mode="HTML")
    tid = int(parts[1]); reason = parts[2] if len(parts)>2 else "No reason"
    with get_db() as conn:
        conn.execute("INSERT INTO banned_users(user_id,banned_by,reason) VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET reason=EXCLUDED.reason", (tid, msg.from_user.id, reason))
        user = conn.execute("SELECT first_name FROM users WHERE user_id=?", (tid,)).fetchone()
    _ban_cache.add(tid)
    try: bot.send_message(tid, f"🚫 Banned: {html_mod.escape(reason)}", parse_mode="HTML")
    except Exception: pass
    name = html_mod.escape((user["first_name"] or str(tid)) if user else str(tid))
    bot.send_message(msg.chat.id, f"✅ <b>{name}</b> (<code>{tid}</code>) banned.", parse_mode="HTML")

@bot.message_handler(commands=["unban"])
def cmd_unban(msg):
    if not is_owner(msg.from_user.id): return bot.send_message(msg.chat.id, "🚫")
    parts = msg.text.split()
    if len(parts)<2 or not parts[1].lstrip("-").isdigit(): return bot.send_message(msg.chat.id, "<code>/unban ID</code>", parse_mode="HTML")
    tid = int(parts[1])
    with get_db() as conn: d = conn.execute("DELETE FROM banned_users WHERE user_id=?", (tid,)).rowcount
    _ban_cache.discard(tid)
    if d:
        try: bot.send_message(tid, "✅ Unbanned.")
        except Exception: pass
        bot.send_message(msg.chat.id, f"✅ <code>{tid}</code> unbanned.", parse_mode="HTML")
    else: bot.send_message(msg.chat.id, "Not banned.")

@bot.message_handler(commands=["users"])
def cmd_users(msg):
    if not is_owner(msg.from_user.id): return bot.send_message(msg.chat.id, "🚫")
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        banned = conn.execute("SELECT COUNT(*) FROM banned_users").fetchone()[0]
        recent = conn.execute("SELECT user_id,first_name,username,created_at FROM users ORDER BY created_at DESC LIMIT 10").fetchall()
    lines = [f"👥 <b>{total}</b> | 🚫 {banned}\n"]
    for u in recent:
        un = f"@{u['username']}" if u["username"] else "—"
        dt = datetime.fromtimestamp(u["created_at"]).strftime("%d %b %I:%M %p")
        lines.append(f"• <b>{html_mod.escape(u['first_name'] or 'User')}</b> {un} | <code>{u['user_id']}</code> | {dt}")
    bot.send_message(msg.chat.id, "\n".join(lines), parse_mode="HTML")

@bot.message_handler(commands=["banlist"])
def cmd_banlist(msg):
    if not is_owner(msg.from_user.id): return bot.send_message(msg.chat.id, "🚫")
    with get_db() as conn:
        rows = conn.execute("SELECT b.user_id,b.reason,u.first_name FROM banned_users b LEFT JOIN users u ON b.user_id=u.user_id ORDER BY b.banned_at DESC").fetchall()
    if not rows: return bot.send_message(msg.chat.id, "✅ None banned.")
    lines = [f"🚫 <b>Banned ({len(rows)}):</b>\n"]
    for r in rows: lines.append(f"• <b>{html_mod.escape(r['first_name'] or '?')}</b> <code>{r['user_id']}</code> — {html_mod.escape(r['reason'])}")
    bot.send_message(msg.chat.id, "\n".join(lines), parse_mode="HTML")

@bot.poll_answer_handler()
def handle_poll_answer(poll_answer):
    uid = poll_answer.user.id
    name = ((poll_answer.user.first_name or "") + " " + (poll_answer.user.last_name or "")).strip() or f"User{uid}"
    selected = poll_answer.option_ids[0] if poll_answer.option_ids else None
    poll_id = poll_answer.poll_id
    def _bg():
        try:
            with get_db() as conn:
                pm = conn.execute("SELECT * FROM poll_map WHERE poll_id=?", (poll_id,)).fetchone()
                if not pm: return
                ic = int(selected is not None and selected == pm["correct_idx"])
                if not conn.execute("SELECT result_id FROM session_results WHERE session_id=? AND user_id=? AND question_id=?",
                    (pm["session_id"], uid, pm["question_id"])).fetchone():
                    conn.execute("INSERT INTO session_results(session_id,user_id,participant_name,question_id,selected_idx,is_correct) VALUES(?,?,?,?,?,?)",
                        (pm["session_id"], uid, name, pm["question_id"], selected, ic))
        except Exception as e: logging.error(f"Poll ans: {e}")
    _bg_run(_bg)

@bot.inline_handler(func=lambda q: True)
def handle_inline(iq):
    uid, qt = iq.from_user.id, iq.query.strip().lower()
    with get_db() as conn:
        quizzes = conn.execute("SELECT z.*,COUNT(q.question_id) AS q_count FROM quizzes z LEFT JOIN questions q ON z.quiz_id=q.quiz_id WHERE z.creator_id=? GROUP BY z.quiz_id ORDER BY z.created_at DESC LIMIT 50", (uid,)).fetchall()
    results = []
    for quiz in quizzes:
        sid = str(quiz["short_id"]).lower(); title = str(quiz["title"]).lower()
        if qt and qt not in title and qt not in sid: continue
        neg_raw = quiz["neg_marking"] or "0"
        neg_display = neg_raw if neg_raw != "0" else "None"
        st = html_mod.escape(quiz['title'])
        u = get_user(uid)
        creator = html_mod.escape((u["first_name"] or "User") if u else "User")
        card = (
            f"🏆 <b><u>Quiz Shared!</u></b>\n"
            f"<blockquote>📖 {st}</blockquote>\n"
            f"┌ 🔢 Questions → <b>{quiz['q_count']}</b>\n"
            f"├ ⏱ Timer → <b>{quiz['timer_seconds']}s</b>\n"
            f"├ 🆔 Quiz ID → <code>{quiz['short_id']}</code>\n"
            f"├ 📉 Neg → <b>{neg_display}</b>\n"
            f"└ 👤 Creator → <b>{creator}</b>"
        )
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("🎯 Start", url=f"https://t.me/{BOT_USER}?start=quiz_{quiz['quiz_id']}"))
        kb.add(InlineKeyboardButton("🚀 Group", url=f"https://t.me/{BOT_USER}?startgroup=quiz_{quiz['quiz_id']}"))
        kb.add(InlineKeyboardButton("🔗 Share", switch_inline_query=quiz["short_id"]))
        results.append(InlineQueryResultArticle(id=str(quiz["quiz_id"]), title=quiz["title"],
            description=f"{quiz['q_count']} Qs | {quiz['short_id']}",
            input_message_content=InputTextMessageContent(card, parse_mode="HTML"), reply_markup=kb))
    bot.answer_inline_query(iq.id, results, cache_time=1, is_personal=True)

# ==============================================================================
# FEATURE 4C: WEEKLY SUNDAY PROGRESS SUMMARY
# ==============================================================================
def _send_user_weekly_summary(uid):
    try:
        week_ago = int(time.time()) - 7 * 24 * 3600
        with get_db() as conn:
            sessions = conn.execute("""
                SELECT s.session_id, s.quiz_id, s.total_q,
                    COUNT(sr.result_id) AS answered,
                    COALESCE(SUM(sr.is_correct), 0) AS correct
                FROM active_sessions s
                LEFT JOIN session_results sr ON s.session_id=sr.session_id AND sr.user_id=?
                WHERE s.user_id=? AND s.start_time>=? AND s.is_completed=1
                GROUP BY s.session_id, s.quiz_id, s.total_q
                ORDER BY s.session_id DESC LIMIT 10
            """, (uid, uid, week_ago)).fetchall()
            quiz_names = {}
            for s in sessions:
                q = conn.execute("SELECT title FROM quizzes WHERE quiz_id=?", (s["quiz_id"],)).fetchone()
                if q: quiz_names[s["session_id"]] = q["title"]
        if not sessions: return
        scores, lines = [], ["📅 *Weekly Progress Summary*\n"]
        for s in sessions:
            total   = s["total_q"] or s["answered"] or 1
            correct = int(s["correct"] or 0)
            pct     = round(correct / total * 100) if total else 0
            scores.append(pct)
            title    = quiz_names.get(s["session_id"], "Quiz")[:15]
            bar_fill = int(pct / 10)
            bar      = "█" * bar_fill + "░" * (10 - bar_fill)
            lines.append(f"`{title:<15}` {bar} {pct}%")
        avg   = round(sum(scores) / len(scores)) if scores else 0
        best  = max(scores) if scores else 0
        worst = min(scores) if scores else 0
        trend = ("↗️ Improving" if len(scores) > 1 and scores[0] > scores[-1]
                 else "↘️ Declining" if len(scores) > 1 and scores[0] < scores[-1]
                 else "➡️ Steady")
        lines += [f"\n━━━━━━━━━━━━━━━━━━",
                  f"📝 Quizzes this week: *{len(sessions)}*",
                  f"📊 Avg: *{avg}%* |  Best: *{best}%* |  Worst: *{worst}%*",
                  f"📈 Trend: {trend}",
                  f"\nKeep it up! 💪"]
        safe_send(uid, "\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        logging.error(f"User weekly summary error {uid}: {e}")

def _weekly_summary_job():
    """Runs daily; on Sunday morning sends weekly progress to all active users."""
    while True:
        try:
            now = datetime.now()
            if now.weekday() == 6 and now.hour == 9 and now.minute < 5:
                week_ago = int(time.time()) - 7 * 24 * 3600
                with get_db() as conn:
                    users = conn.execute("""
                        SELECT DISTINCT user_id FROM active_sessions
                        WHERE start_time>=? AND is_completed=1
                    """, (week_ago,)).fetchall()
                for u in users:
                    uid = u["user_id"]
                    _bg_run(lambda uid=uid: _send_user_weekly_summary(uid))
                time.sleep(360)   
            else:
                time.sleep(60)
        except Exception as e:
            logging.error(f"Weekly summary job error: {e}")
            time.sleep(60)


# ==============================================================================
# FEATURE 9A: TOURNAMENT MODE — ELIMINATION STYLE
# ==============================================================================
@bot.message_handler(commands=["tournament"])
def cmd_tournament(msg):
    try:
        register_user(msg)
        uid   = msg.from_user.id
        parts = msg.text.split(maxsplit=1)
        if len(parts) < 2:
            return safe_send(msg.chat.id,
                "⚔️ *Tournament Usage:*\n`/tournament <quiz_id>`\n\n"
                "Start an elimination tournament in this group.\n"
                "Players join via button, then creator sends /tstart.",
                parse_mode="Markdown")
        if not is_group(msg):
            return safe_send(msg.chat.id, "⚔️ Tournaments can only be started in groups!")
        if not is_group_admin(msg.chat.id, uid):
            return safe_send(msg.chat.id, "🚫 Only group admins can create a tournament.")
        
        quiz = find_quiz(uid, parts[1].strip())
        if not quiz:
            return safe_send(msg.chat.id,
                f"❌ Quiz not found: <code>{html_mod.escape(parts[1].strip())}</code>\n"
                f"Make sure the Quiz ID is correct.", parse_mode="HTML")
        
        with get_db() as conn:
            qc = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz["quiz_id"],)).fetchone()[0]
            if qc < 2:
                return safe_send(msg.chat.id, "❌ Quiz needs at least 2 questions.")
            conn.execute("UPDATE tournaments SET status='finished' WHERE chat_id=? AND status IN ('waiting','round_active')", (msg.chat.id,))
            conn.execute("""INSERT INTO tournaments(quiz_id,chat_id,creator_id,status,current_round,active_players)
                VALUES(?,?,?,'waiting',1,'[]')""", (quiz["quiz_id"], msg.chat.id, uid))
            t_id = conn.execute("SELECT tournament_id FROM tournaments WHERE chat_id=? ORDER BY tournament_id DESC LIMIT 1",
                (msg.chat.id,)).fetchone()["tournament_id"]
        _tournament_cache[msg.chat.id] = t_id
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton("⚔️ Join Tournament", callback_data=f"tj_{t_id}"))
        safe_send(msg.chat.id,
            f"🏆 *Tournament Created!*\n\n"
            f"📝 Quiz: *{html_mod.escape(quiz['title'])}*\n"
            f"❓ Questions: *{qc}*\n\n"
            f"Tap ⚔️ Join below to enter.\n"
            f"Creator: use /tstart when ready!",
            parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        logging.error(f"cmd_tournament error: {e}", exc_info=True)
        safe_send(msg.chat.id, f"⚠️ Tournament error: {e}")

@bot.message_handler(commands=["tstart"])
def cmd_tstart(msg):
    if not is_group(msg): return safe_send(msg.chat.id, "Groups only.")
    uid  = msg.from_user.id
    t_id = _tournament_cache.get(msg.chat.id)
    
    if not t_id:
        try:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT tournament_id FROM tournaments WHERE chat_id=? AND status='waiting' ORDER BY tournament_id DESC LIMIT 1",
                    (msg.chat.id,)
                ).fetchone()
                if row:
                    t_id = row["tournament_id"]
                    _tournament_cache[msg.chat.id] = t_id
        except Exception as e:
            logging.error(f"tstart DB fallback error: {e}")
    
    if not t_id: return safe_send(msg.chat.id, "❌ No active tournament. Use /tournament <quiz_id> first.")
    with get_db() as conn:
        t = conn.execute("SELECT * FROM tournaments WHERE tournament_id=?", (t_id,)).fetchone()
    if not t: return safe_send(msg.chat.id, "❌ Tournament not found.")
    if t["creator_id"] != uid and not is_owner(uid):
        return safe_send(msg.chat.id, "⚠️ Only the tournament creator can start it.")
    if t["status"] not in ("waiting",):
        return safe_send(msg.chat.id, "⚠️ Tournament already running or finished.")
    players = json.loads(t["active_players"] or "[]")
    if len(players) < 2:
        return safe_send(msg.chat.id, "❌ Need at least 2 players. Ask others to join!")
    with get_db() as conn:
        total_q = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (t["quiz_id"],)).fetchone()[0]
    estimated_rounds = math.ceil(math.log2(max(2, len(players))))
    qs_per_round = max(5, total_q // max(1, estimated_rounds))
    with get_db() as conn:
        conn.execute("UPDATE tournaments SET qs_per_round=? WHERE tournament_id=?", (qs_per_round, t_id))
    safe_send(msg.chat.id,
        f"⚔️ Tournament starting!\n"
        f"👥 Players: *{len(players)}* | 🔢 Est. Rounds: *{estimated_rounds}* | ❓ Qs/Round: *{qs_per_round}*",
        parse_mode="Markdown")
    _bg_run(lambda: _run_tournament_round(t_id, msg.chat.id))

def _run_tournament_round(t_id, chat_id):
    try:
        with get_db() as conn:
            t = conn.execute("SELECT * FROM tournaments WHERE tournament_id=?", (t_id,)).fetchone()
        if not t: return
        players       = json.loads(t["active_players"] or "[]")
        current_round = t["current_round"]
        q_offset      = t["q_offset"] or 0
        qs_per_round  = t["qs_per_round"] or 10
        if len(players) < 2:
            _end_tournament(t_id, chat_id, players); return

        # Fetch question IDs for this round's slice
        with get_db() as conn:
            conn.execute("UPDATE tournaments SET status='round_active' WHERE tournament_id=?", (t_id,))
            all_qids = [r["question_id"] for r in conn.execute(
                "SELECT question_id FROM questions WHERE quiz_id=? ORDER BY position, question_id",
                (t["quiz_id"],)).fetchall()]
            pnames = []
            for p in players:
                u = conn.execute("SELECT first_name FROM users WHERE user_id=?", (p,)).fetchone()
                pnames.append(html_mod.escape((u["first_name"] if u else None) or f"User{p}"))

        round_qids = all_qids[q_offset: q_offset + qs_per_round]
        if not round_qids:
            # All questions exhausted — wrap around from beginning
            q_offset = 0
            round_qids = all_qids[:qs_per_round]
        else:
            # If remaining questions after this round are fewer than qs_per_round,
            # absorb them into the current round (Option A)
            leftover = all_qids[q_offset + qs_per_round:]
            if leftover and len(leftover) < qs_per_round:
                round_qids = all_qids[q_offset:]

        bot.send_message(chat_id,
            f"🏆 <b>Round {current_round} — BEGIN!</b>\n"
            f"⚔️ <b>{len(players)}</b> players: {', '.join(pnames)}\n"
            f"❓ Questions: <b>{len(round_qids)}</b> (Q{q_offset+1}–Q{q_offset+len(round_qids)})\n\n"
            f"Quiz starting in your DM now!\n"
            f"Bottom 50% eliminated ⬇️",
            parse_mode="HTML")
        time.sleep(3)

        round_sids = []
        failed = []
        for p in players:
            try:
                sid = _do_start_quiz(p, p, t["quiz_id"], question_ids=round_qids)
                if sid: round_sids.append(sid)
                else: failed.append(p)
            except Exception as e:
                logging.error(f"Tournament quiz start {p}: {e}"); failed.append(p)
            time.sleep(0.5)

        if failed:
            with get_db() as conn:
                fnames = []
                for p in failed:
                    u = conn.execute("SELECT first_name FROM users WHERE user_id=?", (p,)).fetchone()
                    fnames.append(html_mod.escape((u["first_name"] if u else None) or f"User{p}"))
            bot.send_message(chat_id,
                f"⚠️ Could not send quiz to: {', '.join(fnames)}\n"
                f"They need to send /start to the bot in DM first.",
                parse_mode="HTML")

        deadline = time.time() + 600
        if round_sids:
            while time.time() < deadline:
                time.sleep(15)
                with get_db() as conn:
                    placeholders = ",".join(["?"] * len(round_sids))
                    done = conn.execute(
                        f"SELECT COUNT(*) FROM active_sessions "
                        f"WHERE session_id IN ({placeholders}) AND is_completed=1",
                        tuple(round_sids)).fetchone()[0]
                if done >= len(round_sids): break

            if time.time() >= deadline:
                with get_db() as conn:
                    conn.execute(f"UPDATE active_sessions SET is_completed=1 WHERE session_id IN ({placeholders})", tuple(round_sids))

        with get_db() as conn:
            quiz = conn.execute("SELECT neg_marking FROM quizzes WHERE quiz_id=?", (t["quiz_id"],)).fetchone()
            nv   = parse_neg_value(quiz["neg_marking"]) if quiz else 0.0
            scores = []
            for p in players:
                sess = conn.execute(
                    "SELECT session_id FROM active_sessions "
                    "WHERE user_id=? AND quiz_id=? AND is_completed=1 "
                    "ORDER BY session_id DESC LIMIT 1",
                    (p, t["quiz_id"])).fetchone()

                if sess and (sess["session_id"] in round_sids):
                    r = conn.execute(
                        "SELECT COALESCE(SUM(is_correct),0) AS c, COUNT(*) AS a "
                        "FROM session_results WHERE session_id=? AND user_id=?",
                        (sess["session_id"], p)).fetchone()
                    correct  = int(r["c"] or 0)
                    answered = int(r["a"] or 0)
                    sc = round(correct - (answered - correct) * nv, 2)
                else:
                    sc = 0.0
                u = conn.execute("SELECT first_name FROM users WHERE user_id=?", (p,)).fetchone()
                name = (u["first_name"] if u else None) or f"User{p}"
                scores.append((p, name, sc))

        scores.sort(key=lambda x: x[2], reverse=True)
        result_lines = [f'\U0001f4ca <b>Round {current_round} Results:</b>\n']
        for i, (p, n, sc) in enumerate(scores):
            icon = '\u2705' if i < max(1, len(scores) // 2) else '\u274c'
            result_lines.append(f'{icon} {i+1}. {html_mod.escape(n)} \u2014 <b>{sc}</b> pts')
        bot.send_message(chat_id, '\n'.join(result_lines), parse_mode='HTML')

        keep      = max(1, len(scores) // 2)
        survivors = [p for p, _, _ in scores[:keep]]
        eliminated = [n for _, n, _ in scores[keep:]]
        if eliminated:
            bot.send_message(chat_id,
                f'\U0001f6ab <b>Eliminated:</b> {", ".join(html_mod.escape(n) for n in eliminated)}',
                parse_mode='HTML')

        if len(survivors) <= 1:
            _end_tournament(t_id, chat_id, survivors, scores); return

        with get_db() as conn:
            conn.execute('UPDATE tournaments SET active_players=?,current_round=?,status=\'waiting\',q_offset=? WHERE tournament_id=?',
                (json.dumps(survivors), current_round + 1, q_offset + len(round_qids), t_id))
        kb = InlineKeyboardMarkup(row_width=1)
        kb.add(InlineKeyboardButton('\u25b6\ufe0f Start Next Round', callback_data=f'tnext_{t_id}'))
        bot.send_message(chat_id,
            f'\u2705 <b>{len(survivors)} players advance to Round {current_round + 1}!</b>',
            parse_mode='HTML', reply_markup=kb)
    except Exception as e:
        logging.error(f'Tournament round error: {e}', exc_info=True)
        try: bot.send_message(chat_id, '\u26a0\ufe0f Tournament error. Try again.')
        except Exception: pass

def _end_tournament(t_id, chat_id, survivors, scores=None):
    try:
        with get_db() as conn:
            conn.execute("UPDATE tournaments SET status='finished' WHERE tournament_id=?", (t_id,))
        _tournament_cache.pop(chat_id, None)
        if survivors:
            with get_db() as conn:
                u = conn.execute("SELECT first_name FROM users WHERE user_id=?", (survivors[0],)).fetchone()
            winner_name = (u["first_name"] if u else None) or f"User{survivors[0]}"
            bot.send_message(chat_id,
                f"🏆 *Tournament Finished!*\n\n"
                f"👑 *Winner: {html_mod.escape(winner_name)}* 🎉\n\nCongratulations! 🥳",
                parse_mode="Markdown")
        else:
            bot.send_message(chat_id, "🏁 Tournament ended.")
    except Exception as e:
        logging.error(f"End tournament error: {e}")



@bot.message_handler(content_types=["text"])
def handle_text(msg):
    register_user(msg)
    if is_group(msg): return
    uid, text = msg.from_user.id, msg.text.strip()
    state = get_state(uid)
    if is_banned(uid): return bot.send_message(msg.chat.id, "🚫 Banned.")
    if not is_approved_user(uid): return _send_pending_msg(msg.chat.id, uid)

    if state == "awaiting_quiz_title":
        title = text[:100]; _wizard.setdefault(uid, {})["title"] = title; _wizard[uid].setdefault("questions", [])
        set_state(uid, "adding_questions")
        safe_send(msg.chat.id, "Send MCQs, and mark the correct one with✅, or .txt/.json(file) /cancel", parse_mode="Markdown")
    elif state == "adding_questions":
        store = _wizard.setdefault(uid, {"title":"Untitled","questions":[]})
        parsed, errors = bulk_parse_manual(text)
        # Pending image attach karo (photo handler se ya reply-to-photo se)
        pending_img = _wizard[uid].pop("pending_image_file_id", "")
        if not pending_img and msg.reply_to_message and msg.reply_to_message.photo:
            pending_img = msg.reply_to_message.photo[-1].file_id
        # Normalize to 6-tuple: (ref, q, opts, correct, explanation, image_file_id)
        normalized = []
        for i, row in enumerate(parsed):
            r, q, o, c, *rest = row
            exp = rest[0] if rest else ""
            img = pending_img if i == 0 else ""  # image sirf pehle question ko
            normalized.append((r, q, o, c, exp, img))
        pending_img = ""  # clear
        store.setdefault("questions", []).extend(normalized)
        reply = f"✅ *{len(normalized)}* added! Total: *{len(store['questions'])}*\n"
        if errors: reply += "Skipped:\n" + "\n".join(f"• {e}" for e in errors[:5]) + "\n"
        reply += "/done to finish."
        safe_send(msg.chat.id, reply, parse_mode="Markdown")
    elif state == "awaiting_timer":
        if not text.isdigit() or int(text) <= 9: return safe_send(msg.chat.id, "❌ Timer must be >9 seconds.")
        _wizard.setdefault(uid, {})["timer"] = int(text)
        set_state(uid,"awaiting_neg_marking")
        safe_send(msg.chat.id, "📝 *Negative Marking* (0 or 1/3):", parse_mode="Markdown")
    elif state == "awaiting_neg_marking":
        clean = text.strip().lower()
        if clean in ("0","none","n"): neg = "0"
        elif "/" in clean: neg = clean
        else:
            try: neg = str(float(clean))
            except ValueError: return safe_send(msg.chat.id, "Enter 0, 1/3, etc.")
        
        store = _wizard.get(uid, {}); qs = store.get("questions", [])
        title = store.get("title","Untitled"); timer = store.get("timer",45)
        
        if not qs: 
            set_state(uid,"adding_questions")
            return safe_send(msg.chat.id, "No questions found.")
            
        set_state(uid,"idle"); _wizard.pop(uid,None)
        
        _chat_id = msg.chat.id
        creator_name = html_mod.escape(msg.from_user.first_name or "User")

        short_id = make_short_id()
        q_count = len(qs)
        
        try:
            with get_db() as conn:
                cur = conn.execute("INSERT INTO quizzes(creator_id,title,short_id,neg_marking,quiz_type,timer_seconds) VALUES(?,?,?,?,?,?) RETURNING quiz_id",
                    (uid, title, short_id, neg, "free", timer))
                quiz_id = cur.fetchone()[0]

            safe_t = html_mod.escape(str(title))
            neg_display = neg if neg != "0" else "None"
            card = (f"🏆 <b><u>Quiz Created!</u></b>\n\n"
                    f"<blockquote>📖 {safe_t}</blockquote>\n"
                    f"➖➖➖➖➖➖➖➖➖➖\n"
                    f"┌ 🔢 Questions  →  <b>{q_count}</b>\n"
                    f"├ ⏱ Timer  →  <b>{timer} sec</b>\n"
                    f"├ 🆔 Quiz ID  →  <code>{short_id}</code>\n"
                    f"├ 📉 Neg. Mark  →  <b>{neg_display}</b>\n"
                    f"└ 👤 Creator  →  <b>{creator_name}</b>")
            
            bot.send_message(_chat_id, card, parse_mode="HTML", reply_markup=quiz_card_kb(quiz_id, short_id))

            def _bg_save_questions():
                try:
                    with get_db() as conn:
                        query = "INSERT INTO questions(quiz_id,ref_text,q_text,options,correct_idx,position,explanation,image_file_id) VALUES %s"
                        data = []
                        for i, row in enumerate(qs):
                            r, q, o, c, *rest = row
                            exp = rest[0] if rest else ""
                            img = rest[1] if len(rest) > 1 else ""
                            data.append((quiz_id, r, q, json.dumps(o, ensure_ascii=False), c, i, exp or "", img or ""))
                        execute_values(conn._conn.cursor(), query, data, page_size=500)
                except Exception as e:
                    logging.error(f"BG Question Save Error: {e}")

            _bg_run(_bg_save_questions)

        except Exception as e:
            logging.error(f"Quiz Create Error: {e}")
            safe_send(_chat_id, "❌ Save failed. Try again.")
            
    elif state == "awaiting_edit_quiz_id":
        quiz = find_quiz(uid, text.strip())
        if not quiz: return safe_send(msg.chat.id, "Not found.")
        with get_db() as conn: qc = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz["quiz_id"],)).fetchone()[0]
        _wizard[uid] = {"edit_mode":True,"quiz_id":quiz["quiz_id"],"questions":[]}
        set_state(uid,"editing_questions"); send_edit_panel(msg.chat.id, quiz, qc)
    elif state == "editing_questions":
        store = _wizard.setdefault(uid, {"questions":[]})
        parsed, errors = bulk_parse_manual(text)
        # Pending image attach karo
        pending_img = _wizard[uid].pop("pending_image_file_id", "")
        if not pending_img and msg.reply_to_message and msg.reply_to_message.photo:
            pending_img = msg.reply_to_message.photo[-1].file_id
        # Normalize to 6-tuple
        normalized = []
        for i, row in enumerate(parsed):
            r, q, o, c, *rest = row
            exp = rest[0] if rest else ""
            img = pending_img if i == 0 else ""
            normalized.append((r, q, o, c, exp, img))
        store.setdefault("questions", []).extend(normalized)
        reply = f"Queued *{len(normalized)}*. Total: *{len(store['questions'])}*.\n"
        if errors: reply += "\n".join(f"• {e}" for e in errors[:5]) + "\n"
        reply += "/stopedit to save."
        safe_send(msg.chat.id, reply, parse_mode="Markdown")
    elif state == "awaiting_quiz_rename":
        new_name = text.strip()
        if len(new_name) < 2:
            return safe_send(msg.chat.id, "❌ Name too short. Must be at least 2 characters.")
        if len(new_name) > 100:
            return safe_send(msg.chat.id, f"❌ Name too long. Max 100 chars. (Current: {len(new_name)})")
        store = _wizard.get(uid, {}); quiz_id = store.get("quiz_id")
        if not quiz_id:
            set_state(uid, "idle"); return safe_send(msg.chat.id, "❌ Session expired. Please try again.")
        with get_db() as conn:
            conn.execute("UPDATE quizzes SET title=? WHERE quiz_id=? AND creator_id=?", (new_name, quiz_id, uid))
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            qc   = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()[0]
        _invalidate_quiz_cache(quiz_id)
        set_state(uid, "idle"); _wizard.pop(uid, None)
        safe_send(msg.chat.id, f"✅ *Quiz name updated!*\n\n📌 New name: *{html_mod.escape(new_name)}*", parse_mode="Markdown")
        if quiz: send_edit_panel(msg.chat.id, quiz, qc)
    elif state == "awaiting_edit_timer":
        store = _wizard.get(uid, {}); quiz_id = store.get("quiz_id")
        if not quiz_id:
            set_state(uid, "idle"); return safe_send(msg.chat.id, "❌ Session expired. Please try again.")
        if not text.strip().isdigit() or int(text.strip()) < 10:
            return safe_send(msg.chat.id, "❌ Timer must be at least 10 seconds.")
        new_timer = int(text.strip())
        with get_db() as conn:
            conn.execute("UPDATE quizzes SET timer_seconds=? WHERE quiz_id=? AND creator_id=?", (new_timer, quiz_id, uid))
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            qc   = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()[0]
        _invalidate_quiz_cache(quiz_id)
        set_state(uid, "idle"); _wizard.pop(uid, None)
        safe_send(msg.chat.id, f"✅ Timer updated to <b>{new_timer}s</b>", parse_mode="HTML")
        if quiz:
            ep_mid = store.get("edit_panel_mid"); ep_cid = store.get("edit_panel_cid", msg.chat.id)
            send_edit_panel(ep_cid, quiz, qc, ep_mid)
    elif state == "awaiting_edit_neg":
        store = _wizard.get(uid, {}); quiz_id = store.get("quiz_id")
        if not quiz_id:
            set_state(uid, "idle"); return safe_send(msg.chat.id, "❌ Session expired. Please try again.")
        clean = text.strip().lower()
        if clean in ("0","none","n","no"): neg = "0"
        elif "/" in clean: neg = clean
        else:
            try: neg = str(float(clean))
            except ValueError: return safe_send(msg.chat.id, "❌ Invalid value. Use: 0, 0.33, 1/3, etc.")
        with get_db() as conn:
            conn.execute("UPDATE quizzes SET neg_marking=? WHERE quiz_id=? AND creator_id=?", (neg, quiz_id, uid))
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            qc   = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()[0]
        _invalidate_quiz_cache(quiz_id)
        set_state(uid, "idle"); _wizard.pop(uid, None)
        neg_display = neg if neg != "0" else "None"
        safe_send(msg.chat.id, f"✅ Negative marking updated to <b>{neg_display}</b>", parse_mode="HTML")
        if quiz:
            ep_mid = store.get("edit_panel_mid"); ep_cid = store.get("edit_panel_cid", msg.chat.id)
            send_edit_panel(ep_cid, quiz, qc, ep_mid)
    elif state == "awaiting_del_range":
        store = _wizard.get(uid, {}); quiz_id = store.get("quiz_id")
        if not quiz_id:
            set_state(uid, "idle"); return safe_send(msg.chat.id, "❌ Session expired. Please try again.")
        raw = text.strip()
        with get_db() as conn:
            qs = conn.execute("SELECT question_id, position FROM questions WHERE quiz_id=? ORDER BY position, question_id", (quiz_id,)).fetchall()
        total = len(qs)
        if total == 0:
            set_state(uid, "idle"); _wizard.pop(uid, None)
            return safe_send(msg.chat.id, "❌ This quiz has no questions.")
        to_del = set()
        try:
            if "," in raw:
                for part in raw.split(","):
                    n = int(part.strip())
                    if 1 <= n <= total: to_del.add(n - 1)
            elif "-" in raw:
                a, b = raw.split("-", 1)
                a, b = int(a.strip()), int(b.strip())
                if a > b: a, b = b, a
                for i in range(a - 1, min(b, total)): to_del.add(i)
            else:
                n = int(raw)
                if 1 <= n <= total: to_del.add(n - 1)
        except ValueError:
            return safe_send(msg.chat.id, "❌ Invalid format.\nExample: `5` or `3-7` or `1,4,9`", parse_mode="Markdown")
        if not to_del:
            return safe_send(msg.chat.id, f"❌ Invalid range. This quiz has {total} questions.")
        del_ids = [qs[i]["question_id"] for i in sorted(to_del)]
        with get_db() as conn:
            conn.execute(f"DELETE FROM questions WHERE question_id IN ({','.join(['?']*len(del_ids))})", del_ids)
            remaining = conn.execute("SELECT question_id FROM questions WHERE quiz_id=? ORDER BY position, question_id", (quiz_id,)).fetchall()
            for i, r in enumerate(remaining):
                conn.execute("UPDATE questions SET position=? WHERE question_id=?", (i, r["question_id"]))
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            qc   = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()[0]
        _invalidate_quiz_cache(quiz_id)
        set_state(uid, "idle"); _wizard.pop(uid, None)
        safe_send(msg.chat.id, f"✅ *{len(del_ids)} question(s) deleted!*\n🔢 Remaining: *{qc}* questions", parse_mode="Markdown")
        if quiz: send_edit_panel(msg.chat.id, quiz, qc)
    elif state == "awaiting_html_id":
        if not text.isdigit(): return safe_send(msg.chat.id, "Numeric ID.")
        set_state(uid,"idle"); _export_html(msg.chat.id, int(text))
    elif state == "awaiting_txt_id":
        sid = text.strip()
        if sid.isdigit(): return safe_send(msg.chat.id, "❌ Please use Quiz ID (e.g. ZGPZIQKF), not numeric ID.")
        with get_db() as conn:
            quiz = conn.execute("SELECT * FROM quizzes WHERE short_id=? AND creator_id=?", (sid.upper(), uid)).fetchone()
        if not quiz: return safe_send(msg.chat.id, "❌ Quiz not found.")
        set_state(uid,"idle"); _bg_run(lambda: _export_pdf_quizpdf(msg.chat.id, quiz["quiz_id"]))
    elif state == "awaiting_q_replace":
        store = _wizard.get(uid, {})
        quiz_id = store.get("quiz_id"); g_idx = store.get("q_idx")
        if not quiz_id:
            set_state(uid, "idle"); return safe_send(msg.chat.id, "❌ Session expired.")
        # Check if this is a reply to a photo (image question)
        replied_photo = None
        if msg.reply_to_message and msg.reply_to_message.photo:
            replied_photo = msg.reply_to_message.photo[-1].file_id
        with get_db() as conn:
            qs = conn.execute("SELECT question_id FROM questions WHERE quiz_id=? ORDER BY position, question_id", (quiz_id,)).fetchall()
        if g_idx >= len(qs):
            set_state(uid, "idle"); return safe_send(msg.chat.id, "❌ Question not found.")
        q_id = qs[g_idx]["question_id"]
        parsed, errors = bulk_parse_manual(text)
        if not parsed:
            return safe_send(msg.chat.id, f"❌ Invalid format. Please try again:\n" + (errors[0] if errors else ""), parse_mode="Markdown")
        r, q, opts, correct_idx, *rest = parsed[0]
        exp = rest[0] if rest else ""
        img = replied_photo or store.get("pending_image_file_id", "")
        with get_db() as conn:
            conn.execute("UPDATE questions SET ref_text=?, q_text=?, options=?, correct_idx=?, explanation=?, image_file_id=? WHERE question_id=?",
                (r, q, json.dumps(opts, ensure_ascii=False), correct_idx, exp, img, q_id))
            quiz = conn.execute("SELECT * FROM quizzes WHERE quiz_id=?", (quiz_id,)).fetchone()
            qc   = conn.execute("SELECT COUNT(*) FROM questions WHERE quiz_id=?", (quiz_id,)).fetchone()[0]
        _invalidate_quiz_cache(quiz_id)
        set_state(uid, "idle"); _wizard.pop(uid, None)
        safe_send(msg.chat.id, f"✅ <b>Q{g_idx+1} replaced successfully!</b>", parse_mode="HTML")
        ep_cid = store.get("edit_panel_cid", msg.chat.id)
        send_edit_panel(ep_cid, quiz, qc)
    else:
        safe_send(msg.chat.id, "/features", reply_markup=ReplyKeyboardRemove())

@bot.message_handler(content_types=["photo"])
def handle_photo(msg):
    if is_group(msg): return
    register_user(msg)
    uid = msg.from_user.id
    if is_banned(uid): return
    if not is_approved_user(uid): return _send_pending_msg(msg.chat.id, uid)
    state = get_state(uid)
    if state in ("adding_questions", "editing_questions"):
        file_id = msg.photo[-1].file_id
        _wizard.setdefault(uid, {})["pending_image_file_id"] = file_id
        safe_send(msg.chat.id,
            "📸 <b>Image received!</b>\n\n"
            "Now send the question and options for this image:\n\n"
            "<code>Question text here?\n"
            "a) Option A\n"
            "b) Option B ✅\n"
            "c) Option C\n"
            "d) Option D\n"
            "Exp: Explanation (optional)</code>\n\n"
            "💡 <i>Or reply to the image with the options</i>",
            parse_mode="HTML")
    else:
        safe_send(msg.chat.id,
            "📸 To add image questions, use /create or /edit first.",
            parse_mode="HTML")

# ==============================================================================
# MAIN BOT EXECUTION
# ==============================================================================
if __name__ == "__main__":
    print("=" * 60, flush=True)
    print("  QuizBot Pro v6.8 — ALWAYS-ON OPTIMIZED + FONT FIXED", flush=True)
    print(f"  @{BOT_USER} | Owner: {OWNER_NAME} {OWNER_USERNAME}", flush=True)
    print("=" * 60, flush=True)
    
    threading.Thread(target=_weekly_summary_job, daemon=True).start()
    logging.info("Background jobs started: weekly summary.")
    
    def start_bot():
        try:
            bot.remove_webhook()
            print("Webhooks disabled. Polling mode active.", flush=True)
        except Exception:
            pass

        while True:
            try:
                logging.info("Bot polling loop (re)started.")
                print("🚀 Bot is Polling smoothly... Send a message on Telegram now!", flush=True)

                bot.infinity_polling(
                    timeout=60,
                    long_polling_timeout=20,
                    skip_pending=False, 
                    allowed_updates=["message", "poll_answer", "callback_query", "inline_query"],
                    logger_level=logging.INFO,
                )

            except KeyboardInterrupt:
                print("\nStopped by user.", flush=True)
                break

            except (RequestsSSLError, StdSSLError, RequestsReadTimeout) as e:
                logging.warning(f"[PollingLoop] SSL/ReadTimeout drop: {e} — reconnecting in 5s")
                print(f"🔄 Network timeout. Reconnecting in 5s...", flush=True)
                time.sleep(5)

            except telebot.apihelper.ApiTelegramException as e:
                logging.warning(f"[PollingLoop] Telegram API error: {e} — retrying in 10s")
                print(f"⚠️ Telegram error: {e}. Retrying in 10s...", flush=True)
                time.sleep(10)

            except Exception as e:
                logging.error(f"[PollingLoop] Unexpected crash: {e}", exc_info=True)
                print(f"⚠️ Error: {e}. Retrying in 5s...", flush=True)
                time.sleep(5)
                
    start_bot()