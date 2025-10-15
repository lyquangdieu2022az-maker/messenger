from flask import Flask, request
import requests

app = Flask(__name__)

# ====== CẤU HÌNH BOT ======
VERIFY_TOKEN = "0916659939"   # Token để xác minh Webhook (bạn có thể đổi)
PAGE_ACCESS_TOKEN = "EAATHSZCmQwQ8BPhPGgRwoQgMhzoZAAcnbQkXZBZCtZBMtPQFCri06o50bM9XCm0A3VNpx0UzI5v0jbW1QwxddQZC7iZA8w2w3jk1lHDU0qhOQo6ZA1AgWXe7XRw5EZBNnSkhSI0U1W4H0h8LzbjZC9Jl1ak9yrXCZA1m5c7yb7i02uqAQKvLwH2Oe4tQcZB0t57Xnxg01b5MCwkxugZDZD"
OPENROUTER_API_KEY = "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"  # 👉 Key từ https://openrouter.ai/keys
# ===========================


# 🧩 Xác minh Webhook khi bấm “Xác minh và lưu” trong Meta
@app.route("/webhook", methods=['GET'])
def verify():
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if token == VERIFY_TOKEN:
        return challenge
    return "Xác minh thất bại", 403


# 💬 Nhận tin nhắn từ người dùng
@app.route("/webhook", methods=['POST'])
def webhook():
    data = request.get_json()
    print("📩 Dữ liệu nhận được:", data)

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for event in entry.get("messaging", []):
                if "message" in event:
                    sender_id = event["sender"]["id"]
                    message_text = event["message"].get("text", "")
                    reply_text = get_ai_reply(message_text)
                    send_message(sender_id, reply_text)
    return "ok", 200


# 🧠 Gọi API OpenRouter để sinh phản hồi AI
def get_ai_reply(user_message):
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://openrouter.ai",
        "X-Title": "Messenger AI Bot",
        "Content-Type": "application/json",
    }
    data = {
        "model": "gpt-4o-mini",  # bạn có thể đổi model khác nếu muốn
        "messages": [
            {"role": "system", "content": "Bạn là trợ lý AI thân thiện, nói tiếng Việt, trả lời ngắn gọn, dễ hiểu."},
            {"role": "user", "content": user_message}
        ]
    }

    try:
        res = requests.post(url, headers=headers, json=data)
        if res.status_code == 200:
            return res.json()["choices"][0]["message"]["content"]
        else:
            print("⚠️ Lỗi OpenRouter:", res.text)
            return "Xin lỗi, tôi đang bị lỗi xử lý 🥲"
    except Exception as e:
        print("❌ Lỗi khi gọi OpenRouter:", e)
        return "Tôi đang gặp sự cố nhỏ, bạn thử lại sau nhé 🥺"


# ✉️ Gửi phản hồi lại Messenger
def send_message(recipient_id, message_text):
    url = f"https://graph.facebook.com/v18.0/me/messages?access_token={PAGE_ACCESS_TOKEN}"
    payload = {
        "recipient": {"id": recipient_id},
        "message": {"text": message_text}
    }
    res = requests.post(url, json=payload)
    print("📤 Đã gửi phản hồi:", res.text)


if __name__ == "__main__":
    app.run(port=5000)
