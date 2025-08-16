import discord
import requests
import os
import aiohttp
import asyncio

# 環境変数から設定を読み込み
def get_env_var(var_name, required=True):
    value = os.getenv(var_name)
    if required and not value:
        print(f"⚠️  環境変数 {var_name} が設定されていません")
    return value

DISCORD_BOT_TOKEN = get_env_var('DISCORD_BOT_TOKEN')
MISSKEY_TOKEN     = get_env_var('MISSKEY_TOKEN')
MISSKEY_HOST      = get_env_var('MISSKEY_HOST')

# 複数のチャンネルIDをリストに
TARGET_CHANNEL_IDS_STR = get_env_var('TARGET_CHANNEL_IDS')
TARGET_CHANNEL_IDS = [int(x.strip()) for x in TARGET_CHANNEL_IDS_STR.split(',')] if TARGET_CHANNEL_IDS_STR else []

# ★ 自分のDiscordユーザーID（数値）だけ通す
MY_USER_ID = int(get_env_var('MY_USER_ID')) if get_env_var('MY_USER_ID') else None

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 環境変数の検証
def validate_environment():
    print("🔍 環境変数の検証を開始...")
    
    # すべての環境変数を確認
    all_env_vars = os.environ
    print(f"📋 利用可能な環境変数: {list(all_env_vars.keys())}")
    
    required_vars = {
        'DISCORD_BOT_TOKEN': DISCORD_BOT_TOKEN,
        'MISSKEY_TOKEN': MISSKEY_TOKEN,
        'MISSKEY_HOST': MISSKEY_HOST,
        'TARGET_CHANNEL_IDS': TARGET_CHANNEL_IDS_STR,
        'MY_USER_ID': os.getenv('MY_USER_ID')
    }
    
    print("🔍 必要な環境変数の値:")
    for var, value in required_vars.items():
        if value:
            print(f"  ✅ {var}: {'*' * len(str(value)) if 'TOKEN' in var else value}")
        else:
            print(f"  ❌ {var}: 未設定")
    
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
    print(f"📎 添付ファイル数: {len(message.attachments)}")
    for i, att in enumerate(message.attachments):
        try:
            print(f"📁 ファイル {i+1}: {att.filename} ({att.size} bytes)")
            
            # ファイルを読み込み
            file_bytes = await att.read()
            print(f"📥 ファイル読み込み完了: {len(file_bytes)} bytes")
            
            # MisskeyのDriveにアップロード
            async with aiohttp.ClientSession() as session:
                data = aiohttp.FormData()
                data.add_field('i', MISSKEY_TOKEN)
                data.add_field('file', file_bytes, filename=att.filename)
                
                async with session.post(
                    f'{MISSKEY_HOST}/api/drive/files/create',
                    data=data
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        media_id = result.get('id')
                        if media_id:
                            media_ids.append(media_id)
                            print(f"✅ ファイルアップロード成功: {att.filename} -> ID: {media_id}")
                        else:
                            print(f"❌ ファイルアップロード失敗: IDが見つかりません - {result}")
                    else:
                        error_text = await response.text()
                        print(f"❌ ファイルアップロード失敗: {response.status} - {error_text}")
                        
        except Exception as e:
            print(f"❌ ファイル処理エラー ({att.filename}): {e}")
            import traceback
            traceback.print_exc()

    # Misskeyに投稿
    if media_ids:
        print(f"🖼️ 画像付きで投稿: {len(media_ids)}枚の画像")
    else:
        print("📝 テキストのみ投稿")
    
    resp = post_to_misskey(text, media_ids if media_ids else None)
    print(f'📤 Misskey投稿結果: {resp.status_code} - {resp.text}')

if __name__ == "__main__":
    # 環境変数の検証
    validate_environment()
    
    # Botを起動
    print("🚀 Discord to Misskey Botを起動しています...")
    client.run(DISCORD_BOT_TOKEN)