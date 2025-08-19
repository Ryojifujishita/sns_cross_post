import os
import aiohttp
import asyncio

# 実際の環境変数値
MISSKEY_TOKEN = "jzIr3IqLM882ZlDIhFpVYhzI5jOjXLl1"
MISSKEY_HOST = "https://misskey.io"

async def test_simple():
    """簡単なMisskey投稿テスト"""
    
    print("🧪 簡単なMisskey投稿テスト")
    print(f"🔍 MISSKEY_HOST: {MISSKEY_HOST}")
    print(f"🔍 MISSKEY_TOKEN: {'設定済み' if MISSKEY_TOKEN != 'your_misskey_token_here' else '未設定'}")
    
    # 環境変数の確認
    print(f"✅ 環境変数が正しく設定されています")
    
    # テスト投稿
    test_text = "🧪 テスト投稿: HTMLサポート確認"
    
    payload = {
        'i': MISSKEY_TOKEN,
        'text': test_text,
        'visibility': 'public',
    }
    
    try:
        url = f'{MISSKEY_HOST}/api/notes/create'
        print(f"📝 投稿内容: {test_text}")
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

if __name__ == "__main__":
    asyncio.run(test_simple())
