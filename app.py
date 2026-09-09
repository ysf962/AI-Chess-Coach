import chess
import chess.pgn
import streamlit as st
from streamlit_react_chessboard import chessboard

# 1. Page Config
st.set_page_config(page_title="AI Chess Coach", layout="wide", page_icon="♟️")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    div[data-testid="stMetricValue"] { font-size: 1.6rem; font-weight: bold; }
    .stProgress > div > div > div > div { background-color: #00c853; }
    </style>
""", unsafe_allow_html=True)

# 2. State Initialization
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "coach_analysis" not in st.session_state:
    st.session_state.coach_analysis = None

# 3. Audio Controller
def play_sound(sound_type):
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

# 4. Engine & Analysis
PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}

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
    return score

def get_best_move(board, depth=2):
    best_move = None
    best_eval = -float('inf') if board.turn == chess.WHITE else float('inf')
    
    for move in board.legal_moves:
        board.push(move)
        eval_score = evaluate_board(board)
        board.pop()
        
        if board.turn == chess.WHITE:
            if eval_score > best_eval:
                best_eval = eval_score
                best_move = move
        else:
            if eval_score < best_eval:
                best_eval = eval_score
                best_move = move
                
    return best_move

def generate_explanation(board, move):
    reasons = []
    if move.to_square in [chess.D4, chess.D5, chess.E4, chess.E5]:
        reasons.append("Controls critical central squares.")
    if board.is_capture(move):
        reasons.append("Captures material to gain a positional advantage.")
    board.push(move)
    if board.is_check():
        reasons.append("Puts the enemy king under direct check.")
    board.pop()
    if not reasons:
        reasons.append("Improves overall piece position and board control.")
    return " ".join(reasons)

# 5. Sidebar
st.sidebar.title("🎮 Settings")
search_depth = st.sidebar.slider("Engine Level", 1, 3, 2)

if st.sidebar.button("🔄 Reset Board", use_container_width=True):
    st.session_state.board = chess.Board()
    st.session_state.coach_analysis = None
    st.rerun()

st.sidebar.markdown("---")
pgn_game = chess.pgn.Game.from_board(st.session_state.board)
st.sidebar.download_button("📥 Export PGN", data=str(pgn_game), file_name="chess_match.pgn", mime="text/plain", use_container_width=True)

# 6. Layout
col_board, col_dash = st.columns([1.3, 1])

with col_board:
    # Touch/Click interactive board
    board_state = chessboard(
        board_fen=st.session_state.board.fen(),
        key="interactive_chessboard"
    )

    # Process Move
    if board_state and board_state != st.session_state.board.fen():
        play_sound("move")
        st.session_state.board.set_fen(board_state)
        
        # Engine Bot Response
        if not st.session_state.board.is_game_over() and st.session_state.board.turn == chess.BLACK:
            ai_move = get_best_move(st.session_state.board, depth=search_depth)
            if ai_move:
                st.session_state.coach_analysis = {
                    "move": ai_move,
                    "explanation": generate_explanation(st.session_state.board, ai_move)
                }
                st.session_state.board.push(ai_move)
        elif st.session_state.board.is_game_over():
            play_sound("game_over")
            
        st.rerun()

    # Evaluation Bar
    curr_eval = evaluate_board(st.session_state.board)
    norm_eval = max(0.0, min(1.0, (curr_eval + 1000) / 2000))
    st.progress(norm_eval, text=f"Position Score: {curr_eval/100:+.2f}")

with col_dash:
    st.subheader("🎓 Coach Analysis")
    if st.button("💡 Ask Coach for Best Move", use_container_width=True):
        if not st.session_state.board.is_game_over():
            rec_move = get_best_move(st.session_state.board, depth=search_depth)
            if rec_move:
                st.session_state.coach_analysis = {
                    "move": rec_move,
                    "explanation": generate_explanation(st.session_state.board, rec_move)
                }
                st.rerun()

    if st.session_state.coach_analysis:
        an = st.session_state.coach_analysis
        st.metric("Recommended Move", str(an['move']))
        st.info(f"**Reasoning:** {an['explanation']}")

    if st.session_state.board.is_game_over():
        st.error("🏆 Game Over!")

    st.subheader("📜 Move Notation")
    moves = list(st.session_state.board.move_stack)
    if moves:
        st.write(" ".join([m.uci() for m in moves]))