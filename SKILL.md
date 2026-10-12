---
name: wb-gift-claimer
description: 自动领取 WorkBuddy 每日积分/礼包（macOS 视觉自动化）。当用户说"领取积分""领每日礼包""每天自动领积分""WorkBuddy 积分""加油站"时使用。通过点左下角 logo 弹出 buddy 加油站、再点击领取按钮实现，纯本地运行、不读任何凭证。
---

# WorkBuddy 每日积分自动领取（macOS）

## 用途
为 macOS 用户自动领取 WorkBuddy 的每日积分礼包（100 通用积分）。
WorkBuddy 目前**没有**领取积分的开放接口，本技能用"视觉自动化"方式完成：
激活 WorkBuddy → 点左下角 logo → 弹出「buddy 加油站」面板 → 点其中的「领取」按钮。

## 何时使用
- 用户明确要求领取 / 自动领取 WorkBuddy 积分
- 用户提到"每日礼包""加油站""领积分""通用积分"

## 动作（按场景选择）
1. **手动领取**：运行 `领取积分.command`（双击），或 `python3 wb_gift_claimer_mac.py`
2. **校准**：运行 `校准积分.command`（点 logo 开弹窗 + OCR 识别，只识别不点击，安全）
3. **每天自动**：运行 `install.sh` 完成依赖安装、授权引导、launchd 定时（每天 00:05 + 登录补领）

## 前置条件
- macOS；已安装 python3（install.sh 会装好 pyautogui / rapidocr / pyobjc 等依赖）
- 系统设置 → 隐私与安全性 → **屏幕录制** / **辅助功能**：把 `WB积分领取.app` 加入并打勾
- WorkBuddy 保持打开（脚本会自动启动它）

## 安全说明
纯本地截图 + OCR + 模拟点击，**不读取任何登录态 / token / cookie / keychain**，
不外传任何数据（所有处理与日志都在本地），无破坏性操作。

## 文件清单
| 文件 | 作用 |
|------|------|
| `wb_gift_claimer_mac.py` | 主脚本（核心逻辑） |
| `领取积分.command` | 双击手动领取 |
| `校准积分.command` | 双击校准（只识别不点击） |
| `WB积分领取.app` | 供 launchd 以 GUI 会话启动，继承 TCC 权限 |
| `install.sh` | 一键安装 + 配置每天自动领取 |
| `wb_gift_learn.json` | 自学习存档（OCR 结果 / 历史） |

## 已知限制
- 依赖 macOS GUI 会话与屏幕录制权限；锁屏 / 合盖无 GUI 时无法截屏。
- 若 WorkBuddy 大改版导致界面布局变化，跑一次 `校准积分.command` 重新校准即可。
