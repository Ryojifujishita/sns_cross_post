import aiohttp
import asyncio

# 実際の環境変数値
MISSKEY_TOKEN = "jzIr3IqLM882ZlDIhFpVYhzI5jOjXLl1"
MISSKEY_HOST = "https://misskey.io"

async def test_youtube_video():
    """YouTube動画のHTML5 video埋め込みをテスト"""
    
    print("🎬 YouTube動画埋め込みテスト")
    
    # テストケース
    test_cases = [
        {
            'name': 'YouTube動画直接埋め込み',
            'video_id': 'dQw4w9WgXcQ',
            'text': '<video width="560" height="315" controls><source src="https://www.youtube.com/watch?v=dQw4w9WgXcQ" type="video/mp4">Your browser does not support the video tag.</video>'
        },
        {
            'name': 'YouTube動画埋め込みURL',
            'video_id': 'dQw4w9WgXcQ',
            'text': '<video width="560" height="315" controls><source src="https://www.youtube.com/embed/dQw4w9WgXcQ" type="video/mp4">Your browser does not support the video tag.</video>'
        },
        {
            'name': 'YouTube動画短縮URL',
            'video_id': 'dQw4w9WgXcQ',
            'text': '<video width="560" height="315" controls><source src="https://youtu.be/dQw4w9WgXcQ" type="video/mp4">Your browser does not support the video tag.</video>'
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🧪 テスト {i}: {test_case['name']}")
        print(f"📝 動画ID: {test_case['video_id']}")
        print(f"📝 投稿内容: {test_case['text']}")
        
        payload = {
            'i': MISSKEY_TOKEN,
            'text': test_case['text'],
            'visibility': 'public',
            'noExtractUrl': True,  # URL自動抽出を無効化
        }
        
        try:
            url = f'{MISSKEY_HOST}/api/notes/create'
            
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
        await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(test_youtube_video())
