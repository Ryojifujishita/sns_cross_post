#!/bin/bash

# 色付きのログ出力用関数
print_info() {
    echo -e "\033[34m[INFO]\033[0m $1"
}

print_success() {
    echo -e "\033[32m[SUCCESS]\033[0m $1"
}

print_error() {
    echo -e "\033[31m[ERROR]\033[0m $1"
}

print_warning() {
    echo -e "\033[33m[WARNING]\033[0m $1"
}

# スクリプト開始
print_info "🚀 デプロイプロセスを開始します..."

# 1. Gitの変更を確認
print_info "📋 Gitの変更状況を確認中..."
if [[ -n $(git status --porcelain) ]]; then
    print_info "変更されたファイルがあります"
    git status --short
else
    print_warning "変更されたファイルがありません"
    read -p "続行しますか？ (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "デプロイをキャンセルしました"
        exit 0
    fi
fi

# 2. 変更をステージング
print_info "📦 変更をステージング中..."
git add .

# 3. コミットメッセージの入力
print_info "💬 コミットメッセージを入力してください:"
read commit_message

if [[ -z "$commit_message" ]]; then
    commit_message="Update $(date '+%Y-%m-%d %H:%M:%S')"
    print_warning "コミットメッセージが空のため、デフォルトメッセージを使用: $commit_message"
fi

# 4. コミット
print_info "💾 変更をコミット中..."
git commit -m "$commit_message"

if [ $? -eq 0 ]; then
    print_success "コミットが完了しました"
else
    print_error "コミットに失敗しました"
    exit 1
fi

# 5. Git push
print_info "📤 Gitにプッシュ中..."
git push

if [ $? -eq 0 ]; then
    print_success "Gitプッシュが完了しました"
else
    print_error "Gitプッシュに失敗しました"
    exit 1
fi

# 6. Railwayプロジェクトがリンクされているか確認
print_info "🔗 Railwayプロジェクトのリンク状況を確認中..."
if ! railway status > /dev/null 2>&1; then
    print_warning "Railwayプロジェクトがリンクされていません"
    print_info "プロジェクトをリンクしてください:"
    railway link
fi

# 7. Railwayデプロイログの監視開始
print_info "🚂 Railwayデプロイログの監視を開始します..."
print_info "ログの監視を停止するには Ctrl+C を押してください"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Railway デプロイログ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# 少し待ってからログを開始（デプロイが開始されるまで）
sleep 3

# Railwayログをリアルタイムで表示
railway logs --follow

print_success "デプロイプロセスが完了しました！"
