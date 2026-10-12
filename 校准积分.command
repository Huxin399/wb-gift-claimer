#!/bin/bash
# 校准积分.command —— 双击运行
# 作用：安装依赖 + 跑 --dry 校准，把「带坐标的 OCR 文字」和截图存到工作区，
#       之后把这两个文件发给助手，他据此把按钮坐标/关键词写死进脚本。
# 说明：本文件在你自己的 Terminal（GUI 会话）中运行，所以能截屏；
#       WorkBuddy 的进程无法截屏，与权限无关（已验证）。

cd "$(dirname "$0")" || exit 1

# 强制使用与脚本/定时任务一致的 managed python（避免双击时用到系统 python3 撞 PEP668）
PY="/Users/hx/.workbuddy/binaries/python/versions/3.13.12/bin/python3"
if [ ! -x "$PY" ]; then
  echo "⚠️ 未找到 managed python，回退到 PATH 中的 python3"
  PY="$(command -v python3)"
fi

LOG="wb_gift_setup.log"
# 全程日志（含 pip 报错的完整内容），跑完助手可直接读取诊断
exec > >(tee -a "$LOG") 2>&1

echo "=================================================="
echo " WorkBuddy 积分领取 · 一键校准"
echo " 使用 python: $PY"
echo " 日志文件: $LOG"
echo "=================================================="
echo
echo "【前置检查】请确保："
echo "  1) WorkBuddy 已打开，且停留在能看到「领取积分/礼包」按钮的界面"
echo "  2) 系统设置 → 隐私与安全性 → 屏幕录制 / 辅助功能 已授权「终端.app」"
echo
read -p "确认 WorkBuddy 已打开并可见？按回车继续（Ctrl+C 取消）…"

# ---- 权限自检：屏幕录制（截图必需）----
while true; do
  echo
  echo "【0/3】自检：屏幕录制权限（截图必需）…"
  rm -f /tmp/_scr_perm_test.png
  if screencapture -x /tmp/_scr_perm_test.png 2>/dev/null && [ -s /tmp/_scr_perm_test.png ]; then
    echo "✅ 屏幕截图可用（已授予『屏幕录制』权限）"
    rm -f /tmp/_scr_perm_test.png
    break
  else
    echo "❌ 无法截图：『屏幕录制』权限未授予，或终端需重启后才能生效。"
    echo "   修复步骤："
    echo "   1) 打开 系统设置 → 隐私与安全性 → 屏幕录制"
    echo "   2) 确认列表中有『终端.app』(Terminal) 且开关为【打开】"
    echo "      - 若已打开但依旧失败：先关掉开关，再重新打开以重置授权"
    echo "   3) 完全退出终端（终端菜单 → 退出终端 / 快捷键 Cmd+Q，关窗口不够）"
    echo "   4) 重新打开终端，再次双击本文件"
    echo "   （若你用 iTerm2 等其他终端跑，请对应授予『屏幕录制』权限）"
    read -p "完成授权并重启终端后，按回车重试；或按 Ctrl+C 取消…"
  fi
done

echo
echo "【1/3】检查并安装 Python 依赖（首次约 1~2 分钟，请耐心）…"

# 清除可能继承自环境的代理（指向本机已失效的 sandbox 代理会导致 pip 连不上 PyPI）
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY http_proxy https_proxy all_proxy
export PIP_NO_PROXY="*"

if "$PY" -c "import pyautogui, rapidocr_onnxruntime" 2>/dev/null; then
  echo "✅ 依赖已就绪，跳过安装"
else
  echo "（首次安装中，若卡住请稍候；完整日志已写入 $LOG）"
  "$PY" -m pip install --user --proxy="" pyautogui numpy pillow pyobjc rapidocr-onnxruntime
  if [ $? -ne 0 ]; then
    echo "❌ 依赖安装失败。完整报错已写入 $LOG，请将该文件发给助手诊断。"
    read -p "按回车关闭窗口…"
    exit 1
  fi
fi
echo "✅ 依赖就绪"

echo
echo "【2/3】激活 WorkBuddy 并截图 + OCR（不点击）…"
"$PY" wb_gift_claimer_mac.py --dry > wb_gift_dry_output.txt 2>&1
echo "✅ 校准完成"

echo
echo "【3/3】结果已保存到："
echo "   - wb_gift_dry_output.txt  （带坐标的识别文字）"
echo "   - _calib_dry.png          （当前屏幕截图）"
echo "把这两个文件交给助手即可，他会据此完成按钮坐标校准。"
echo
open -R wb_gift_dry_output.txt 2>/dev/null
open _calib_dry.png 2>/dev/null
echo "（已在访达中定位输出文件，并已打开截图供你查看）"
read -p "按回车关闭窗口…"
