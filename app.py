import chess
import chess.svg
import chess.pgn
import streamlit as st
import base64

# 1. Page Configuration
st.set_page_config(page_title="Bilingual AI Chess Coach Pro", layout="wide", page_icon="♟️")

# 2. Session State Setup
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "last_move" not in st.session_state:
    st.session_state.last_move = None
if "coach_analysis" not in st.session_state:
    st.session_state.coach_analysis = None
if "lang" not in st.session_state:
    st.session_state.lang = "EN"

def play_sound(sound_type):
    sound_urls = {
        "move": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/move-self.mp3",
        "capture": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/capture.mp3",
        "check": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/move-check.mp3"
    }
    url = sound_urls.get(sound_type)
    if url:
        st.components.v1.html(
            f"""
            <script>
                var audio = new Audio('{url}');
                audio.play().catch(function(error) {{
                    console.log("Autoplay prevented by browser:", error);
                }});
            </script>
            """,
            height=0,
            width=0
        )

# 4. Material & Evaluation Engine
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

def get_captured_pieces(board):
    white_captured, black_captured = [], []
    white_pts, black_pts = 0, 0
    for piece_type, count in STARTING_PIECES.items():
        b_took = count - len(board.pieces(piece_type, chess.WHITE))
        for _ in range(b_took):
            black_captured.append(PIECE_SYMBOLS[piece_type])
            black_pts += PIECE_VALUES[piece_type]
        w_took = count - len(board.pieces(piece_type, chess.BLACK))
        for _ in range(w_took):
            white_captured.append(PIECE_SYMBOLS[-piece_type])
            white_pts += PIECE_VALUES[piece_type]
    return {"white": "".join(white_captured), "black": "".join(black_captured), "eval": white_pts - black_pts}

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
                max_eval, best_move = eval_score, move
            alpha = max(alpha, eval_score)
            if beta <= alpha: break
        return max_eval, best_move
    else:
        min_eval = float('inf')
        for move in board.legal_moves:
            board.push(move)
            eval_score, _ = alpha_beta(board, depth - 1, alpha, beta, True, node_counter)
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
        reasons_en.append("Controls the board center.")
        reasons_ar.append("يفرض سيطرة قوية في منتصف الرقعة.")
    if board.is_capture(move):
        reasons_en.append("Captures material to gain advantage.")
        reasons_ar.append("يستحوذ على قطعة منافسة لتحقيق تفوق مادي.")
    board.push(move)
    if board.is_check():
        reasons_en.append("Puts king in check.")
        reasons_ar.append("يضع ملك الخصم تحت التهديد (كش ملك).")
    board.pop()

    if not reasons_en:
        reasons_en.append("Improves piece positioning.")
        reasons_ar.append("يحسن تموضع القطع وخطوط الرؤية.")

    return {"en": " ".join(reasons_en), "ar": " ".join(reasons_ar)}

# 5. UI Localisation Translations
TEXT = {
    "EN": {
        "title": "♟️ Bilingual AI Chess Coach Pro",
        "bot_cap": "🤖 Bot Captured",
        "you_cap": "👤 You Captured",
        "from": "From Square:",
        "to": "To Square:",
        "submit": "Play Move",
        "coach_title": "🎓 Tactical AI Coach",
        "ask_coach": "💡 Ask Coach for Best Move",
        "reset": "Reset Board",
        "options": "⚙️ Game Options",
        "difficulty": "Difficulty",
        "download": "Download Game PGN",
        "history": "📜 Move History"
    },
    "AR": {
        "title": "♟️ مدرب الشطرنج الذكي",
        "bot_cap": "🤖 القطع المستحوذ عليها للروبوت",
        "you_cap": "👤 القطع المستحوذ عليها لك",
        "from": "من المربع:",
        "to": "إلى المربع:",
        "submit": "تنفيذ الحركة",
        "coach_title": "🎓 مدرب التكتيك الذكي",
        "ask_coach": "💡 اسأل المدرب عن أفضل حركة",
        "reset": "إعادة ضبط اللعبة",
        "options": "⚙️ إعدادات اللعبة",
        "difficulty": "مستوى الصعوبة",
        "download": "تحميل ملف المباراة PGN",
        "history": "📜 سجل الحركات"
    }
}

# 6. Sidebar Controls
st.sidebar.header(TEXT[st.session_state.lang]["options"])
st.session_state.lang = st.sidebar.radio("🌐 Language / اللغة", ["EN", "AR"], index=0 if st.session_state.lang == "EN" else 1)
diff_label = st.sidebar.select_slider(TEXT[st.session_state.lang]["difficulty"], options=["Beginner", "Intermediate", "Advanced"], value="Intermediate")
search_depth = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}[diff_label]

if st.sidebar.button(TEXT[st.session_state.lang]["reset"]):
    st.session_state.board = chess.Board()
    st.session_state.last_move = None
    st.session_state.coach_analysis = None
    st.rerun()

st.sidebar.markdown("---")
pgn_game = chess.pgn.Game.from_board(st.session_state.board)
st.sidebar.download_button(
    label=TEXT[st.session_state.lang]["download"],
    data=str(pgn_game),
    file_name="chess_coach_match.pgn",
    mime="text/plain"
)

# 7. Main Application Dashboard
st.title(TEXT[st.session_state.lang]["title"])
t = TEXT[st.session_state.lang]

col_board, col_dash = st.columns([1.3, 1])

with col_board:
    mat = get_captured_pieces(st.session_state.board)
    st.markdown(f"**{t['bot_cap']}:** {mat['black']}")

    # Interactive SVG Board Render
    board_svg = chess.svg.board(
        board=st.session_state.board,
        lastmove=st.session_state.last_move,
        size=420
    )
    st.image(board_svg, use_container_width=True)
    st.markdown(f"**{t['you_cap']}:** {mat['white']}")

    # Evaluation Progress Bar
    eval_score = evaluate_board(st.session_state.board)
    norm_eval = max(0.0, min(1.0, (eval_score + 1000) / 2000))
    st.progress(norm_eval, text=f"Engine Advantage Score: {eval_score/100:+.2f}")

    # Move Control Panel
    squares = [chess.square_name(sq) for sq in chess.SQUARES]
    col_f, col_t = st.columns(2)
    with col_f:
        from_sq = st.selectbox(t["from"], ["-- Select --"] + sorted(squares), key="f_sq")
    with col_t:
        to_sq = st.selectbox(t["to"], ["-- Select --"] + sorted(squares), key="t_sq")

    if st.button(t["submit"], type="primary", use_container_width=True):
        if from_sq != "-- Select --" and to_sq != "-- Select --":
            uci_str = f"{from_sq}{to_sq}"
            try_move = chess.Move.from_uci(uci_str)
            if try_move not in st.session_state.board.legal_moves:
                try_move = chess.Move.from_uci(f"{uci_str}q")

            if try_move in st.session_state.board.legal_moves:
                sound_type = "capture" if st.session_state.board.is_capture(try_move) else "move"
                st.session_state.board.push(try_move)
                st.session_state.last_move = try_move
                play_sound(sound_type)

                # AI Engine Response
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
            else:
                st.error("Illegal move! Check piece destination.")

with col_dash:
    st.subheader(t["coach_title"])

    if st.button(t["ask_coach"], use_container_width=True):
        if not st.session_state.board.is_game_over():
            nodes = [0]
            _, rec = alpha_beta(
                st.session_state.board, search_depth, -float('inf'), float('inf'),
                st.session_state.board.turn == chess.WHITE, nodes
            )
            if rec:
                st.session_state.coach_analysis = {
                    "move": rec,
                    "explanation": generate_explanation(st.session_state.board, rec),
                    "nodes": nodes[0]
                }
                st.rerun()

    if st.session_state.coach_analysis:
        analysis = st.session_state.coach_analysis
        st.success(f"**Recommended Move:** {analysis['move']}")
        st.info(f"**English:** {analysis['explanation']['en']}")
        st.info(f"**العربية:** {analysis['explanation']['ar']}")

    st.markdown("---")
    st.subheader(t["history"])
    move_list = list(st.session_state.board.move_stack)
    if move_list:
        moves_san = []
        temp_board = chess.Board()
        for m in move_list:
            moves_san.append(temp_board.san(m))
            temp_board.push(m)

        paired_moves = []
        for i in range(0, len(moves_san), 2):
            w_m = moves_san[i]
            b_m = moves_san[i+1] if i+1 < len(moves_san) else ""
            paired_moves.append({"Turn": (i//2)+1, "White": w_m, "Black": b_m})

        st.dataframe(paired_moves, use_container_width=True, hide_index=True)
    else:
        st.write("No moves played yet.")