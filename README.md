# Discord to Misskey Cross-Post Bot

Discordの特定チャンネルのメッセージを自動的にMisskeyに投稿するBotです。

## 機能

- 指定されたDiscordチャンネルのメッセージを監視
- 自分の投稿のみをMisskeyに自動投稿
- 画像・動画の添付ファイルも対応
- テキスト長制限（3000文字）の自動調整

## クラウドデプロイ

### Fly.io でのデプロイ

1. **Fly.io CLIをインストール**
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```

2. **ログイン**
   ```bash
   fly auth login
   ```

3. **アプリを作成**
   ```bash
   fly apps create discord-misskey-bot
   ```

4. **環境変数を設定**
   ```bash
   fly secrets set DISCORD_BOT_TOKEN="your_token"
   fly secrets set MISSKEY_TOKEN="your_token"
   fly secrets set MISSKEY_HOST="https://misskey.io"
   fly secrets set TARGET_CHANNEL_IDS="863820588148981790,886645059963990037,971336110053683200,1059416854638108682"
   fly secrets set MY_USER_ID="123456789012345678"
   ```

5. **デプロイ**
   ```bash
   fly deploy
   ```

### Railway でのデプロイ

1. **Railwayにログイン**
   - [railway.app](https://railway.app) でGitHubアカウントと連携

2. **新しいプロジェクトを作成**
   - GitHubリポジトリと連携

3. **環境変数を設定**
   - Railwayダッシュボードで以下の環境変数を設定：
     - `DISCORD_BOT_TOKEN`
     - `MISSKEY_TOKEN`
     - `MISSKEY_HOST`
     - `TARGET_CHANNEL_IDS`
     - `MY_USER_ID`

4. **自動デプロイ**
   - GitHubにプッシュすると自動的にデプロイされます

## 環境変数

| 変数名 | 説明 | 例 |
|--------|------|-----|
| `DISCORD_BOT_TOKEN` | Discord Botのトークン | `MTQwNDg1MTU4NjYyNjQ4NjI4Mg...` |
| `MISSKEY_TOKEN` | Misskeyのアクセストークン | `wHrEYkpmnCvXuSfGqAbZHumnBIzHYvxn` |
| `MISSKEY_HOST` | MisskeyインスタンスのURL | `https://misskey.io` |
| `TARGET_CHANNEL_IDS` | 監視するDiscordチャンネルID（カンマ区切り） | `863820588148981790,886645059963990037` |
| `MY_USER_ID` | 自分のDiscordユーザーID | `123456789012345678` |

## ローカル実行

1. **依存関係をインストール**
   ```bash
   pip install -r requirements.txt
   ```

2. **環境変数を設定**
   ```bash
   cp env.example .env
   # .envファイルを編集して実際の値を設定
   ```

3. **実行**
   ```bash
   python discord_to_misskey.py
   ```

## 注意事項

- Discord Botには適切な権限が必要です
- MisskeyのAPIレート制限に注意してください
- 月200ポスト程度ならFly.io/Railwayの無料枠で十分です
- セキュリティのため、トークンは環境変数で管理してください

## トラブルシューティング

- **Botが起動しない**: トークンが正しく設定されているか確認
- **メッセージが投稿されない**: チャンネルIDとユーザーIDが正しいか確認
- **Misskey投稿エラー**: トークンとホストURLが正しいか確認
