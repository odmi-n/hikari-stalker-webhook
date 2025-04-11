# Webhook/webhook_server.py

from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent
from linebot.v3.messaging import TextMessage, QuickReply, QuickReplyItem, MessageAction
import os
import logging
import sys
from dotenv import load_dotenv

# .env ファイルから環境変数を読み込む
load_dotenv()

# hikari-py ディレクトリを import 可能にする
sys.path.append(os.path.abspath("../hikari-py"))
try:
    from db import get_latest_companies_by_date
except ImportError:
    logging.error("❌ ../hikari-py/db.py が見つかりません")
    # エラーでも続行する（他の機能は使える）

# Flaskアプリケーションの初期化
app = Flask(__name__)

# 環境変数からLINEトークンとシークレットを取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

# 環境変数チェック
if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    logging.error("❌ 環境変数LINE_CHANNEL_ACCESS_TOKENとLINE_CHANNEL_SECRETを設定してください")
    sys.exit(1)

# V3 SDKの設定
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ログ設定
logging.basicConfig(level=logging.INFO)

@app.route("/", methods=["GET"])
def health_check():
    return "✅ Webhook server is running."

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    app.logger.info(f"📩 Received webhook: {body}")

    try:
        handler.handle(body, signature)
    except Exception as e:
        app.logger.error(f"❌ Error in webhook handling: {e}")
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    text = event.message.text
    
    if text == "光通信を分析":
        # 最新の銘柄を取得して QuickReply を動的に作成
        try:
            companies = get_latest_companies_by_date(limit=5)
            quick_reply_items = [
                QuickReplyItem(
                    action=MessageAction(
                        label=name[:20],
                        text=f"詳細:{name}"
                    )
                )
                for name in companies
            ]

            reply = "🔍 詳細を知りたい銘柄を選んでください"
            
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    reply_message_request={
                        "replyToken": event.reply_token,
                        "messages": [
                            TextMessage(
                                text=reply,
                                quick_reply=QuickReply(items=quick_reply_items)
                            )
                        ]
                    }
                )
        except Exception as e:
            logging.error(f"❌ クイックリプライの生成中にエラーが発生しました: {e}")
            reply = f"🤖 すみません、銘柄情報の取得中にエラーが発生しました。"
            
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    reply_message_request={
                        "replyToken": event.reply_token,
                        "messages": [TextMessage(text=reply)]
                    }
                )
    
    elif text.startswith("詳細:"):
        company_name = text.replace("詳細:", "").strip()
        # TODO: company_name を使って要約処理（summarizer.py）へ渡す
        reply = f"🔎 {company_name} の詳細分析を開始します（仮）"
        
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                reply_message_request={
                    "replyToken": event.reply_token,
                    "messages": [TextMessage(text=reply)]
                }
            )
    
    else:
        reply = f"🤖 メッセージを受け取りました: 「{text}」\n（後で分析Botに接続予定）"
        
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                reply_message_request={
                    "replyToken": event.reply_token,
                    "messages": [TextMessage(text=reply)]
                }
            )

@handler.add(PostbackEvent)
def handle_postback(event):
    data = event.postback.data
    reply = ""

    if data == "action=detail":
        reply = "📄 報告書の詳細をお送りします（ダミー）"
    elif data == "action=holdings":
        reply = "📊 あなたの持ち株を分析します（ダミー）"
    elif data == "action=fortune":
        reply = "🎯 今日の株みくじ：〇〇テクノロジーズ（ダミー）"
    else:
        reply = "⚠️ 不明な操作です"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            reply_message_request={
                "replyToken": event.reply_token,
                "messages": [TextMessage(text=reply)]
            }
        )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
