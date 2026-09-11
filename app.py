import streamlit as st
import chess
import chess.svg
import chess.pgn
import chess.engine
import random
import requests
import pandas as pd

# ==========================================
# 1. PAGE CONFIG & STYLES
# ==========================================
st.set_page_config(page_title="AI Chess Coach Pro", layout="wide", page_icon="♟️")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: bold; }
    .move-card {
        background-color: #161b22;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #30363d;
        margin-top: 15px;
    }
    .coach-box {
        background-color: #1f242d;
        border-left: 5px solid #00c853;
        padding: 15px;
        border-radius: 8px;
        margin-bottom: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. SESSION STATE INITIALIZATION
# ==========================================
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "last_move" not in st.session_state:
    st.session_state.last_move = None
if "move_history" not in st.session_state:
    st.session_state.move_history = []
if "eval_score" not in st.session_state:
    st.session_state.eval_score = 0.0
if "coach_analysis" not in st.session_state:
    st.session_state.coach_analysis = None
if "last_move_feedback" not in st.session_state:
    st.session_state.last_move_feedback = None
if "last_explanation" not in st.session_state:
    st.session_state.last_explanation = ""
if "player_color" not in st.session_state:
    st.session_state.player_color = chess.WHITE
if "difficulty" not in st.session_state:
    st.session_state.difficulty = "Medium"
if "lang" not in st.session_state:
    st.session_state.lang = "EN"
if "user_elo" not in st.session_state:
    st.session_state.user_elo = 800
if "unlocked_badges" not in st.session_state:
    st.session_state.unlocked_badges = set()
if "blunder_puzzles" not in st.session_state:
    st.session_state.blunder_puzzles = []
if "game_over" not in st.session_state:
    st.session_state.game_over = False
if "move_eval_history" not in st.session_state:
    st.session_state.move_eval_history = []
if "eval_chart_data" not in st.session_state:
    st.session_state.eval_chart_data = []

# ==========================================
# 3. CONSTANTS & DATA TABLES
# ==========================================
OPENINGS_DB = {
    "e2e4 e7e5": "King's Pawn Game",
    "e2e4 e7e5 g1f3 b8c6 f1c4": "Italian Game",
    "e2e4 e7e5 g1f3 b8c6 f1b5": "Ruy Lopez",
    "e2e4 c7c5": "Sicilian Defense",
    "d2d4 d7d5": "Queen's Pawn Game",
    "d2d4 d7d5 c2c4": "Queen's Gambit",
    "c2c4": "English Opening",
    "g1f3": "Réti Opening"
}

PIECE_VALUES = {
    chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
    chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 20000
}

PIECE_SYMBOLS = {
    (chess.PAWN, chess.WHITE): "♙", (chess.KNIGHT, chess.WHITE): "♘", (chess.BISHOP, chess.WHITE): "♗", 
    (chess.ROOK, chess.WHITE): "♖", (chess.QUEEN, chess.WHITE): "♕", (chess.KING, chess.WHITE): "♔",
    (chess.PAWN, chess.BLACK): "♟", (chess.KNIGHT, chess.BLACK): "♞", (chess.BISHOP, chess.BLACK): "♝", 
    (chess.ROOK, chess.BLACK): "♜", (chess.QUEEN, chess.BLACK): "♛", (chess.KING, chess.BLACK): "♚"
}

STARTING_PIECES = {chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 2, chess.QUEEN: 1}

PAWN_TABLE = [
    0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0
]

KNIGHT_TABLE = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50
]

COACH_QUOTES = {
    "Brilliant": [
        "Now that's a move I'd play! Great tactical vision.",
        "Precision execution. You're pressing the advantage like a champion.",
        "Fantastic piece coordination. Keep squeezing!"
    ],
    "Best": [
        "Solid, precise, and logical. Exactly what the position requires.",
        "Good move. You're keeping control of the board.",
        "Simple, clean chess. Don't give them any counterplay."
    ],
    "Good": [
        "Playable, but there was a slightly cleaner line available.",
        "Not bad, but you need to build more pressure.",
        "Decent move. Keep your pieces active."
    ],
    "Inaccuracy": [
        "A bit careless. You're giving away slight initiative.",
        "Hmm, you had better options. Look for more energetic squares.",
        "That allows them a comfortable defense. Stay sharper."
    ],
    "Mistake": [
        "That's a clear mistake. You just handed them control.",
        "Why give up activity like that? Always look at their dynamic threats.",
        "Not precise. You're making life much harder than it needs to be."
    ],
    "Blunder": [
        "That's a blunder! Completely unforced error.",
        "What was that? You just dropped serious material or evaluation.",
        "Huge tactical oversight! In high-level chess, that loses instantly."
    ]
}

THEMES = {
    "Classic Wood": {"square_light": "#f0d9b5", "square_dark": "#b58863"},
    "Lichess Green": {"square_light": "#ffffdd", "square_dark": "#86a666"},
    "Midnight Dark": {"square_light": "#9e9e9e", "square_dark": "#424242"},
    "Neon Cyber": {"square_light": "#2a2d37", "square_dark": "#00adb5"}
}

BOT_CONFIGS = {
    "Easy": {"elo": 400, "depth": 1, "skill_level": 0, "time_limit": 0.05, "random_chance": 0.60},
    "Medium": {"elo": 800, "depth": 3, "skill_level": 3, "time_limit": 0.1, "random_chance": 0.20},
    "Hard": {"elo": 1200, "depth": 6, "skill_level": 8, "time_limit": 0.2, "random_chance": 0.05},
    "Grandmaster": {"elo": 1750, "depth": 12, "skill_level": 14, "time_limit": 0.4, "random_chance": 0.0}
}

# ==========================================
# 4. AUDIO CONTROLLER
# ==========================================
def play_sound(sound_type, enabled):
    if not enabled:
        return
    sound_urls = {
        "move": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/move-self.mp3",
        "capture": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/capture.mp3",
        "game_over": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/game-end.mp3"
    }
    url = sound_urls.get(sound_type)
    if url:
        st.components.v1.html(
            f"""
            <audio id="chess-sound" autoplay>
                <source src="{url}" type="audio/mp3">
            </audio>
            <script>
                var audio = document.getElementById('chess-sound');
                if (audio) {{
                    audio.volume = 1.0;
                    audio.play().catch(function(e) {{ console.log("Audio blocked:", e); }});
                }}
            </script>
            """,
            height=0,
            width=0
        )

# ==========================================
# 5. ENGINES & EVALUATION
# ==========================================
@st.cache_resource
def get_stockfish():
    paths = ["/usr/games/stockfish", "/usr/bin/stockfish", "stockfish"]
    for p in paths:
        try:
            return chess.engine.SimpleEngine.popen_uci(p)
        except Exception:
            continue
    return None

def evaluate_board_custom(board):
    if board.is_checkmate():
        return -9999 if board.turn == chess.WHITE else 9999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0

    score = 0
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            val = PIECE_VALUES[piece.piece_type]
            pos_bonus = 0
            if piece.piece_type == chess.PAWN:
                pos_bonus = PAWN_TABLE[sq if piece.color == chess.WHITE else chess.square_mirror(sq)]
            elif piece.piece_type == chess.KNIGHT:
                pos_bonus = KNIGHT_TABLE[sq if piece.color == chess.WHITE else chess.square_mirror(sq)]

            total = val + pos_bonus
            score += total if piece.color == chess.WHITE else -total
    return score / 100.0

def evaluate_position(board):
    engine = get_stockfish()
    if engine:
        try:
            info = engine.analyse(board, chess.engine.Limit(time=0.1, depth=10))
            score = info["score"].relative.score(mate_score=10000)
            pv = info.get("pv", [])
            best_move = pv[0] if pv else None
            cp = score / 100.0 if score is not None else 0.0
            return best_move, cp
        except Exception:
            pass
    return None, evaluate_board_custom(board)

def minimax(board, depth, alpha, beta, maximizing):
    if depth == 0 or board.is_game_over():
        return evaluate_board_custom(board), None

    best_move = None
    legal_moves = list(board.legal_moves)

    if maximizing:
        max_eval = -float('inf')
        for move in legal_moves:
            board.push(move)
            eval_val, _ = minimax(board, depth - 1, alpha, beta, False)
            board.pop()
            if eval_val > max_eval:
                max_eval = eval_val
                best_move = move
            alpha = max(alpha, eval_val)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        min_eval = float('inf')
        for move in legal_moves:
            board.push(move)
            eval_val, _ = minimax(board, depth - 1, alpha, beta, True)
            board.pop()
            if eval_val < min_eval:
                min_eval = eval_val
                best_move = move
            beta = min(beta, eval_val)
            if beta <= alpha:
                break
        return min_eval, best_move

def get_bot_move(board, difficulty):
    config = BOT_CONFIGS.get(difficulty, BOT_CONFIGS["Medium"])
    engine = get_stockfish()

    if engine:
        try:
            engine.configure({
                "UCI_LimitStrength": True,
                "UCI_Elo": config["elo"]
            })
            info = engine.analyse(
                board, 
                chess.engine.Limit(time=config["time_limit"], depth=config["depth"])
            )
            pv = info.get("pv", [])
            if pv:
                return pv[0]
        except Exception:
            pass

    is_max = (board.turn == chess.WHITE)
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None

    if random.random() < config["random_chance"]:
        return random.choice(legal_moves)

    _, move = minimax(board, depth=min(config["depth"], 4), alpha=-10000, beta=10000, maximizing=is_max)
    return move or random.choice(legal_moves)

def get_captured(board):
    w_cap, b_cap = [], []
    for p_type, count in STARTING_PIECES.items():
        b_took = count - len(board.pieces(p_type, chess.WHITE))
        for _ in range(b_took):
            b_cap.append(PIECE_SYMBOLS[(p_type, chess.WHITE)])
        w_took = count - len(board.pieces(p_type, chess.BLACK))
        for _ in range(w_took):
            w_cap.append(PIECE_SYMBOLS[(p_type, chess.BLACK)])
    return {"white": "".join(w_cap), "black": "".join(b_cap)}

# ==========================================
# 6. OVERLAYS, ANALYSIS & BADGES
# ==========================================
def get_threat_and_guard_fill(board):
    fill_dict = {}
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            is_attacked = board.is_attacked_by(not piece.color, sq)
            is_defended = board.is_attacked_by(piece.color, sq)

            if is_attacked and not is_defended:
                fill_dict[sq] = "#ff4d4d88"
            elif is_attacked and is_defended:
                fill_dict[sq] = "#ffa50088"
            elif is_defended and piece.color == board.turn:
                fill_dict[sq] = "#4da6ff44"
    return fill_dict

def analyze_blunder(board_before, move, board_after):
    reasons = []
    moving_piece = board_before.piece_at(move.from_square)
    dest_sq = move.to_square

    if board_after.is_attacked_by(board_after.turn, dest_sq):
        if not board_after.is_attacked_by(not board_after.turn, dest_sq):
            reasons.append(f"Leaves your **{chess.piece_name(moving_piece.piece_type).title()}** undefended on {chess.square_name(dest_sq)}.")

    valuable_targets = 0
    for target_sq in chess.SQUARES:
        p = board_after.piece_at(target_sq)
        if p and p.color == board_before.turn and board_after.is_attacked_by(not board_after.turn, target_sq):
            if p.piece_type in [chess.KING, chess.ROOK, chess.QUEEN]:
                valuable_targets += 1
    if valuable_targets >= 2:
        reasons.append("Allows a fork targeting multiple high-value pieces.")

    if not reasons:
        reasons.append("Loss of positional control or tactical superiority.")
    return " ".join(reasons)

def analyze_move_quality(board_before, move, is_white_player):
    eval_before = evaluate_board_custom(board_before)
    _, best_move = minimax(board_before, depth=2, alpha=-10000, beta=10000, maximizing=is_white_player)
    
    board_before.push(move)
    eval_after = evaluate_board_custom(board_before)
    board_before.pop()

    score_change = (eval_after - eval_before) if is_white_player else (eval_before - eval_after)
    is_sacrifice = board_before.is_capture(move) and PIECE_VALUES.get(board_before.piece_at(move.from_square).piece_type, 0) > 300

    if move == best_move and is_sacrifice:
        cat = "Brilliant"
        alert = "success"
    elif move == best_move:
        cat = "Best"
        alert = "success"
    elif score_change >= -0.3:
        cat = "Good"
        alert = "info"
    elif score_change >= -1.0:
        cat = "Inaccuracy"
        alert = "warning"
    elif score_change >= -2.5:
        cat = "Mistake"
        alert = "warning"
    else:
        cat = "Blunder"
        alert = "error"

    quote = random.choice(COACH_QUOTES[cat])
    return cat, f"**{cat} Move!** — *\"{quote}\"*", alert

def update_elo(user_won, difficulty):
    bot_elo = BOT_CONFIGS.get(difficulty, BOT_CONFIGS["Medium"])["elo"]
    expected = 1 / (1 + 10 ** ((bot_elo - st.session_state.user_elo) / 400))
    actual = 1.0 if user_won else 0.0
    st.session_state.user_elo += int(32 * (actual - expected))

def check_achievements(board, move):
    if board.is_checkmate():
        piece = board.piece_at(move.to_square)
        if piece and piece.piece_type == chess.PAWN:
            st.session_state.unlocked_badges.add("♟️ Checkmate with a Pawn")

    from_piece = board.piece_at(move.from_square)
    to_piece = board.piece_at(move.to_square)

    if from_piece and to_piece:
        if PIECE_VALUES.get(from_piece.piece_type, 0) > PIECE_VALUES.get(to_piece.piece_type, 0):
            st.session_state.unlocked_badges.add("⚔️ First Sacrifice")

    if st.session_state.eval_score > 3.0:
        st.session_state.unlocked_badges.add("🛡️ Flawless Defense")

def fetch_lichess_opening(fen):
    try:
        res = requests.get(f"https://explorer.lichess.ovh/masters?fen={fen}", timeout=2)
        if res.status_code == 200:
            data = res.json()
            opening = data.get("opening", {})
            name = opening.get("name", "Unknown Position")
            moves = data.get("moves", [])
            return name, moves
    except Exception:
        pass
    return None, []

# SAFE UNDO TURN IMPLEMENTATION
def undo_last_turn():
    board = st.session_state.board
    
    # Determine how many moves to undo based on move stack
    moves_to_undo = 0
    if len(board.move_stack) >= 2:
        moves_to_undo = 2
    elif len(board.move_stack) == 1:
        moves_to_undo = 1

    for _ in range(moves_to_undo):
        board.pop()
        if st.session_state.move_history:
            st.session_state.move_history.pop()
        if st.session_state.move_eval_history:
            st.session_state.move_eval_history.pop()
        if st.session_state.eval_chart_data:
            st.session_state.eval_chart_data.pop()

    st.session_state.last_move = board.peek() if board.move_stack else None
    st.session_state.last_move_feedback = None
    st.session_state.coach_analysis = None
    st.session_state.last_explanation = ""
    st.session_state.game_over = False
    st.rerun()

# ==========================================
# 7. SIDEBAR CONTROLS
# ==========================================
st.sidebar.title("🎮 Controls & Settings")

st.session_state.lang = st.sidebar.radio("🌐 Language / اللغة", ["EN", "AR"], index=0 if st.session_state.lang == "EN" else 1)
audio_enabled = st.sidebar.toggle("🔊 Enable Audio", value=True)

st.session_state.difficulty = st.sidebar.selectbox("🎯 Bot Difficulty", ["Easy", "Medium", "Hard", "Grandmaster"], index=1)
coach_persona = st.sidebar.selectbox("🤖 AI Coach Persona", [
    "Grandmaster Magnus (Analytical)",
    "Coach Sparky (Encouraging)",
    "Tactical Master (Aggressive)"
])

chosen_side = st.sidebar.radio("♟️ Choose Side", ["White", "Black"])
new_color = chess.WHITE if chosen_side == "White" else chess.BLACK

if new_color != st.session_state.player_color:
    st.session_state.player_color = new_color
    st.session_state.board = chess.Board()
    st.session_state.last_move = None
    st.session_state.move_history = []
    st.session_state.coach_analysis = None
    st.session_state.last_move_feedback = None
    st.session_state.move_eval_history = []
    st.session_state.eval_chart_data = []
    st.session_state.game_over = False
    if st.session_state.player_color == chess.BLACK:
        ai_m = get_bot_move(st.session_state.board, st.session_state.difficulty)
        if ai_m:
            st.session_state.board.push(ai_m)
            st.session_state.last_move = ai_m
            st.session_state.move_history.append(ai_m)
    st.rerun()

theme_choice = st.sidebar.selectbox("🎨 Board Theme", ["Classic Wood", "Lichess Green", "Midnight Dark", "Neon Cyber"])

st.sidebar.markdown("---")
st.sidebar.subheader("🎨 Board Overlays")
show_threats = st.sidebar.checkbox("Threat & Guard Indicators", value=True)
show_eval_bar = st.sidebar.checkbox("Live Evaluation Bar", value=True)

st.sidebar.markdown("---")
st.sidebar.subheader("🏆 Player Stats")
st.sidebar.metric("Your Rating (ELO)", st.session_state.user_elo)

if st.session_state.unlocked_badges:
    st.sidebar.markdown("**Badges Unlocked:**")
    for badge in st.session_state.unlocked_badges:
        st.sidebar.caption(badge)

c_undo, c_reset = st.sidebar.columns(2)
with c_undo:
    if st.button("↩️ Undo", width="stretch"):
        undo_last_turn()

with c_reset:
    if st.button("🔄 Reset", width="stretch"):
        st.session_state.board = chess.Board()
        st.session_state.last_move = None
        st.session_state.move_history = []
        st.session_state.eval_score = 0.0
        st.session_state.coach_analysis = None
        st.session_state.last_move_feedback = None
        st.session_state.last_explanation = ""
        st.session_state.move_eval_history = []
        st.session_state.eval_chart_data = []
        st.session_state.game_over = False
        if st.session_state.player_color == chess.BLACK:
            ai_m = get_bot_move(st.session_state.board, st.session_state.difficulty)
            if ai_m:
                st.session_state.board.push(ai_m)
                st.session_state.last_move = ai_m
                st.session_state.move_history.append(ai_m)
        st.rerun()

st.sidebar.markdown("---")
pgn_game = chess.pgn.Game.from_board(st.session_state.board)
st.sidebar.download_button("📥 Export PGN", data=str(pgn_game), file_name="chess_match.pgn", mime="text/plain", width="stretch")

# ==========================================
# 8. MAIN DASHBOARD LAYOUT
# ==========================================
is_ar = st.session_state.lang == "AR"

col_board, col_dash = st.columns([1.3, 1])
board = st.session_state.board
player_turn = (board.turn == st.session_state.player_color)

with col_board:
    mat = get_captured(board)
    top_captures = mat['white'] if st.session_state.player_color == chess.BLACK else mat['black']
    bottom_captures = mat['black'] if st.session_state.player_color == chess.BLACK else mat['white']

    bot_elo_display = BOT_CONFIGS.get(st.session_state.difficulty, BOT_CONFIGS["Medium"])["elo"]
    st.markdown(f"**🤖 Bot ({st.session_state.difficulty} - {bot_elo_display} ELO):** {top_captures}")

    theme_colors = THEMES[theme_choice]
    fill_colors = get_threat_and_guard_fill(board) if show_threats else {}

    board_svg = chess.svg.board(
        board=board,
        orientation=st.session_state.player_color,
        lastmove=st.session_state.last_move,
        fill=fill_colors,
        colors={"square light": theme_colors["square_light"], "square dark": theme_colors["square_dark"]},
        size=420
    )

    if show_eval_bar:
        c1, c2 = st.columns([1, 8])
        with c1:
            eval_val = max(-10.0, min(10.0, st.session_state.eval_score))
            white_pct = int(((eval_val + 10) / 20) * 100)
            st.markdown(
                f"""
                <div style="background-color: #333; height: 320px; width: 22px; border-radius: 5px; display: flex; flex-direction: column-reverse; overflow: hidden; border: 1px solid #555;">
                    <div style="background-color: #fff; height: {white_pct}%; width: 100%;"></div>
                </div>
                <p style="text-align: center; font-size: 11px; margin-top: 4px;">{st.session_state.eval_score:+.1f}</p>
                """,
                unsafe_allow_html=True
            )
        with c2:
            st.image(board_svg, width="content")
    else:
        st.image(board_svg, width="content")

    st.markdown(f"**👤 {'أنت' if is_ar else 'You'}:** {bottom_captures}")

    if player_turn and not board.is_game_over():
        legal_moves = list(board.legal_moves)
        from_squares = sorted(list(set(m.from_square for m in legal_moves)))
        from_square_names = [chess.square_name(sq) for sq in from_squares]

        if from_square_names:
            st.markdown('<div class="move-card">', unsafe_allow_html=True)
            st.subheader("🎯 " + ("إجراء حركة" if is_ar else "Make Your Move"))
            
            c1, c2 = st.columns(2)
            with c1:
                selected_from = st.selectbox("1. " + ("اختر القطعة" if is_ar else "Select Piece"), from_square_names)
            
            from_sq_idx = chess.parse_square(selected_from)
            to_squares = sorted([m.to_square for m in legal_moves if m.from_square == from_sq_idx])
            to_square_names = [chess.square_name(sq) for sq in to_squares]

            with c2:
                selected_to = st.selectbox("2. " + ("اختر المربع" if is_ar else "Select Target Square"), to_square_names)

            if st.button("🚀 " + ("تحريك القطعة" if is_ar else "Play Move"), width="stretch"):
                move_uci = f"{selected_from}{selected_to}"
                move = chess.Move.from_uci(move_uci)
                if move not in board.legal_moves:
                    move = chess.Move.from_uci(f"{move_uci}q")

                if move in board.legal_moves:
                    pre_board = board.copy()
                    pre_eval = st.session_state.eval_score

                    cat, feedback_text, alert_type = analyze_move_quality(board, move, st.session_state.player_color == chess.WHITE)
                    st.session_state.last_move_feedback = (feedback_text, alert_type)
                    st.session_state.move_eval_history.append((board.san(move), cat))

                    sound = "capture" if board.is_capture(move) else "move"
                    board.push(move)
                    st.session_state.last_move = move
                    st.session_state.move_history.append(move)

                    _, post_eval = evaluate_position(board)
                    st.session_state.eval_score = post_eval
                    st.session_state.eval_chart_data.append(post_eval)
                    check_achievements(board, move)
                    play_sound(sound, audio_enabled)

                    if (pre_eval - post_eval) > 1.5 if st.session_state.player_color == chess.WHITE else (post_eval - pre_eval) > 1.5:
                        explanation = analyze_blunder(pre_board, move, board)
                        st.session_state.last_explanation = explanation
                        st.session_state.blunder_puzzles.append((pre_board.fen(), move))

                    if board.is_game_over():
                        st.session_state.game_over = True
                        play_sound("game_over", audio_enabled)
                        if board.is_checkmate():
                            update_elo(True, st.session_state.difficulty)
                    else:
                        bot_move = get_bot_move(board, st.session_state.difficulty)
                        if bot_move:
                            board.push(bot_move)
                            st.session_state.last_move = bot_move
                            st.session_state.move_history.append(bot_move)
                            _, bot_eval = evaluate_position(board)
                            st.session_state.eval_score = bot_eval
                            st.session_state.eval_chart_data.append(bot_eval)

                            if board.is_game_over():
                                st.session_state.game_over = True
                                play_sound("game_over", audio_enabled)
                                if board.is_checkmate():
                                    update_elo(False, st.session_state.difficulty)

                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

with col_dash:
    tab_coach, tab_review, tab_opening, tab_history = st.tabs([
        "👑 " + ("المدرب" if is_ar else "Coach"), 
        "📊 " + ("المراجعة" if is_ar else "Review"),
        "📖 " + ("الافتتاحية" if is_ar else "Opening"),
        "📜 " + ("السجل" if is_ar else "History")
    ])

    with tab_coach:
        st.markdown(f'<div class="coach-box"><b>👑 {coach_persona}:</b> "Focus on position control and structure."</div>', unsafe_allow_html=True)

        if st.session_state.last_move_feedback:
            lbl, box_style = st.session_state.last_move_feedback
            getattr(st, box_style)(lbl)

        if st.session_state.last_explanation:
            st.warning(f"**Tactical Warning:** {st.session_state.last_explanation}")

        if st.button("💡 " + ("طلب نصيحة" if is_ar else "Ask Coach Suggestion"), width="stretch"):
            if not board.is_game_over():
                rec_move, _ = evaluate_position(board)
                if not rec_move:
                    rec_is_max = (st.session_state.player_color == chess.WHITE)
                    _, rec_move = minimax(board, depth=2, alpha=-10000, beta=10000, maximizing=rec_is_max)
                
                if rec_move:
                    st.session_state.coach_analysis = board.san(rec_move)
                    st.rerun()

        if st.session_state.coach_analysis:
            st.info(f"**Recommended Move:** {st.session_state.coach_analysis}")

        if board.is_game_over():
            st.error("🏆 Game Over!")

    with tab_review:
        st.subheader("📊 Post-Match Review")
        eval_history = st.session_state.move_eval_history

        if eval_history:
            total_moves = len(eval_history)
            cats = [c for _, c in eval_history]

            brilliant_count = cats.count("Brilliant")
            best_count = cats.count("Best")
            good_count = cats.count("Good")
            inaccuracy_count = cats.count("Inaccuracy")
            mistake_count = cats.count("Mistake")
            blunder_count = cats.count("Blunder")

            quality_points = (brilliant_count * 100 + best_count * 100 + good_count * 80 + inaccuracy_count * 50 + mistake_count * 20)
            accuracy_pct = min(100, round(quality_points / (total_moves * 100) * 100, 1))

            st.metric("Player Accuracy", f"{accuracy_pct}%")

            c1, c2 = st.columns(2)
            with c1:
                st.write(f"💎 **Brilliant:** {brilliant_count}")
                st.write(f"⭐ **Best:** {best_count}")
                st.write(f"✅ **Good:** {good_count}")
            with c2:
                st.write(f"⚠️ **Inaccuracies:** {inaccuracy_count}")
                st.write(f"❌ **Mistakes:** {mistake_count}")
                st.write(f"🔴 **Blunders:** {blunder_count}")
        else:
            st.info("Play a few moves to generate match analysis!")

        st.markdown("---")
        st.subheader("📈 Evaluation Graph")
        if st.session_state.eval_chart_data:
            chart_df = pd.DataFrame({
                "Move": list(range(1, len(st.session_state.eval_chart_data) + 1)),
                "Evaluation": st.session_state.eval_chart_data
            })
            st.line_chart(chart_df.set_index("Move"))

        st.markdown("---")
        st.subheader("🧩 Blunder Puzzles")
        if st.session_state.blunder_puzzles:
            st.write(f"**{len(st.session_state.blunder_puzzles)}** saved blunder puzzle(s).")
            if st.button("Replay Last Blunder Position", width="stretch"):
                fen, bad_move = st.session_state.blunder_puzzles[-1]
                st.session_state.board = chess.Board(fen)
                st.session_state.game_over = False
                st.session_state.last_explanation = ""
                st.rerun()

    with tab_opening:
        st.subheader("📖 Opening Explorer")
        move_uci_str = " ".join([m.uci() for m in st.session_state.move_history])
        opening_name = "Custom / Standard Continuation"
        for prefix, name in OPENINGS_DB.items():
            if move_uci_str.startswith(prefix):
                opening_name = name

        lichess_name, master_moves = fetch_lichess_opening(board.fen())
        final_opening = lichess_name if lichess_name else opening_name
        st.info(f"**Identified Opening:** {final_opening}")

        if master_moves:
            st.markdown("**Top Master Moves in this Position:**")
            move_df = pd.DataFrame([
                {"Move": m["san"], "White Wins": m["white"], "Draws": m["draws"], "Black Wins": m["black"]}
                for m in master_moves[:5]
            ])
            st.dataframe(move_df, width="stretch", hide_index=True)

    with tab_history:
        move_stack = list(board.move_stack)
        if move_stack:
            san_moves = []
            tb = chess.Board()
            for m in move_stack:
                san_moves.append(tb.san(m))
                tb.push(m)
            table = []
            for i in range(0, len(san_moves), 2):
                table.append({
                    "#": (i//2) + 1,
                    "White": san_moves[i],
                    "Black": san_moves[i+1] if i+1 < len(san_moves) else ""
                })
            st.dataframe(table, width="stretch", hide_index=True)