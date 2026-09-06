import chess
import chess.pgn
import streamlit as st
from streamlit_chessboard import st_chessboard

# 1. Page Setup
st.set_page_config(page_title="Bilingual AI Chess Coach", layout="wide")
st.title("♟️ Chess.com-Style AI Coach")

# 2. Session State Setup
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "last_move" not in st.session_state:
    st.session_state.last_move = None
if "coach_analysis" not in st.session_state:
    st.session_state.coach_analysis = None

# 3. Material Evaluation Engine
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

def generate_explanation(board, move):
    reasons_en, reasons_ar = [], []
    dest = move.to_square

    if dest in [chess.D4, chess.D5, chess.E4, chess.E5]:
        reasons_en.append("Establishes control in the center.")
        reasons_ar.append("يفرض سيطرة قوية في منتصف الرقعة.")

    if board.is_capture(move):
        reasons_en.append("Captures active material to gain advantage.")
        reasons_ar.append("يستحوذ على قطعة منافسة لتحقيق تفوق مادي.")

    board.push(move)
    if board.is_check():
        reasons_en.append("Delivers a direct check to the king.")
        reasons_ar.append("يضع ملك الخصم تحت التهديد (كش ملك).")
    board.pop()

    if not reasons_en:
        reasons_en.append("Improves piece position and sight lines.")
        reasons_ar.append("يحسن تموضع القطع وخطوط الرؤية.")

    return {"en": " ".join(reasons_en), "ar": " ".join(reasons_ar)}

# 4. Sidebar Options
st.sidebar.header("🕹️ Controls")
search_depth = st.sidebar.slider("Engine Search Depth", 1, 4, 2)
if st.sidebar.button("Reset Game Board"):
    st.session_state.board = chess.Board()
    st.session_state.last_move = None
    st.session_state.coach_analysis = None
    st.rerun()

# 5. Interface Layout
col_board, col_dash = st.columns([1.2, 1])

with col_board:
    mat = get_captured(st.session_state.board)
    st.markdown(f"**🤖 Bot Captured:** {mat['black']}")

    # Interactive Touch & Drag Board
    fen = st.session_state.board.fen()
    move_data = st_chessboard(fen=fen, key="drag_board")

    st.markdown(f"**👤 You Captured:** {mat['white']}")

    # Process Drag and Drop Moves
    if move_data and "from" in move_data and "to" in move_data:
        move_uci = f"{move_data['from']}{move_data['to']}"
        try_move = chess.Move.from_uci(move_uci)

        # Handle Pawn Promotion Defaulting to Queen
        if try_move not in st.session_state.board.legal_moves:
            try_move = chess.Move.from_uci(f"{move_uci}q")

        if try_move in st.session_state.board.legal_moves:
            st.session_state.board.push(try_move)
            st.session_state.last_move = try_move

            # AI Counter-Move
            if not st.session_state.board.is_game_over():
                _, ai_move = alpha_beta(
                    st.session_state.board, search_depth, -float('inf'), float('inf'),
                    st.session_state.board.turn == chess.WHITE
                )
                if ai_move:
                    st.session_state.coach_analysis = {
                        "move": ai_move,
                        "explanation": generate_explanation(st.session_state.board, ai_move)
                    }
                    st.session_state.board.push(ai_move)
                    st.session_state.last_move = ai_move
            st.rerun()

with col_dash:
    st.subheader("🎓 AI Coach Dashboard")
    if st.button("💡 Ask Coach for Best Move", use_container_width=True):
        if not st.session_state.board.is_game_over():
            _, recommended_move = alpha_beta(
                st.session_state.board, search_depth, -float('inf'), float('inf'),
                st.session_state.board.turn == chess.WHITE
            )
            if recommended_move:
                st.session_state.coach_analysis = {
                    "move": recommended_move,
                    "explanation": generate_explanation(st.session_state.board, recommended_move)
                }
                st.rerun()

    if st.session_state.coach_analysis:
        analysis = st.session_state.coach_analysis
        st.success(f"**Recommended Move:** {analysis['move']}")
        st.markdown("---")
        st.info(f"**English:** {analysis['explanation']['en']}")
        st.info(f"**العربية:** {analysis['explanation']['ar']}")