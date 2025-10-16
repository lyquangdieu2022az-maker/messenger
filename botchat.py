# ================= Messenger Emotion Bot V4 (AI + Voice + Vision + Maps) =================
# - ENV-based (KHÔNG chứa key trong file)
# - Giọng nam nhanh (gTTS)
# - Cà khịa/mắng yêu theo cảm xúc
# - Vision (GPT-4o) giải bài tập từ ảnh
# - Google Maps API trả địa điểm (kiểu cà khịa mạnh)
# - Quy tắc xưng hô ưu tiên theo cách user gọi: mày↔tao, bạn↔tôi, anh↔em, ông/chú/bác↔con/cháu
# - Nếu không rõ cách xưng hô → C (mặc định theo mood)

from flask import Flask, request, send_from_directory
import requests, os, random, time, re
from gtts import gTTS

# ---------- APP ----------
app = Flask(__name__)
os.makedirs("voices", exist_ok=True)

# ---------- ENV ----------
VERIFY_TOKEN         = os.getenv("VERIFY_TOKEN", "")
PAGE_ACCESS_TOKEN    = os.getenv("PAGE_ACCESS_TOKEN", "")
OPENROUTER_API_KEY   = os.getenv("OPENROUTER_API_KEY", "")
GOOGLE_MAPS_API_KEY  = os.getenv("GOOGLE_MAPS_API_KEY", "")
PUBLIC_HOSTNAME      = os.getenv("PUBLIC_HOSTNAME", "")

# ---------- UTILS ----------
def host_base() -> str:
    base = (PUBLIC_HOSTNAME or os.environ.get("RENDER_EXTERNAL_HOSTNAME") or "").strip()
    if base and not base.startswith("http"):
        base = f"https://{base}"
    if base.endswith("/"):
        base = base[:-1]
    return base

def log(*args):
    print("🪵", *args, flush=True)

def normalize(s: str) -> str:
    return (s or "").strip().lower()

# ---------- ROUTES BASIC ----------
@app.route("/", methods=["GET"])
def home():
    return "✅ Messenger Emotion Bot V4 (AI + Voice + Vision + Maps)", 200

@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token and token == VERIFY_TOKEN:
        return challenge
    return "Xác minh thất bại", 403

# ---------- SERVE VOICE ----------
@app.route("/voices/<path:filename>", methods=["GET"])
def serve_voice(filename):
    return send_from_directory("voices", filename, as_attachment=False)

# ============================== NLP RULES ==============================

GREETINGS = {"hi", "hello", "chào", "alo", "hí", "helo", "hế lô", "yo", "hii", "ê"}

INSULT_WORDS = ["ngu", "đần", "khùng", "điên", "óc chó", "vô dụng", "bố láo", "láo", "hỗn"]
SAD_WORDS    = ["buồn", "chán", "mệt", "khó chịu", "tệ quá", "stress", "căng thẳng", "tuyệt vọng"]

ADDRESS_TRIGGERS = [
    "ở đâu", "địa chỉ", "map", "bản đồ", "chỉ đường", "tới đâu", "đi tới", "gần nhất",
    "đường nào", "định vị", "location", "address", "where"
]

def is_plain_greeting(text: str) -> bool:
    return normalize(text) in GREETINGS

def is_address_query(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ADDRESS_TRIGGERS) and len(t) >= 3

def extract_place_query(text: str) -> str:
    t = normalize(text)
    for cut in [" ở đâu", " dia chi", " địa chỉ", " map", " bản đồ", " chi duong", " chỉ đường"]:
        if cut in t:
            return t.replace(cut, "").strip()
    return t.strip()

def asks_who_made(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ["ai tạo", "who made", "ai làm", "ai lập trình", "ai build"])

def asks_who_you_are(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ["mày là ai", "bạn là ai", "who are you", "giới thiệu"])

def looks_like_emoji_only(text: str) -> bool:
    if not text: return False
    stripped = text.strip()
    emoji_pat = r"^[\u2600-\u27BF\U0001F300-\U0001FAFF]+$"
    try:
        return re.match(emoji_pat, stripped)
    except:
        return False

def is_sticker_message(msg: dict) -> bool:
    for a in msg.get("attachments", []):
        if a.get("type") == "image" and a.get("payload", {}).get("sticker_id"):
            return True
    return bool(msg.get("sticker_id"))

def reply_for_sticker_or_emoji(msg: dict, text: str) -> str:
    return random.choice([
        "Cười gì mà cười 😏", "Vỗ tay cho tao à 😎", "Gửi icon chi dzị 🤨",
        "Được lắm, icon chất 😆", "Thả sticker dữ ha 🤭"
    ])

def mentions_image(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ["ảnh", "hình", "photo", "image", "picture", "gửi hình"])

# ---------- Pronoun override theo cách user gọi ----------
def detect_addressing(text: str):
    """
    Trả về (bot_pronoun, user_pronoun) nếu phát hiện được xưng hô.
    Ưu tiên:
      - user dùng 'mày' → bot 'tao', user 'mày'
      - user dùng 'bạn' → bot 'tôi', user 'bạn'
      - user gọi 'anh'  → bot 'em',  user 'anh'
      - user gọi 'ông/chú/bác' → bot 'con' (hoặc 'cháu'), user giữ nguyên
    Không phát hiện → trả về None
    """
    t = f" {normalize(text)} "
    # “mày” / “mầy”
    if " mày " in t or " mầy " in t or " mi " in t:
        return ("tao", "mày")
    # “bạn”
    if " bạn " in t or t.endswith(" bạn") or t.startswith("bạn "):
        return ("tôi", "bạn")
    # “anh”
    if " anh " in t or t.startswith("anh "):
        return ("em", "anh")
    # “ông/chú/bác”
    for elder in ["ông", "chú", "bác"]:
        if f" {elder} " in t or t.startswith(elder + " "):
            return ("con", elder)
    return None

# ============================== AI TEXT ==============================

def detect_mood(text: str) -> str:
    t = normalize(text)
    if any(w in t for w in INSULT_WORDS):
        return "insult"
    if any(w in t for w in SAD_WORDS):
        return "sad"
    if any(p in t for p in ["xin", "làm ơn", "vui lòng", "cảm ơn"]):
        return "polite"
    if any(k in t for k in ["hay quá", "tuyệt", "đỉnh", "xịn", "yêu"]):
        return "friendly"
    return "playful"

def choose_pronouns(mood: str):
    # Mặc định theo mood (áp dụng khi KHÔNG phát hiện xưng hô rõ)
    bot = {
        "insult": ["tao", "tui"],
        "sad":    ["em", "tui"],
        "polite": ["em", "tui"],
        "friendly":["tui", "em"],
        "playful":["tao", "tui", "em"],
    }.get(mood, ["tui"])
    user = {
        "insult": ["mày", "bạn"],
        "sad":    ["bạn", "anh", "chị"],
        "polite": ["anh", "chị", "bạn", "sếp"],
        "friendly":["bạn", "anh", "chị", "người iu"],
        "playful":["mày", "bạn", "anh", "chị"],
    }.get(mood, ["bạn"])
    return random.choice(bot), random.choice(user)

def generate_reply(user_text: str, mood: str) -> str:
    # Ưu tiên override theo cách user gọi
    override = detect_addressing(user_text)
    if override:
        bp, ut = override
    else:
        bp, ut = choose_pronouns(mood)

    if not OPENROUTER_API_KEY:
        if mood == "insult":
            return f"Ê nói chuyện đàng hoàng nha 😤 {bp} không phải cái thùng cho {ut} xả đâu!"
        if mood == "sad":
            return f"Nè {ut}, ai làm {ut} buồn vậy? Kể {bp} nghe đi 🥺"
        return f"Ờ {ut}, {bp} nghe nè — muốn gì nói lẹ đi 😏"

    style = {
        "insult":   f"mắng yêu nhưng không tục; xưng '{bp}', gọi '{ut}'; gắt mà vui 😤",
        "sad":      f"vỗ về nhẹ nhàng; xưng '{bp}', gọi '{ut}' 🥺",
        "polite":   f"lịch sự, tôn trọng; xưng '{bp}', gọi '{ut}' 🤝",
        "friendly": f"vui vẻ thân mật; xưng '{bp}', gọi '{ut}' 😆",
        "playful":  f"cà khịa nhẹ; xưng '{bp}', gọi '{ut}' 😏"
    }.get(mood, "thân thiện ngắn gọn")

    system_prompt = (
        "Bạn là trợ lý AI người Việt có cảm xúc (giọng nam), biết mắng yêu/cà khịa đúng lúc, "
        "nhưng KHÔNG chửi tục nặng. Luôn trả lời ngắn gọn, tự nhiên, có emoji. "
        "Nếu hỏi nguồn gốc → 'Tao là trợ lý của *Lý Quang Diệu*, thành viên Facebook Developers Việt Nam.'"
    )

    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": f"Phong cách hiện tại: {style}"},
            {"role": "user", "content": user_text}
        ],
        "temperature": 0.7,
        "max_tokens": 200
    }
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://openrouter.ai",
        "X-Title": "Messenger Emotion Bot V4"
    }
    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"{bp} bận tí, {ut} hỏi lại sau 😅"
    except Exception:
        return f"{bp} lỗi nhẹ rồi, {ut} đợi xíu nghen 🥲"

# ============================== VISION (GPT-4o) ==============================

HOMEWORK_KEYWORDS = [
    "giải phương trình", "tính", "chứng minh", "rút gọn", "đạo hàm", "tích phân", "lim", "giới hạn",
    "tam giác", "hình tròn", "parabol", "vector", "ma trận", "cộng trừ nhân chia",
    "hoá học", "phương trình hoá học", "phân tử", "mol", "nồng độ",
    "dịch", "ngữ pháp", "viết lại câu", "chọn đáp án đúng", "điền vào chỗ trống"
]
MATH_TOKENS = r"[0-9\=\+\-\×\*\/\^√∑∫π≈≤≥<>:\(\)]"

def is_likely_homework(text: str) -> bool:
    t = (text or "").lower()
    if any(k in t for k in HOMEWORK_KEYWORDS):
        return True
    has_math = re.search(MATH_TOKENS, t) is not None
    many_words = len(t.split()) >= 6
    return has_math and many_words

def call_openrouter_vision(image_url: str, instruction: str, max_tokens: int = 900) -> str:
    if not OPENROUTER_API_KEY:
        return "Thiếu OPENROUTER_API_KEY nên không dùng Vision được."
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://openrouter.ai",
        "X-Title": "Messenger Vision Solver",
    }
    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": (
                    "Bạn là gia sư Việt Nam phong cách 😎, giải bài tập CHÍNH XÁC, từng bước, rõ ràng, dễ hiểu. "
                    "Chỉ trình bày lời giải, không lan man. Nếu không phải bài tập thì mô tả ngắn và hài hước."
                )
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instruction},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        return f"(Vision lỗi {r.status_code})"
    except Exception as e:
        return f"(Vision exception: {e})"

def solve_problem_from_image(image_url: str) -> tuple[str, bool]:
    describe = call_openrouter_vision(
        image_url,
        "Nhận dạng nội dung ảnh. Nếu là bài tập thì trích nguyên văn đề. Nếu không phải bài tập thì mô tả.",
        max_tokens=400
    )
    log("Vision describe:", (describe or "")[:200])
    hw = is_likely_homework(describe)

    if hw:
        instruction = (
            "Đây là ảnh bài tập. Hãy GIẢI TỪNG BƯỚC chi tiết, đánh số Bước 1, Bước 2... "
            "Dùng ký hiệu Toán/Lý/Hóa chuẩn. Cuối cùng kết luận rõ ràng. "
            "Nếu thiếu dữ liệu thì nêu giả định hợp lý, KHÔNG bịa số. Chỉ trả lời phần giải."
        )
        solution = call_openrouter_vision(image_url, instruction, max_tokens=950)
        if not solution or "(Vision" in solution:
            return ("Ảnh mờ quá, mày chụp lại coi 😑", True)
        reply = f"Bài này dễ như ăn cháo 😎\n\n{solution}"
        return (reply, True)
    else:
        fun_lines = [
            "Ảnh này nhìn cũng được đó bạn 😆",
            "Gửi tấm này là muốn tao khen hay muốn tao troll nè? 🤭",
            "Tấm này mà đăng lên chắc cháy tương tác á bạn 😎",
            "Ảnh này vibe ổn á, muốn tao phân tích hay ngắm thôi? 👀",
        ]
        desc = describe if describe and "Vision" not in describe else "Ảnh này có vẻ không phải bài tập."
        reply = f"{random.choice(fun_lines)}\n\nTao thấy nè:\n{desc}"
        return (reply, False)

# ============================== GOOGLE MAPS ==============================

def maps_text_search(query: str) -> dict | None:
    if not GOOGLE_MAPS_API_KEY:
        return None
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {"query": query, "key": GOOGLE_MAPS_API_KEY, "language": "vi"}
    try:
        r = requests.get(url, params=params, timeout=12)
        data = r.json()
        if data.get("status") in ("OK", "ZERO_RESULTS"):
            results = data.get("results", [])
            return results[0] if results else None
        return None
    except Exception as e:
        log("Maps text search error:", e)
        return None

def maps_link_from_place(place: dict) -> str:
    pid = place.get("place_id")
    if pid:
        return f"https://www.google.com/maps/place/?q=place_id:{pid}"
    loc = place.get("geometry", {}).get("location", {})
    if loc.get("lat") and loc.get("lng"):
        return f"https://maps.google.com/?q={loc['lat']},{loc['lng']}"
    return "https://maps.google.com"

def format_place_reply(place: dict) -> str:
    name = place.get("name", "Địa điểm")
    addr = place.get("formatted_address", "Không rõ địa chỉ")
    rating = place.get("rating")
    link = maps_link_from_place(place)
    head = "Muốn gặp tao hả? 😏"  # Kiểu 2 cà khịa mạnh
    rate = f" · ⭐ {rating}/5" if rating else ""
    return f"{head}\n{name}{rate}\n📍 {addr}\n👉 Chui vô đây rồi tự mò tới nha: {link}"

# ============================== IMAGE PICKER & VOICE ==============================

def pick_fun_image() -> str:
    return random.choice([
        "https://source.unsplash.com/random/800x500?smile",
        "https://source.unsplash.com/random/800x500?funny",
        "https://source.unsplash.com/random/800x500?friendship",
        "https://source.unsplash.com/random/800x500?food",
        "https://source.unsplash.com/random/800x500?cat"
    ])

def create_voice_file(text: str) -> str | None:
    ts = int(time.time() * 1000)
    filename = f"voices/voice_{ts}.mp3"
    try:
        tts = gTTS(text, lang='vi', slow=False)
        tts.save(filename)
        log("TTS saved:", filename)
        return filename
    except Exception as e:
        log("gTTS error:", e)
        return None

def send_voice(recipient_id: str, text: str):
    fname = create_voice_file(text)
    if not fname:
        return
    base = host_base()
    if not base:
        log("⚠️ Chưa thiết lập PUBLIC_HOSTNAME")
        return
    voice_url = f"{base}/voices/{os.path.basename(fname)}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"attachment": {"type": "audio", "payload": {"url": voice_url}}}
    }
    fb_url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    try:
        r = requests.post(fb_url, json=payload, timeout=15)
        log("send_voice:", r.status_code, r.text[:200])
    except Exception as e:
        log("send_voice EXC:", e)

def should_send_voice(reply_text: str) -> bool:
    return any(k in reply_text for k in ["😆", "🥺", "😤", "😏", "❤️", "😂", "😅"]) or len(reply_text) >= 20

# ============================== SENDER ==============================

def send_message(recipient_id: str, message_text: str, image_url: str | None = None):
    fb_url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    if image_url:
        img_payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {"type": "image", "payload": {"url": image_url, "is_reusable": True}}
            }
        }
        try:
            ri = requests.post(fb_url, json=img_payload, timeout=15)
            log("send_image:", ri.status_code, ri.text[:200])
        except Exception as e:
            log("send_image EXC:", e)

    text_payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    try:
        r = requests.post(fb_url, json=text_payload, timeout=15)
        log("send_message:", r.status_code, r.text[:200])
    except Exception as e:
        log("send_message EXC:", e)

# ============================== WEBHOOK (POST) ==============================

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True, force=True)
    log("Received webhook:", data)

    if not data or data.get("object") != "page":
        return "ok", 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            if "message" in event:
                sender_id  = event["sender"]["id"]
                msg        = event["message"]
                text       = msg.get("text", "") or ""
                attachments= msg.get("attachments", [])

                # 1) Ảnh → Vision
                if attachments:
                    first = attachments[0]
                    if first.get("type") == "image":
                        image_url = first.get("payload", {}).get("url")
                        if image_url:
                            log("📷 Ảnh nhận được:", image_url)
                            vision_reply, is_hw = solve_problem_from_image(image_url)
                            send_message(sender_id, vision_reply)
                            if should_send_voice(vision_reply):
                                send_voice(sender_id, vision_reply)
                            continue

                # 2) Địa chỉ / Maps
                if is_address_query(text):
                    if not GOOGLE_MAPS_API_KEY:
                        send_message(sender_id, "Thiếu GOOGLE_MAPS_API_KEY nên tao chưa tra map được 😿")
                        continue
                    q = extract_place_query(text)
                    log("📍 Địa điểm đang hỏi:", q)
                    place = maps_text_search(q if q else text)
                    if not place:
                        send_message(sender_id, "Hỏi gì mơ hồ quá 😑 ghi rõ tên địa điểm đi, ví dụ: 'Bệnh viện Chợ Rẫy ở đâu'.")
                        continue
                    reply = format_place_reply(place)
                    send_message(sender_id, reply)
                    if should_send_voice(reply):
                        send_voice(sender_id, reply)
                    continue

                # 3) Sticker / Emoji
                if is_sticker_message(msg) or looks_like_emoji_only(text):
                    reply = reply_for_sticker_or_emoji(msg, text)
                    send_message(sender_id, reply)
                    if should_send_voice(reply):
                        send_voice(sender_id, reply)
                    continue

                # 4) Greeting
                if is_plain_greeting(text):
                    reply = "Chào gì mà chào, hỏi lẹ đi tao còn bận 😆"
                    send_message(sender_id, reply)
                    if should_send_voice(reply):
                        send_voice(sender_id, reply)
                    continue

                # 5) Ai tạo / Giới thiệu
                if asks_who_made(text) or asks_who_you_are(text):
                    reply = "Tao là trợ lý của *Lý Quang Diệu*, thành viên Facebook Developers Việt Nam."
                    send_message(sender_id, reply)
                    if should_send_voice(reply):
                        send_voice(sender_id, reply)
                    continue

                # 6) Người dùng muốn ảnh ngẫu nhiên
                if mentions_image(text):
                    send_message(sender_id, "Cho mày tấm hình nè 😎", image_url=pick_fun_image())
                    continue

                # 7) Mặc định → AI text
                mood = detect_mood(text)
                reply = generate_reply(text, mood)
                send_message(sender_id, reply)
                if should_send_voice(reply):
                    send_voice(sender_id, reply)

    return "ok", 200

# ============================== RUN ==============================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    log(f"Starting Flask on 0.0.0.0:{port} | PUBLIC_HOSTNAME={host_base()}")
    app.run(host="0.0.0.0", port=port)

