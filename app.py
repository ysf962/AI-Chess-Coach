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

# Square colors only — piece artwork (see PIECE_DATA_URI below) is the same
# hand-drawn ivory/bronze set on every theme, so themes just set the board.
THEMES = {
    "Classic Wood": {"light": "#f0d9b5", "dark": "#b58863"},
    "Lichess Green": {"light": "#ffffdd", "dark": "#86a666"},
    "Midnight Dark": {"light": "#9e9e9e", "dark": "#424242"},
    "Neon Cyber": {"light": "#2a2d37", "dark": "#00adb5"},
    "Old Money": {"light": "#e4d9bd", "dark": "#5c4430"},
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

# ---------- Real piece artwork ----------
# Cropped directly from a photo the user supplied of their preferred piece set
# (background removed, trimmed, and centered on a uniform square canvas so the
# existing percentage-based CSS sizing in board_css works unchanged). Each value
# is a self-contained base64 PNG data URI — no external image files.
PIECE_DATA_URI = {
    (chess.KING, chess.WHITE): "data:image/png;base64,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",
    (chess.KING, chess.BLACK): "data:image/png;base64,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",
    (chess.QUEEN, chess.WHITE): "data:image/png;base64,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",
    (chess.QUEEN, chess.BLACK): "data:image/png;base64,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",
    (chess.ROOK, chess.WHITE): "data:image/png;base64,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",
    (chess.ROOK, chess.BLACK): "data:image/png;base64,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",
    (chess.BISHOP, chess.WHITE): "data:image/png;base64,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",
    (chess.BISHOP, chess.BLACK): "data:image/png;base64,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",
    (chess.KNIGHT, chess.WHITE): "data:image/png;base64,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",
    (chess.KNIGHT, chess.BLACK): "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAIwAAACMCAMAAACZHrEMAAAAn1BMVEUAAABWU1JIRUUoKCg5NzZ3dHRraWgkIyJAPj4TEhEmJSUYFxcbGxoeHh4dHR1gXl0kIyIODg4lIyAiIB1CQD8yMC5iYF4REA4gHhwgIB8gHh4gHh4hHx8iIB0fHyAgHx4gHyAgIB6AfXwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACPz6FjAAAAKHRSTlMA/fz4+v79svsvz1Bw/Yz9lSJ1afvX/hxZkW6XpVue+577/wAAAAAAhwpLZAAABoxJREFUeNrtnNt2ozoMhostMDZsQtq0087MPr7/Q258AnOKJWyaXlQXnTVrmuTLL1mSZTNPT3ST3Jh8+grWWpj2K7AIy8KVeDxLN3CwgsHwR/cVdIGqrJgW59HaqIHlrSzLotY0nXy0MmxgqSrjKN4/FKbn/FJqGhs2XFwfxyIVryujTOFoPh7G8j6EDPMwlgYeFsU9cChGGEfzqLgZki/YkDEwPm6+Boyj6Rptn73MOxcyI4yj0QZKfjaLgyk9TMHqEUe1Xdf2L5/D8lN//6KcKTOjMQLx5pOW0iTMBFOwwQACIjHYyS57DljKgMUDAQRE8NfTj7N1uTmW8lIUa5zBggA6Mf8YXeqiXDlpjTQkRtcLNs2ZLFWExSvk/QVn0HSG5WILwV2WKYAsTnNG4uW2Wq9Dd1+dc2h6Lfgi88ZxaidO3+dc5tdpTWNZ5uLkrBNXRWdxOG6l56ORzfB2BZllTM1ZacTkpKKg07CsNIpPbW/wMQQajZOpWAnnpHKR+RmNRmXYRjRC6R3krIOxUQkonKzaiOF9ipmXWO0rM5FG5Uh49UyYqc8caIieStVm7HovKxaKNM5T1zwwG8IgYTxN+gpvhO16x63JAZiQJiWKdbm+XcKlFDbfuJiZ0YBKg9n1EmeMlIrrxCXV+L2Jhwm2JYAWJpQmwU/NohToVVFbA8aoMIZGHe22ru0QF7MkQyHYpjk6QpG6kXmr6L3DLkx9fEYqeTgaygGjpRHNURg3GiqKTDQmER+ZrTf9OI3JBmNiuDnmpPm6xnwiZkHRYf40ac2wXAjfHiON6o40MtZJJcUTURijjaSXa6D14XgYavFuBHVPEGuMQ2VaSa2Qs94hH4wub/BKjt6KuJIixSKUhhNWNfipA5UFoYyNGkKB5OTcS4QRpM6B0wIGAXNwPfnddUXWBQmjQ/gZv5LM+I7AAkCAIbQ1esZqaxKBhUN8/z2D4f+g6wDRSRq/JsLg6tNvn2GwHaZNHIYGGVjYhu+qpw6F0YXEwq2j8DAtbiWZ+kjyERUGl2l0C86PsXAAEky8F5ZuJeH7KXss2GK23guYaKaRh1iEuyKBFsamvZ8Rls4GzBuN5er6QjyMSQZNNHpvQ+qtcH2cUxt0mVE0mDpaEJrOOQnXrtg9ENid/CtEJyQrN909WXVHBBWqEvrhz6v0w2IKDMPAxITxOKuJoYap8SHDohtL2Bdm2p26GgSLO2CKFr9xGOOlGAsEh7RyfuGI4CUUzO3OG920G/Xq2TgNbeJDNTrMzrcLDrK8tctrCbGhGjVmYB9mOj9X8ioHmx3tYqaNRBix63ivi1JCtRvHzKD7VAIKAkY2OzT+eG94tVxfKngx/8Yyw9hmZk0zTrc3J/8oliMw5t7AisZluF/7VwHILBiY53HazFbCbE+T3w1ntEE9AvPUgDJVBm5jFfIs+1cB4izHYJ6kOTj2TSQbT962L3EeZwF8S+55pjqUVxeTzXETWCk7v/twhQj4/nUNxIZmDYPp9Lz9UNCrMPn/2mMB2lgA38+sdgpjOVp/h3fRW12OOAnT6a0/sPv46Lu2X+9E5StgWbZh8t0BGDKA3V0XB52kYXJdQJevhBPKLZY635MCThfKOfIGzO88LBRd9mGyuEkC/Uh7M34zsLyodJaUo8r51R5Apt37LMcPcZeVi3jSvwWT5QkBKZJ9RJ2Q3z9sYWlOop4d3Bvj87pIc5Lp7kUmlsSAsVVSZYFJ1sUu7DwwyboYL6k++S6Y0mPwZGUgR5K5UjLMfS/x9LVEcFIEJvmOnGwpwpwMo3J5KRPMHsv2mqn3QwZkeoWsw5P04fNGgzs2/lLwlITIAGPfbD5kxNv0suQmTx/+BAh//0Gx8BmfDLf/W57RkmCklGIteM1QtvTpv3qkIQ8/4iMXHC6EK2PlPdO/cAmfOJqe8TlaHtU0rzHrqEJglOV/IZF9viV86OjgYxrcdTFVGScoo0KVlbs4S2+vZP8hzKb6koYxZ7IneKJ/JrrIjj/f5t9vJn/EvJzVAofTE7Ftp6ql1lMYhD+GUL0s/v4WYs1xyJfSrh33Dx3MGC7aCNcXL2suQ9NeaWvaXjAaXkv58PtkxUQjaL0dGz2Sch14cfxr35PR7oGR2ikSl/lJyX0v4mQYILhJl1h2CoxDuhEe7VFnCeNhasJ/uyFOhikouxaBHIAfNxpM/Q2z14J/w3zDfMNkSnrsTKMqA8EFnuzGiMpw4OeZfW8CzPn2VWH+B1AZbHpCslveAAAAAElFTkSuQmCC",
    (chess.PAWN, chess.WHITE): "data:image/png;base64,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",
    (chess.PAWN, chess.BLACK): "data:image/png;base64,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",
}



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

        # Translucent tints (check glow, selection, last move, hint) — painted
        # *under* the piece artwork so the piece stays crisp on top of them.
        tints = []
        if sq == check_sq:
            tints.append(CHECK_GRADIENT)
        if selected == sq:
            tints.append(tint(TINT_SELECT))
        if last_move and sq in (last_move.from_square, last_move.to_square):
            tints.append(tint(TINT_LAST))
        if hint and sq in (hint.from_square, hint.to_square):
            tints.append(tint(TINT_HINT))

        shadows = []
        if sq in rings:
            shadows.append(f"inset 0 0 0 3px {rings[sq]}")
        if sq in targets and piece:
            shadows.append("inset 0 0 0 4px rgba(224,67,58,.95)")
        box_shadow = ", ".join(shadows) if shadows else "none"

        # The piece itself is now real vector artwork (see PIECE_DATA_URI), not
        # styled text, so the button's own text is only ever the empty-square
        # dot or (for pieces) an invisible accessibility label.
        images, sizes, positions, repeats = [], [], [], []
        if piece:
            images.append(f"url('{PIECE_DATA_URI[(piece.piece_type, piece.color)]}')")
            sizes.append("86% 86%")
            positions.append("center")
            repeats.append("no-repeat")
        for t in tints:
            images.append(t)
            sizes.append("100% 100%")
            positions.append("center")
            repeats.append("no-repeat")
        if not images:
            images, sizes, positions, repeats = ["none"], ["auto"], ["0 0"], ["no-repeat"]

        fg = "rgba(46,139,255,.9)" if (sq in targets and not piece) else "transparent"

        sel = f".st-key-sq_{name} button"
        out.append(
            f"{sel}, {sel}:hover, {sel}:focus, {sel}:active {{ "
            f"background-color:{base} !important; "
            f"background-image:{', '.join(images)} !important; "
            f"background-size:{', '.join(sizes)} !important; "
            f"background-position:{', '.join(positions)} !important; "
            f"background-repeat:{', '.join(repeats)} !important; "
            f"color:{fg} !important; text-shadow:none !important; box-shadow:{box_shadow} !important; "
            f"outline:none !important; }}"
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