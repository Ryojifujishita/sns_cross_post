#!/bin/bash

# 簡単なデプロイスクリプト
echo "🚀 クイックデプロイを開始..."

# コミットメッセージを引数から取得、なければデフォルト
COMMIT_MSG=${1:-"Update $(date '+%Y-%m-%d %H:%M:%S')"}

echo "📦 変更をステージング中..."
git add .

echo "💾 コミット中: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"

echo "📤 プッシュ中..."
git push

echo "🚂 Railwayデプロイログを開始..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
railway logs --follow
