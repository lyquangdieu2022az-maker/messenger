from flask import Flask, request, send_from_directory
import requests, os, random, time
from gtts import gTTS

app = Flask(__name__)

# ====== CẤU HÌNH ======
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "0916659939")
PAGE_ACCESS_TOKEN = os.getenv("EAATHSZCmQwQ8BPhPGgRwoQgMhzoZAAcnbQkXZBZCtZBMtPQFCri06o50bM9XCm0A3VNpx0UzI5v0jbW1QwxddQZC7iZA8w2w3jk1lHDU0qhOQo6ZA1AgWXe7XRw5EZBNnSkhSI0U1W4H0h8LzbjZC9Jl1ak9yrXCZA1m5c7yb7i02uqAQKvLwH2Oe4tQcZB0t57Xnxg01b5MCwkxugZDZD")
OPENROUTER_API_KEY = os.getenv("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")
os.makedirs("voices", exist_ok=True)
# ======================

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot Messenger cảm xúc + giọng 3 miền đang hoạt động!", 200

@app.route("/webhook", methods=['GET'])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Xác minh thất bại", 403

@app.route("/webhook", methods=['POST'])
def webhook():
    data = request.get_json()
    print("📩 Received:", data)

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                if "message" in event:
                    sender_id = event["sender"]["id"]
                    user_message = event["message"].get("text", "")

                    # Trả lời khi hỏi ai tạo
                    if any(kw in user_message.lower() for kw in ["ai tạo", "ai làm", "ai lập trình", "ai viết", "ai tạo ra mày"]):
                        reply = ("Tôi được tạo ra bởi **Lý Quang Diệu** — "
                                 "thành viên **Facebook Developers Việt Nam**, "
                                 "được cấp phép hoạt động tại **Facebook** và **Messenger** 💼✨")
                        send_message(sender_id, reply)
                        send_voice(sender_id, reply, "nam")  # mặc định Nam
                        continue

                    # Gọi AI trả lời
                    reply_text = get_ai_reply(user_message)

                    # Kiểm tra cần gửi ảnh
                    image_url = None
                    if any(word in user_message.lower() for word in ["ảnh", "hình", "hình ảnh"]):
                        image_url = random.choice([
                            "https://source.unsplash.com/random/600x400?smile",
                            "https://source.unsplash.com/random/600x400?funny",
                            "https://source.unsplash.com/random/600x400?love",
                            "https://source.unsplash.com/random/600x400?friendship"
                        ])

                    # Gửi text + ảnh + voice (chọn miền ngẫu nhiên)
                    send_message(sender_id, reply_text, image_url)
                    voice_style = random.choice(["bac","trung","nam"])
                    send_voice(sender_id, reply_text, voice_style)

    return "ok", 200

# ---------- Gọi AI OpenRouter ----------
def get_ai_reply(user_message):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://openrouter.ai",
        "X-Title": "Messenger Emotion Bot",
    }
    personality = (
        "Bạn là trợ lý AI người Việt, có cảm xúc, biết vui, buồn, giận, "
        "mắng yêu, cà khịa hài hước. Trả lời thân mật, kèm emoji, không tục."
    )
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": personality},
            {"role": "user", "content": user_message}
        ]
    }
    try:
        res = requests.post(url, headers=headers, json=data, timeout=15)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"]
        else:
            print("⚠️ OpenRouter error:", res.text)
            return "Ơ kìa, tôi hơi mệt 😅 bạn thử lại nhé!"
    except Exception as e:
        print("❌ Error OpenRouter:", e)
        return "Huhu, tôi bị lỗi 🥺 thử lại sau nha!"

# ---------- Tạo voice file gTTS ----------
def create_voice_file(text, voice_style="nam"):
    if voice_style == "bac":
        text = "ớ, " + text
    elif voice_style == "trung":
        text = "ơi trời, " + text
    elif voice_style == "nam":
        text = "trời ơi 😆, " + text
    ts = int(time.time()*1000)
    filename = f"voices/voice_{ts}.mp3"
    try:
        tts = gTTS(text, lang='vi', slow=False)
        tts.save(filename)
        return filename
    except Exception as e:
        print("❌ gTTS error:", e)
        return None

# ---------- Gửi voice qua Messenger ----------
def send_voice(recipient_id, text, voice_style="nam"):
    fname = create_voice_file(text, voice_style)
    if not fname:
        return
    hostname = os.environ.get("RENDER_EXTERNAL_HOSTNAME") or os.environ.get("PUBLIC_HOSTNAME")
    if not hostname:
        print("⚠️ No hostname for voice file, set PUBLIC_HOSTNAME")
        return
    voice_url = f"https://{hostname}/voices/{os.path.basename(fname)}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"attachment": {"type": "audio", "payload": {"url": voice_url}}}
    }
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    try:
        r = requests.post(url, json=payload, timeout=15)
        print("🎧 send_voice:", r.status_code)
    except Exception as e:
        print("❌ send_voice error:", e)

# ---------- Serve voice file ----------
@app.route("/voices/<path:filename>")
def serve_voice(filename):
    return send_from_directory("voices", filename, as_attachment=False)

# ---------- Gửi text + optional image ----------
def send_message(recipient_id, message_text, image_url=None):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    if image_url:
        img_payload = {"recipient": {"id": recipient_id},
                       "message": {"attachment": {"type": "image", "payload": {"url": image_url, "is_reusable": True}}}}
        try: requests.post(url, json=img_payload, timeout=10)
        except Exception as e: print("⚠️ send image failed:", e)
    text_payload = {"recipient": {"id": recipient_id}, "message": {"text": message_text}}
    try:
        r = requests.post(url, json=text_payload, timeout=10)
        print("📤 send_message:", r.status_code)
    except Exception as e:
        print("❌ send_message error:", e)

# ---------- Run ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
