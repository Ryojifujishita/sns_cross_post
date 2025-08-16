import discord
import requests
import os

# 環境変数から設定を読み込み
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
MISSKEY_TOKEN     = os.getenv('MISSKEY_TOKEN')
MISSKEY_HOST      = os.getenv('MISSKEY_HOST')

# 複数のチャンネルIDをリストに
TARGET_CHANNEL_IDS_STR = os.getenv('TARGET_CHANNEL_IDS')
TARGET_CHANNEL_IDS = [int(x.strip()) for x in TARGET_CHANNEL_IDS_STR.split(',')] if TARGET_CHANNEL_IDS_STR else []

# ★ 自分のDiscordユーザーID（数値）だけ通す
MY_USER_ID = int(os.getenv('MY_USER_ID')) if os.getenv('MY_USER_ID') else None

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 環境変数の検証
def validate_environment():
    required_vars = {
        'DISCORD_BOT_TOKEN': DISCORD_BOT_TOKEN,
        'MISSKEY_TOKEN': MISSKEY_TOKEN,
        'MISSKEY_HOST': MISSKEY_HOST,
        'TARGET_CHANNEL_IDS': TARGET_CHANNEL_IDS_STR,
        'MY_USER_ID': os.getenv('MY_USER_ID')
    }
    
    missing_vars = [var for var, value in required_vars.items() if not value]
    
    if missing_vars:
        print(f"❌ 必要な環境変数が設定されていません: {', '.join(missing_vars)}")
        print("環境変数を設定してから再実行してください。")
        exit(1)
    
    if not TARGET_CHANNEL_IDS:
        print("❌ TARGET_CHANNEL_IDSが正しく設定されていません")
        exit(1)
    
    if not MY_USER_ID:
        print("❌ MY_USER_IDが正しく設定されていません")
        exit(1)
    
    print("✅ 環境変数の検証が完了しました")
    print(f"📺 監視チャンネル数: {len(TARGET_CHANNEL_IDS)}")
    print(f"👤 対象ユーザーID: {MY_USER_ID}")

MAX_TEXT = 3000  # Misskeyのノート上限

def truncate_for_misskey(text: str) -> str:
    return text if len(text) <= MAX_TEXT else (text[:MAX_TEXT-3] + '...')

def post_to_misskey(text: str, media_ids=None):
    payload = {
        'i': MISSKEY_TOKEN,
        'text': text,
        'visibility': 'public'
    }
    if media_ids:
        payload['mediaIds'] = media_ids
    return requests.post(f'{MISSKEY_HOST}/api/notes/create', json=payload)

@client.event
async def on_ready():
    print(f'✅ Discord Botにログインしました: {client.user}')
    print(f'🔍 監視を開始しています...')

@client.event
async def on_message(message: discord.Message):
    # 対象チャンネルのみ
    if message.channel.id not in TARGET_CHANNEL_IDS:
        return
    # 自分の投稿のみ
    if message.author.id != MY_USER_ID:
        return
    # Botや空メッセージは除外
    if message.author.bot:
        return
    if not (message.content or message.attachments):
        return

    text = truncate_for_misskey(message.content or '')
    media_ids = []

    # 添付画像/動画もMisskeyに上げたい場合（任意）
    # ※Discordの添付URLは基本的に直接GETできます
    for att in message.attachments:
        try:
            file_bytes = await att.read()
            files_create = requests.post(
                f'{MISSKEY_HOST}/api/drive/files/create',
                data={'i': MISSKEY_TOKEN},
                files={'file': (att.filename, file_bytes)}
            )
            if files_create.status_code == 200:
                media_ids.append(files_create.json()['id'])
            else:
                print('Drive upload failed:', files_create.status_code, files_create.text)
        except Exception as e:
            print('Attachment upload error:', e)

    resp = post_to_misskey(text, media_ids or None)
    print('Misskey status:', resp.status_code, resp.text)

if __name__ == "__main__":
    # 環境変数の検証
    validate_environment()
    
    # Botを起動
    print("🚀 Discord to Misskey Botを起動しています...")
    client.run(DISCORD_BOT_TOKEN)