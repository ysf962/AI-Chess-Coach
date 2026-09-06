import chess
import chess.pgn
import streamlit as st
from stchess import chess_board

# 1. Page Configuration
st.set_page_config(page_title="Bilingual AI Chess Coach", layout="wide")
st.title("♟️ Explainable AI Chess Coach")

# 2. Session State Setup
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "last_move" not in st.session_state:
    st.session_state.last_move = None
if "coach_analysis" not in st.session_state:
    st.session_state.coach_analysis = None

# 3. Piece Values & Material Tracker
PIECE_VALUES = {
    chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3,
    chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0
}

PIECE_SYMBOLS = {
    chess.PAWN: "♙", chess.KNIGHT: "♘", chess.BISHOP: "♗",
    chess.ROOK: "♖", chess.QUEEN: "♕",
    -chess.PAWN: "♟", -chess.KNIGHT: "♞", -chess.BISHOP: "♝",
    -chess.ROOK: "♜", -chess.QUEEN: "♛"
}

STARTING_PIECES = {
    chess.PAWN: 8, chess.KNIGHT: 2, chess.BISHOP: 2,
    chess.ROOK: 2, chess.QUEEN: 1
}

def get_captured_pieces_and_score(board):
    white_captured, black_captured = [], []
    white_points, black_points = 0, 0

    for piece_type, count in STARTING_PIECES.items():
        w_current = len(board.pieces(piece_type, chess.WHITE))
        b_current = len(board.pieces(piece_type, chess.BLACK))
        
        b_took = count - w_current
        for _ in range(b_took):
            black_captured.append(PIECE_SYMBOLS[piece_type])
            black_points += PIECE_VALUES[piece_type]

        w_took = count - b_current
        for _ in range(w_took):
            white_captured.append(PIECE_SYMBOLS[-piece_type])
            white_points += PIECE_VALUES[piece_type]

    return {
        "white_captured": "".join(white_captured),
        "black_captured": "".join(black_captured),
        "diff": white_points - black_points
    }

def evaluate_board(board):
    if board.is_checkmate():
        return -99999 if board.turn == chess.WHITE else 99999
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    
    score = 0
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            val = PIECE_VALUES[piece.piece_type] * 100
            score += val if piece.color == chess.WHITE else -val

    score += board.legal_moves.count() if board.turn == chess.WHITE else -board.legal_moves.count()
    for sq in [chess.D4, chess.D5, chess.E4, chess.E5]:
        piece = board.piece_at(sq)
        if piece is not None:
            score += 30 if piece.color == chess.WHITE else -30

    return score

# 4. Alpha-Beta Search Algorithm
def alpha_beta(board, depth, alpha, beta, is_maximizing, node_counter):
    node_counter[0] += 1
    if depth == 0 or board.is_game_over():
        return evaluate_board(board), None

    best_move = None
    if is_maximizing:
        max_eval = -float('inf')
        for move in board.legal_moves:
            board.push(move)
            eval_score, _ = alpha_beta(board, depth - 1, alpha, beta, False, node_counter)
            board.pop()
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        min_eval = float('inf')
        for move in board.legal_moves:
            board.push(move)
            eval_score, _ = alpha_beta(board, depth - 1, alpha, beta, True, node_counter)
            board.pop()
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval, best_move

# 5. Tactical Explanation Engine
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
    
    attacked_pieces = [sq for sq in board.attacks(dest) if board.piece_at(sq) and board.piece_at(sq).color != board.turn]
    if len(attacked_pieces) >= 2:
        reasons_en.append("Executes a tactical fork attacking multiple pieces!")
        reasons_ar.append("ينفذ شوكة تكتيكية (Fork) تهجم على أكثر من قطعة!")
    board.pop()

    if not reasons_en:
        reasons_en.append("Improves piece position and sight lines.")
        reasons_ar.append("يحسن تموضع القطع وخطوط الرؤية.")

    return {"en": " ".join(reasons_en), "ar": " ".join(reasons_ar)}

# 6. Sidebar Controls
st.sidebar.header("🕹️ Game Options")
enable_coach = st.sidebar.toggle("Enable AI Coach Panel", value=True)
search_depth = st.sidebar.slider("Engine Search Depth", 1, 4, 2)

if st.sidebar.button("Reset Game Board"):
    st.session_state.board = chess.Board()
    st.session_state.last_move = None
    st.session_state.coach_analysis = None
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("📄 Export Match Data")
pgn_game = chess.pgn.Game.from_board(st.session_state.board)
st.sidebar.download_button(
    label="Download Game PGN",
    data=str(pgn_game),
    file_name="ai_coach_match.pgn",
    mime="text/plain"
)

# 7. Main Dashboard Interface
col_board, col_dashboard = st.columns([1.2, 1])

with col_board:
    st.subheader("Interactive Board")
    
    mat = get_captured_pieces_and_score(st.session_state.board)
    bot_diff = f"+{-mat['diff']}" if mat['diff'] < 0 else ""
    you_diff = f"+{mat['diff']}" if mat['diff'] > 0 else ""

    st.markdown(f"**🤖 Bot Captured:** {mat['black_captured']} `{bot_diff}`")

    # Render Interactive Board
    move_uci = chess_board(fen=st.session_state.board.fen(), key="interactive_board")

    st.markdown(f"**👤 You Captured:** {mat['white_captured']} `{you_diff}`")

    # Handle Moves
    if move_uci:
        try_move = chess.Move.from_uci(move_uci)

        if try_move not in st.session_state.board.legal_moves:
            try_move = chess.Move.from_uci(f"{move_uci}q")

        if try_move in st.session_state.board.legal_moves:
            st.session_state.board.push(try_move)
            st.session_state.last_move = try_move

            # Engine Counter-Move
            if not st.session_state.board.is_game_over():
                nodes = [0]
                _, ai_move = alpha_beta(
                    st.session_state.board, search_depth, -float('inf'), float('inf'),
                    st.session_state.board.turn == chess.WHITE, nodes
                )
                if ai_move:
                    st.session_state.coach_analysis = {
                        "move": ai_move,
                        "explanation": generate_explanation(st.session_state.board, ai_move),
                        "nodes": nodes[0]
                    }
                    st.session_state.board.push(ai_move)
                    st.session_state.last_move = ai_move
            st.rerun()

with col_dashboard:
    if enable_coach:
        st.subheader("🎓 AI Coach Dashboard")

        if st.button("💡 Ask Coach for Best Move", use_container_width=True):
            if not st.session_state.board.is_game_over():
                nodes = [0]
                _, recommended_move = alpha_beta(
                    st.session_state.board, search_depth, -float('inf'), float('inf'),
                    st.session_state.board.turn == chess.WHITE, nodes
                )
                if recommended_move:
                    explanation = generate_explanation(st.session_state.board, recommended_move)
                    st.session_state.coach_analysis = {
                        "move": recommended_move,
                        "explanation": explanation,
                        "nodes": nodes[0]
                    }
                    st.rerun()

        if st.session_state.coach_analysis:
            analysis = st.session_state.coach_analysis
            st.success(f"**Recommended Engine Move:** {analysis['move']}")
            st.metric("Tree Nodes Processed (Alpha-Beta Benchmark)", analysis["nodes"])

            st.markdown("---")
            st.markdown("### 💬 Tactical Explanations")
            st.info(f"**English:** {analysis['explanation']['en']}")
            st.info(f"**العربية:** {analysis['explanation']['ar']}")
        else:
            st.info("Make a move or tap 'Ask Coach for Best Move' to display tactical analysis.")
    else:
        st.subheader("Match Status")
        st.write(f"**Current Turn:** {'White' if st.session_state.board.turn == chess.WHITE else 'Black'}")
        st.write(f"**Total Legal Moves:** {st.session_state.board.legal_moves.count()}")
        if st.session_state.board.is_game_over():
            st.error("Game Over!")