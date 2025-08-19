import os
import aiohttp
import asyncio
from dotenv import load_dotenv

# .envファイルを読み込み
load_dotenv()

# 実際の環境変数値
MISSKEY_TOKEN = "jzIr3IqLM882ZlDIhFpVYhzI5jOjXLl1"
MISSKEY_HOST = "https://misskey.io"

async def test_misskey_html():
    """MisskeyのHTMLサポートをテスト"""
    
    # 環境変数の確認
    print(f"🔍 MISSKEY_HOST: {MISSKEY_HOST}")
    print(f"🔍 MISSKEY_TOKEN: {'設定済み' if MISSKEY_TOKEN else '未設定'}")
    
    if not MISSKEY_HOST or not MISSKEY_TOKEN:
        print("❌ 環境変数が設定されていません")
        return
    
    # テストケース
    test_cases = [
        {
            'name': 'プレーンテキスト',
            'text': 'これは通常のテキストです。'
        },
        {
            'name': 'Markdownリンク',
            'text': '[YouTube](https://youtube.com/watch?v=dQw4w9WgXcQ)'
        },
        {
            'name': 'HTMLリンク',
            'text': '<a href="https://youtube.com/watch?v=dQw4w9WgXcQ">YouTubeリンク</a>'
        },
        {
            'name': 'iframe埋め込み',
            'text': '<iframe width="560" height="315" src="https://www.youtube.com/embed/dQw4w9WgXcQ" frameborder="0" allowfullscreen></iframe>'
        },
        {
            'name': 'HTML5 video',
            'text': '<video width="320" height="240" controls><source src="https://sample-videos.com/zip/10/mp4/SampleVideo_1280x720_1mb.mp4" type="video/mp4">Your browser does not support the video tag.</video>'
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 テスト {i}: {test_case['name']}")
        print(f"📝 投稿内容: {test_case['text']}")
        
        payload = {
            'i': MISSKEY_TOKEN,
            'text': test_case['text'],
            'visibility': 'public',
            'noExtractMentions': True,
            'noExtractHashtags': True,
            'noExtractEmojis': True,
            'noExtractUrl': True,
        }
        
        try:
            url = f'{MISSKEY_HOST}/api/notes/create'
            print(f"🔗 投稿URL: {url}")
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        result = await response.json()
                        print(f"✅ 投稿成功: {result.get('id', 'N/A')}")
                    else:
                        error_text = await response.text()
                        print(f"❌ 投稿失敗: {response.status} - {error_text}")
        except Exception as e:
            print(f"❌ エラー: {e}")
        
        # テスト間隔を空ける
        await asyncio.sleep(2)

if __name__ == "__main__":
    print("🧪 Misskey HTMLサポートテストを開始...")
    asyncio.run(test_misskey_html())
    print("\n✅ テスト完了！")
