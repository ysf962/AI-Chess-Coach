import chess
import chess.svg
import chess.pgn
import streamlit as st

# 1. Page Configuration
st.set_page_config(page_title="AI Chess Coach Pro", layout="wide", page_icon="♟️")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: bold; }
    .stProgress > div > div > div > div { background-color: #00c853; }
    
    .move-card {
        background-color: #161b22;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #30363d;
        margin-top: 15px;
    }
    </style>
""", unsafe_allow_html=True)

# 2. Session State Initialization
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "last_move" not in st.session_state:
    st.session_state.last_move = None
if "coach_analysis" not in st.session_state:
    st.session_state.coach_analysis = None
if "player_color" not in st.session_state:
    st.session_state.player_color = chess.WHITE
if "lang" not in st.session_state:
    st.session_state.lang = "EN"

# 3. Audio Controller
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

# 4. Engine & Evaluation System
PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
PIECE_SYMBOLS = {
    (chess.PAWN, chess.WHITE): "♙", (chess.KNIGHT, chess.WHITE): "♘", (chess.BISHOP, chess.WHITE): "♗", 
    (chess.ROOK, chess.WHITE): "♖", (chess.QUEEN, chess.WHITE): "♕", (chess.KING, chess.WHITE): "♔",
    (chess.PAWN, chess.BLACK): "♟", (chess.KNIGHT, chess.BLACK): "♞", (chess.BISHOP, chess.BLACK): "♝", 
    (chess.ROOK, chess.BLACK): "♜", (chess.QUEEN, chess.BLACK): "♛", (chess.KING, chess.BLACK): "♚"
}
STARTING_PIECES = {chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 2, chess.QUEEN: 1}

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

def evaluate_board(board):
    if board.is_checkmate():
        return -99999 if board.turn == chess.WHITE else 99999
    if board.is_game_over():
        return 0
    score = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p:
            val = PIECE_VALUES[p.piece_type] * 100
            score += val if p.color == chess.WHITE else -val
    score += board.legal_moves.count() if board.turn == chess.WHITE else -board.legal_moves.count()
    return score

def get_best_move(board, is_max):
    best_move = None
    best_eval = -float('inf') if is_max else float('inf')
    for m in board.legal_moves:
        board.push(m)
        ev = evaluate_board(board)
        board.pop()
        if is_max and ev > best_eval:
            best_eval = ev
            best_move = m
        elif not is_max and ev < best_eval:
            best_eval = ev
            best_move = m
    return best_move

# 5. Sidebar Controls
st.sidebar.title("🎮 Controls & Settings")
st.session_state.lang = st.sidebar.radio("🌐 Language / اللغة", ["EN", "AR"], index=0 if st.session_state.lang == "EN" else 1)
audio_enabled = st.sidebar.toggle("🔊 Enable Audio", value=True)

chosen_side = st.sidebar.radio("♟️ Choose Side", ["White", "Black"])
new_color = chess.WHITE if chosen_side == "White" else chess.BLACK

if new_color != st.session_state.player_color:
    st.session_state.player_color = new_color
    st.session_state.board = chess.Board()
    st.session_state.last_move = None
    st.session_state.coach_analysis = None
    # Trigger bot move immediately if player chooses Black
    if st.session_state.player_color == chess.BLACK:
        ai_m = get_best_move(st.session_state.board, True)
        if ai_m:
            st.session_state.board.push(ai_m)
            st.session_state.last_move = ai_m
    st.rerun()

theme_choice = st.sidebar.selectbox("🎨 Board Theme", ["Classic Wood", "Lichess Green", "Midnight Dark", "Neon Cyber"])
THEMES = {
    "Classic Wood": {"square_light": "#f0d9b5", "square_dark": "#b58863"},
    "Lichess Green": {"square_light": "#ffffdd", "square_dark": "#86a666"},
    "Midnight Dark": {"square_light": "#9e9e9e", "square_dark": "#424242"},
    "Neon Cyber": {"square_light": "#2a2d37", "square_dark": "#00adb5"}
}

if st.sidebar.button("🔄 Reset Game", use_container_width=True):
    st.session_state.board = chess.Board()
    st.session_state.last_move = None
    st.session_state.coach_analysis = None
    if st.session_state.player_color == chess.BLACK:
        ai_m = get_best_move(st.session_state.board, True)
        if ai_m:
            st.session_state.board.push(ai_m)
            st.session_state.last_move = ai_m
    st.rerun()

st.sidebar.markdown("---")
pgn_game = chess.pgn.Game.from_board(st.session_state.board)
st.sidebar.download_button("📥 Export PGN", data=str(pgn_game), file_name="chess_match.pgn", mime="text/plain", use_container_width=True)

# 6. Main Dashboard Layout
is_ar = st.session_state.lang == "AR"
col_board, col_dash = st.columns([1.3, 1])

board = st.session_state.board
player_turn = (board.turn == st.session_state.player_color)

with col_board:
    mat = get_captured(board)
    top_captures = mat['white'] if st.session_state.player_color == chess.BLACK else mat['black']
    bottom_captures = mat['black'] if st.session_state.player_color == chess.BLACK else mat['white']

    st.markdown(f"**🤖 {'الروبوت' if is_ar else 'Bot'}:** {top_captures}")

    # Render Board SVG flipped according to player color
    theme_colors = THEMES[theme_choice]
    board_svg = chess.svg.board(
        board=board,
        orientation=st.session_state.player_color,
        lastmove=st.session_state.last_move,
        colors={"square light": theme_colors["square_light"], "square dark": theme_colors["square_dark"]},
        size=400
    )
    st.image(board_svg, use_container_width=True)

    st.markdown(f"**👤 {'أنت' if is_ar else 'You'}:** {bottom_captures}")

    # Modern Move Selectors
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

            if st.button("🚀 " + ("تحريك القطعة" if is_ar else "Play Move"), use_container_width=True):
                move_uci = f"{selected_from}{selected_to}"
                move = chess.Move.from_uci(move_uci)
                if move not in board.legal_moves:
                    move = chess.Move.from_uci(f"{move_uci}q")

                if move in board.legal_moves:
                    sound = "capture" if board.is_capture(move) else "move"
                    board.push(move)
                    st.session_state.last_move = move
                    play_sound(sound, audio_enabled)

                    # Bot Counter-Move
                    if not board.is_game_over():
                        bot_is_max = (st.session_state.player_color == chess.BLACK)
                        ai_move = get_best_move(board, bot_is_max)
                        if ai_move:
                            board.push(ai_move)
                            st.session_state.last_move = ai_move
                    else:
                        play_sound("game_over", audio_enabled)

                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

    # Position Evaluation Bar
    curr_eval = evaluate_board(board)
    norm_eval = max(0.0, min(1.0, (curr_eval + 1000) / 2000))
    st.progress(norm_eval, text=f"Position Score: {curr_eval/100:+.2f}")

with col_dash:
    tab_coach, tab_history = st.tabs(["🎓 " + ("المدرب" if is_ar else "Coach"), "📜 " + ("سجل الحركات" if is_ar else "History")])

    with tab_coach:
        if st.button("💡 " + ("طلب نصيحة" if is_ar else "Ask Coach Best Move"), use_container_width=True):
            if not board.is_game_over():
                rec_is_max = (st.session_state.player_color == chess.WHITE)
                rec_move = get_best_move(board, rec_is_max)
                if rec_move:
                    st.session_state.coach_analysis = board.san(rec_move)
                    st.rerun()

        if st.session_state.coach_analysis:
            st.info(f"**Recommended Move:** {st.session_state.coach_analysis}")

        if board.is_game_over():
            st.error("🏆 Game Over!")

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
            st.dataframe(table, use_container_width=True, hide_index=True)