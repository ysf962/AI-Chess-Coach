import streamlit as st
import chess
import chess.svg
import random
import math

# ==========================================
# 1. SETUP & SESSION STATE INITIALIZATION
# ==========================================
st.set_page_config(page_title="Ultimate Chess Coach", layout="wide")

if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "move_history" not in st.session_state:
    st.session_state.move_history = []
if "eval_score" not in st.session_state:
    st.session_state.eval_score = 0.0
if "user_elo" not in st.session_state:
    st.session_state.user_elo = 1200
if "unlocked_badges" not in st.session_state:
    st.session_state.unlocked_badges = set()
if "blunder_puzzles" not in st.session_state:
    st.session_state.blunder_puzzles = []
if "game_over" not in st.session_state:
    st.session_state.game_over = False
if "last_explanation" not in st.session_state:
    st.session_state.last_explanation = ""

# Opening Database (Sample ECO mappings)
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

# Square tables for Grandmaster/Hard positional play
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

# ==========================================
# 2. EVALUATION & AI BOT ENGINE
# ==========================================
def evaluate_board(board):
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
            if piece.color == chess.WHITE:
                score += total
            else:
                score -= total
    return score / 100.0  # Convert to standard pawn units

def minimax(board, depth, alpha, beta, maximizing):
    if depth == 0 or board.is_game_over():
        return evaluate_board(board), None

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
    legal_moves = list(board.legal_moves)
    if not legal_moves:
        return None

    if difficulty == "Easy":
        # 80% random, 20% shallow search
        if random.random() < 0.8:
            return random.choice(legal_moves)
        _, move = minimax(board, depth=1, alpha=-10000, beta=10000, maximizing=(board.turn == chess.WHITE))
        return move or random.choice(legal_moves)

    elif difficulty == "Medium":
        # Depth 2 Minimax search
        _, move = minimax(board, depth=2, alpha=-10000, beta=10000, maximizing=(board.turn == chess.WHITE))
        return move or random.choice(legal_moves)

    elif difficulty == "Hard":
        # Depth 3 Minimax search
        _, move = minimax(board, depth=3, alpha=-10000, beta=10000, maximizing=(board.turn == chess.WHITE))
        return move or random.choice(legal_moves)

    elif difficulty == "Grandmaster":
        # Depth 4 Minimax with zero random blunders
        _, move = minimax(board, depth=4, alpha=-10000, beta=10000, maximizing=(board.turn == chess.WHITE))
        return move or random.choice(legal_moves)

# ==========================================
# 3. HELPER FUNCTIONS & ANALYSIS
# ==========================================
def get_threat_and_guard_fill(board):
    fill_dict = {}
    for sq in chess.SQUARES:
        piece = board.piece_at(sq)
        if piece:
            is_attacked = board.is_attacked_by(not piece.color, sq)
            is_defended = board.is_attacked_by(piece.color, sq)

            if is_attacked and not is_defended:
                fill_dict[sq] = "#ff4d4d88"  # Red: Hanging
            elif is_attacked and is_defended:
                fill_dict[sq] = "#ffa50088"  # Orange: Under Attack
            elif is_defended and piece.color == board.turn:
                fill_dict[sq] = "#4da6ff44"  # Blue/Green: Safely Defended
    return fill_dict

def analyze_blunder(board_before, move, board_after):
    reasons = []
    moving_piece = board_before.piece_at(move.from_square)
    dest_sq = move.to_square

    # Check if piece was dropped into an undefended attack
    if board_after.is_attacked_by(board_after.turn, dest_sq):
        if not board_after.is_attacked_by(not board_after.turn, dest_sq):
            reasons.append(f"Leaves your **{chess.piece_name(moving_piece.piece_type).title()}** undefended on {chess.square_name(dest_sq)}.")

    # Check for forks against opponent
    attackers = board_after.attackers(not board_after.turn, dest_sq)
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

def update_elo(user_won, difficulty):
    diff_ratings = {"Easy": 800, "Medium": 1200, "Hard": 1600, "Grandmaster": 2200}
    bot_elo = diff_ratings.get(difficulty, 1200)
    expected = 1 / (1 + 10 ** ((bot_elo - st.session_state.user_elo) / 400))
    actual = 1.0 if user_won else 0.0
    st.session_state.user_elo += int(32 * (actual - expected))

def check_achievements(board, move, prev_eval):
    if board.is_checkmate():
        piece = board.piece_at(move.to_square)
        if piece and piece.piece_type == chess.PAWN:
            st.session_state.unlocked_badges.add("♟️ Checkmate with a Pawn")

    # Sacrifice check
    if board.piece_at(move.to_square) and PIECE_VALUES.get(board.piece_at(move.from_square).piece_type, 0) > PIECE_VALUES.get(board.piece_at(move.to_square).piece_type, 0):
        st.session_state.unlocked_badges.add("⚔️ First Sacrifice")

    if st.session_state.eval_score > 3.0:
        st.session_state.unlocked_badges.add("🛡️ Flawless Defense")

# ==========================================
# 4. SIDEBAR CONFIGURATION
# ==========================================
st.sidebar.title("🎮 Match Settings")

difficulty = st.sidebar.selectbox("Bot Difficulty", ["Easy", "Medium", "Hard", "Grandmaster"], index=1)
coach_persona = st.sidebar.selectbox("AI Coach Persona", [
    "Grandmaster Magnus (Analytical)",
    "Coach Sparky (Encouraging)",
    "Tactical Master (Aggressive)"
])

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

if st.sidebar.button("Reset Game"):
    st.session_state.board = chess.Board()
    st.session_state.move_history = []
    st.session_state.eval_score = 0.0
    st.session_state.game_over = False
    st.session_state.last_explanation = ""
    st.rerun()

# ==========================================
# 5. MAIN INTERFACE
# ==========================================
st.title("♟️ Interactive Chess Engine & AI Coach")

col_board, col_panel = st.columns([2, 1.2])

with col_board:
    # Render Board SVG with optional threats
    fill_colors = get_threat_and_guard_fill(st.session_state.board) if show_threats else {}
    last_move = st.session_state.move_history[-1] if st.session_state.move_history else None

    board_svg = chess.svg.board(
        board=st.session_state.board,
        lastmove=last_move,
        fill=fill_colors,
        size=460
    )

    if show_eval_bar:
        c1, c2 = st.columns([1, 8])
        with c1:
            eval_val = max(-10.0, min(10.0, st.session_state.eval_score))
            white_pct = int(((eval_val + 10) / 20) * 100)
            st.markdown(
                f"""
                <div style="background-color: #333; height: 300px; width: 25px; border-radius: 5px; display: flex; flex-direction: column-reverse; overflow: hidden; border: 1px solid #555;">
                    <div style="background-color: #fff; height: {white_pct}%; width: 100%;"></div>
                </div>
                <p style="text-align: center; font-size: 11px; margin-top: 4px;">{st.session_state.eval_score:+.1f}</p>
                """,
                unsafe_allow_html=True
            )
        with c2:
            st.image(board_svg, use_container_width=False)
    else:
        st.image(board_svg, use_container_width=False)

    # Manual Move Selection
    if not st.session_state.game_over and st.session_state.board.turn == chess.WHITE:
        legal_san_moves = [st.session_state.board.san(m) for m in st.session_state.board.legal_moves]
        if legal_san_moves:
            selected_san = st.selectbox("Select Your Move:", ["-- Select Move --"] + sorted(legal_san_moves))
            if selected_san != "-- Select Move --":
                if st.button("Play Move"):
                    pre_board = st.session_state.board.copy()
                    pre_eval = st.session_state.eval_score

                    move = st.session_state.board.parse_san(selected_san)
                    st.session_state.board.push(move)
                    st.session_state.move_history.append(move)

                    # Update evaluation & check achievements
                    post_eval = evaluate_board(st.session_state.board)
                    st.session_state.eval_score = post_eval
                    check_achievements(st.session_state.board, move, pre_eval)

                    # Blunder Detection (Eval drop > 1.5 pawns)
                    if (pre_eval - post_eval) > 1.5:
                        explanation = analyze_blunder(pre_board, move, st.session_state.board)
                        st.session_state.last_explanation = explanation
                        st.session_state.blunder_puzzles.append((pre_board.fen(), move))

                    # Check match end
                    if st.session_state.board.is_game_over():
                        st.session_state.game_over = True
                        if st.session_state.board.is_checkmate():
                            update_elo(True, difficulty)
                    else:
                        # AI Turn
                        bot_move = get_bot_move(st.session_state.board, difficulty)
                        if bot_move:
                            st.session_state.board.push(bot_move)
                            st.session_state.move_history.append(bot_move)
                            st.session_state.eval_score = evaluate_board(st.session_state.board)

                            if st.session_state.board.is_game_over():
                                st.session_state.game_over = True
                                if st.session_state.board.is_checkmate():
                                    update_elo(False, difficulty)

                    st.rerun()

with col_panel:
    st.subheader("📖 Opening Explorer")
    move_uci_str = " ".join([m.uci() for m in st.session_state.move_history])
    opening_name = "Custom / Standard Continuation"
    for prefix, name in OPENINGS_DB.items():
        if move_uci_str.startswith(prefix):
            opening_name = name

    st.info(f"**Identified Opening:** {opening_name}")

    st.markdown("---")
    st.subheader("🤖 AI Coach Feedback")

    if st.session_state.last_explanation:
        st.warning(f"**Blunder Alert!** {st.session_state.last_explanation}")
        if "Magnus" in coach_persona:
            st.caption("💬 *Magnus:* Accuracy is non-negotiable. Re-evaluate your piece coordination.")
        elif "Sparky" in coach_persona:
            st.caption("💬 *Coach Sparky:* That's okay! Mistakes are where the real learning happens!")
        else:
            st.caption("💬 *Tactical Master:* You opened up a line of attack for me. Watch your flanks!")
    else:
        st.success("Solid position. Keep building your board influence.")

    st.markdown("---")
    st.subheader("🧩 Custom Blunder Puzzles")
    if st.session_state.blunder_puzzles:
        st.write(f"You have **{len(st.session_state.blunder_puzzles)}** saved blunder puzzle(s) from this session.")
        if st.button("Load Last Blunder Position"):
            fen, bad_move = st.session_state.blunder_puzzles[-1]
            st.session_state.board = chess.Board(fen)
            st.session_state.game_over = False
            st.session_state.last_explanation = ""
            st.rerun()
    else:
        st.caption("No blunders recorded yet. Keep playing cleanly!")