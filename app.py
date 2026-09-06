import chess
import chess.svg
import chess.pgn
import streamlit as st

st.set_page_config(page_title="Bilingual AI Chess Coach", layout="wide")
st.title("♟️ Explainable AI Chess Coach")

# Initialize Session State
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "last_move" not in st.session_state:
    st.session_state.last_move = None
if "coach_analysis" not in st.session_state:
    st.session_state.coach_analysis = None

PIECE_VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}
PIECE_SYMBOLS = {chess.PAWN: "♙", chess.KNIGHT: "♘", chess.BISHOP: "♗", chess.ROOK: "♖", chess.QUEEN: "♕", -chess.PAWN: "♟", -chess.KNIGHT: "♞", -chess.BISHOP: "♝", -chess.ROOK: "♜", -chess.QUEEN: "♛"}
STARTING_PIECES = {chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2, chess.ROOK: 2, chess.QUEEN: 1}

def get_captured(board):
    w_cap, b_cap = [], []
    w_pts, b_pts = 0, 0
    for p_type, count in STARTING_PIECES.items():
        b_took = count - len(board.pieces(p_type, chess.WHITE))
        for _ in range(b_took):
            b_cap.append(PIECE_SYMBOLS[p_type])
            b_pts += PIECE_VALUES[p_type]
        w_took = count - len(board.pieces(p_type, chess.BLACK))
        for _ in range(w_took):
            w_cap.append(PIECE_SYMBOLS[-p_type])
            w_pts += PIECE_VALUES[p_type]
    return {"white": "".join(w_cap), "black": "".join(b_cap), "diff": w_pts - b_pts}

def evaluate_board(board):
    if board.is_checkmate():
        return -99999 if board.turn == chess.WHITE else 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    score = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p:
            val = PIECE_VALUES[p.piece_type] * 100
            score += val if p.color == chess.WHITE else -val
    return score

def alpha_beta(board, depth, alpha, beta, is_max):
    if depth == 0 or board.is_game_over():
        return evaluate_board(board), None
    best_move = None
    if is_max:
        max_eval = -float('inf')
        for move in board.legal_moves:
            board.push(move)
            eval_score, _ = alpha_beta(board, depth - 1, alpha, beta, False)
            board.pop()
            if eval_score > max_eval:
                max_eval, best_move = eval_score, move
            alpha = max(alpha, eval_score)
            if beta <= alpha: break
        return max_eval, best_move
    else:
        min_eval = float('inf')
        for move in board.legal_moves:
            board.push(move)
            eval_score, _ = alpha_beta(board, depth - 1, alpha, beta, True)
            board.pop()
            if eval_score < min_eval:
                min_eval, best_move = eval_score, move
            beta = min(beta, eval_score)
            if beta <= alpha: break
        return min_eval, best_move

# Sidebar
st.sidebar.header("🕹️ Options")
search_depth = st.sidebar.slider("Engine Depth", 1, 4, 2)
if st.sidebar.button("Reset Game"):
    st.session_state.board = chess.Board()
    st.session_state.last_move = None
    st.session_state.coach_analysis = None
    st.rerun()

# Layout
col_board, col_dash = st.columns([1.2, 1])

with col_board:
    mat = get_captured(st.session_state.board)
    st.markdown(f"**🤖 Bot Captured:** {mat['black']}")
    
    board_svg = chess.svg.board(board=st.session_state.board, lastmove=st.session_state.last_move, size=380)
    st.image(board_svg, use_container_width=True)
    
    st.markdown(f"**👤 You Captured:** {mat['white']}")

    st.markdown("### Move Selector")
    moves = [st.session_state.board.san(m) for m in st.session_state.board.legal_moves]
    
    with st.form("chess_move_form"):
        chosen = st.selectbox("Choose Move:", ["-- Select Move --"] + moves)
        submitted = st.form_submit_button("Play Move", type="primary")
        
        if submitted and chosen != "-- Select Move --":
            user_m = st.session_state.board.parse_san(chosen)
            st.session_state.board.push(user_m)
            st.session_state.last_move = user_m
            
            if not st.session_state.board.is_game_over():
                _, ai_m = alpha_beta(st.session_state.board, search_depth, -float('inf'), float('inf'), st.session_state.board.turn == chess.WHITE)
                if ai_m:
                    st.session_state.board.push(ai_m)
                    st.session_state.last_move = ai_m
            st.rerun()

with col_dash:
    st.subheader("🎓 AI Coach")
    if st.button("💡 Get Advice"):
        if not st.session_state.board.is_game_over():
            _, rec = alpha_beta(st.session_state.board, search_depth, -float('inf'), float('inf'), st.session_state.board.turn == chess.WHITE)
            st.session_state.coach_analysis = rec
            st.rerun()
            
    if st.session_state.coach_analysis:
        st.info(f"Recommended Move: **{st.session_state.coach_analysis}**")