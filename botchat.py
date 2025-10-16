from flask import Flask, request, send_from_directory
import requests, os, random, time
from gtts import gTTS

app = Flask(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PUBLIC_HOSTNAME = os.getenv("PUBLIC_HOSTNAME")

os.makedirs("voices", exist_ok=True)

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot AI + Voice 3 miền đang hoạt động!", 200

@app.route("/webhook", methods=["GET"])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Xác minh thất bại", 403

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()
    print("📩 Received webhook:", data)

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                if "message" in event:
                    sender_id = event["sender"]["id"]
                    user_message = event["message"].get("text", "")

                    # Nếu hỏi ai tạo
                    if any(kw in user_message.lower() for kw in ["ai tạo", "ai làm", "ai lập trình", "ai viết"]):
                        reply = ("Tôi được tạo ra bởi Lý Quang Diệu — "
                                 "thành viên Facebook Developers Việt Nam.")
                        send_message(sender_id, reply)
                        send_voice(sender_id, reply, "nam")
                        continue

                    # Gọi AI
                    reply_text = get_ai_reply(user_message)

                    image_url = None
                    if any(w in user_message.lower() for w in ["ảnh", "hình"]):
                        image_url = random.choice([
                            "https://source.unsplash.com/random/600x400?smile",
                            "https://source.unsplash.com/random/600x400?funny"
                        ])

                    send_message(sender_id, reply_text, image_url)
                    voice_style = random.choice(["bac","trung","nam"])
                    send_voice(sender_id, reply_text, voice_style)

    return "ok", 200

def get_ai_reply(user_message):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
    personality = (
        "Bạn là AI người Việt có cảm xúc, mắng yêu, cà khịa, trả lời thân thiện, không tục."
    )
    data = {"model":"gpt-4o-mini", "messages":[{"role":"system","content":personality},{"role":"user","content":user_message}]}
    try:
        res = requests.post(url, headers=headers, json=data, timeout=15)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"]
        else:
            print("⚠️ OpenRouter error:", res.status_code, res.text)
            return "Xin lỗi, mình gặp lỗi 😢"
    except Exception as e:
        print("❌ Error calling OpenRouter:", e)
        return "Mình bị lỗi, thử lại nhé!"

def create_voice_file(text, voice_style="nam"):
    if voice_style == "bac":
        text = "ớ, " + text
    elif voice_style == "trung":
        text = "ơi trời, " + text
    elif voice_style == "nam":
        text = "trời ơi 😆, " + text
    ts = int(time.time()*1000)
    fname = f"voices/voice_{ts}.mp3"
    try:
        tts = gTTS(text, lang='vi', slow=False)
        tts.save(fname)
        return fname
    except Exception as e:
        print("❌ gTTS error:", e)
        return None

def send_voice(recipient_id, text, voice_style="nam"):
    fname = create_voice_file(text, voice_style)
    if not fname:
        return
    hostname = PUBLIC_HOSTNAME or os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if not hostname:
        print("⚠️ PUBLIC_HOSTNAME not set")
        return
    voice_url = f"{hostname}/voices/{os.path.basename(fname)}"
    payload = {"recipient":{"id":recipient_id},"message":{"attachment":{"type":"audio","payload":{"url":voice_url}}}}
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    try:
        r = requests.post(url, json=payload, timeout=15)
        print("🎧 send_voice:", r.status_code, r.text)
    except Exception as e:
        print("❌ send_voice error:", e)

@app.route("/voices/<path:fname>")
def serve_voice(fname):
    return send_from_directory("voices", fname, as_attachment=False)

def send_message(recipient_id, message_text, image_url=None):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    if image_url:
        payload = {"recipient":{"id":recipient_id},"message":{"attachment":{"type":"image","payload":{"url":image_url,"is_reusable":True}}}}
        try: requests.post(url, json=payload, timeout=10)
        except Exception as e: print("⚠️ send_image err:", e)
    text_payload = {"recipient":{"id":recipient_id},"message":{"text":message_text}}
    try:
        r = requests.post(url, json=text_payload, timeout=10)
        print("📤 send_message:", r.status_code, r.text)
    except Exception as e:
        print("❌ send_message error:", e)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
