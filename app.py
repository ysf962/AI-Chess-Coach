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
if "selected_square" not in st.session_state:
    st.session_state.selected_square = None
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

def classify_move(prev_eval, curr_eval):
    diff = curr_eval - prev_eval
    if diff >= 150: return ("‼️ Great", "‼️ ممتاز", "🟩")
    elif diff >= -30: return ("⭐ Best", "⭐ الأفضل", "🟩")
    elif diff >= -150: return ("?! Inaccuracy", "?! عدم دقة", "🟨")
    else: return ("?? Blunder", "?? خطأ فادح", "🟥")

def generate_explanation(board, move):
    reasons_en, reasons_ar = [], []
    dest = move.to_square
    if dest in [chess.D4, chess.D5, chess.E4, chess.E5]:
        reasons_en.append("Controls central board squares.")
        reasons_ar.append("يفرض سيطرة على المربعات المركزية.")
    if board.is_capture(move):
        reasons_en.append("Captures material to build tactical advantage.")
        reasons_ar.append("يستحوذ على قطعة لبناء تفوق مادي.")
    board.push(move)
    if board.is_check():
        reasons_en.append("Delivers a direct check to the king.")
        reasons_ar.append("يضع ملك الخصم تحت التهديد المباشر.")
    board.pop()
    if not reasons_en:
        reasons_en.append("Improves general piece positioning and activity.")
        reasons_ar.append("يحسن تموضع ونشاط القطع.")
    return {"en": " ".join(reasons_en), "ar": " ".join(reasons_ar)}

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

diff_label = st.sidebar.select_slider("Engine Depth", options=["Beginner", "Intermediate", "Advanced"], value="Intermediate")
search_depth = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}[diff_label]

if st.sidebar.button("🔄 Reset Game", use_container_width=True):
    st.session_state.board = chess.Board()
    st.session_state.history = [chess.Board().fen()]
    st.session_state.move_records = []
    st.session_state.selected_square = None
    st.session_state.last_move = None
    st.session_state.coach_analysis = None
    st.rerun()

st.sidebar.markdown("---")
pgn_game = chess.pgn.Game.from_board(st.session_state.board)
st.sidebar.download_button("📥 Export PGN", data=str(pgn_game), file_name="chess_match.pgn", mime="text/plain", use_container_width=True)

# 6. Main Dashboard
is_ar = st.session_state.lang == "AR"
col_board, col_dash = st.columns([1.3, 1])

# Click Handler for SVG Square Selections
def handle_square_click(sq_name):
    board = st.session_state.board
    selected = st.session_state.selected_square

    if selected is None:
        sq_idx = chess.parse_square(sq_name)
        piece = board.piece_at(sq_idx)
        if piece and piece.color == board.turn:
            st.session_state.selected_square = sq_name
    else:
        move_uci = f"{selected}{sq_name}"
        try_move = chess.Move.from_uci(move_uci)
        if try_move not in board.legal_moves:
            try_move = chess.Move.from_uci(f"{move_uci}q")

        if try_move in board.legal_moves:
            p_eval = evaluate_board(board)
            san_str = board.san(try_move)
            sound = "capture" if board.is_capture(try_move) else "move"

            board.push(try_move)
            st.session_state.history.append(board.fen())
            st.session_state.last_move = try_move
            st.session_state.selected_square = None

            c_eval = evaluate_board(board)
            quality = classify_move(p_eval, c_eval)
            st.session_state.move_records.append({"san": san_str, "badge": f"{quality[2]} {quality[0]}"})

            play_sound(sound, audio_enabled)

            # Engine Bot Counter-Move
            if not board.is_game_over():
                _, ai_move = alpha_beta(board, search_depth, -float('inf'), float('inf'), board.turn == chess.WHITE)
                if ai_move:
                    ai_san = board.san(ai_move)
                    st.session_state.coach_analysis = {
                        "move": ai_move,
                        "explanation": generate_explanation(board, ai_move),
                        "quality": quality
                    }
                    board.push(ai_move)
                    st.session_state.history.append(board.fen())
                    st.session_state.last_move = ai_move
                    st.session_state.move_records.append({"san": ai_san, "badge": "🤖 Bot"})
            else:
                play_sound("game_over", audio_enabled)
        else:
            sq_idx = chess.parse_square(sq_name)
            piece = board.piece_at(sq_idx)
            if piece and piece.color == board.turn:
                st.session_state.selected_square = sq_name
            else:
                st.session_state.selected_square = None
    st.rerun()

with col_board:
    mat = get_captured(st.session_state.board)
    st.markdown(f"**🤖 {'الروبوت' if is_ar else 'Bot'}:** {mat['black']}")

    # Highlights for Coach Arrows
    arrows = []
    if st.session_state.coach_analysis and "move" in st.session_state.coach_analysis:
        rec_move = st.session_state.coach_analysis["move"]
        arrows = [chess.svg.Arrow(rec_move.from_square, rec_move.to_square, color="#00ff00cc")]

    # Render Visual SVG Board
    theme_colors = THEMES[theme_choice]
    board_svg = chess.svg.board(
        board=st.session_state.board,
        lastmove=st.session_state.last_move,
        arrows=arrows,
        colors={"square light": theme_colors["square_light"], "square dark": theme_colors["square_dark"]},
        size=420
    )
    st.image(board_svg, use_container_width=True)
    st.markdown(f"**👤 {'أنت' if is_ar else 'You'}:** {mat['white']}")

    # Interactive Touch/Click Grid Selector
    st.markdown("**Click pieces and squares to move:**")
    for rank in range(7, -1, -1):
        cols = st.columns(8)
        for file in range(8):
            sq_idx = chess.square(file, rank)
            sq_name = chess.square_name(sq_idx)
            piece = st.session_state.board.piece_at(sq_idx)
            piece_symbol = PIECE_SYMBOLS[piece.piece_type if piece.color == chess.WHITE else -piece.piece_type] if piece else "·"
            
            # Active selected square styling
            label = f"[{piece_symbol}]" if st.session_state.selected_square == sq_name else piece_symbol
            with cols[file]:
                if st.button(label, key=f"btn_{sq_name}"):
                    handle_square_click(sq_name)

    # Evaluation Score Bar
    curr_eval = evaluate_board(st.session_state.board)
    norm_eval = max(0.0, min(1.0, (curr_eval + 1000) / 2000))
    st.progress(norm_eval, text=f"Position Score: {curr_eval/100:+.2f}")

with col_dash:
    tab_coach, tab_history = st.tabs(["🎓 " + ("المدرب" if is_ar else "Coach"), "📜 " + ("سجل الحركات" if is_ar else "History")])

    with tab_coach:
        if st.button("💡 " + ("طلب نصيحة" if is_ar else "Ask Coach Best Move"), use_container_width=True):
            if not st.session_state.board.is_game_over():
                _, rec = alpha_beta(st.session_state.board, search_depth, -float('inf'), float('inf'), st.session_state.board.turn == chess.WHITE)
                if rec:
                    st.session_state.coach_analysis = {
                        "move": rec,
                        "explanation": generate_explanation(st.session_state.board, rec),
                        "quality": ("⭐ Recommended", "⭐ موصى به", "🟩")
                    }
                    st.rerun()

        if st.session_state.coach_analysis:
            an = st.session_state.coach_analysis
            st.metric("Recommended Move" if not is_ar else "الحركة الموصى بها", str(an['move']))
            if "quality" in an:
                st.info(f"**Move Classification:** {an['quality'][1 if is_ar else 0]}")
            st.success(f"**Explanation:** {an['explanation']['ar' if is_ar else 'en']}")

        if st.session_state.board.is_game_over():
            st.error("🏆 Game Over!")

    with tab_history:
        records = st.session_state.move_records
        if records:
            table = []
            for i in range(0, len(records), 2):
                w_item = records[i]
                b_item = records[i+1] if i+1 < len(records) else None
                table.append({
                    "#": (i//2) + 1,
                    "White": f"{w_item['san']} ({w_item['badge']})",
                    "Black": f"{b_item['san']} ({b_item['badge']})" if b_item else ""
                })
            st.dataframe(table, use_container_width=True, hide_index=True)