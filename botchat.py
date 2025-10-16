# ============ PHẦN 1/?? — KHÔNG TRẢ LỜI GÌ KHI CHƯA COPY XONG ============

from flask import Flask, request, send_from_directory
import requests, os, random, time, re
from gtts import gTTS

app = Flask(__name__)

# ========= ENV =========
VERIFY_TOKEN       = os.getenv("VERIFY_TOKEN", "0916659939")
PAGE_ACCESS_TOKEN  = os.getenv("PAGE_ACCESS_TOKEN", "EAATHSZCmQwQ8BPqHzs2KB1D6L3KSd0sv3ZB9ZBbJkb9Eg9884jDta84hHqiFUuOZCEeKZA1eTgNjd723u3tycEafmuskplrgPuFDZBC4vRZBZCijxEMbxZCVdPlOztZB3bQrBcMwFWJf9c0KRUJIbQm7LCKpNpKEaL4e0KrooBrcfIMKZCFF6ChxsNjdDWDfQiSD459IRdMOjMwZBQZDZD")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
PUBLIC_HOSTNAME    = os.getenv("PUBLIC_HOSTNAME", "https://messenger-2-mui1.onrender.com")

os.makedirs("voices", exist_ok=True)

def host_base() -> str:
    base = (PUBLIC_HOSTNAME or os.environ.get("RENDER_EXTERNAL_HOSTNAME") or "").strip()
    if base and not base.startswith("http"):
        base = f"https://{base}"
    if base.endswith("/"):
        base = base[:-1]
    return base

def log(*args):
    print("🪵", *args, flush=True)

@app.route("/", methods=["GET"])
def home():
    return "✅ Messenger Emotion Bot is running! (AI + Voice + Stickers)", 200

@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Xác minh thất bại", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json(silent=True, force=True)
    log("Received webhook:", data)

    if not data or data.get("object") != "page":
        return "ok", 200

    for entry in data.get("entry", []):
        for event in entry.get("messaging", []):
            if "message" in event:
                sender_id = event["sender"]["id"]
                msg       = event["message"]
                text      = msg.get("text", "") or ""
                attachments = msg.get("attachments", [])
                # 1) Sticker / Emoji
                if is_sticker_message(msg) or looks_like_emoji_only(text):
                    reply = reply_for_sticker_or_emoji(msg, text)
                    send_message(sender_id, reply)
                    if should_send_voice(reply):
                        send_voice(sender_id, reply)
                    continue

                # 2) Chào hỏi đơn giản
                if is_plain_greeting(text):
                    reply = "Chào gì mà chào, hỏi lẹ đi tôi còn bận 😆"
                    send_message(sender_id, reply)
                    if should_send_voice(reply):
                        send_voice(sender_id, reply)
                    continue

                # 3) Ai tạo / giới thiệu
                if asks_who_made(text) or asks_who_you_are(text):
                    reply = "Tôi là trợ lý của *Lý Quang Diệu*, thành viên của Facebook Developers Việt Nam."
                    send_message(sender_id, reply)
                    if should_send_voice(reply):
                        send_voice(sender_id, reply)
                    continue

                # 4) Nếu hỏi ảnh
                image_url = None
                if mentions_image(text):
                    image_url = pick_fun_image()

                # 5) Phân tích cảm xúc
                mood = detect_mood(text)
                log(f"Mood => {mood}")

                reply_text = generate_reply(text, mood)

                send_message(sender_id, reply_text, image_url=image_url)

                # 6) Voice
                if should_send_voice(reply_text):
                    send_voice(sender_id, reply_text)

    return "ok", 200
# Phục vụ file voice
@app.route("/voices/<path:filename>", methods=["GET"])
def serve_voice(filename):
    return send_from_directory("voices", filename, as_attachment=False)

# ========= NHẬN DIỆN =========
GREETINGS = {"hi", "hello", "chào", "alo", "hí", "helo", "hế lô", "yo", "hii", "ê"}

INSULT_WORDS = ["ngu", "đần", "khùng", "điên", "óc chó", "vô dụng", "bố láo", "láo", "hỗn"]

SAD_WORDS = ["buồn", "chán", "mệt", "khó chịu", "tệ quá", "stress", "căng thẳng", "tuyệt vọng"]

def is_plain_greeting(text: str) -> bool:
    t = normalize(text)
    return t in GREETINGS

def asks_who_made(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ["ai tạo", "who made", "ai làm", "ai lập trình", "ai build"])

def asks_who_you_are(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ["mày là ai", "bạn là ai", "who are you", "giới thiệu"])

def mentions_image(text: str) -> bool:
    t = normalize(text)
    return any(k in t for k in ["ảnh", "hình", "photo", "image", "picture"])

def looks_like_emoji_only(text: str) -> bool:
    if not text:
        return False
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
def normalize(s: str) -> str:
    return (s or "").strip().lower()

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
# ========= OPENROUTER REPLY =========
def generate_reply(user_text: str, mood: str) -> str:
    bp, ut = choose_pronouns(mood)

    if not OPENROUTER_API_KEY:
        if mood == "insult":
            return f"Ê nói chuyện đàng hoàng nha 😤 {bp} không phải cái thùng rác cho {ut} xả đâu!"
        if mood == "sad":
            return f"Nè {ut}, ai làm {ut} buồn vậy? Kể {bp} nghe đi 🥺"
        return f"Ờ {ut}, {bp} nghe nè — muốn gì nói lẹ đi 😏"

    style = {
        "insult":   f"mắng yêu nhưng không tục; xưng '{bp}', gọi '{ut}'; gắt mà vui 😤",
        "sad":      f"vỗ về nhẹ nhàng; xưng '{bp}', gọi '{ut}'; có emoji 🥺",
        "polite":   f"trả lời lịch sự, tôn trọng; xưng '{bp}', gọi '{ut}' 🤝",
        "friendly": f"vui vẻ thân mật; xưng '{bp}', gọi '{ut}' 😆",
        "playful":  f"cà khịa nhẹ; xưng '{bp}', gọi '{ut}' 😏"
    }.get(mood, "thân thiện ngắn gọn")

    system_prompt = (
        "Bạn là trợ lý AI người Việt có cảm xúc (giọng nam), biết mắng yêu và cà khịa đúng lúc, "
        "nhưng KHÔNG chửi tục nặng. Luôn trả lời ngắn gọn, tự nhiên, có emoji. "
        "Nếu chào hỏi đơn giản → dùng 'Chào gì mà chào, hỏi lẹ đi tôi còn bận 😆'. "
        "Nếu hỏi nguồn gốc → 'Tôi là trợ lý của *Lý Quang Diệu*, thành viên của Facebook Developers Việt Nam.'"
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
        "X-Title": "Messenger Emotion Bot"
    }

    try:
        r = requests.post("https://openrouter.ai/api/v1/chat/completions", json=payload, headers=headers, timeout=20)
        if r.status_code == 200:
            return r.json()["choices"][0]["message"]["content"].strip()
        else:
            return f"{bp} bận tí rồi, {ut} hỏi lại sau nha 😅"
    except:
        return f"{bp} lỗi nhẹ rồi, {ut} đợi xíu nghen 🥲"
# ========= IMAGE =========
def pick_fun_image() -> str:
    return random.choice([
        "https://source.unsplash.com/random/800x500?smile",
        "https://source.unsplash.com/random/800x500?funny",
        "https://source.unsplash.com/random/800x500?friendship",
        "https://source.unsplash.com/random/800x500?food",
        "https://source.unsplash.com/random/800x500?cat"
    ])

# ========= VOICE (chỉ 1 giọng, không prefix, nhanh) =========
def create_voice_file(text: str) -> str | None:
    ts = int(time.time() * 1000)
    filename = f"voices/voice_{ts}.mp3"
    try:
        tts = gTTS(text, lang='vi', slow=False)  # Giọng nhanh, không prefix
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
# ========= MESSAGE SENDER =========
def send_message(recipient_id: str, message_text: str, image_url: str | None = None):
    fb_url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"

    # Gửi ảnh nếu có
    if image_url:
        img_payload = {
            "recipient": {"id": recipient_id},
            "message": {
                "attachment": {
                    "type": "image",
                    "payload": {"url": image_url, "is_reusable": True}
                }
            }
        }
        try:
            ri = requests.post(fb_url, json=img_payload, timeout=15)
            log("send_image:", ri.status_code, ri.text[:200])
        except Exception as e:
            log("send_image EXC:", e)

    # Gửi text
    text_payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    try:
        r = requests.post(fb_url, json=text_payload, timeout=15)
        log("send_message:", r.status_code, r.text[:200])
    except Exception as e:
        log("send_message EXC:", e)

# ========= RUN APP =========
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    log(f"Starting Flask on 0.0.0.0:{port} | PUBLIC_HOSTNAME={host_base()}")
    app.run(host="0.0.0.0", port=port)

# ⚠️ HẾT CODE


