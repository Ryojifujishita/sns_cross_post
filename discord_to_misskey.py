import discord
import requests
import os
import aiohttp
import asyncio
import re
from urllib.parse import urlparse, parse_qs

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

def get_youtube_thumbnail_urls(video_id: str) -> dict:
    """YouTubeの高解像度サムネイルURLを生成"""
    base_url = f"https://img.youtube.com/vi/{video_id}"
    return {
        'maxres': f'{base_url}/maxresdefault.jpg',      # 1280x720 (最高解像度)
        'sd': f'{base_url}/sddefault.jpg',             # 640x480 (標準解像度)
        'hq': f'{base_url}/hqdefault.jpg',             # 480x360 (高解像度)
        'mq': f'{base_url}/mqdefault.jpg',             # 320x180 (中解像度)
        'default': f'{base_url}/default.jpg'            # 120x90 (低解像度)
    }

async def download_youtube_thumbnail(video_id: str, quality: str = 'maxres') -> bytes:
    """YouTubeのサムネイル画像をダウンロード"""
    try:
        urls = get_youtube_thumbnail_urls(video_id)
        url = urls.get(quality, urls['maxres'])
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    # 最高解像度が利用できない場合は標準解像度を試す
                    if quality == 'maxres':
                        return await download_youtube_thumbnail(video_id, 'sd')
                    return None
    except Exception as e:
        print(f"❌ サムネイルダウンロードエラー: {e}")
        return None

def extract_youtube_video_id(text: str) -> str:
    """テキストからYouTubeのビデオIDを抽出"""
    print(f"🔍 ===== extract_youtube_video_id開始 =====")
    print(f"🔍 入力テキスト: {repr(text)}")
    print(f"🔍 テキスト長: {len(text)}")
    print(f"🔍 テキストの型: {type(text)}")
    
    youtube_patterns = [
        r'https?://(?:www\.)?youtube\.com/shorts/([a-zA-Z0-9_-]+)',
        r'https?://(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]+)',
        r'https?://(?:www\.)?youtu\.be/([a-zA-Z0-9_-]+)'
    ]
    
    print(f"🔍 検索パターン数: {len(youtube_patterns)}")
    
    for i, pattern in enumerate(youtube_patterns):
        print(f"🔍 パターン {i+1} を試行: {pattern}")
        print(f"🔍 正規表現オブジェクト: {re.compile(pattern)}")
        
        match = re.search(pattern, text)
        print(f"🔍 マッチ結果: {match}")
        
        if match:
            video_id = match.group(1)
            print(f"🔍 ✅ マッチ成功: video_id={video_id}")
            print(f"🔍 マッチ位置: {match.start()} - {match.end()}")
            print(f"🔍 マッチした文字列: {match.group(0)}")
            return video_id
        else:
            print(f"🔍 ❌ パターン {i+1} にマッチしませんでした")
    
    print(f"🔍 ❌ すべてのパターンにマッチしませんでした")
    print(f"🔍 ===== extract_youtube_video_id終了 =====")
    return None

def customize_youtube_display(text: str, video_id: str = None) -> str:
    """YouTubeリンクの表示をカスタマイズ"""
    print(f"🔍 ===== customize_youtube_display開始 =====")
    print(f"🔍 入力テキスト: {repr(text)}")
    print(f"🔍 テキスト長: {len(text)}")
    print(f"🔍 video_id: {video_id}")
    print(f"🔍 video_idの型: {type(video_id)}")
    
    if not video_id:
        print(f"🔍 ❌ video_idがNoneです")
        print(f"🔍 ===== customize_youtube_display終了（早期リターン） =====")
        return text
    
    print(f"🔍 ✅ video_idが有効です: {video_id}")
    
    # Misskeyの自動埋め込みを完全に防ぐ根本的対策
    # URLを完全に無効化してプレーンテキストで表示
    
    # 元のURLを保存
    original_urls = []
    print(f"🔍 URL検索を開始します")
    
    # 実際のURLパターンに合わせて検索
    actual_url = f"https://youtube.com/shorts/{video_id}"
    actual_url_with_params = f"https://youtube.com/shorts/{video_id}?si="
    
    print(f"🔍 検索対象URL1: {actual_url}")
    print(f"🔍 検索対象URL2: {actual_url_with_params}")
    
    # 部分一致で検索
    if actual_url in text:
        print(f"🔍 ✅ 完全一致URLを発見: {actual_url}")
        original_urls.append(actual_url)
    elif any(url in text for url in [f"https://youtube.com/shorts/{video_id}", f"https://www.youtube.com/shorts/{video_id}", f"https://youtu.be/{video_id}"]):
        # 部分一致で検索
        for pattern in [f"https://youtube.com/shorts/{video_id}", f"https://www.youtube.com/shorts/{video_id}", f"https://youtu.be/{video_id}"]:
            if pattern in text:
                print(f"🔍 ✅ 部分一致URLを発見: {pattern}")
                original_urls.append(pattern)
                break
    else:
        print(f"🔍 ❌ どのURLパターンにも一致しません")
    
    print(f"🔍 検出されたURL数: {len(original_urls)}")
    print(f"🔍 検出されたURL一覧: {original_urls}")
    
    # テキストからURLを完全に削除
    modified_text = text
    print(f"🔍 元のテキスト: {repr(modified_text)}")
    
    for i, url in enumerate(original_urls):
        print(f"🔍 URL {i+1} を削除中: {url}")
        old_text = modified_text
        modified_text = modified_text.replace(url, "")
        print(f"🔍 削除前: {repr(old_text)}")
        print(f"🔍 削除後: {repr(modified_text)}")
        print(f"🔍 変更があったか: {old_text != modified_text}")
    
    print(f"🔍 URL削除後のテキスト: {repr(modified_text)}")
    
    # プレーンテキストでURLを表示（クリック不可）
    if original_urls:
        print(f"🔍 プレーンテキストURLの生成を開始")
        # URLを完全に無効化するために特殊文字で囲む
        url_text = "\n\n".join([f"[{url}]" for url in original_urls])
        print(f"🔍 生成されたURLテキスト: {repr(url_text)}")
        modified_text = f"{modified_text}\n\n{url_text}"
        print(f"🔍 最終テキストに追加後: {repr(modified_text)}")
    else:
        print(f"🔍 検出されたURLがないため、テキストは変更されません")
    
    print(f"🔍 ===== customize_youtube_display終了 =====")
    print(f"🔍 最終結果: {repr(modified_text)}")
    return modified_text

def post_to_misskey(text: str, media_ids=None):
    payload = {
        'i': MISSKEY_TOKEN,
        'text': text,
        'visibility': 'public',
        'noExtractMentions': True,  # メンションの自動抽出を無効化
        'noExtractHashtags': True,  # ハッシュタグの自動抽出を無効化
        'noExtractEmojis': True,    # 絵文字の自動抽出を無効化
        'noExtractUrl': True,       # URLの自動埋め込みを無効化（重要！）
        'noExtractMentionsAsTags': True,  # メンションをタグとして抽出しない
        'noExtractHashtagsAsTags': True,  # ハッシュタグをタグとして抽出しない
        'noExtractEmojisAsTags': True,    # 絵文字をタグとして抽出しない
        'noExtractUrlsAsTags': True,      # URLをタグとして抽出しない
        'localOnly': False,               # ローカルのみ投稿を無効化
        'reactionAcceptance': None,       # リアクション受付設定をデフォルトに
        'cw': None,                       # 内容警告を無効化
        'viaMobile': False,               # モバイル経由でないことを明示
        'viaWeb': True,                   # Web経由であることを明示
        'noExtractUrlFromText': True,     # テキストからのURL抽出を無効化
        'noExtractUrlFromMedia': True,    # メディアからのURL抽出を無効化
        'noExtractUrlFromAttachments': True,  # 添付ファイルからのURL抽出を無効化
        'noExtractUrlFromEmbeds': True,       # 埋め込みからのURL抽出を無効化
        'noExtractUrlFromLinks': True,        # リンクからのURL抽出を無効化
        'noExtractUrlFromUrls': True,         # URLからのURL抽出を無効化
        'noExtractUrlFromUrl': True,          # URLからのURL抽出を無効化（重複）
        'noExtractUrlFromUrlText': True,      # URLテキストからのURL抽出を無効化
        'noExtractUrlFromUrlMedia': True,     # URLメディアからのURL抽出を無効化
        'noExtractUrlFromUrlAttachments': True,  # URL添付ファイルからのURL抽出を無効化
        'noExtractUrlFromUrlEmbeds': True,       # URL埋め込みからのURL抽出を無効化
        'noExtractUrlFromUrlLinks': True,        # URLリンクからのURL抽出を無効化
        'noExtractUrlFromUrlUrls': True          # URL URLからのURL抽出を無効化（重複）
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
    print(f"🔍 ===== on_messageイベント開始 =====")
    print(f"🔍 メッセージID: {message.id}")
    print(f"🔍 チャンネルID: {message.channel.id}")
    print(f"🔍 チャンネル名: {message.channel.name}")
    print(f"🔍 ユーザーID: {message.author.id}")
    print(f"🔍 ユーザー名: {message.author.name}")
    print(f"🔍 ユーザーがBotか: {message.author.bot}")
    print(f"🔍 メッセージ内容: {repr(message.content)}")
    print(f"🔍 添付ファイル数: {len(message.attachments)}")
    print(f"🔍 環境変数TARGET_CHANNEL_IDS: {TARGET_CHANNEL_IDS}")
    print(f"🔍 環境変数MY_USER_ID: {MY_USER_ID}")
    
    # 対象チャンネルのみ
    if message.channel.id not in TARGET_CHANNEL_IDS:
        print(f"🔍 ❌ 対象チャンネルではありません: {message.channel.id} not in {TARGET_CHANNEL_IDS}")
        return
    print(f"🔍 ✅ 対象チャンネルです: {message.channel.id}")
    
    # 自分の投稿のみ
    if message.author.id != MY_USER_ID:
        print(f"🔍 ❌ 対象ユーザーではありません: {message.author.id} != {MY_USER_ID}")
        return
    print(f"🔍 ✅ 対象ユーザーです: {message.author.id}")
    
    # Botや空メッセージは除外
    if message.author.bot:
        print(f"🔍 ❌ Botの投稿です: {message.author.bot}")
        return
    print(f"🔍 ✅ ユーザーの投稿です")
    
    if not (message.content or message.attachments):
        print(f"🔍 ❌ 空のメッセージです")
        return
    print(f"🔍 ✅ メッセージ内容があります")
    
    print(f"🔍 ===== メッセージ処理開始 =====")
    
    # YouTubeリンクの検出とサムネイル取得
    original_text = message.content or ''
    print(f"🔍 元のテキスト: {repr(original_text)}")
    print(f"🔍 テキスト長: {len(original_text)}")
    
    video_id = extract_youtube_video_id(original_text)
    print(f"🔍 抽出されたvideo_id: {video_id}")
    print(f"🔍 video_idの型: {type(video_id)}")
    
    youtube_thumbnail_id = None
    
    # YouTubeリンクがある場合は高解像度サムネイルを取得
    if video_id:
        print(f"🎬 YouTube動画検出: {video_id}")
        try:
            # 最高解像度から順番に試行
            thumbnail_bytes = None
            for quality in ['maxres', 'sd', 'hq']:
                thumbnail_bytes = await download_youtube_thumbnail(video_id, quality)
                if thumbnail_bytes:
                    print(f"✅ {quality}画質のサムネイル取得成功")
                    break
            
            if thumbnail_bytes:
                # サムネイルをMisskeyのDriveにアップロード
                async with aiohttp.ClientSession() as session:
                    data = aiohttp.FormData()
                    data.add_field('i', MISSKEY_TOKEN)
                    data.add_field('file', thumbnail_bytes, filename=f'youtube_thumbnail_{video_id}.jpg')
                    
                    async with session.post(
                        f'{MISSKEY_HOST}/api/drive/files/create',
                        data=data
                    ) as response:
                        if response.status == 200:
                            result = await response.json()
                            youtube_thumbnail_id = result.get('id')
                            if youtube_thumbnail_id:
                                print(f"✅ YouTubeサムネイルアップロード成功: ID: {youtube_thumbnail_id}")
                            else:
                                print(f"❌ YouTubeサムネイルアップロード失敗: IDが見つかりません")
                        else:
                            error_text = await response.text()
                            print(f"❌ YouTubeサムネイルアップロード失敗: {response.status} - {error_text}")
            else:
                print("⚠️ YouTubeサムネイルの取得に失敗しました")
        except Exception as e:
            print(f"❌ YouTubeサムネイル処理エラー: {e}")
            import traceback
            traceback.print_exc()

    # テキストをカスタマイズ（Misskeyの自動埋め込みを回避）
    print(f"🔍 元のテキスト: {repr(original_text)}")
    text = customize_youtube_display(original_text, video_id)
    print(f"🔍 カスタマイズ後: {repr(text)}")
    text = truncate_for_misskey(text)
    print(f"🔍 最終テキスト: {repr(text)}")
    
    # メディアIDのリストを作成（YouTubeサムネイル + 添付ファイル）
    media_ids = []
    if youtube_thumbnail_id:
        media_ids.append(youtube_thumbnail_id)
        print(f"🖼️ YouTubeサムネイルをメディアに追加: {youtube_thumbnail_id}")
    
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
        print(f"📋 メディアID一覧: {media_ids}")
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