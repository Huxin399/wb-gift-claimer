# wb-gift-claimer · WorkBuddy 每日积分自动领取（macOS）

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Platform: macOS](https://img.shields.io/badge/Platform-macOS-blue.svg)](https://www.apple.com/macos/)

一个**可分享、可复用**的 WorkBuddy 用户技能：在 macOS 上**自动领取** WorkBuddy 的每日积分礼包（100 通用积分）。

仿自 Windows 版 `workbuddy-gift-claimer`，在 macOS 上用**视觉自动化**（截图 + OCR + 模拟点击）实现。
WorkBuddy 目前**没有**"领取积分"的开放接口，所以只能靠"看屏幕、点按钮"——这是原版也是本技能唯一的实现方式。

---

## ✨ 功能
- **每 10 分钟智能检查**：你空闲（≥180 秒无键鼠操作）且未锁屏时，自动领取 100 通用积分；错过不漏，空闲即补领
- **智能不打扰守卫**：检测到你正在用电脑 / 锁屏时自动跳过，**绝不会抢鼠标、不会突然弹窗打扰你**
- 也可手动：双击 `领取积分.command` 立即领取
- 纯本地运行，**不读取任何登录态 / 凭证，不外传任何数据**

---

## 📦 安装（推荐：从 GitHub）

```bash
# 1. 克隆到 WorkBuddy 技能目录
git clone https://github.com/<你的用户名>/wb-gift-claimer \
  ~/.workbuddy/skills/wb-gift-claimer

# 2. 一键安装：装依赖 + 配置定时任务 + 引导授权
bash ~/.workbuddy/skills/wb-gift-claimer/install.sh
```

> 装完后**重启 WorkBuddy**，即可在技能列表中看到 `wb-gift-claimer`，对话里说"帮我领积分"就能触发。

### 不使用 WorkBuddy 技能体系、只要个能自动领的程序？
克隆下来后，跳过第 2 步里的技能注册，直接：
```bash
# 装依赖（只需一次）
~/.workbuddy/binaries/python/versions/3.13.12/bin/python3 \
  -m pip install pyautogui rapidocr-onnxruntime pyobjc pillow numpy
# 给 .app 授权（见下）后，双击 领取积分.command 即可手动领；
# 想自动就跑一次 install.sh（它只做依赖+定时+引导，不影响其它）
```

---

## 🔐 必须授权（macOS 安全限制，漏掉必失败 ⚠️）

系统设置 → 隐私与安全性 → **屏幕录制** 和 **辅助功能**：
把 `WB积分领取.app` 加进去并打勾。（裸进程拿不到截屏权限，必须用 `.app` 形式运行。）

> ⚠️ **最容易踩的坑**：脚本会自动"点 logo 弹出加油站面板 → 截图 OCR 找领取按钮 → 点击"。
> 若只授权了**辅助功能**而漏了**屏幕录制**，则 logo 能点开、弹窗能弹出，但截图 OCR 那一步会因
> `screencapture` 被系统拒绝而直接抛异常 → **你只会看到弹窗、永远看不到点击**。
> 两个权限必须**都给** `WB积分领取.app`，且授予后**必须完全退出并重新运行本程序**，权限才生效。

授权后让权限生效（屏幕录制权限 toggle 后，进程必须重启）：
```bash
launchctl bootout gui/$(id -u)/com.workbuddy.giftclaim 2>/dev/null
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.workbuddy.giftclaim.plist
```

---

## 🚀 用法

| 方式 | 操作 |
|------|------|
| 对话触发 | 在 WorkBuddy 里说"帮我领积分"，技能会被自动调用 |
| 手动领取 | 双击 `领取积分.command` |
| 强制领取（绕过守卫/防重复） | 终端运行 `python3 wb_gift_claimer_mac.py --force` |
| 校准 | 双击 `校准积分.command`（只识别按钮、绝不点击，用于界面变化后重新校准） |
| 仅截图 | `python3 wb_gift_claimer_mac.py --screenshot` 生成 `_calib_screen.png` 发给我标注 |

---

## ⏱️ 自动领取是怎么工作的

1. `install.sh` 写入一个 **launchd 定时任务**（`~/Library/LaunchAgents/com.workbuddy.giftclaim.plist`），
   每 **10 分钟** 唤醒一次脚本（替代"定点 00:05"，好处是错峰、错过不漏）。
2. 脚本启动先做**权限自检**，确认屏幕录制可用。
3. 再跑**不打扰守卫**：
   - 你**正在用电脑**（最近 180 秒内碰过键鼠）→ 立刻跳过，等下个周期；
   - 你**锁屏**了 → 跳过，解锁后再补；
   - 你**离开 ≥3 分钟且没锁屏** → 才真正动手。
4. 动手时：激活 WorkBuddy → 点左下角 logo → 弹「buddy 加油站」→ OCR 找到「领取」按钮并点击 → 关闭弹窗。
5. 领取结果写进 `wb_gift.log`，今天已领会识别「今日已领」并干净收尾，不会重复乱点。

> 所以你**正常关机 / 睡眠即可**，不用电脑整夜不睡；回来解锁后几分钟内会自动补领。

---

## ✅ 怎么确认它真的领到了

看日志（每次运行都有记录）：
```bash
tail -20 ~/.workbuddy/skills/wb-gift-claimer/wb_gift.log
```
成功会看到类似：
```
[权限自检] 屏幕录制可用 ✅
OCR 命中领取按钮: [立即领取] @ 屏幕(201,460)
[OK] 今日礼包领取成功
```
或在 WorkBuddy 的「buddy 加油站」面板里查看本期已领天数 +1。

---

## 🛠️ 排错速查表

| 现象 | 原因 / 解决 |
|------|------|
| 弹窗开了但**从不点领取** | **缺屏幕录制权限**（见上「必须授权」）。日志会出现 `screencapture ... exit status 1` |
| 日志首行 `缺少「屏幕录制」权限` | 没给 `WB积分领取.app` 屏幕录制；去系统设置补上并**重跑 launchd 任务** |
| 任务一直不运行 | 检查是否加载：`launchctl list \| grep giftclaim`；没有就 `bootstrap` 一次 |
| 提示 `缺少依赖` / `No module named pyautogui` | 跑 `install.sh` 或手动 `pip install pyautogui rapidocr-onnxruntime pyobjc` |
| 点击落空 / 找不到按钮 | WorkBuddy 界面改版了，双击 `校准积分.command` 重新校准 |
| 锁屏 / 合盖时没领 | 正常：锁屏无 GUI，脚本自动跳过，解锁空闲后补领 |

---

## 📁 文件清单

| 文件 | 作用 |
|------|------|
| `SKILL.md` | 技能元数据（WorkBuddy 识别用） |
| `wb_gift_claimer_mac.py` | 主脚本（核心逻辑：激活→点logo→OCR→点领取） |
| `领取积分.command` / `校准积分.command` | 双击启动器（macOS） |
| `WB积分领取.app` | 供 launchd 以 GUI 会话启动，继承 TCC 权限 |
| `install.sh` | 一键安装 + 配置每 10 分钟定时 + 引导授权 |
| `LICENSE` / `.gitignore` | 开源协议与忽略规则 |
| `wb_gift_learn.json` / `wb_gift.log` | 运行时生成（已 gitignore） |

---

## 🗑️ 卸载
```bash
launchctl bootout gui/$(id -u)/com.workbuddy.giftclaim 2>/dev/null
rm ~/Library/LaunchAgents/com.workbuddy.giftclaim.plist
rm -rf ~/.workbuddy/skills/wb-gift-claimer
```

---

## ⚠️ 免责声明
- 本工具通过"视觉自动化"操作 WorkBuddy 界面，**非官方 API**；WorkBuddy 大改版导致布局变化时需重跑校准。
- 仅在 **macOS** 可用；依赖系统 GUI 会话与屏幕录制权限。锁屏 / 合盖时会自动跳过。
- 本仓库与 WorkBuddy 官方无隶属关系，仅供个人便捷使用。

## 🤝 贡献
欢迎 Fork + PR：
1. Fork 本仓库
2. 新建分支 `feat/你的改动`
3. 提交后发起 Pull Request

界面坐标已尽量用比例存储、并支持重新校准，适配不同分辨率 / 缩放。
