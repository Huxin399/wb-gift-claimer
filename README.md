# wb-gift-claimer · WorkBuddy 每日积分自动领取（macOS）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS-blue.svg)](https://www.apple.com/macos/)

一个**可分享、可复用**的 WorkBuddy 用户技能：在 macOS 上自动领取 WorkBuddy 的每日积分礼包（100 通用积分）。

仿自 Windows 版 `workbuddy-gift-claimer`，在 macOS 上用**视觉自动化**（截图 + OCR + 模拟点击）实现。
WorkBuddy 目前没有"领取积分"的开放接口，所以只能靠"看屏幕、点按钮"——这是原版也是本技能唯一的实现方式。

---

## ✨ 功能
- 每天 **00:05** 自动领取 100 通用积分（登录时若昨晚没领也会补领）
- 也可手动：双击 `领取积分.command` 立即领取
- 纯本地运行，**不读取任何登录态 / 凭证，不外传任何数据**

## 📦 从 GitHub 安装（推荐）
```bash
# 1. 克隆到 WorkBuddy 技能目录
git clone https://github.com/<你的用户名>/wb-gift-claimer \
  ~/.workbuddy/skills/wb-gift-claimer

# 2. 一键安装（装依赖 + 配置定时 + 引导授权）
bash ~/.workbuddy/skills/wb-gift-claimer/install.sh
```
> 若已安装过 WorkBuddy，重启它即可在技能列表中看到 `wb-gift-claimer`。

## 🚀 用法
| 方式 | 操作 |
|------|------|
| 对话触发 | 在 WorkBuddy 里说"帮我领积分"，技能会被自动调用 |
| 手动 | 双击 `领取积分.command` |
| 校准 | 双击 `校准积分.command`（只识别按钮、绝不点击，用于界面变化后重新校准） |

## 🔐 必须授权（macOS 安全限制）
系统设置 → 隐私与安全性 → **屏幕录制** 和 **辅助功能**：
把 `WB积分领取.app` 加进去并打勾。（裸进程拿不到截屏权限，必须用 `.app` 形式运行。）

## 📁 文件清单
| 文件 | 作用 |
|------|------|
| `SKILL.md` | 技能元数据（WorkBuddy 识别用） |
| `wb_gift_claimer_mac.py` | 主脚本（核心逻辑） |
| `领取积分.command` / `校准积分.command` | 双击启动器 |
| `WB积分领取.app` | 供 launchd 以 GUI 会话启动，继承 TCC 权限 |
| `install.sh` | 一键安装 + 配置每天自动领取 |
| `wb_gift_learn.json` | 自学习存档（运行时生成，已被 .gitignore 忽略） |

## 🤝 贡献
欢迎 Fork + PR：
1. Fork 本仓库
2. 新建分支 `feat/你的改动`
3. 提交后发起 Pull Request

界面坐标已尽量用比例存储、并支持重新校准，适配不同分辨率/缩放。

## ⚠️ 免责声明
- 本工具通过"视觉自动化"操作 WorkBuddy 界面，**非官方 API**，WorkBuddy 大改版导致布局变化时需重跑校准。
- 仅在 **macOS** 可用；依赖系统 GUI 会话与屏幕录制权限，锁屏 / 合盖无 GUI 时无法截屏。
- 本仓库与 WorkBuddy 官方无隶属关系，仅供个人便捷使用。
