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
    </style>
""", unsafe_allow_html=True)

# 2. Session State Initialization
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "history" not in st.session_state:
    st.session_state.history = [chess.Board().fen()]
if "move_records" not in st.session_state:
    st.session_state.move_records = []
if "last_move" not in st.session_state:
    st.session_state.last_move = None
if "coach_analysis" not in st.session_state:
    st.session_state.coach_analysis = None
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
    w_pts, b_pts = 0, 0
    for p_type, count in STARTING_PIECES.items():
        b_took = count - len(board.pieces(p_type, chess.WHITE))
        for _ in range(b_took):
            b_cap.append(PIECE_SYMBOLS[(p_type, chess.WHITE)])
            b_pts += PIECE_VALUES[p_type]
        w_took = count - len(board.pieces(p_type, chess.BLACK))
        for _ in range(w_took):
            w_cap.append(PIECE_SYMBOLS[(p_type, chess.BLACK)])
            w_pts += PIECE_VALUES[p_type]
    return {"white": "".join(w_cap), "black": "".join(b_cap), "eval": w_pts - b_pts}

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
    for sq in [chess.D4, chess.D5, chess.E4, chess.E5]:
        p = board.piece_at(sq)
        if p:
            score += 30 if p.color == chess.WHITE else -30
    return score

def get_best_move(board):
    best_move = None
    best_eval = float('inf')
    for m in board.legal_moves:
        board.push(m)
        ev = evaluate_board(board)
        board.pop()
        if ev < best_eval:
            best_eval = ev
            best_move = m
    return best_move

# 5. Sidebar
st.sidebar.title("🎮 Controls & Settings")
st.session_state.lang = st.sidebar.radio("🌐 Language / اللغة", ["EN", "AR"], index=0 if st.session_state.lang == "EN" else 1)
audio_enabled = st.sidebar.toggle("🔊 Enable Audio", value=True)

theme_choice = st.sidebar.selectbox("🎨 Board Theme", ["Classic Wood", "Lichess Green", "Midnight Dark", "Neon Cyber"])
THEMES = {
    "Classic Wood": {"square_light": "#f0d9b5", "square_dark": "#b58863"},
    "Lichess Green": {"square_light": "#ffffdd", "square_dark": "#86a666"},
    "Midnight Dark": {"square_light": "#9e9e9e", "square_dark": "#424242"},
    "Neon Cyber": {"square_light": "#2a2d37", "square_dark": "#00adb5"}
}

if st.sidebar.button("🔄 Reset Game", use_container_width=True):
    st.session_state.board = chess.Board()
    st.session_state.history = [chess.Board().fen()]
    st.session_state.move_records = []
    st.session_state.last_move = None
    st.session_state.coach_analysis = None
    st.rerun()

st.sidebar.markdown("---")
pgn_game = chess.pgn.Game.from_board(st.session_state.board)
st.sidebar.download_button("📥 Export PGN", data=str(pgn_game), file_name="chess_match.pgn", mime="text/plain", use_container_width=True)

# 6. Main Dashboard
is_ar = st.session_state.lang == "AR"
col_board, col_dash = st.columns([1.3, 1])

with col_board:
    mat = get_captured(st.session_state.board)
    st.markdown(f"**🤖 {'الروبوت' if is_ar else 'Bot'}:** {mat['black']}")

    # Render Visual SVG Board
    theme_colors = THEMES[theme_choice]
    board_svg = chess.svg.board(
        board=st.session_state.board,
        lastmove=st.session_state.last_move,
        colors={"square light": theme_colors["square_light"], "square dark": theme_colors["square_dark"]},
        size=400
    )
    st.image(board_svg)

    st.markdown(f"**👤 {'أنت' if is_ar else 'You'}:** {mat['white']}")

    # Universal Move Controls
    legal_moves = [st.session_state.board.san(m) for m in st.session_state.board.legal_moves]
    
    if legal_moves and not st.session_state.board.is_game_over():
        selected_move_san = st.selectbox("🎯 " + ("اختر الحركتك:" if is_ar else "Select your move:"), sorted(legal_moves))
        if st.button("🚀 " + ("تنفيذ الحركة" if is_ar else "Play Move"), use_container_width=True):
            move = st.session_state.board.parse_san(selected_move_san)
            sound = "capture" if st.session_state.board.is_capture(move) else "move"
            
            # Execute player move
            st.session_state.board.push(move)
            st.session_state.last_move = move
            play_sound(sound, audio_enabled)

            # Bot counter-move
            if not st.session_state.board.is_game_over():
                ai_move = get_best_move(st.session_state.board)
                if ai_move:
                    st.session_state.board.push(ai_move)
                    st.session_state.last_move = ai_move
            else:
                play_sound("game_over", audio_enabled)
                
            st.rerun()

    # Evaluation Score Bar
    curr_eval = evaluate_board(st.session_state.board)
    norm_eval = max(0.0, min(1.0, (curr_eval + 1000) / 2000))
    st.progress(norm_eval, text=f"Position Score: {curr_eval/100:+.2f}")

with col_dash:
    tab_coach, tab_history = st.tabs(["🎓 " + ("المدرب" if is_ar else "Coach"), "📜 " + ("سجل الحركات" if is_ar else "History")])

    with tab_coach:
        if st.button("💡 " + ("طلب نصيحة" if is_ar else "Ask Coach Best Move"), use_container_width=True):
            if not st.session_state.board.is_game_over():
                rec_move = get_best_move(st.session_state.board)
                if rec_move:
                    st.session_state.coach_analysis = st.session_state.board.san(rec_move)
                    st.rerun()

        if st.session_state.coach_analysis:
            st.info(f"**Recommended Move:** {st.session_state.coach_analysis}")

        if st.session_state.board.is_game_over():
            st.error("🏆 Game Over!")

    with tab_history:
        move_stack = list(st.session_state.board.move_stack)
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