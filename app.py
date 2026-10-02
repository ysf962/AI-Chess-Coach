"""
The Chess Coach (v2)

Run:      streamlit run app.py
Needs:    streamlit>=1.50, python-chess, pandas, requests
Optional: Stockfish (apt: `stockfish`, or set STOCKFISH_PATH) for a much stronger
          bot and far better move ratings. Without it the app uses a built-in
          engine. Optional LICHESS_TOKEN (env or st.secrets) for the opening explorer.

Rating, win/loss record and badges persist between sessions in a small JSON file
next to this script (chess_coach_profile.json), or wherever CHESS_COACH_PROFILE
points. Delete that file, or use "Reset rating" in the sidebar, to start over.
"""
import json
import math
import os
import random
import shutil
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import chess
import chess.engine
import chess.pgn
import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="The Chess Coach", layout="wide", page_icon="♟️")

# ==========================================
# 1. CONSTANTS & DATA TABLES
# ==========================================
MATE_CP = 10000
ANALYSIS_SECONDS = 0.15

PIECE_VALUES = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0,
}
STARTING_PIECES = {chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 2, chess.QUEEN: 1}

# Outline (white) / solid (black) symbols, used for captured-piece strips
PIECE_SYMBOLS = {
    (chess.PAWN, chess.WHITE): "♙", (chess.KNIGHT, chess.WHITE): "♘", (chess.BISHOP, chess.WHITE): "♗",
    (chess.ROOK, chess.WHITE): "♖", (chess.QUEEN, chess.WHITE): "♕", (chess.KING, chess.WHITE): "♔",
    (chess.PAWN, chess.BLACK): "♟", (chess.KNIGHT, chess.BLACK): "♞", (chess.BISHOP, chess.BLACK): "♝",
    (chess.ROOK, chess.BLACK): "♜", (chess.QUEEN, chess.BLACK): "♛", (chess.KING, chess.BLACK): "♚",
}
# Solid glyphs for the playable board (colored with CSS). \ufe0e forces text style on the pawn.
BOARD_GLYPH = {
    chess.PAWN: "♟\ufe0e", chess.KNIGHT: "♞", chess.BISHOP: "♝",
    chess.ROOK: "♜", chess.QUEEN: "♛", chess.KING: "♚",
}

# Piece-square tables are written the way you read a board (rank 8 first, from White's side),
# so White looks them up with square_mirror(sq) and Black with sq.
PAWN_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
    5, 5, 10, 25, 25, 10, 5, 5,
    0, 0, 0, 20, 20, 0, 0, 0,
    5, -5, -10, 0, 0, -10, -5, 5,
    5, 10, 10, -20, -20, 10, 10, 5,
    0, 0, 0, 0, 0, 0, 0, 0,
]
KNIGHT_TABLE = [
    -50, -40, -30, -30, -30, -30, -40, -50,
    -40, -20, 0, 0, 0, 0, -20, -40,
    -30, 0, 10, 15, 15, 10, 0, -30,
    -30, 5, 15, 20, 20, 15, 5, -30,
    -30, 0, 15, 20, 20, 15, 0, -30,
    -30, 5, 10, 15, 15, 10, 5, -30,
    -40, -20, 0, 5, 5, 0, -20, -40,
    -50, -40, -30, -30, -30, -30, -40, -50,
]
BISHOP_TABLE = [
    -20, -10, -10, -10, -10, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 10, 10, 5, 0, -10,
    -10, 5, 5, 10, 10, 5, 5, -10,
    -10, 0, 10, 10, 10, 10, 0, -10,
    -10, 10, 10, 10, 10, 10, 10, -10,
    -10, 5, 0, 0, 0, 0, 5, -10,
    -20, -10, -10, -10, -10, -10, -10, -20,
]
ROOK_TABLE = [
    0, 0, 0, 0, 0, 0, 0, 0,
    5, 10, 10, 10, 10, 10, 10, 5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    -5, 0, 0, 0, 0, 0, 0, -5,
    0, 0, 0, 5, 5, 0, 0, 0,
]
QUEEN_TABLE = [
    -20, -10, -10, -5, -5, -10, -10, -20,
    -10, 0, 0, 0, 0, 0, 0, -10,
    -10, 0, 5, 5, 5, 5, 0, -10,
    -5, 0, 5, 5, 5, 5, 0, -5,
    0, 0, 5, 5, 5, 5, 0, -5,
    -10, 5, 5, 5, 5, 5, 0, -10,
    -10, 0, 5, 0, 0, 0, 0, -10,
    -20, -10, -10, -5, -5, -10, -10, -20,
]
KING_TABLE = [
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -30, -40, -40, -50, -50, -40, -40, -30,
    -20, -30, -30, -40, -40, -30, -30, -20,
    -10, -20, -20, -20, -20, -20, -20, -10,
    20, 20, 0, 0, 0, 0, 20, 20,
    20, 30, 10, 0, 0, 10, 30, 20,
]
PST = {
    chess.PAWN: PAWN_TABLE, chess.KNIGHT: KNIGHT_TABLE, chess.BISHOP: BISHOP_TABLE,
    chess.ROOK: ROOK_TABLE, chess.QUEEN: QUEEN_TABLE, chess.KING: KING_TABLE,
}

OPENINGS_DB = {
    "e2e4": "King's Pawn Opening",
    "e2e4 e7e5": "Open Game (King's Pawn)",
    "e2e4 e7e5 g1f3": "King's Knight Opening",
    "e2e4 e7e5 g1f3 b8c6": "Open Game: Knights Defended",
    "e2e4 e7e5 g1f3 b8c6 f1c4": "Italian Game",
    "e2e4 e7e5 g1f3 b8c6 f1b5": "Ruy Lopez",
    "e2e4 e7e5 g1f3 b8c6 d2d4": "Scotch Game",
    "e2e4 e7e5 f2f4": "King's Gambit",
    "e2e4 c7c5": "Sicilian Defense",
    "e2e4 e7e6": "French Defense",
    "e2e4 c7c6": "Caro-Kann Defense",
    "e2e4 d7d5": "Scandinavian Defense",
    "e2e4 g8f6": "Alekhine's Defense",
    "d2d4": "Queen's Pawn Opening",
    "d2d4 d7d5": "Queen's Pawn Game",
    "d2d4 d7d5 c2c4": "Queen's Gambit",
    "d2d4 d7d5 c2c4 e7e6": "Queen's Gambit Declined",
    "d2d4 d7d5 c2c4 d5c4": "Queen's Gambit Accepted",
    "d2d4 g8f6": "Indian Defense",
    "c2c4": "English Opening",
    "g1f3": "Réti Opening",
    "f2f4": "Bird's Opening",
}

# Every theme may optionally override piece coloring (otherwise plain white/black
# pieces with a dark/light outline are used — see board_css).
THEMES = {
    "Classic Wood": {"light": "#f0d9b5", "dark": "#b58863"},
    "Lichess Green": {"light": "#ffffdd", "dark": "#86a666"},
    "Midnight Dark": {"light": "#9e9e9e", "dark": "#424242"},
    "Neon Cyber": {"light": "#2a2d37", "dark": "#00adb5"},
    "Old Money": {
        "light": "#e4d9bd", "dark": "#5c4430",
        "white_piece": "#f6ecd2", "white_shadow": "0 0 1px #2a1d10, 0 1px 2px rgba(0,0,0,.5)",
        "black_piece": "#241a10", "black_shadow": "0 0 1px #d9c48f, 0 1px 1px rgba(0,0,0,.4)",
        "accent": "#8a6d3b",
    },
}

# "elo" below ~1320 falls back to Stockfish "Skill Level" (UCI_Elo has a minimum).
# "random_chance" = probability of a deliberate random (human-like) slip.
BOT_CONFIGS = {
    "Easy": {"elo": 400, "depth": 1, "skill_level": 0, "time_limit": 0.05, "random_chance": 0.60},
    "Medium": {"elo": 800, "depth": 3, "skill_level": 3, "time_limit": 0.1, "random_chance": 0.20},
    "Hard": {"elo": 1200, "depth": 6, "skill_level": 8, "time_limit": 0.2, "random_chance": 0.05},
    "Grandmaster": {"elo": 1750, "depth": 12, "skill_level": 14, "time_limit": 0.4, "random_chance": 0.0},
}

CATEGORIES = ["Brilliant", "Best", "Good", "Inaccuracy", "Mistake", "Blunder"]
CAT_ICON = {"Brilliant": "💎", "Best": "⭐", "Good": "✅", "Inaccuracy": "⚠️", "Mistake": "❌", "Blunder": "🔴"}
CAT_ALERT = {"Brilliant": "success", "Best": "success", "Good": "info",
             "Inaccuracy": "warning", "Mistake": "warning", "Blunder": "error"}
CAT_NAG = {
    "Brilliant": chess.pgn.NAG_BRILLIANT_MOVE, "Inaccuracy": chess.pgn.NAG_DUBIOUS_MOVE,
    "Mistake": chess.pgn.NAG_MISTAKE, "Blunder": chess.pgn.NAG_BLUNDER,
}

PERSONAS = {
    "Grandmaster Magnus (Analytical)": {
        "intro": "Let's evaluate the position calmly: structure first, tactics second.",
        "quotes": {
            "Brilliant": ["A deep idea that holds up under scrutiny. Well found.",
                          "The sacrifice works tactically, and the engine agrees."],
            "Best": ["The most accurate continuation. Structure preserved.",
                     "Precisely what the position demands."],
            "Good": ["Sound, though a more accurate option existed.",
                     "Playable. The evaluation barely moves."],
            "Inaccuracy": ["A small concession. Note which squares you have weakened.",
                           "Imprecise; your opponent's position improves slightly."],
            "Mistake": ["This shifts the balance. Re-examine their forcing replies first.",
                        "A significant concession of the initiative."],
            "Blunder": ["A decisive error. Check captures, checks and threats before every move.",
                        "This changes the evaluation drastically. Slow down and verify."],
        },
    },
    "Coach Sparky (Encouraging)": {
        "intro": "You've got this! Every game makes you stronger.",
        "quotes": {
            "Brilliant": ["WOW! That was incredible. You should be proud! 🌟",
                          "Absolutely brilliant! You're playing like a pro!"],
            "Best": ["Perfect move! Keep it up! ⭐",
                     "Great job, that's exactly the move I was hoping for!"],
            "Good": ["Nice one! There was an even better move, but this works well.",
                     "Good thinking! You're doing great."],
            "Inaccuracy": ["Almost! A small slip. You've got this next time.",
                           "No worries, that was a tiny inaccuracy. Keep going!"],
            "Mistake": ["Oops, that one hurt a bit, but mistakes are how we learn!",
                        "Don't worry! Take a breath and look for their threats."],
            "Blunder": ["Ouch! That's a big one, but shake it off. You can still fight back!",
                        "It happens to everyone! Let's learn from it and keep playing."],
        },
    },
    "Tactical Master (Aggressive)": {
        "intro": "Initiative wins games. Attack, or be attacked.",
        "quotes": {
            "Brilliant": ["Now THAT'S how you attack! Devastating.",
                          "Sacrifice, strike, conquer. Beautiful."],
            "Best": ["Strong and forceful. Keep the pressure on.",
                     "Precise. Give them no air to breathe."],
            "Good": ["Fine, but I want more aggression. Where's the initiative?",
                     "Acceptable. Find the sharper line next time."],
            "Inaccuracy": ["Soft. You let them off the hook.",
                           "Too passive. Attackers don't drift."],
            "Mistake": ["That's a gift to your opponent. Punish or be punished.",
                        "Weak. Every tempo counts, and you just threw one away."],
            "Blunder": ["DISASTER. You handed them the game on a plate.",
                        "A gross blunder. Sharp players never miss this."],
        },
    },
}

SOUND_URLS = {
    "move": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/move-self.mp3",
    "capture": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/capture.mp3",
    "game_over": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/game-end.mp3",
}

# ---------- Translations: key -> (English, Arabic) ----------
TR = {
    "controls": ("Controls & Settings", "التحكم والإعدادات"),
    "audio": ("Enable Audio", "تفعيل الصوت"),
    "difficulty": ("Bot Difficulty", "مستوى الخصم"),
    "persona": ("AI Coach Persona", "شخصية المدرب"),
    "side": ("Choose Side", "اختر اللون"),
    "white": ("White", "أبيض"),
    "black": ("Black", "أسود"),
    "theme": ("Board Theme", "شكل الرقعة"),
    "overlays": ("Board Overlays", "مؤشرات الرقعة"),
    "threats": ("Threat & Guard Indicators", "مؤشرات التهديد والحماية"),
    "legal": ("Show legal moves", "إظهار الحركات المتاحة"),
    "evalbar": ("Live Evaluation Bar", "شريط التقييم المباشر"),
    "stats": ("Player Stats", "إحصائيات اللاعب"),
    "rating": ("Your Rating (ELO)", "تصنيفك (ELO)"),
    "games": ("Games played", "المباريات"),
    "record": ("Record (W/D/L)", "السجل (فوز/تعادل/خسارة)"),
    "badges": ("Badges Unlocked", "الأوسمة المكتسبة"),
    "reset_rating": ("Reset rating", "إعادة تعيين التصنيف"),
    "reset_rating_confirm": ("Yes, erase my saved rating and badges", "نعم، امسح تصنيفي وأوسمتي المحفوظة"),
    "new_game": ("New Game", "مباراة جديدة"),
    "undo": ("Undo", "تراجع"),
    "undo_help": ("Using undo makes the game unrated.", "استخدام التراجع يجعل المباراة غير مصنّفة."),
    "hint": ("Hint", "تلميح"),
    "resign": ("Resign", "استسلام"),
    "export": ("Export PGN", "تصدير PGN"),
    "you": ("You", "أنت"),
    "bot": ("Bot", "الخصم"),
    "your_turn": ("Your turn", "دورك"),
    "check": ("Check!", "كش!"),
    "unrated_note": ("Unrated game (undo used)", "مباراة غير مصنّفة (تم استخدام التراجع)"),
    "unrated_msg": ("Your rating is unchanged because this game was unrated.",
                    "لم يتغير تصنيفك لأن المباراة غير مصنّفة."),
    "changing_note": ("Changing side or difficulty starts a new game.",
                      "تغيير اللون أو المستوى يبدأ مباراة جديدة."),
    "tab_review": ("Review", "المراجعة"),
    "tab_puzzles": ("Puzzles", "الألغاز"),
    "tab_coach": ("Coach", "المدرب"),
    "tab_opening": ("Opening", "الافتتاحية"),
    "tab_history": ("History", "السجل"),
    "accuracy": ("Accuracy", "الدقة"),
    "eval_graph": ("Evaluation Graph", "منحنى التقييم"),
    "no_moves": ("Play a few moves to see your analysis here.", "العب بضع نقلات لتظهر التحليلات هنا."),
    "key_moments": ("Key moments", "اللحظات الحاسمة"),
    "better_was": ("Better was", "الأفضل كان"),
    "promote_to": ("Promote to", "الترقية إلى"),
    "res_win": ("🎉 You won!", "🎉 فزت!"),
    "res_loss": ("💀 You lost.", "💀 خسرت."),
    "res_draw": ("🤝 Draw", "🤝 تعادل"),
    "elo_change": ("Rating change", "تغيّر التصنيف"),
    "new_rating": ("New rating", "التصنيف الجديد"),
    "puzzle_title": ("Puzzles from your mistakes", "ألغاز من أخطائك"),
    "puzzle_none": ("No puzzles yet. Your big mistakes are saved here automatically.",
                    "لا توجد ألغاز بعد! تُحفظ أخطاؤك الكبيرة هنا تلقائيًا."),
    "puzzle_count": ("saved", "محفوظة"),
    "puzzle_solved": ("solved", "محلولة"),
    "puzzle_pick": ("Choose a puzzle", "اختر لغزًا"),
    "puzzle_start": ("Start puzzle", "ابدأ اللغز"),
    "puzzle_giveup": ("Show solution", "أظهر الحل"),
    "puzzle_exit": ("Back to game", "العودة إلى المباراة"),
    "puzzle_correct": ("✅ Correct! Well done.", "✅ صحيح! أحسنت."),
    "puzzle_wrong": ("❌ Not the best move. Try again.", "❌ ليست الأفضل، حاول مرة أخرى."),
    "puzzle_banner": ("🧩 Puzzle: find the best move", "🧩 لغز: جد أفضل نقلة"),
    "puzzle_solution": ("Solution", "الحل"),
    "recommended": ("Recommended move", "النقلة المقترحة"),
    "tactical_warning": ("Tactical warning", "تحذير تكتيكي"),
    "opening_id": ("Identified opening", "الافتتاحية المحددة"),
    "top_master": ("Top master moves in this position", "أشهر نقلات الأساتذة في هذا الوضع"),
    "builtin_engine": ("Built-in engine (install Stockfish for full strength)",
                       "المحرك المدمج (ثبّت Stockfish لقوة أكبر)"),
    "col_move": ("Move", "النقلة"),
    "col_white_wins": ("White wins", "فوز الأبيض"),
    "col_draws": ("Draws", "تعادل"),
    "col_black_wins": ("Black wins", "فوز الأسود"),
    "diff_Easy": ("Easy", "سهل"),
    "diff_Medium": ("Medium", "متوسط"),
    "diff_Hard": ("Hard", "صعب"),
    "diff_Grandmaster": ("Grandmaster", "أستاذ كبير"),
    "cat_Brilliant": ("Brilliant", "رائعة"),
    "cat_Best": ("Best", "الأفضل"),
    "cat_Good": ("Good", "جيدة"),
    "cat_Inaccuracy": ("Inaccuracy", "غير دقيقة"),
    "cat_Mistake": ("Mistake", "خطأ"),
    "cat_Blunder": ("Blunder", "خطأ فادح"),
    "term_CHECKMATE": ("Checkmate", "كش مات"),
    "term_STALEMATE": ("Stalemate", "تعادل بالجمود"),
    "term_INSUFFICIENT_MATERIAL": ("Insufficient material", "مادة غير كافية"),
    "term_THREEFOLD_REPETITION": ("Threefold repetition", "تكرار ثلاثي"),
    "term_FIVEFOLD_REPETITION": ("Fivefold repetition", "تكرار خماسي"),
    "term_FIFTY_MOVES": ("50-move rule", "قاعدة الخمسين نقلة"),
    "term_SEVENTYFIVE_MOVES": ("75-move rule", "قاعدة الخمس والسبعين نقلة"),
    "term_RESIGNATION": ("Resignation", "استسلام"),
}


def t(key):
    """Translate a UI string for the selected language."""
    en, ar = TR[key]
    return ar if st.session_state.get("lang", "EN") == "AR" else en


def tr_term(name):
    key = "term_" + name
    return t(key) if key in TR else name.replace("_", " ").title()


# ==========================================
# 2. PERSISTENT PROFILE (rating, record, badges — survive across sessions/restarts)
# ==========================================
DEFAULT_PROFILE = {"user_elo": 800, "games_played": 0, "record": {"W": 0, "D": 0, "L": 0}, "badges": []}
PROFILE_PATH = Path(os.environ.get("CHESS_COACH_PROFILE", "")) if os.environ.get("CHESS_COACH_PROFILE") \
    else Path(__file__).resolve().with_name("chess_coach_profile.json")
_profile_lock = threading.Lock()


def load_profile():
    try:
        data = json.loads(PROFILE_PATH.read_text())
        return {**DEFAULT_PROFILE, **data}
    except Exception:
        return dict(DEFAULT_PROFILE)


def save_profile():
    """Best-effort, atomic write so a crash mid-write can't corrupt the file."""
    ss = st.session_state
    data = {
        "user_elo": ss.user_elo, "games_played": ss.games_played,
        "record": ss.record, "badges": sorted(ss.badges),
    }
    try:
        with _profile_lock:
            tmp = PROFILE_PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(data))
            tmp.replace(PROFILE_PATH)
    except Exception:
        pass  # persistence is a nice-to-have; never break gameplay over it


def reset_profile():
    ss = st.session_state
    ss.user_elo = DEFAULT_PROFILE["user_elo"]
    ss.games_played = DEFAULT_PROFILE["games_played"]
    ss.record = dict(DEFAULT_PROFILE["record"])
    ss.badges = set()
    save_profile()


# ==========================================
# 3. SESSION STATE
# ==========================================
def init_state():
    ss = st.session_state
    ss.setdefault("board", chess.Board())
    ss.setdefault("log", [])                # one record per ply (see apply_move)
    ss.setdefault("player_color", chess.WHITE)
    ss.setdefault("game_difficulty", "Medium")
    if "user_elo" not in ss:                # first run of this browser session: load from disk
        profile = load_profile()
        ss.user_elo = profile["user_elo"]
        ss.games_played = profile["games_played"]
        ss.record = profile["record"]
        ss.badges = set(profile["badges"])
    ss.setdefault("puzzles", [])
    ss.setdefault("puzzle", None)
    ss.setdefault("puzzle_board", None)
    ss.setdefault("puzzle_msg", None)
    ss.setdefault("selected_sq", None)
    ss.setdefault("pending_promo", None)
    ss.setdefault("hint_uci", None)
    ss.setdefault("hint_san", None)
    ss.setdefault("feedback", None)
    ss.setdefault("explanation", "")
    ss.setdefault("game_over", False)
    ss.setdefault("result", None)           # (kind, termination name)
    ss.setdefault("elo_msg", None)          # "unrated" or (delta, new_elo)
    ss.setdefault("rated", True)
    ss.setdefault("counted", False)
    ss.setdefault("sound", None)
    ss.setdefault("sound_nonce", 0)


# ==========================================
# 4. ENGINES & EVALUATION
# ==========================================
def find_stockfish():
    candidates = [
        os.environ.get("STOCKFISH_PATH"), shutil.which("stockfish"),
        "/usr/games/stockfish", "/usr/bin/stockfish", "/usr/local/bin/stockfish",
    ]
    for path in candidates:
        if path and os.path.exists(path) and os.access(path, os.X_OK):
            return path
    return None


@st.cache_resource(show_spinner=False)
def get_engines():
    """Two separate Stockfish processes: one for the bot (strength-limited), one for
    analysis (full strength), each behind a lock because sessions share them."""
    path = find_stockfish()
    if not path:
        return None
    try:
        bot = chess.engine.SimpleEngine.popen_uci(path)
        ana = chess.engine.SimpleEngine.popen_uci(path)
        for eng in (bot, ana):
            try:
                eng.configure({"Threads": 1})
            except Exception:
                pass
        return {
            "bot": bot, "analysis": ana,
            "bot_lock": threading.Lock(), "analysis_lock": threading.Lock(),
            "name": bot.id.get("name", "Stockfish"),
        }
    except Exception:
        return None


def evaluate_board_custom(board):
    """Static evaluation in centipawns from White's point of view."""
    if board.is_checkmate():
        return -MATE_CP if board.turn == chess.WHITE else MATE_CP
    if board.is_insufficient_material():
        return 0
    score = 0
    for sq, piece in board.piece_map().items():
        idx = chess.square_mirror(sq) if piece.color == chess.WHITE else sq
        value = PIECE_VALUES[piece.piece_type] + PST[piece.piece_type][idx]
        score += value if piece.color == chess.WHITE else -value
    return score


def order_moves(board):
    def key(move):
        if board.is_capture(move):
            victim = board.piece_type_at(move.to_square) or chess.PAWN  # en passant
            attacker = board.piece_type_at(move.from_square)
            return 10 * PIECE_VALUES[victim] - PIECE_VALUES[attacker] + 1000
        if move.promotion:
            return 900
        return 0
    return sorted(board.legal_moves, key=key, reverse=True)


def minimax(board, depth, alpha, beta):
    """Alpha-beta search. Returns (score in centipawns from White's view, best move)."""
    if depth == 0:
        return evaluate_board_custom(board), None
    moves = order_moves(board)
    if not moves:
        if board.is_check():
            mate = MATE_CP - 1000 + depth  # closer mates score higher
            return (-mate if board.turn == chess.WHITE else mate), None
        return 0, None

    best_move = moves[0]
    if board.turn == chess.WHITE:
        best = -10 ** 9
        for move in moves:
            board.push(move)
            score, _ = minimax(board, depth - 1, alpha, beta)
            board.pop()
            if score > best:
                best, best_move = score, move
            alpha = max(alpha, best)
            if beta <= alpha:
                break
    else:
        best = 10 ** 9
        for move in moves:
            board.push(move)
            score, _ = minimax(board, depth - 1, alpha, beta)
            board.pop()
            if score < best:
                best, best_move = score, move
            beta = min(beta, best)
            if beta <= alpha:
                break
    return best, best_move


def terminal_cp(board):
    if board.is_checkmate():
        return -MATE_CP if board.turn == chess.WHITE else MATE_CP
    return 0


@st.cache_data(show_spinner=False, max_entries=2048)
def cached_analysis(fen, seconds):
    """Best move (UCI) and eval (centipawns, White's view) for a position."""
    board = chess.Board(fen)
    if board.is_game_over():
        return None, terminal_cp(board)
    pool = get_engines()
    if pool:
        try:
            with pool["analysis_lock"]:
                info = pool["analysis"].analyse(board, chess.engine.Limit(time=seconds))
            score = info["score"].white().score(mate_score=MATE_CP)
            pv = info.get("pv") or []
            return (pv[0].uci() if pv else None), int(score)
        except chess.engine.EngineTerminatedError:
            get_engines.clear()
        except Exception:
            pass
    score, move = minimax(board, 2, -10 ** 9, 10 ** 9)
    return (move.uci() if move else None), int(score)


def get_analysis(board):
    return cached_analysis(board.fen(), ANALYSIS_SECONDS)


def get_bot_move(board, difficulty):
    cfg = BOT_CONFIGS.get(difficulty, BOT_CONFIGS["Medium"])
    legal = list(board.legal_moves)
    if not legal:
        return None
    if random.random() < cfg["random_chance"]:
        return random.choice(legal)

    pool = get_engines()
    if pool:
        try:
            with pool["bot_lock"]:
                eng = pool["bot"]
                elo_opt = eng.options.get("UCI_Elo")
                if elo_opt is not None and cfg["elo"] >= elo_opt.min:
                    eng.configure({"UCI_LimitStrength": True, "UCI_Elo": min(cfg["elo"], elo_opt.max)})
                else:
                    settings = {"UCI_LimitStrength": False}
                    if "Skill Level" in eng.options:
                        settings["Skill Level"] = cfg["skill_level"]
                    eng.configure(settings)
                result = eng.play(board, chess.engine.Limit(time=cfg["time_limit"], depth=cfg["depth"]))
            if result.move:
                return result.move
        except chess.engine.EngineTerminatedError:
            get_engines.clear()
        except Exception:
            pass

    _, move = minimax(board, min(cfg["depth"], 3), -10 ** 9, 10 ** 9)
    return move or random.choice(legal)


# ==========================================
# 5. MOVE ASSESSMENT & COACHING
# ==========================================
def win_pct(cp):
    """White's winning chances (0-100) for an evaluation in centipawns."""
    cp = max(-1500, min(1500, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def fmt_eval(cp):
    if abs(cp) >= 9000:
        n = MATE_CP - abs(cp)
        sign = "+" if cp > 0 else "-"
        return f"{sign}M{n}" if 0 < n < 500 else f"{sign}#"
    return f"{cp / 100:+.1f}"


def is_sacrifice(board, move):
    """True if the move puts a piece where it can be won for less than its value."""
    piece = board.piece_at(move.from_square)
    if not piece or piece.piece_type in (chess.PAWN, chess.KING):
        return False
    mine = piece.color
    gain = 0
    if board.is_capture(move):
        gain = PIECE_VALUES[board.piece_type_at(move.to_square) or chess.PAWN]
    b = board.copy(stack=False)
    b.push(move)
    attackers = list(b.attackers(not mine, move.to_square))
    if not attackers:
        return False
    cheapest = min(PIECE_VALUES[b.piece_type_at(sq)] for sq in attackers)
    defended = bool(b.attackers(mine, move.to_square))
    value = PIECE_VALUES[piece.piece_type]
    risk = (max(0, value - cheapest) if defended else value) - gain
    return risk >= 200


def classify(loss, is_best, is_sac, mover_before, mover_after):
    if is_best or loss < 1.0:
        if is_sac and mover_before < 600 and mover_after > -100:
            return "Brilliant"
        return "Best"
    if loss < 5:
        return "Good"
    if loss < 10:
        return "Inaccuracy"
    if loss < 15:
        return "Mistake"
    return "Blunder"


def assess_move(board, move):
    """Grade `move` (legal in `board`) against best play. Never mutates `board` — this
    makes it safe to call from a worker thread while other code reads the same board."""
    sign = 1 if board.turn == chess.WHITE else -1
    best_uci, before_cp = get_analysis(board)
    best_san = None
    if best_uci:
        best_move = chess.Move.from_uci(best_uci)
        if best_move in board.legal_moves:
            best_san = board.san(best_move)
    san = board.san(move)
    sac = is_sacrifice(board, move)

    after_board = board.copy(stack=False)
    after_board.push(move)
    _, after_cp = get_analysis(after_board)
    gives_mate = after_board.is_checkmate()

    is_best = move.uci() == best_uci or gives_mate
    loss = 0.0 if is_best else max(0.0, win_pct(sign * before_cp) - win_pct(sign * after_cp))
    cat = classify(loss, is_best, sac, sign * before_cp, sign * after_cp)
    accuracy = max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * loss) - 3.1669))
    return {
        "uci": move.uci(), "san": san, "cat": cat, "loss": loss, "acc": accuracy,
        "best_uci": best_uci, "best_san": best_san, "cp_after": after_cp, "gives_mate": gives_mate,
    }


def analyze_blunder(before, move, after, best_san=None):
    """Plain-language reasons a move was bad. `after` is `before` with `move` played."""
    reasons = []
    mover = before.turn
    piece = before.piece_at(move.from_square)
    dest = move.to_square

    for reply in list(after.legal_moves):
        after.push(reply)
        mate = after.is_checkmate()
        after.pop()
        if mate:
            reasons.append("Allows checkmate in one move.")
            break

    if piece and piece.piece_type != chess.KING:
        if after.is_attacked_by(not mover, dest) and not after.is_attacked_by(mover, dest):
            reasons.append(f"Leaves your **{chess.piece_name(piece.piece_type).title()}** "
                           f"undefended on {chess.square_name(dest)}.")

    big = [sq for sq, p in after.piece_map().items()
           if p.color == mover and p.piece_type in (chess.KING, chess.ROOK, chess.QUEEN)
           and after.is_attacked_by(not mover, sq)]
    if len(big) >= 2:
        reasons.append("Allows a fork on several high-value pieces.")

    hanging = [chess.square_name(sq) for sq, p in after.piece_map().items()
               if p.color == mover and sq != dest and p.piece_type not in (chess.KING, chess.PAWN)
               and after.is_attacked_by(not mover, sq) and not after.is_attacked_by(mover, sq)]
    if hanging:
        reasons.append(f"A piece is left undefended on {', '.join(hanging[:2])}.")

    if not reasons:
        reasons.append("You lose positional control or tactical superiority.")
    if best_san:
        reasons.append(f"{t('better_was')} **{best_san}**.")
    return " ".join(reasons[:3])


def make_feedback(rec):
    persona = st.session_state.get("persona", next(iter(PERSONAS)))
    quotes = PERSONAS.get(persona, next(iter(PERSONAS.values())))["quotes"][rec["cat"]]
    return {"cat": rec["cat"], "san": rec["san"], "quote": random.choice(quotes),
            "best_san": rec["best_san"], "loss": rec["loss"]}


# ==========================================
# 6. GAME FLOW (all called from button callbacks)
# ==========================================
def queue_sound(kind):
    st.session_state.sound = kind
    st.session_state.sound_nonce += 1


def apply_move(move, by_player):
    """Assess, play and log a move on the main board. Returns the log record."""
    ss = st.session_state
    board = ss.board
    rec = assess_move(board, move)
    rec["piece"] = board.piece_type_at(move.from_square)
    rec["capture"] = board.is_capture(move)
    board.push(move)
    rec["by_player"] = by_player
    ss.log.append(rec)
    if by_player and rec["cat"] == "Brilliant":
        ss.badges.add("💎 Brilliant Move")
        save_profile()
    if by_player and rec["gives_mate"] and rec["piece"] == chess.PAWN:
        ss.badges.add("♟️ Pawn Checkmate")
        save_profile()
    return rec


def record_result(score):
    ss = st.session_state
    if ss.counted:
        return
    ss.counted = True
    if not ss.rated:
        ss.elo_msg = "unrated"
        return

    ss.record["W" if score == 1.0 else "L" if score == 0.0 else "D"] += 1
    ss.games_played += 1
    bot_elo = BOT_CONFIGS[ss.game_difficulty]["elo"]
    k_factor = 40 if ss.games_played <= 30 else 20  # Chess.com-style provisional K
    expected = 1 / (1 + 10 ** ((bot_elo - ss.user_elo) / 400))
    delta = round(k_factor * (score - expected))
    ss.user_elo = max(100, ss.user_elo + delta)
    ss.elo_msg = (delta, ss.user_elo)

    player_recs = [r for r in ss.log if r["by_player"]]
    if score == 1.0:
        ss.badges.add("🏆 First Win")
        if ss.game_difficulty in ("Hard", "Grandmaster"):
            ss.badges.add("👑 Giant Slayer")
        sign = 1 if ss.player_color == chess.WHITE else -1
        if any(sign * r["cp_after"] <= -300 for r in ss.log):
            ss.badges.add("🔥 Comeback")
    if len(player_recs) >= 15 and all(r["cat"] not in ("Mistake", "Blunder") for r in player_recs):
        ss.badges.add("🎯 Clean Game")
    save_profile()


def finish_game():
    ss = st.session_state
    outcome = ss.board.outcome(claim_draw=True)
    ss.game_over = True
    if outcome is None:
        kind, term, score = "draw", "DRAW", 0.5
    elif outcome.winner is None:
        kind, term, score = "draw", outcome.termination.name, 0.5
    elif outcome.winner == ss.player_color:
        kind, term, score = "win", outcome.termination.name, 1.0
    else:
        kind, term, score = "loss", outcome.termination.name, 0.0
    ss.result = (kind, term)
    queue_sound("game_over")
    record_result(score)


def play_player_move(move):
    """Assess the player's move and pick the bot's reply at the same time — both
    only need to read the resulting position, so running them in parallel (on
    separate Stockfish processes) roughly halves the wait compared to doing them
    one after another."""
    ss = st.session_state
    board = ss.board

    sim_after = board.copy(stack=False)
    sim_after.push(move)
    bot_needed = not sim_after.is_game_over(claim_draw=True)

    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_rec = pool.submit(assess_move, board, move)
        fut_bot = pool.submit(get_bot_move, sim_after, ss.game_difficulty) if bot_needed else None
        rec = fut_rec.result()
        bot_move = fut_bot.result() if fut_bot else None

    rec["piece"] = board.piece_type_at(move.from_square)
    rec["capture"] = board.is_capture(move)
    rec["by_player"] = True
    before = board.copy(stack=False)
    board.push(move)
    ss.log.append(rec)
    if rec["cat"] == "Brilliant":
        ss.badges.add("💎 Brilliant Move")
        save_profile()
    if rec["gives_mate"] and rec["piece"] == chess.PAWN:
        ss.badges.add("♟️ Pawn Checkmate")
        save_profile()

    ss.selected_sq = None
    ss.pending_promo = None
    ss.hint_uci = None
    ss.hint_san = None
    ss.feedback = make_feedback(rec)
    ss.explanation = ""

    if rec["cat"] in ("Mistake", "Blunder"):
        ss.explanation = analyze_blunder(before, move, board, rec["best_san"])
        if rec["best_uci"] and rec["best_uci"] != rec["uci"]:
            ss.puzzles.append({
                "fen": before.fen(), "best_uci": rec["best_uci"], "best_san": rec["best_san"],
                "played_san": rec["san"], "move_no": before.fullmove_number,
                "color": before.turn, "solved": False,
            })

    sound = "capture" if rec["capture"] else "move"
    if board.is_game_over(claim_draw=True):
        finish_game()
        return

    if bot_move:
        bot_rec = apply_move(bot_move, False)
        if bot_rec["capture"]:
            sound = "capture"
        if board.is_game_over(claim_draw=True):
            finish_game()
            return
    queue_sound(sound)


def new_game():
    ss = st.session_state
    ss.player_color = chess.WHITE if ss.get("side_choice", "White") == "White" else chess.BLACK
    ss.game_difficulty = ss.get("difficulty_choice", "Medium")
    ss.board = chess.Board()
    ss.log = []
    ss.selected_sq = None
    ss.pending_promo = None
    ss.hint_uci = None
    ss.hint_san = None
    ss.feedback = None
    ss.explanation = ""
    ss.game_over = False
    ss.result = None
    ss.elo_msg = None
    ss.rated = True
    ss.counted = False
    ss.puzzle = None
    ss.puzzle_board = None
    ss.puzzle_msg = None
    if ss.player_color == chess.BLACK:
        first = get_bot_move(ss.board, ss.game_difficulty)
        if first:
            apply_move(first, False)


def on_undo():
    ss = st.session_state
    board = ss.board
    floor = 1 if ss.player_color == chess.BLACK else 0  # never undo the bot's opening move
    if len(board.move_stack) <= floor:
        return
    while len(board.move_stack) > floor:
        board.pop()
        if ss.log:
            ss.log.pop()
        if board.turn == ss.player_color:
            break
    ss.selected_sq = None
    ss.pending_promo = None
    ss.hint_uci = None
    ss.hint_san = None
    ss.feedback = None
    ss.explanation = ""
    ss.game_over = False
    ss.result = None
    ss.elo_msg = None
    ss.rated = False  # taking moves back forfeits the rating change


def on_resign():
    ss = st.session_state
    if ss.game_over or not ss.board.move_stack:
        return
    ss.game_over = True
    ss.result = ("loss", "RESIGNATION")
    queue_sound("game_over")
    record_result(0.0)


def on_hint():
    ss = st.session_state
    board = ss.board
    if ss.game_over or board.turn != ss.player_color:
        return
    best_uci, _ = get_analysis(board)
    if best_uci:
        ss.hint_uci = best_uci
        ss.hint_san = board.san(chess.Move.from_uci(best_uci))


# ---------- Puzzles ----------
def on_start_puzzle():
    ss = st.session_state
    idx = ss.get("puzzle_pick", 0)
    if not 0 <= idx < len(ss.puzzles):
        return
    p = ss.puzzles[idx]
    ss.puzzle = {"idx": idx, "best": p["best_uci"], "color": p["color"], "done": False}
    ss.puzzle_board = chess.Board(p["fen"])
    ss.puzzle_msg = None
    ss.selected_sq = None
    ss.pending_promo = None
    ss.hint_uci = None


def on_exit_puzzle():
    ss = st.session_state
    ss.puzzle = None
    ss.puzzle_board = None
    ss.puzzle_msg = None
    ss.selected_sq = None
    ss.pending_promo = None
    ss.hint_uci = None


def on_giveup_puzzle():
    ss = st.session_state
    if ss.puzzle and not ss.puzzle["done"]:
        ss.puzzle["done"] = True
        ss.hint_uci = ss.puzzle["best"]
        ss.puzzle_msg = ("info", "solution")
        ss.selected_sq = None


def submit_puzzle_move(move):
    ss = st.session_state
    pz, pb = ss.puzzle, ss.puzzle_board
    ok = move.uci() == pz["best"]
    if not ok:  # accept any move that is about as good as the engine's choice
        ok = assess_move(pb, move)["loss"] < 3
    ss.selected_sq = None
    if ok:
        pb.push(move)
        pz["done"] = True
        ss.puzzles[pz["idx"]]["solved"] = True
        ss.badges.add("🧩 Puzzle Solver")
        save_profile()
        ss.puzzle_msg = ("success", "puzzle_correct")
        queue_sound("move")
    else:
        ss.puzzle_msg = ("error", "puzzle_wrong")


# ---------- Board interaction ----------
def submit_move(move):
    if st.session_state.puzzle is not None:
        submit_puzzle_move(move)
    else:
        play_player_move(move)


def on_square_click(sq):
    ss = st.session_state
    in_puzzle = ss.puzzle is not None
    if in_puzzle:
        if ss.puzzle["done"]:
            return
        board, mover = ss.puzzle_board, ss.puzzle["color"]
    else:
        board, mover = ss.board, ss.player_color
        if ss.game_over or board.turn != mover:
            return

    if ss.pending_promo:  # any click cancels the promotion picker
        ss.pending_promo = None
        ss.selected_sq = None
        return

    sel = ss.selected_sq
    piece = board.piece_at(sq)
    if sel is None:
        if piece and piece.color == mover:
            ss.selected_sq = sq
        return
    if sq == sel:
        ss.selected_sq = None
        return
    if piece and piece.color == mover:
        ss.selected_sq = sq
        return

    moves = [m for m in board.legal_moves if m.from_square == sel and m.to_square == sq]
    if not moves:
        ss.selected_sq = None
    elif len(moves) > 1:  # promotion: ask which piece
        ss.pending_promo = (sel, sq)
    else:
        submit_move(moves[0])


def on_promote(piece_type):
    ss = st.session_state
    if not ss.pending_promo:
        return
    from_sq, to_sq = ss.pending_promo
    ss.pending_promo = None
    submit_move(chess.Move(from_sq, to_sq, promotion=piece_type))


# ==========================================
# 7. RENDERING HELPERS
# ==========================================
BASE_CSS = """
.stApp { background-color: #0e1117; }
.game-over-banner { background:#1f242d; border:2px solid #00c853; padding:16px; border-radius:12px;
                    text-align:center; margin-bottom:16px; }
.game-over-banner h2 { margin:0 0 6px 0; }
.game-over-banner p { margin:2px 0; }
.coach-box { background:#1f242d; border-left:5px solid #00c853; padding:14px; border-radius:8px; margin-bottom:14px; }
.puzzle-banner { background:#1f242d; border:2px solid #4da6ff; padding:12px; border-radius:12px;
                 text-align:center; margin-bottom:12px; font-weight:600; }
.evalbar { position:relative; height:22px; background:#333; border:1px solid #555; border-radius:6px;
           overflow:hidden; margin:6px 0 10px 0; }
.evalfill { background:#f2f2f2; height:100%; transition:width .4s; }
.evallabel { position:absolute; top:2px; left:50%; transform:translateX(-50%); font-size:12px;
             font-weight:700; color:#fff; mix-blend-mode:difference; }
.playerline { font-size:1.05rem; margin:4px 0; }
"""

BOARD_BASE_CSS = """
.st-key-board { max-width:540px; margin:0 auto; gap:0 !important; direction:ltr; }
.st-key-board [data-testid="stVerticalBlock"] { gap:0 !important; }
.st-key-board [data-testid="stHorizontalBlock"] { flex-wrap:nowrap !important; gap:0 !important; }
.st-key-board [data-testid="stColumn"] { min-width:0 !important; flex:1 1 0 !important; width:auto !important; }
.st-key-board [data-testid="stElementContainer"], .st-key-board [data-testid="stButton"] { width:100% !important; margin:0 !important; }
.st-key-board button { position:relative; aspect-ratio:1/1; width:100% !important; min-height:0 !important;
    height:auto !important; padding:0 !important; border:none !important; border-radius:0 !important;
    line-height:1 !important; overflow:hidden; cursor:pointer; }
.st-key-board button p { font-size:clamp(1.6rem,7vw,2.8rem) !important; line-height:1 !important; margin:0 !important;
    font-family:"Segoe UI Symbol","Noto Sans Symbols 2","DejaVu Sans","Apple Symbols",sans-serif !important; }
.st-key-board button:hover { filter:brightness(1.12); }
"""

TINT_LAST = "rgba(246,246,105,.45)"
TINT_SELECT = "rgba(20,160,255,.55)"
TINT_HINT = "rgba(0,200,83,.55)"
CHECK_GRADIENT = "radial-gradient(circle, rgba(255,0,0,.9) 0%, rgba(255,0,0,0) 75%)"

# A subtle metallic shimmer painted onto the piece glyphs themselves (ivory/gold for
# the light side, graphite/bronze for the dark side) — layered on top of the existing
# outline shadow, so pieces read as engraved rather than flat text on every theme.
WHITE_PIECE_GRADIENT = "linear-gradient(145deg, #fffdf6 0%, #f0dd9e 40%, #fffdf6 62%, #d8b45f 100%)"
BLACK_PIECE_GRADIENT = "linear-gradient(145deg, #5a4630 0%, #17120c 45%, #4a3a26 68%, #1d1610 100%)"


def tint(color):
    return f"linear-gradient({color},{color})"


def threat_rings(board):
    """Per-square outline colors: hanging pieces, contested pieces, guarded pieces."""
    rings = {}
    for sq, piece in board.piece_map().items():
        attacked = board.is_attacked_by(not piece.color, sq)
        defended = board.is_attacked_by(piece.color, sq)
        if attacked and not defended:
            rings[sq] = "rgba(255,77,77,.95)"
        elif attacked and defended:
            rings[sq] = "rgba(255,165,0,.95)"
        elif defended and piece.color == board.turn:
            rings[sq] = "rgba(77,166,255,.6)"
    return rings


def board_css(board, orientation, colors, selected, targets, last_move, hint_uci, rings):
    flipped = orientation == chess.BLACK
    bottom_rank = 7 if flipped else 0
    left_file = 7 if flipped else 0
    hint = chess.Move.from_uci(hint_uci) if hint_uci else None
    check_sq = board.king(board.turn) if board.is_check() else None
    out = [BOARD_BASE_CSS]

    for sq in chess.SQUARES:
        name = chess.square_name(sq)
        f, r = chess.square_file(sq), chess.square_rank(sq)
        light = (f + r) % 2 == 1
        base = colors["light"] if light else colors["dark"]
        piece = board.piece_at(sq)

        layers = []
        if sq == check_sq:
            layers.append(CHECK_GRADIENT)
        if selected == sq:
            layers.append(tint(TINT_SELECT))
        if last_move and sq in (last_move.from_square, last_move.to_square):
            layers.append(tint(TINT_LAST))
        if hint and sq in (hint.from_square, hint.to_square):
            layers.append(tint(TINT_HINT))
        background = ", ".join(layers + [base])

        shadows = []
        if sq in rings:
            shadows.append(f"inset 0 0 0 3px {rings[sq]}")
        if sq in targets and piece:
            shadows.append("inset 0 0 0 4px rgba(224,67,58,.95)")
        box_shadow = ", ".join(shadows) if shadows else "none"

        if piece and piece.color == chess.WHITE:
            fg = colors.get("white_piece", "#ffffff")
            shadow = colors.get("white_shadow", "0 0 2px #000, 0 0 3px #000, 0 1px 2px #000")
        elif piece:
            fg = colors.get("black_piece", "#151515")
            shadow = colors.get("black_shadow", "0 0 2px #fff, 0 0 3px #fff")
        elif sq in targets:
            fg, shadow = "rgba(46,139,255,.9)", "none"
        else:
            fg, shadow = "transparent", "none"

        sel = f".st-key-sq_{name} button"
        out.append(
            f"{sel}, {sel}:hover, {sel}:focus, {sel}:active {{ background:{background} !important; "
            f"color:{fg} !important; text-shadow:{shadow} !important; box-shadow:{box_shadow} !important; "
            f"outline:none !important; }}"
        )
        if piece:
            grad = WHITE_PIECE_GRADIENT if piece.color == chess.WHITE else BLACK_PIECE_GRADIENT
            out.append(
                f"{sel} p {{ background-image:{grad} !important; -webkit-background-clip:text !important; "
                f"background-clip:text !important; -webkit-text-fill-color:transparent !important; }}"
            )

        coord_color = colors["dark"] if light else colors["light"]
        coord_style = f"position:absolute; font-size:11px; font-weight:700; line-height:1; color:{coord_color}; text-shadow:none;"
        if r == bottom_rank:
            out.append(f'{sel}::after {{ content:"{chess.FILE_NAMES[f]}"; right:3px; bottom:2px; {coord_style} }}')
        if f == left_file:
            out.append(f'{sel}::before {{ content:"{r + 1}"; left:3px; top:2px; {coord_style} }}')
    return "\n".join(out)


def render_board(board, orientation, theme, selected, targets, last_move, hint_uci, rings):
    st.markdown(
        f"<style>{board_css(board, orientation, theme, selected, targets, last_move, hint_uci, rings)}</style>",
        unsafe_allow_html=True,
    )
    flipped = orientation == chess.BLACK
    ranks = list(range(8)) if flipped else list(range(7, -1, -1))
    files = list(range(7, -1, -1)) if flipped else list(range(8))
    with st.container(key="board"):
        for r in ranks:
            cols = st.columns(8, gap="small")
            for col, f in zip(cols, files):
                sq = chess.square(f, r)
                piece = board.piece_at(sq)
                if piece:
                    label = BOARD_GLYPH[piece.piece_type]
                elif sq in targets:
                    label = "•"
                else:
                    label = "\u00a0"
                col.button(label, key=f"sq_{chess.square_name(sq)}", on_click=on_square_click,
                           args=(sq,), width="stretch")


def eval_bar_html(cp):
    pct = win_pct(cp)
    return (f'<div class="evalbar"><div class="evalfill" style="width:{pct:.1f}%"></div>'
            f'<span class="evallabel">{fmt_eval(cp)}</span></div>')


def captured_by(board, color):
    """Symbols of the enemy pieces `color` has captured."""
    enemy = not color
    out = []
    for piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN):
        missing = STARTING_PIECES[piece_type] - len(board.pieces(piece_type, enemy))
        out.extend([PIECE_SYMBOLS[(piece_type, enemy)]] * max(0, missing))
    return "".join(out)


def material_diff(board):
    """Material balance in pawns, positive if White is ahead."""
    total = 0
    for piece in board.piece_map().values():
        value = PIECE_VALUES[piece.piece_type]
        total += value if piece.color == chess.WHITE else -value
    return round(total / 100)


def play_sound(kind):
    """Play a sound effect. Each rerun renders this inside a brand-new, sandboxed
    iframe, and browsers block autoplay-with-sound in a frame that hasn't itself
    received a user gesture — the click happened in the *top* page, not in this
    throwaway iframe, so a plain <audio autoplay> here is silently blocked. We
    instead reach up to window.parent (the actual Streamlit page, which persists
    across reruns and did receive the click) and keep one set of <audio> elements
    there, created once and reused, which browsers are willing to play."""
    if kind not in SOUND_URLS:
        return
    nonce = st.session_state.sound_nonce
    urls_json = json.dumps(SOUND_URLS)
    components.html(
        f"""<script>
        (function() {{
            try {{
                var top = window.parent;
                if (!top.__chessAudio) {{
                    var urls = {urls_json};
                    top.__chessAudio = {{}};
                    for (var key in urls) {{
                        var a = new Audio(urls[key]);
                        a.preload = "auto";
                        top.__chessAudio[key] = a;
                    }}
                }}
                var snd = top.__chessAudio[{kind!r}];
                if (snd) {{
                    snd.currentTime = 0;
                    snd.volume = 1.0;
                    snd.play().catch(function() {{}});
                }}
            }} catch (e) {{}}
        }})();
        </script>
        <!-- {nonce} -->""",
        height=0,
    )


def build_pgn():
    ss = st.session_state
    game = chess.pgn.Game()
    you, bot = "You", f"Chess Coach Bot ({ss.game_difficulty})"
    game.headers["Event"] = "The Chess Coach"
    game.headers["White"] = you if ss.player_color == chess.WHITE else bot
    game.headers["Black"] = bot if ss.player_color == chess.WHITE else you
    node = game
    for move, rec in zip(ss.board.move_stack, ss.log):
        node = node.add_variation(move)
        nag = CAT_NAG.get(rec["cat"])
        if nag:
            node.nags.add(nag)
        node.comment = f"[%eval {rec['cp_after'] / 100:.2f}]"
    if ss.result and ss.result[1] == "RESIGNATION":
        game.headers["Result"] = "0-1" if ss.player_color == chess.WHITE else "1-0"
    elif ss.board.outcome(claim_draw=True):
        game.headers["Result"] = ss.board.result(claim_draw=True)
    return str(game)


@st.cache_data(ttl=3600, show_spinner=False, max_entries=256)
def fetch_lichess_opening(fen):
    """Raises on failure so failures are never cached."""
    headers = {}
    token = os.environ.get("LICHESS_TOKEN")
    if not token:
        try:
            token = st.secrets.get("LICHESS_TOKEN")
        except Exception:
            token = None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    res = requests.get("https://explorer.lichess.ovh/masters", params={"fen": fen},
                       headers=headers, timeout=2)
    res.raise_for_status()
    data = res.json()
    name = (data.get("opening") or {}).get("name")
    return name, data.get("moves", [])


def local_opening_name(board):
    ucis = [m.uci() for m in board.move_stack]
    best_name, best_len = None, 0
    for prefix, name in OPENINGS_DB.items():
        parts = prefix.split()
        if len(parts) > best_len and ucis[:len(parts)] == parts:
            best_name, best_len = name, len(parts)
    return best_name


# ==========================================
# 8. SIDEBAR
# ==========================================
init_state()
ss = st.session_state

st.sidebar.radio("🌐 Language / اللغة", ["EN", "AR"], key="lang", horizontal=True)
is_ar = ss.lang == "AR"
st.sidebar.title("🎮 " + t("controls"))

audio_enabled = st.sidebar.toggle("🔊 " + t("audio"), value=True, key="audio")
st.sidebar.selectbox("🎯 " + t("difficulty"), list(BOT_CONFIGS), index=1, key="difficulty_choice",
                     format_func=lambda d: t("diff_" + d), on_change=new_game)
st.sidebar.radio("♟️ " + t("side"), ["White", "Black"], key="side_choice", horizontal=True,
                 format_func=lambda s: t("white") if s == "White" else t("black"), on_change=new_game)
st.sidebar.caption(t("changing_note"))
st.sidebar.selectbox("🤖 " + t("persona"), list(PERSONAS), key="persona")
theme_name = st.sidebar.selectbox("🎨 " + t("theme"), list(THEMES), index=list(THEMES).index("Old Money"), key="theme")

st.sidebar.markdown("---")
st.sidebar.subheader("🎨 " + t("overlays"))
show_threats = st.sidebar.checkbox(t("threats"), value=True, key="show_threats")
show_legal = st.sidebar.checkbox(t("legal"), value=True, key="show_legal")
show_eval_bar = st.sidebar.checkbox(t("evalbar"), value=True, key="show_eval")

st.sidebar.markdown("---")
st.sidebar.subheader("🏆 " + t("stats"))
st.sidebar.metric(t("rating"), ss.user_elo)
st.sidebar.caption(f"{t('games')}: {ss.games_played}  ·  {t('record')}: "
                   f"{ss.record['W']}/{ss.record['D']}/{ss.record['L']}")
if ss.badges:
    st.sidebar.markdown(f"**{t('badges')}:**")
    for badge in sorted(ss.badges):
        st.sidebar.caption(badge)
with st.sidebar.expander(t("reset_rating")):
    st.checkbox(t("reset_rating_confirm"), key="confirm_reset")
    st.button(t("reset_rating"), key="btn_reset_rating", on_click=reset_profile,
              disabled=not ss.get("confirm_reset"), width="stretch")

st.sidebar.markdown("---")
st.sidebar.button("🔄 " + t("new_game"), key="btn_new", on_click=new_game, width="stretch")
st.sidebar.download_button("📥 " + t("export"), data=build_pgn(), file_name="chess_match.pgn",
                           mime="text/plain", width="stretch")
pool = get_engines()
st.sidebar.caption("⚙️ " + (pool["name"] if pool else t("builtin_engine")))

# ==========================================
# 9. MAIN DASHBOARD
# ==========================================
css = BASE_CSS
if is_ar:
    css += ".st-key-panel { direction:rtl; text-align:right; }"
if theme_name == "Old Money":
    # Warm, muted "old money" chrome: parchment text, brass accents, a serif
    # typeface, in place of the default dark/neon-green tech look.
    css += """
    .stApp { background-color: #171310 !important; font-family: Georgia, 'Times New Roman', serif; }
    .stMarkdown, .stCaption, h1, h2, h3, h4, h5, h6,
    .stButton button, .stDownloadButton button,
    div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"],
    .game-over-banner, .coach-box, .puzzle-banner, .playerline {
        font-family: Georgia, 'Times New Roman', serif !important;
    }
    /* Never touch Streamlit's own icon font (chevrons, arrows, etc.) — forcing a
       serif font onto it makes it fall back to showing the icon's literal name,
       e.g. "keyboard_double_arrow_right", instead of the glyph. */
    [data-testid="stIconMaterial"], [class*="material-symbols"], [class*="material-icons"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined', 'Material Icons', sans-serif !important;
    }
    section[data-testid="stSidebar"] { background-color: #1d1712 !important; border-right: 1px solid #5c4430; }
    .game-over-banner, .coach-box, .puzzle-banner {
        background:#241d16 !important; border-color:#8a6d3b !important;
    }
    .stButton button, .stDownloadButton button {
        background:#241d16 !important; color:#e4d9bd !important; border:1px solid #8a6d3b !important;
    }
    .stButton button:hover, .stDownloadButton button:hover { border-color:#d9c48f !important; color:#f6ecd2 !important; }
    div[data-testid="stMetricValue"], div[data-testid="stMetricLabel"] { color:#d9c48f !important; }
    .evalfill { background:#e4d9bd !important; }
    """
st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)

if ss.sound:
    if audio_enabled:
        play_sound(ss.sound)
    ss.sound = None

in_puzzle = ss.puzzle is not None
board = ss.puzzle_board if in_puzzle else ss.board
if in_puzzle:
    orientation = ss.puzzle["color"]
    mover = ss.puzzle["color"]
    can_move = not ss.puzzle["done"]
else:
    orientation = ss.player_color
    mover = ss.player_color
    can_move = (not ss.game_over) and board.turn == mover

col_board, col_dash = st.columns([1.25, 1])

# ---------------- Board column ----------------
with col_board:
    if in_puzzle:
        st.markdown(f'<div class="puzzle-banner">{t("puzzle_banner")}</div>', unsafe_allow_html=True)
        if ss.puzzle_msg:
            level, key = ss.puzzle_msg
            if key == "solution":
                p = ss.puzzles[ss.puzzle["idx"]]
                st.info(f"{t('puzzle_solution')}: **{p['best_san']}**")
            else:
                getattr(st, level)(t(key))
    elif ss.game_over and ss.result:
        kind, term = ss.result
        head = {"win": t("res_win"), "loss": t("res_loss"), "draw": t("res_draw")}[kind]
        if ss.elo_msg == "unrated":
            elo_line = t("unrated_msg")
        elif ss.elo_msg:
            delta, new_elo = ss.elo_msg
            elo_line = f"{t('elo_change')}: <b>{delta:+d}</b> · {t('new_rating')}: <b>{new_elo}</b>"
        else:
            elo_line = ""
        st.markdown(
            f'<div class="game-over-banner"><h2>{head}</h2><p>{tr_term(term)}</p><p>{elo_line}</p></div>',
            unsafe_allow_html=True,
        )

    bot_color = not ss.player_color
    if not in_puzzle:
        adv = material_diff(board)
        bot_adv = f" +{abs(adv)}" if (adv > 0) == (bot_color == chess.WHITE) and adv != 0 else ""
        you_adv = f" +{abs(adv)}" if (adv > 0) == (ss.player_color == chess.WHITE) and adv != 0 else ""
        cfg = BOT_CONFIGS[ss.game_difficulty]
        st.markdown(
            f'<div class="playerline">🤖 <b>{t("bot")}</b> ({t("diff_" + ss.game_difficulty)} · {cfg["elo"]}) '
            f'{captured_by(board, bot_color)}{bot_adv}</div>',
            unsafe_allow_html=True,
        )
        if show_eval_bar:
            current_cp = ss.log[-1]["cp_after"] if ss.log else 0
            st.markdown(eval_bar_html(current_cp), unsafe_allow_html=True)

    selected = ss.selected_sq if can_move else None
    targets = set()
    if selected is not None and show_legal:
        targets = {m.to_square for m in board.legal_moves if m.from_square == selected}
    last_move = board.peek() if board.move_stack else None
    rings = threat_rings(board) if (show_threats and not in_puzzle) else {}
    render_board(board, orientation, THEMES[theme_name], selected, targets, last_move, ss.hint_uci, rings)

    if not in_puzzle:
        st.markdown(
            f'<div class="playerline">👤 <b>{t("you")}</b> {captured_by(board, ss.player_color)}{you_adv}</div>',
            unsafe_allow_html=True,
        )
        if not ss.game_over:
            st.caption(("⚠️ " + t("check")) if board.is_check() else t("your_turn"))
        if not ss.rated and not ss.game_over:
            st.caption("ℹ️ " + t("unrated_note"))

    if ss.pending_promo:
        st.markdown(f"**{t('promote_to')}:**")
        promo_cols = st.columns(4)
        for pc, (ptype, glyph) in zip(promo_cols, [(chess.QUEEN, "♛"), (chess.ROOK, "♜"),
                                                  (chess.BISHOP, "♝"), (chess.KNIGHT, "♞")]):
            pc.button(glyph, key=f"promo_{ptype}", on_click=on_promote, args=(ptype,), width="stretch")

    if in_puzzle:
        p1, p2 = st.columns(2)
        p1.button("👁️ " + t("puzzle_giveup"), key="btn_giveup", on_click=on_giveup_puzzle,
                  width="stretch", disabled=ss.puzzle["done"])
        p2.button("↩️ " + t("puzzle_exit"), key="btn_exit", on_click=on_exit_puzzle, width="stretch")
    else:
        a1, a2, a3 = st.columns(3)
        a1.button("💡 " + t("hint"), key="btn_hint", on_click=on_hint, width="stretch", disabled=not can_move)
        a2.button("↩️ " + t("undo"), key="btn_undo", on_click=on_undo, width="stretch",
                  help=t("undo_help"), disabled=not ss.board.move_stack)
        a3.button("🏳️ " + t("resign"), key="btn_resign", on_click=on_resign, width="stretch",
                  disabled=ss.game_over or not ss.board.move_stack)

# ---------------- Dashboard column ----------------
with col_dash:
    with st.container(key="panel"):
        tab_review, tab_puzzles, tab_coach, tab_opening, tab_history = st.tabs([
            "📊 " + t("tab_review"), "🧩 " + t("tab_puzzles"), "👑 " + t("tab_coach"),
            "📖 " + t("tab_opening"), "📜 " + t("tab_history"),
        ])

        # ----- Review -----
        with tab_review:
            player_recs = [(i, r) for i, r in enumerate(ss.log) if r["by_player"]]
            if player_recs:
                accuracy = sum(r["acc"] for _, r in player_recs) / len(player_recs)
                st.metric(t("accuracy"), f"{accuracy:.1f}%")
                counts = Counter(r["cat"] for _, r in player_recs)
                c1, c2 = st.columns(2)
                for i, cat in enumerate(CATEGORIES):
                    (c1 if i < 3 else c2).write(f"{CAT_ICON[cat]} **{t('cat_' + cat)}:** {counts.get(cat, 0)}")

                worst = sorted([(i, r) for i, r in player_recs if r["cat"] in ("Inaccuracy", "Mistake", "Blunder")],
                               key=lambda x: x[1]["loss"], reverse=True)[:3]
                if worst:
                    st.markdown(f"**{t('key_moments')}**")
                    for i, r in worst:
                        num = f"{i // 2 + 1}{'.' if i % 2 == 0 else '...'}"
                        better = f" → {t('better_was')} **{r['best_san']}**" if r["best_san"] else ""
                        st.write(f"{CAT_ICON[r['cat']]} {num} {r['san']} ({t('cat_' + r['cat'])}){better}")
            else:
                st.info(t("no_moves"))

            st.markdown("---")
            st.subheader("📈 " + t("eval_graph"))
            if ss.log:
                chart = pd.DataFrame({
                    "Move": list(range(1, len(ss.log) + 1)),
                    "Evaluation": [max(-10.0, min(10.0, r["cp_after"] / 100)) for r in ss.log],
                })
                st.line_chart(chart.set_index("Move"))

        # ----- Puzzles -----
        with tab_puzzles:
            st.subheader("🧩 " + t("puzzle_title"))
            if ss.puzzles:
                solved = sum(1 for p in ss.puzzles if p["solved"])
                st.write(f"**{len(ss.puzzles)}** {t('puzzle_count')} · **{solved}** {t('puzzle_solved')}")
                st.selectbox(
                    t("puzzle_pick"), list(range(len(ss.puzzles))), key="puzzle_pick",
                    format_func=lambda i: f"#{i + 1} · {ss.puzzles[i]['move_no']}. {ss.puzzles[i]['played_san']}"
                                          f" {'✅' if ss.puzzles[i]['solved'] else '🧩'}",
                )
                st.button("▶️ " + t("puzzle_start"), key="btn_puzzle_start", on_click=on_start_puzzle,
                          width="stretch")
            else:
                st.info(t("puzzle_none"))

        # ----- Coach -----
        with tab_coach:
            persona = ss.get("persona", next(iter(PERSONAS)))
            st.markdown(
                f'<div class="coach-box"><b>👑 {persona}:</b> {PERSONAS[persona]["intro"]}</div>',
                unsafe_allow_html=True,
            )
            fb = ss.feedback
            if fb:
                text = (f"**{CAT_ICON[fb['cat']]} {t('cat_' + fb['cat'])} — {fb['san']}**  \n"
                        f"*\"{fb['quote']}\"*")
                getattr(st, CAT_ALERT[fb["cat"]])(text)
            if ss.explanation:
                st.warning(f"**{t('tactical_warning')}:** {ss.explanation}")
            if ss.hint_san and not in_puzzle:
                st.info(f"**{t('recommended')}:** {ss.hint_san}")

        # ----- Opening -----
        with tab_opening:
            st.subheader("📖 " + t("tab_opening"))
            game_board = ss.board
            name, master_moves = local_opening_name(game_board), []
            if len(game_board.move_stack) <= 24 and time.time() >= ss.get("opening_retry_at", 0):
                try:
                    lichess_name, master_moves = fetch_lichess_opening(game_board.fen())
                    name = lichess_name or name
                except Exception:
                    master_moves = []
                    ss.opening_retry_at = time.time() + 300  # back off for 5 minutes
            st.info(f"**{t('opening_id')}:** {name or '—'}")
            if master_moves:
                st.markdown(f"**{t('top_master')}:**")
                st.dataframe(
                    pd.DataFrame([
                        {t("col_move"): m["san"], t("col_white_wins"): m["white"],
                         t("col_draws"): m["draws"], t("col_black_wins"): m["black"]}
                        for m in master_moves[:5]
                    ]),
                    width="stretch", hide_index=True,
                )

        # ----- History -----
        with tab_history:
            if ss.log:
                tag = lambda r: f"{r['san']} {CAT_ICON[r['cat']]}"
                rows = []
                for i in range(0, len(ss.log), 2):
                    rows.append({
                        "#": i // 2 + 1,
                        t("white"): tag(ss.log[i]),
                        t("black"): tag(ss.log[i + 1]) if i + 1 < len(ss.log) else "",
                    })
                st.dataframe(rows, width="stretch", hide_index=True)
            else:
                st.info(t("no_moves"))