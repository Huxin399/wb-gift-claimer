#!/bin/bash
# 双击本文件即可领取今日 WorkBuddy 积分（macOS）
# 首次使用前请先按 README 装好依赖并授权"辅助功能"
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"
PY="${PYTHON3:-python3}"
if ! "$PY" -c "import pyautogui, rapidocr_onnxruntime" >/dev/null 2>&1; then
  osascript -e 'display dialog "尚未安装依赖。请在终端运行：\npython3 -m pip install pyautogui rapidocr-onnxruntime pyobjc" buttons {"好"} default button 1' >/dev/null 2>&1
  echo "缺少依赖，请先：python3 -m pip install pyautogui rapidocr-onnxruntime pyobjc"
  exit 1
fi
"$PY" wb_gift_claimer_mac.py
echo "按任意键关闭窗口…"
read -n 1
