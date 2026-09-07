import chess
import chess.svg
import chess.pgn
import streamlit as st

# 1. Page Configuration
st.set_page_config(page_title="Bilingual AI Chess Coach Pro", layout="wide", page_icon="♟️")

# 2. Session State Initialization
if "board" not in st.session_state:
    st.session_state.board = chess.Board()
if "history" not in st.session_state:
    st.session_state.history = [chess.Board().fen()]
if "nav_index" not in st.session_state:
    st.session_state.nav_index = 0
if "last_move" not in st.session_state:
    st.session_state.last_move = None
if "coach_analysis" not in st.session_state:
    st.session_state.coach_analysis = None
if "lang" not in st.session_state:
    st.session_state.lang = "EN"
if "eval_history" not in st.session_state:
    st.session_state.eval_history = [0]

# 3. Audio Controller
def play_sound(sound_type, enabled):
    if not enabled:
        return
    sound_urls = {
        "move": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/move-self.mp3",
        "capture": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/capture.mp3",
        "check": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/move-check.mp3",
        "game_over": "https://images.chesscomfiles.com/chess-themes/sounds/_default/mp3/game-end.mp3"
    }
    url = sound_urls.get(sound_type)
    if url:
        st.components.v1.html(
            f"""
            <script>
                var audio = new Audio('{url}');
                audio.play().catch(function(e) {{ console.log("Audio block:", e); }});
            </script>
            """,
            height=0,
            width=0
        )

# 4. Openings Explorer Database
OPENINGS = {
    "e2e4 e7e5 g1f3 b8c6 f1b5": ("Ruy Lopez", "افتتاح روي لوبيز"),
    "e2e4 c7c5": ("Sicilian Defense", "الدفاع الصقلي"),
    "d2d4 d7d5 c2c4": ("Queen's Gambit", "جامبت الملكة"),
    "e2e4 e7e6": ("French Defense", "الدفاع الفرنسي"),
    "e2e4 c7c6": ("Caro-Kann Defense", "دفاع كارو-كان"),
    "g1f3 d7d5 g2g3": ("King's Indian Attack", "الهجوم الهندي للملك")
}

def detect_opening(board):
    moves_uci = " ".join([m.uci() for m in board.move_stack[:5]])
    for pattern, name in OPENINGS.items():
        if moves_uci.startswith(pattern):
            return name
    return ("Custom Opening", "افتتاح مخصص")

# 5. Engine & Evaluation System
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
    if board.is_stalemate() or board.is_insufficient_material():
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
    if diff >= 200: return ("‼️ Great Move", "‼️ حركة ممتازة")
    elif diff >= 0: return ("⭐ Best Move", "⭐ أفضل حركة")
    elif diff >= -150: return ("?! Inaccuracy", "?! عدم دقة")
    else: return ("?? Blunder", "?? خطأ فادح")

def generate_explanation(board, move):
    reasons_en, reasons_ar = [], []
    dest = move.to_square
    if dest in [chess.D4, chess.D5, chess.E4, chess.E5]:
        reasons_en.append("Controls the central squares.")
        reasons_ar.append("يفرض سيطرة على المربعات المركزية.")
    if board.is_capture(move):
        reasons_en.append("Captures material to build advantage.")
        reasons_ar.append("يستحوذ على قطعة لبناء تفوق مادي.")
    board.push(move)
    if board.is_check():
        reasons_en.append("Puts opponent king in check.")
        reasons_ar.append("يضع ملك الخصم تحت التهديد.")
    board.pop()
    if not reasons_en:
        reasons_en.append("Improves piece activity.")
        reasons_ar.append("يحسن نشاط القطعة.")
    return {"en": " ".join(reasons_en), "ar": " ".join(reasons_ar)}

# 6. Sidebar Controls
st.sidebar.header("⚙️ Options / الإعدادات")
st.session_state.lang = st.sidebar.radio("🌐 Language", ["EN", "AR"], index=0 if st.session_state.lang == "EN" else 1)
audio_enabled = st.sidebar.toggle("🔊 Sound Effects", value=True)

theme_choice = st.sidebar.selectbox("🎨 Board Theme", ["Classic Wood", "Lichess Green", "Midnight Dark"])
THEMES = {
    "Classic Wood": {"light": "#f0d9b5", "dark": "#b58863"},
    "Lichess Green": {"light": "#ffffdd", "dark": "#86a666"},
    "Midnight Dark": {"light": "#9e9e9e", "dark": "#424242"}
}

diff_label = st.sidebar.select_slider("Difficulty", options=["Beginner", "Intermediate", "Advanced"], value="Intermediate")
search_depth = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}[diff_label]

if st.sidebar.button("Reset Game"):
    st.session_state.board = chess.Board()
    st.session_state.history = [chess.Board().fen()]
    st.session_state.nav_index = 0
    st.session_state.last_move = None
    st.session_state.coach_analysis = None
    st.session_state.eval_history = [0]
    st.rerun()

st.sidebar.markdown("---")
pgn_game = chess.pgn.Game.from_board(st.session_state.board)
st.sidebar.download_button("Download PGN", data=str(pgn_game), file_name="match.pgn", mime="text/plain")

# 7. Main Dashboard
is_ar = st.session_state.lang == "AR"
st.title("♟️ " + ("مدرب الشطرنج الذكي" if is_ar else "Bilingual AI Chess Coach Pro"))

# Opening Banner
op_en, op_ar = detect_opening(st.session_state.board)
st.caption(f"📖 **Opening:** {op_ar if is_ar else op_en}")

col_board, col_dash = st.columns([1.3, 1])

with col_board:
    mat = get_captured(st.session_state.board)
    st.markdown(f"**🤖 {'الربوت' if is_ar else 'Bot'}:** {mat['black']}")

    # Render Active Board State based on Nav Index
    display_board = chess.Board(st.session_state.history[st.session_state.nav_index])
    board_svg = chess.svg.board(
        board=display_board,
        lastmove=st.session_state.last_move,
        colors=THEMES[theme_choice],
        size=420
    )
    st.image(board_svg, use_container_width=True)
    st.markdown(f"**👤 {'أنت' if is_ar else 'You'}:** {mat['white']}")

    # Evaluation Bar
    curr_eval = evaluate_board(st.session_state.board)
    norm_eval = max(0.0, min(1.0, (curr_eval + 1000) / 2000))
    st.progress(norm_eval, text=f"Eval Score: {curr_eval/100:+.2f}")

    # Move Navigation Timeline
    c1, c2, c3, c4 = st.columns(4)
    if c1.button("⏮️ First") and st.session_state.history:
        st.session_state.nav_index = 0
        st.rerun()
    if c2.button("◀️ Back") and st.session_state.nav_index > 0:
        st.session_state.nav_index -= 1
        st.rerun()
    if c3.button("Next ▶️") and st.session_state.nav_index < len(st.session_state.history) - 1:
        st.session_state.nav_index += 1
        st.rerun()
    if c4.button("Latest ⏭️") and st.session_state.history:
        st.session_state.nav_index = len(st.session_state.history) - 1
        st.rerun()

    # Move Submission Controls
    if not st.session_state.board.is_game_over():
        st.markdown("### " + ("نفذ حركتك" if is_ar else "Make Your Move"))
        squares = [chess.square_name(sq) for sq in chess.SQUARES]
        col_f, col_t = st.columns(2)
        with col_f:
            from_sq = st.selectbox("From:", ["-- Select --"] + sorted(squares), key="f_sq")
        with col_t:
            to_sq = st.selectbox("To:", ["-- Select --"] + sorted(squares), key="t_sq")

        if st.button("Play Move" if not is_ar else "تنفيذ الحركة", type="primary", use_container_width=True):
            if from_sq != "-- Select --" and to_sq != "-- Select --":
                uci_str = f"{from_sq}{to_sq}"
                try_move = chess.Move.from_uci(uci_str)
                if try_move not in st.session_state.board.legal_moves:
                    try_move = chess.Move.from_uci(f"{uci_str}q")

                if try_move in st.session_state.board.legal_moves:
                    p_eval = evaluate_board(st.session_state.board)
                    sound = "capture" if st.session_state.board.is_capture(try_move) else "move"
                    
                    st.session_state.board.push(try_move)
                    st.session_state.history.append(st.session_state.board.fen())
                    st.session_state.nav_index = len(st.session_state.history) - 1
                    st.session_state.last_move = try_move
                    
                    c_eval = evaluate_board(st.session_state.board)
                    quality = classify_move(p_eval, c_eval)
                    
                    play_sound(sound, audio_enabled)

                    # Engine Counter-Move
                    if not st.session_state.board.is_game_over():
                        _, ai_move = alpha_beta(st.session_state.board, search_depth, -float('inf'), float('inf'), st.session_state.board.turn == chess.WHITE)
                        if ai_move:
                            st.session_state.coach_analysis = {
                                "move": ai_move,
                                "explanation": generate_explanation(st.session_state.board, ai_move),
                                "quality": quality
                            }
                            st.session_state.board.push(ai_move)
                            st.session_state.history.append(st.session_state.board.fen())
                            st.session_state.nav_index = len(st.session_state.history) - 1
                            st.session_state.last_move = ai_move
                    else:
                        play_sound("game_over", audio_enabled)
                    st.rerun()

with col_dash:
    st.subheader("🎓 " + ("لوحة التحليل التكتيكي" if is_ar else "Tactical Coach"))

    if st.button("💡 " + ("طلب نصيحة المدرب" if is_ar else "Ask Coach"), use_container_width=True):
        if not st.session_state.board.is_game_over():
            _, rec = alpha_beta(st.session_state.board, search_depth, -float('inf'), float('inf'), st.session_state.board.turn == chess.WHITE)
            if rec:
                st.session_state.coach_analysis = {
                    "move": rec,
                    "explanation": generate_explanation(st.session_state.board, rec),
                    "quality": ("⭐ Recommended", "⭐ موصى به")
                }
                st.rerun()

    if st.session_state.coach_analysis:
        an = st.session_state.coach_analysis
        st.success(f"**{'الحركة الموصى بها' if is_ar else 'Recommended Move'}:** {an['move']}")
        if "quality" in an:
            st.warning(f"**{'تقييم الحركة' if is_ar else 'Move Quality'}:** {an['quality'][1 if is_ar else 0]}")
        st.info(f"**Explanation:** {an['explanation']['ar' if is_ar else 'en']}")

    # Match Report
    if st.session_state.board.is_game_over():
        st.error("🏆 Game Over!")
        if st.session_state.board.is_checkmate():
            st.write("Result: Checkmate!")
        else:
            st.write("Result: Draw / Stalemate")

    st.markdown("---")
    st.subheader("📜 " + ("سجل الحركات" if is_ar else "Move History"))
    move_stack = list(st.session_state.board.move_stack)
    if move_stack:
        san_moves = []
        tb = chess.Board()
        for m in move_stack:
            san_moves.append(tb.san(m))
            tb.push(m)
        table = []
        for i in range(0, len(san_moves), 2):
            table.append({"#": (i//2)+1, "White": san_moves[i], "Black": san_moves[i+1] if i+1 < len(san_moves) else ""})
        st.dataframe(table, use_container_width=True, hide_index=True)