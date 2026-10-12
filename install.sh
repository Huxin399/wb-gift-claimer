#!/bin/bash
# WorkBuddy 积分自动领取 · 一键安装（macOS）
# 用法：bash install.sh
# 完成：①装 Python 依赖 ②赋可执行权限 ③写入 launchd 定时(每天00:05+登录补领) ④引导授权

set -e
SKILL_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "=================================================="
echo " WorkBuddy 积分自动领取 · 一键安装"
echo " 技能目录: $SKILL_DIR"
echo "=================================================="

# ---------- 1) 依赖 ----------
PY="$(command -v python3)"
echo
echo "【1/4】安装 Python 依赖（pyautogui / rapidocr_onnxruntime / pyobjc）…"
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
if "$PY" -c "import pyautogui, rapidocr_onnxruntime" >/dev/null 2>&1; then
  echo "✅ 依赖已就绪，跳过"
else
  "$PY" -m pip install --user pyautogui numpy pillow pyobjc rapidocr-onnxruntime \
    || "$PY" -m pip install pyautogui numpy pillow pyobjc rapidocr-onnxruntime
  echo "✅ 依赖安装完成"
fi

# ---------- 2) 可执行权限 ----------
echo
echo "【2/4】设置可执行权限…"
chmod +x "$SKILL_DIR/WB积分领取.app/Contents/MacOS/runner"
chmod +x "$SKILL_DIR/领取积分.command" "$SKILL_DIR/校准积分.command"
echo "✅ 完成"

# ---------- 3) launchd 定时任务 ----------
echo
echo "【3/4】写入定时任务（每天 00:05 + 登录补领）…"
PLIST_DST="$HOME/Library/LaunchAgents/com.workbuddy.giftclaim.plist"
mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.workbuddy.giftclaim</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>-a</string>
        <string>$SKILL_DIR/WB积分领取.app</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key><integer>0</integer>
        <key>Minute</key><integer>5</integer>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>$SKILL_DIR</string>
    <key>StandardOutPath</key>
    <string>$SKILL_DIR/wb_gift.log</string>
    <key>StandardErrorPath</key>
    <string>$SKILL_DIR/wb_gift.err</string>
    <key>AbandonProcessGroup</key>
    <true/>
</dict>
</plist>
EOF
echo "✅ 已写入: $PLIST_DST"

# ---------- 4) 授权引导 + 加载 ----------
echo
echo "【4/4】请在 系统设置 → 隐私与安全性 中完成以下授权（必须，否则无法截屏）："
echo "   • 屏幕录制：点『+』加入 『$SKILL_DIR/WB积分领取.app』并打勾"
echo "   • 辅助功能：同样加入 『$SKILL_DIR/WB积分领取.app』并打勾"
echo "   （首次运行时系统也可能弹窗请求，点『允许』即可）"
read -p "完成授权后按回车，立即加载定时任务…"

launchctl bootstrap "gui/$(id -u)" "$PLIST_DST" 2>/dev/null \
  || launchctl load "$PLIST_DST" 2>/dev/null \
  || echo "⚠️ 自动加载失败，请手动运行：launchctl bootstrap gui/$(id -u) \"$PLIST_DST\""

echo
echo "✅ 安装完成！"
echo "  • 手动领取 ：双击 『领取积分.command』"
echo "  • 每天自动 ：每天 00:05 自动领取（登录时若昨晚没领会补领）"
echo "  • 立即验证 ：open -a \"$SKILL_DIR/WB积分领取.app\""
