# Webhook/webhook_server.py

from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi
from linebot.v3.webhooks import MessageEvent, TextMessageContent, PostbackEvent
from linebot.v3.messaging import TextMessage, QuickReply, QuickReplyItem, MessageAction
import os
import logging
import sys
import json
import random
from datetime import datetime
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

# 株みくじデータを読み込む
def load_stock_fortune_data():
    try:
        with open('stock_fortune.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"❌ 株みくじデータの読み込みに失敗しました: {e}")
        # フォールバックデータ（最低限のデータセット）
        return [
            {
                "code": "9432",
                "name": "日本電信電話",
                "sector": "情報・通信",
                "comment": "安定した通信大手。長期保有向き。"
            },
            {
                "code": "7203",
                "name": "トヨタ自動車",
                "sector": "輸送用機器",
                "comment": "世界最大級の自動車メーカー。安定した実績。"
            },
            {
                "code": "8306",
                "name": "三菱UFJフィナンシャル・グループ",
                "sector": "銀行業",
                "comment": "日本最大のメガバンク。配当利回りに期待。"
            }
        ]

# 株みくじのデータをグローバル変数として保持
STOCK_FORTUNE_DATA = load_stock_fortune_data()

# 気分ごとの銘柄特性マッピング
MOOD_MAPPING = {
    "積極的": ["情報・通信", "サービス業", "電気機器"],
    "保守的": ["銀行業", "食料品", "卸売業", "小売業"],
    "冒険的": ["情報・通信", "医薬品", "サービス業"],
    "長期的": ["輸送用機器", "電気機器", "食料品", "銀行業"],
    "短期的": ["情報・通信", "サービス業", "小売業"]
}

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

# 今日の株みくじをランダムに選ぶ関数
def get_todays_stock_fortune(mood=None):
    if not STOCK_FORTUNE_DATA:
        return None
    
    # 日付をシード値として使うことで、同じ日なら同じ結果を返す
    today = datetime.now().strftime('%Y%m%d')
    random.seed(today)
    
    # 気分に応じた絞り込み
    filtered_stocks = STOCK_FORTUNE_DATA
    if mood and mood in MOOD_MAPPING:
        preferred_sectors = MOOD_MAPPING[mood]
        filtered_stocks = [stock for stock in STOCK_FORTUNE_DATA if stock['sector'] in preferred_sectors]
        
        # 絞り込み結果が0件の場合は全銘柄から選択
        if not filtered_stocks:
            filtered_stocks = STOCK_FORTUNE_DATA
    
    # ランダムに1銘柄選択
    fortune = random.choice(filtered_stocks)
    
    # シードをリセット
    random.seed()
    
    return fortune

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event):
    text = event.message.text
    app.logger.info(f"📩 受信テキスト: 「{text}」")
    app.logger.info(f"📩 イベント詳細: type={event.type}, source={event.source.type}, user_id={event.source.user_id}")
    
    # すべての受信パターンに対応するために、前処理でテキストを標準化
    normalized_text = text.strip()
    
    if normalized_text == "光通信を分析":
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
    
    elif normalized_text.startswith("詳細:"):
        company_name = normalized_text.replace("詳細:", "").strip()
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
    
    elif normalized_text == "今日の株みくじをする！🥠" or normalized_text == "今日の株みくじ🍀" or normalized_text == "今日の株みくじ" or normalized_text == "今日の株みくじをする":
        app.logger.info(f"🎯 株みくじ機能を実行します")
        # 株みくじ機能を直接実行
        fortune = get_todays_stock_fortune()
        if fortune:
            today = datetime.now().strftime('%Y年%m月%d日')
            reply = f"🎯 {today}の株みくじ\n\n" \
                    f"【{fortune['name']}】({fortune['code']})\n" \
                    f"業種：{fortune['sector']}\n" \
                    f"コメント：{fortune['comment']}"
        else:
            reply = "😢 株みくじデータを読み込めませんでした。"
        
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                reply_message_request={
                    "replyToken": event.reply_token,
                    "messages": [TextMessage(text=reply)]
                }
            )
    
    elif normalized_text.startswith("株みくじ:"):
        # 気分を取得
        mood = normalized_text.replace("株みくじ:", "").strip()
        if mood == "おまかせ":
            mood = None
        
        # 気分に合わせた株みくじを取得
        fortune = get_todays_stock_fortune(mood)
        if fortune:
            today = datetime.now().strftime('%Y年%m月%d日')
            mood_text = f"【{mood}な気分向け】" if mood else ""
            reply = f"🎯 {today}の株みくじ {mood_text}\n\n" \
                    f"【{fortune['name']}】({fortune['code']})\n" \
                    f"業種：{fortune['sector']}\n" \
                    f"コメント：{fortune['comment']}"
        else:
            reply = "😢 株みくじデータを読み込めませんでした。"
        
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
    app.logger.info(f"📩 受信ポストバック: 「{data}」")
    app.logger.info(f"📩 ポストバックイベント詳細: type={event.type}, source={event.source.type}, user_id={event.source.user_id}")
    reply = ""

    if data == "action=detail":
        reply = "📄 報告書の詳細をお送りします（ダミー）"
    elif data == "action=holdings":
        reply = "📊 あなたの持ち株を分析します（ダミー）"
    elif data == "action=fortune":
        app.logger.info(f"🎯 ポストバックから株みくじ機能を実行します")
        # 株みくじ機能を直接実行
        fortune = get_todays_stock_fortune()
        if fortune:
            today = datetime.now().strftime('%Y年%m月%d日')
            reply = f"🎯 {today}の株みくじ\n\n" \
                    f"【{fortune['name']}】({fortune['code']})\n" \
                    f"業種：{fortune['sector']}\n" \
                    f"コメント：{fortune['comment']}"
        else:
            reply = "😢 株みくじデータを読み込めませんでした。"
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
