/**
 * Facebook Messenger Bot with AI (Facebook-only) + Quick Reply Menu
 * NOT affiliated with Meta/Facebook
 */

const express = require("express");
const bodyParser = require("body-parser");
const axios = require("axios");

const app = express();
app.use(bodyParser.json());

// ===== ENV =====
const PAGE_TOKEN = process.env.PAGE_TOKEN;
const VERIFY_TOKEN = process.env.VERIFY_TOKEN || "VERIFY_TOKEN_123";
const OPENAI_API_KEY = process.env.OPENAI_API_KEY;

// ===== VERIFY WEBHOOK =====
app.get("/webhook", (req, res) => {
  const mode = req.query["hub.mode"];
  const token = req.query["hub.verify_token"];
  const challenge = req.query["hub.challenge"];

  if (mode === "subscribe" && token === VERIFY_TOKEN) {
    return res.status(200).send(challenge);
  }
  return res.sendStatus(403);
});

// ===== RECEIVE MESSAGE =====
app.post("/webhook", async (req, res) => {
  const entry = req.body.entry?.[0];
  const event = entry?.messaging?.[0];
  const senderId = event?.sender?.id;

  if (event?.message?.quick_reply) {
    handleMenu(senderId, event.message.quick_reply.payload);
  } else if (event?.message?.text) {
    await handleAI(senderId, event.message.text);
  }

  res.sendStatus(200);
});

// ===== MENU =====
function sendMenu(senderId) {
  sendQuickReply(senderId, "📌 Chọn nội dung cần hỗ trợ:", [
    { title: "📜 Điều khoản", payload: "TERMS" },
    { title: "⚠️ Vi phạm", payload: "VIOLATION" },
    { title: "🔓 Mở khóa", payload: "UNLOCK" },
    { title: "🤖 Hỏi AI", payload: "AI" }
  ]);
}

function handleMenu(senderId, payload) {
  let text = "";
  if (payload === "TERMS") {
    text = "📜 Điều khoản & chính sách Facebook:\nhttps://www.facebook.com/policies";
  } else if (payload === "VIOLATION") {
    text =
      "⚠️ Tiêu chuẩn cộng đồng Facebook:\n" +
      "https://transparency.meta.com/vi-vn/policies/community-standards/";
  } else if (payload === "UNLOCK") {
    text =
      "🔓 Kháng nghị tài khoản bị vô hiệu hóa:\n" +
      "https://www.facebook.com/help/contact/260749603972907";
  } else if (payload === "AI") {
    text =
      "🤖 Bạn có thể hỏi AI mọi vấn đề LIÊN QUAN ĐẾN FACEBOOK.\n" +
      "❗ AI không trả lời ngoài chủ đề Facebook.";
  }
  sendMessage(senderId, text);
}

// ===== AI HANDLER =====
async function handleAI(senderId, userText) {
  // simple Facebook-only filter
  const keywords = ["facebook", "fb", "meta", "fanpage", "tài khoản", "khóa", "vi phạm"];
  const allowed = keywords.some(k => userText.toLowerCase().includes(k));

  if (!allowed) {
    return sendMessage(
      senderId,
      "❌ Bot AI chỉ trả lời các câu hỏi LIÊN QUAN ĐẾN FACEBOOK."
    );
  }

  const response = await axios.post(
    "https://api.openai.com/v1/chat/completions",
    {
      model: "gpt-4o-mini",
      messages: [
        {
          role: "system",
          content:
            "Bạn là bot tư vấn Facebook. Chỉ trả lời về Facebook, chính sách, mở khóa tài khoản. Không trả lời chủ đề khác. Luôn kèm link chính thức nếu có."
        },
        { role: "user", content: userText }
      ]
    },
    {
      headers: {
        Authorization: `Bearer ${OPENAI_API_KEY}`,
        "Content-Type": "application/json"
      }
    }
  );

  const reply = response.data.choices[0].message.content;
  sendMessage(senderId, reply);
}

// ===== SEND HELPERS =====
function sendMessage(senderId, text) {
  axios.post(
    `https://graph.facebook.com/v19.0/me/messages?access_token=${PAGE_TOKEN}`,
    {
      recipient: { id: senderId },
      message: { text }
    }
  ).catch(() => {});
}

function sendQuickReply(senderId, text, replies) {
  axios.post(
    `https://graph.facebook.com/v19.0/me/messages?access_token=${PAGE_TOKEN}`,
    {
      recipient: { id: senderId },
      message: {
        text,
        quick_replies: replies.map(r => ({
          content_type: "text",
          title: r.title,
          payload: r.payload
        }))
      }
    }
  ).catch(() => {});
}

// ===== START =====
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log("FB AI Bot running on port " + PORT);
});
