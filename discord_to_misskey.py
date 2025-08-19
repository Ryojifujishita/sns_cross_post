import discord
import requests
import os
import aiohttp
import asyncio
import re
from urllib.parse import urlparse, parse_qs
import json

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

MAX_TEXT = 1000  # Misskeyのノート上限を大幅短縮（折りたたみ完全防止）

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
                        return await download_youtube_thumbnail(video_id, 'medium')  # sd → mediumに変更
                    return None
    except Exception as e:
        print(f"❌ サムネイルダウンロードエラー: {e}")
        return None

async def get_youtube_video_info(video_id: str) -> dict:
    """YouTube APIを使用して動画情報を取得"""
    try:
        # YouTube Data API v3を使用
        api_key = os.getenv('YOUTUBE_API_KEY')
        if not api_key:
            print(f"⚠️ YouTube APIキーが設定されていません")
            return None
        
        url = f"https://www.googleapis.com/youtube/v3/videos"
        params = {
            'part': 'snippet,contentDetails,statistics',
            'id': video_id,
            'key': api_key
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get('items'):
                        item = data['items'][0]
                        snippet = item['snippet']
                        return {
                            'title': snippet.get('title', ''),
                            'channel': snippet.get('channelTitle', ''),
                            'published_at': snippet.get('publishedAt', ''),
                            'thumbnails': snippet.get('thumbnails', {}),
                            'tags': snippet.get('tags', []),
                            'category_id': snippet.get('categoryId', ''),
                            'default_language': snippet.get('defaultLanguage', ''),
                            'default_audio_language': snippet.get('defaultAudioLanguage', '')
                        }
                    else:
                        print(f"⚠️ 動画情報が見つかりません: {video_id}")
                        return None
                else:
                    print(f"❌ YouTube API エラー: {response.status}")
                    return None
    except Exception as e:
        print(f"❌ YouTube動画情報取得エラー: {e}")
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

async def customize_youtube_display(text: str, video_id: str = None) -> str:
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
    
    # 元のテキストをそのまま保持（URL削除しない）
    modified_text = text
    print(f"🔍 元のテキストを保持: {repr(modified_text)}")
    
    # URLの削除処理を無効化 - Misskeyのネイティブ埋め込みを活用
    print(f"🔍 URL削除処理を無効化 - ネイティブ埋め込みに任せます")
    
    # 余分な改行を削除してテキストを短縮
    final_text = modified_text.replace('\n\n\n', '\n').replace('\n\n', '\n').strip()
    
    # 特殊文字で囲まれたURLも削除
    for url in original_urls:
        final_text = final_text.replace(f"【{url}】", "")
    
    # さらに余分な改行を削除
    final_text = final_text.replace('\n\n\n', '\n').replace('\n\n', '\n').strip()
    
    # YouTube動画の場合は、Misskeyのネイティブ埋め込みを活用
    if video_id:
        # 元のURLをyoutu.be形式に変換して、Misskeyの自動埋め込みに任せる
        youtube_url = f"https://youtu.be/{video_id}"
        final_text = f"{final_text}\n\n{youtube_url}"
        print(f"🔍 YouTube動画検出: {video_id} - youtu.be形式で追加: {youtube_url}")
    
    print(f"🔍 最終的なテキスト: {repr(final_text)}")
    return final_text

def create_custom_youtube_card(video_id: str, video_info: dict = None) -> str:
    """カスタムYouTubeカードを作成"""
    if not video_info:
        # 動画情報がない場合のフォールバック
        return f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎬 YouTube動画
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📺 動画ID: {video_id}
🔗 https://youtu.be/{video_id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    
    # 動画情報がある場合のカスタムカード
    title = video_info.get('title', 'タイトル不明')
    channel = video_info.get('channel', 'チャンネル不明')
    description = video_info.get('description', '')
    
    # 説明文を短縮
    if len(description) > 100:
        description = description[:100] + '...'
    
    card = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎬 **{title}**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📺 **チャンネル**: {channel}
📝 **説明**: {description}
🔗 **リンク**: https://youtu.be/{video_id}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return card

def remove_emojis(text: str) -> str:
    """テキストから絵文字を削除"""
    import re
    # 絵文字のUnicode範囲を指定して削除
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002702-\U000027B0"  # dingbats
        "\U000024C2-\U0001F251"  # enclosed characters
        "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
        "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
        "\U0001F004"             # mahjong tile red dragon
        "\U0001F0CF"             # playing card black joker
        "\U0001F170-\U0001F251"  # enclosed alphanumeric supplement
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub('', text).strip()

def create_discord_style_card(video_id: str, video_info: dict = None) -> str:
    """Discord風のカードを作成（最小限版）"""
    if video_info and 'title' in video_info:
        title = remove_emojis(video_info['title'])  # タイトルから絵文字を削除
        channel = remove_emojis(video_info.get('channel', 'Unknown Channel'))  # チャンネル名から絵文字を削除
    else:
        title = "動画タイトルを取得できませんでした"
        channel = "Unknown Channel"
    
    # MisskeyのネイティブYouTube埋め込みを活用するため、youtu.be短縮URLを使用
    # カスタムカードは削除し、Misskeyの自動埋め込みに任せる
    return f"https://youtu.be/{video_id}"

async def post_to_misskey(text: str, media_ids=None):
    payload = {
        'i': MISSKEY_TOKEN,
        'text': text,
        'visibility': 'public',
        'noExtractMentions': True,  # メンションの自動抽出を無効化
        'noExtractHashtags': True,  # ハッシュタグの自動抽出を無効化
        'noExtractEmojis': True,    # 絵文字の自動抽出を無効化
        # URLの自動埋め込みを有効化（MisskeyのYouTube埋め込み機能を活用）
        'noExtractMentionsAsTags': True,  # メンションをタグとして抽出しない
        'noExtractHashtagsAsTags': True,  # ハッシュタグをタグとして抽出しない
        'noExtractEmojisAsTags': True,    # 絵文字をタグとして抽出しない
        'cw': None,                                   # 内容警告を無効化（折りたたみ防止）
        'localOnly': False,                           # ローカルのみ投稿を無効化
        'reactionAcceptance': None,                   # リアクション受付設定をデフォルトに
        'viaMobile': False,                           # モバイル経由でないことを明示
        'viaWeb': True,                               # Web経由であることを明示
    }
    if media_ids:
        payload['mediaIds'] = media_ids
    
    async with aiohttp.ClientSession() as session:
        async with session.post(f'{MISSKEY_HOST}/api/notes/create', json=payload) as response:
            try:
                response_text = await response.text()
                print(f'📤 Misskey投稿結果: {response.status} - {response_text}')
                return response
            except Exception as e:
                print(f'⚠️ レスポンス読み取りエラー: {e}')
                print(f'📤 Misskey投稿結果: {response.status} - レスポンス読み取り失敗')
                return response

async def upload_to_misskey_drive(file_data: bytes, filename: str) -> str | None:
    """MisskeyのDriveに画像をアップロード"""
    try:
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field('i', MISSKEY_TOKEN)
            data.add_field('file', file_data, filename=filename, content_type='image/jpeg')
            
            async with session.post(
                f'{MISSKEY_HOST}/api/drive/files/create',
                data=data
            ) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get('id')
                else:
                    error_text = await response.text()
                    print(f"❌ Misskey Driveアップロード失敗: {response.status} - {error_text}")
                    return None
    except Exception as e:
        print(f"❌ Misskey Driveアップロードエラー: {e}")
        return None

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
    
    # YouTubeリンクの検出
    original_text = message.content or ''
    print(f"🔍 元のテキスト: {repr(original_text)}")
    print(f"🔍 テキスト長: {len(original_text)}")
    
    video_id = extract_youtube_video_id(original_text)
    print(f"🔍 抽出されたvideo_id: {video_id}")
    print(f"🔍 video_idの型: {type(video_id)}")
    
    if video_id:
        print(f"🎬 YouTube動画検出: {video_id}")

    # テキストをカスタマイズ（Misskeyの自動埋め込みを回避）
    print(f"🔍 元のテキスト: {repr(original_text)}")
    text = await customize_youtube_display(original_text, video_id)
    print(f"🔍 カスタマイズ後: {repr(text)}")
    text = truncate_for_misskey(text)
    print(f"🔍 最終テキスト: {repr(text)}")
    
    # 添付ファイルの処理（任意）
    media_ids = []
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
    
    resp = await post_to_misskey(text, media_ids if media_ids else None)
    try:
        resp_text = await resp.text()
        print(f'📤 Misskey投稿結果: {resp.status} - {resp_text}')
    except Exception as e:
        print(f'⚠️ レスポンス読み取りエラー: {e}')
        print(f'📤 Misskey投稿結果: {resp.status} - レスポンス読み取り失敗')

if __name__ == "__main__":
    # 環境変数の検証
    validate_environment()
    
    # Botを起動
    print("🚀 Discord to Misskey Botを起動しています...")
    client.run(DISCORD_BOT_TOKEN)