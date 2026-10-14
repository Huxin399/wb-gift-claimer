#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WorkBuddy 每日礼包自动领取脚本 · macOS 版
=========================================
仿 workbuddy-gift-claimer (Windows) 的视觉自动化思路，适配 macOS：

    Windows 原版：pyautogui(Windows) + rapidocr，找窗口 → OCR → 点击
    本 Mac 版  ：pyautogui(macOS) + rapidocr，截全屏 → OCR → 点击

界面流程（用户确认）：
  左侧菜单没有领取入口 → 点【左下角 logo】→ 弹出「buddy 加油站」窗口
  → 窗口下方两个按钮，点其中的【领取】即可。

核心原则（与原版一致，安全）：
  - 不读取任何登录态 / token / cookie / keychain
  - 不外传任何数据（纯本地截图 + 本地 OCR + 本地日志）
  - 无破坏性操作（只点击 WorkBuddy 界面上的"领取"按钮）

运行前置（见 README）：
  1) pip install pyautogui rapidocr-onnxruntime pyobjc
  2) 系统设置 → 隐私与安全性 → 辅助功能 + 屏幕录制：授权运行本脚本的终端/Python
  3) WorkBuddy 保持打开，并最终停在能看到左下角 logo 的主界面

用法：
  python3 wb_gift_claimer_mac.py            # 普通领取（带防重复）
  python3 wb_gift_claimer_mac.py --force    # 忽略今日已领记录，强制尝试
  python3 wb_gift_claimer_mac.py --dry      # 两阶段校准：阶段1截主界面 → 阶段2真点logo开弹窗、
                                            #   识别并记录「领取」按钮坐标但不点击（安全，不会领取）
  python3 wb_gift_claimer_mac.py --screenshot  # 仅截全屏存图（_calib_screen.png），不需 OCR 依赖
"""

import sys
import os
import time
import json
import logging
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pyautogui
    import numpy as np
    from PIL import Image
except ImportError as e:
    sys.stderr.write(
        f"\n[缺少依赖] {e}\n"
        "请先安装基础依赖：\n"
        "    python3 -m pip install pyautogui numpy pillow pyobjc\n"
        "（Apple Silicon 若报 pyobjc 错误，先：python3 -m pip install pyobjc-core pyobjc）\n\n"
    )
    sys.exit(1)


# ---------------- 配置 ----------------
SCRIPT_DIR = Path(__file__).parent.resolve()
LOG_FILE   = SCRIPT_DIR / "wb_gift.log"
LEARN_FILE = SCRIPT_DIR / "wb_gift_learn.json"
# 领取状态文件：记录最近一次成功领取日期，用于「当天只领一次」判断（比解析日志更可靠）
CLAIM_STATE_FILE = SCRIPT_DIR / ".claimed_today"

# 领取按钮候选文字（命中任意一个即点击）
GIFT_BTN_KEYWORDS = ["领取100积分", "领取积分", "立即领取", "签到领积分", "领取礼包",
                     "领取奖励", "100 Credits", "领取"]
# 已领取状态的识别文字（命中说明今天已领过）
CLAIMED_KEYWORDS = ["今日礼包已到账", "已领取", "已签到", "今日已领", "已到账"]

# ===== 真实界面流程（用户 2026-10-12 亲口确认）=====
# 1) 左侧菜单里【没有】领取按钮；
# 2) 必须先点【左下角的 logo】→ 弹出「buddy 加油站」窗口；
# 3) 窗口下方有两个按钮，其中一个是「领取」，点它即可。
# 因此脚本动作 = 点左下角 logo → 等弹窗 → 对全屏 OCR 找「领取」→ 点它。
# 若弹窗未出（logo 没点中），则换下一个候选坐标重试。
POPUP_KEYWORDS = ["buddy 加油站", "加油站"]   # 用于确认弹窗已打开

# 左下角 logo 候选坐标（屏幕比例，原点在左上）。
# 2026-10-12 干净截图实测：「胡鑫」头像中心 ≈ 逻辑 (147,857) = 比例 (0.097, 0.873)。
# ⚠️ 注意：窗口底部被 Dock 占据，旧候选 y≈0.97 会点进 Dock，已废弃。
LOGO_CANDIDATES = [
    (0.097, 0.873), (0.10, 0.86), (0.08, 0.87),
    (0.10, 0.85), (0.12, 0.86),
]

# 「领取」按钮兜底坐标：2026-10-12 弹窗截图实测，按钮（未领时显示「领取」、
# 已领时显示「今日已领」）中心 ≈ 逻辑 (202,460) = 比例 (0.134, 0.468)。
# OCR 偶尔把「领取」识别成乱码时，用此坐标兜底点一次，避免漏领。
CLAIM_BUTTON_CANDIDATES = [(0.134, 0.468)]

WAIT_PANEL   = 4.0   # 点开头像后等待面板展开（秒）
WAIT_CLICK   = 1.0
RETRY_INTERVAL = 180  # 失败重试间隔（秒）= 3 分钟
MAX_RETRIES  = 3

# 🛡️ 不打扰用户守卫：用户至少空闲这么久（秒）才动手，避免打断正在操作
#   建议 120~300 秒。设太小（如 5 秒）可能你刚停手就弹窗；设太大则可能一直不触发。
IDLE_THRESHOLD = 180

pyautogui.FAILSAFE = True   # 鼠标移到屏幕四角可紧急中止
pyautogui.PAUSE = 0.3

_ocr = None
def get_ocr():
    global _ocr
    if _ocr is None:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            sys.stderr.write(
                "\n[缺少 OCR 依赖] 请安装：\n"
                "    python3 -m pip install rapidocr-onnxruntime\n\n"
                "（只想截图的纯截图模式 --screenshot 不需要此依赖）\n"
            )
            sys.exit(1)
        _ocr = RapidOCR()
    return _ocr


# ---------------- 日志 ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("wb_gift_mac")


# ========== 日志分析（防重复领取 + 开机补偿） ==========
def _today() -> str:
    return datetime.now().strftime("%Y-%m-%d")

def already_claimed_today() -> bool:
    """判断今天是否已成功领取。

    优先读状态文件（领取成功时写入当天日期，最可靠）；
    若状态文件缺失，再回退到「今天日志里出现过成功标记」的判定（兼容旧逻辑）。
    """
    today = _today()
    # 1) 状态文件首选
    try:
        if CLAIM_STATE_FILE.exists() and CLAIM_STATE_FILE.read_text(encoding="utf-8").strip() == today:
            return True
    except Exception:
        pass
    # 2) 日志兜底
    if LOG_FILE.exists():
        content = LOG_FILE.read_text(encoding="utf-8", errors="replace")
        if (f"{today}  INFO  [OK]" in content) or (f"{today}  INFO  ✅" in content):
            return True
    return False

def mark_claimed_today():
    """写入「今天已领取」状态。之后当天任何一次运行都会在首行直接跳过，不再弹窗/点击。"""
    try:
        CLAIM_STATE_FILE.write_text(_today(), encoding="utf-8")
    except Exception as e:
        log.warning(f"写入领取状态文件失败（不影响本次领取）: {e}")

def should_run_on_boot() -> bool:
    if not LOG_FILE.exists():
        return True
    lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").strip().split("\n")
    last_date = None
    for line in reversed(lines):
        if line.strip() and len(line) >= 10:
            last_date = line[:10]
            break
    if last_date and last_date < _today() and not already_claimed_today():
        log.info(f"[开机补偿] 上次日志={last_date}，今天未领，触发补偿")
        return True
    return False


# ========== 自学习（校准用） ==========
def load_learn() -> dict:
    if LEARN_FILE.exists():
        try:
            d = json.loads(LEARN_FILE.read_text(encoding="utf-8"))
            d.setdefault("gift_btn_keywords", list(GIFT_BTN_KEYWORDS))
            d.setdefault("claimed_keywords", list(CLAIMED_KEYWORDS))
            d.setdefault("logo_candidates", [list(c) for c in LOGO_CANDIDATES])
            d.setdefault("history", [])
            return d
        except Exception:
            log.warning("经验文件损坏，使用默认配置")
    return {
        "gift_btn_keywords": list(GIFT_BTN_KEYWORDS),
        "claimed_keywords": list(CLAIMED_KEYWORDS),
        "logo_candidates": [list(c) for c in LOGO_CANDIDATES],
        "history": [],
    }

def save_learn(d: dict):
    if len(d.get("history", [])) > 30:
        d["history"] = d["history"][-30:]
    LEARN_FILE.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

def record_ocr(d: dict, texts: list, ctx: str):
    d.setdefault("history", []).append({
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ctx": ctx, "texts": texts,
    })
    # 自动发现可能的"领取"新按钮文字
    for t in texts:
        t2 = t.replace(" ", "").strip()
        if "领取" in t2 and t2 not in d["gift_btn_keywords"] and len(t2) <= 12:
            d["gift_btn_keywords"].insert(0, t2)
            log.info(f"[自学习] 发现可能的领取按钮文字: [{t2}]")


# ========== 🛡️ 不打扰用户守卫（空闲 / 锁屏检测） ==========
def get_idle_seconds() -> float:
    """返回系统自上次键盘/鼠标输入以来的秒数（HIDIdleTime）。
    通过 ioreg 读取，无需屏幕录制权限。取不到时返回 0（宁可跳过、不冒险打扰）。"""
    try:
        import re
        out = subprocess.run(["ioreg", "-c", "IOHIDSystem"],
                             capture_output=True, text=True, timeout=10).stdout
        m = re.search(r'"HIDIdleTime"\s*=\s*(\d+)', out)
        if m:
            return int(m.group(1)) / 1_000_000_000.0  # ns → s
    except Exception:
        pass
    return 0.0

def is_locked() -> bool:
    """判断系统是否处于锁屏（登录界面）状态。锁屏时最前进程是 loginwindow。"""
    try:
        r = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to get name of first process whose frontmost is true'],
            capture_output=True, text=True, timeout=10)
        return r.stdout.strip().lower() == "loginwindow"
    except Exception:
        return False

def guard_user_busy() -> bool:
    """返回 True 表示当前不适合运行（应跳过），False 表示可安全动手。
    锁屏、或用户最近在活跃操作 → 跳过，绝不抢鼠标/弹窗。"""
    if is_locked():
        log.info("[守卫] 系统处于锁屏，跳过（解锁后会再尝试补领）")
        return True
    idle = get_idle_seconds()
    if idle < IDLE_THRESHOLD:
        log.info(f"[守卫] 你正在使用电脑（空闲仅 {idle:.0f}s < {IDLE_THRESHOLD}s），本次跳过")
        return True
    return False


# ========== 窗口 / 截图 / OCR ==========
def activate_workbuddy():
    """把 WorkBuddy 带到最前，并隐藏会挡路的 终端/访达 窗口。

    经验教训（2026-10-12 校准实测）：
    - `tell application "WorkBuddy" to activate` 对该 Electron 应用不可靠，
      终端窗口仍盖在最前，截图里全是终端内容；
    - 终端/访达窗口不清开，OCR 全是干扰，且「领取」按钮会被盖住。
    """
    # 确保 WorkBuddy 已启动（launchd 定时跑时它可能还没开）
    try:
        chk = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to (name of processes) contains "WorkBuddy"'],
            capture_output=True, text=True, timeout=10)
        if chk.stdout.strip().lower() != "true":
            log.info("WorkBuddy 未运行，先启动…")
            subprocess.run(["open", "-a", "WorkBuddy"],
                           capture_output=True, text=True, timeout=15)
            time.sleep(5.0)
    except Exception as e:
        log.warning(f"检查/启动 WorkBuddy 异常（继续）: {e}")

    activated = False
    for cmd in [
        # 进程名匹配（AppleScript 文本比较默认不区分大小写，WorkBuddy/workbuddy 都能中）
        'tell application "System Events" to set frontmost of '
        '(first process whose name contains "workbuddy") to true',
        'tell application "WorkBuddy" to activate',
    ]:
        try:
            r = subprocess.run(["osascript", "-e", cmd],
                               capture_output=True, text=True, timeout=10)
            if r.returncode == 0:
                activated = True
                break
        except Exception as e:
            log.warning(f"激活命令异常（继续尝试）: {e}")
    if not activated:
        log.warning("WorkBuddy 激活未确认成功（继续尝试）")
    time.sleep(1.0)

    # 隐藏 终端 和 访达（launchd 定时跑时无终端进程，失败无害忽略）
    for app in ("Terminal", "Finder"):
        try:
            subprocess.run(
                ["osascript", "-e",
                 f'tell application "System Events" to set visible of process "{app}" to false'],
                capture_output=True, text=True, timeout=10,
            )
        except Exception:
            pass
    time.sleep(1.0)


def ocr_screen(save_path: str | None = None) -> list:
    """截全屏并 OCR，返回 [(cx, cy, text, score), ...]，坐标已换算成逻辑点。

    Retina 适配（2026-10-12 校准实测发现的关键坑）：
    pyautogui.screenshot() 拿到的是设备像素（本机 2x，3024x1964），
    而 pyautogui.click() 用的是逻辑坐标（1512x982）。
    若不除以缩放比，点击位置会整体偏 2 倍，永远点不到按钮。
    """
    try:
        img = pyautogui.screenshot()
    except Exception as e:
        # 最常见根因：运行本脚本的进程（WB积分领取.app / 终端）未获「屏幕录制」授权，
        # 导致底层 screencapture 返回 exit 1。给出可操作的明确提示，避免只看到一堆堆栈。
        msg = str(e)
        if "screencapture" in msg or "exit status 1" in msg:
            raise RuntimeError(
                "截图失败：运行本脚本的进程缺少「屏幕录制」权限。\n"
                "→ 请打开 系统设置 → 隐私与安全性 → 屏幕录制，\n"
                "  把本程序对应的 App（WB积分领取.app 或 终端.app）加入并打勾；\n"
                "  授予后必须完全退出并重新运行本程序权限才生效。"
            )
        raise
    if save_path:
        try:
            img.save(save_path)
            log.info(f"[截图] 已保存到: {save_path}")
        except Exception as e:
            log.warning(f"截图保存失败: {e}")
    arr = np.asarray(img)
    result, _ = get_ocr()(arr)
    try:
        scale = img.size[0] / pyautogui.size()[0]
    except Exception:
        scale = 1.0
    if scale != 1.0:
        log.info(f"[Retina] 截图 {img.size[0]}x{img.size[1]}，缩放比 {scale:.2f}，坐标将换算为逻辑点")
    scaled = []
    for item in (result or []):
        if len(item) < 3:
            continue
        box, text, score = item[0], str(item[1]).strip(), float(item[2])
        xs = [p[0] / scale for p in box]
        ys = [p[1] / scale for p in box]
        cx = int((min(xs) + max(xs)) / 2)
        cy = int((min(ys) + max(ys)) / 2)
        scaled.append((cx, cy, text, score))
    return scaled


def find_keyword(results: list, keywords: list):
    """在 OCR 结果（(cx,cy,text,score) 列表）里找含关键词的条目，
    优先文字最短的（最像独立按钮），返回 (cx, cy, text, score) 或 None。"""
    best = None
    for cx, cy, text, score in results:
        for kw in keywords:
            if kw in text:
                if best is None or len(text) < len(best[2]):
                    best = (cx, cy, text, score)
    return best


# ⚠️ 2026-10-12 实测教训：聊天正文里也会出现"加油站/领取"等词
# （比如助手消息"「buddy 加油站』弹窗的真实位置…"），导致弹窗检测假阳性。
# 按钮必须是【短】文本；长句一律视为正文排除；再排除教学/对话常见词兜底。
FALSE_POSITIVE_WORDS = ["弹窗", "校准", "坐标", "候选", "脚本", "识别", "真实", "位置", "消息", "点击"]

def find_button(results: list, keywords: list, max_len: int = 8):
    """找"独立短按钮文字"：文本长度 ≤ max_len 才算按钮，长句（聊天正文）直接排除。
    用于弹窗确认与「领取」按钮定位，替代 find_keyword 的宽松匹配。"""
    best = None
    for cx, cy, text, score in results:
        if len(text) > max_len:
            continue
        if any(w in text for w in FALSE_POSITIVE_WORDS):
            continue
        for kw in keywords:
            if kw in text:
                if best is None or len(text) < len(best[2]):
                    best = (cx, cy, text, score)
    return best


# 系统隐私弹窗（TCC）特征词：出现即说明有授权框挡在屏幕上，点击会被它吃掉
TCC_DIALOG_KEYWORDS = ["打开系统设置", "想要录制此电脑", "想要控制", "允许下面的应用程序"]

def find_tcc_dialog(results: list):
    """判断屏幕上是否真有系统隐私授权弹窗（TCC）挡路。

    教训（2026-10-12）：聊天正文里会提及『打开系统设置/想要录制此电脑』等词，
    若用 find_keyword 宽松匹配会被误判成系统弹窗，导致校准/领取无故中止。
    真 TCC 弹窗的特征：包含上述词的【短文本块】（按钮/标题，≤20字），
    且通常伴随「打开系统设置」按钮。长句（>20字）一律视为聊天正文，忽略。
    """
    for cx, cy, text, score in results:
        if len(text) > 20:
            continue
        for kw in TCC_DIALOG_KEYWORDS:
            if kw in text:
                return (cx, cy, text, score)
    return None


# ========== 单次领取尝试 ==========
def try_claim_once(learn: dict) -> str:
    """
    真实流程：点左下角 logo → 弹出「buddy 加油站」→ 点其中的「领取」按钮。
    返回: "claimed" 已领过 | "success" 成功 | "fail" 失败
    """
    activate_workbuddy()

    W, H = pyautogui.size()
    log.info(f"屏幕尺寸: {W}x{H}")

    for idx, (xr, yr) in enumerate(learn["logo_candidates"]):
        ax = int(W * xr); ay = int(H * yr)
        log.info(f"点击左下角 logo 候选#{idx+1} @ ({ax},{ay}) [比例 {xr:.0%},{yr:.0%}]")
        pyautogui.click(ax, ay)
        time.sleep(WAIT_PANEL)

        results = ocr_screen()
        texts = [r[2] for r in results]
        record_ocr(learn, texts, "gift_search")

        # 系统授权框（TCC）挡路检查：出现会让一切点击无效（仅短文本块才算，避免聊天正文误判）
        tcc = find_tcc_dialog(results)
        if tcc:
            log.error(f"检测到系统授权弹窗挡在屏幕上: [{tcc[2]}] @ ({tcc[0]},{tcc[1]})。"
                      "请在系统设置里完成授权、关掉该弹窗后重跑。本次中止。")
            return "fail"

        popup_open = find_button(results, POPUP_KEYWORDS) is not None
        log.info(f"弹窗（buddy 加油站）状态: {'已打开' if popup_open else '未打开'}")

        # 先判断是否已领取（可能在弹窗内直接显示）
        claimed = find_button(results, learn["claimed_keywords"], max_len=12)
        if claimed:
            log.info(f"检测到已领取标识: [{claimed[2]}]，今天已领过")
            return "claimed"

        # 找「领取」按钮（必须是独立短按钮，防止聊天正文误命中）
        hit = find_button(results, learn["gift_btn_keywords"])
        if hit:
            log.info(f"OCR 命中领取按钮: [{hit[2]}] @ 屏幕({hit[0]},{hit[1]})")
            pyautogui.click(hit[0], hit[1])
            time.sleep(WAIT_CLICK)
            pyautogui.press("escape")
            time.sleep(0.5)
            # 二次确认
            res2 = ocr_screen()
            if find_keyword(res2, learn["claimed_keywords"]):
                return "success"
            log.info("已点击领取按钮，标记成功（如未到账请手动确认）")
            return "success"

        # OCR 没认出「领取」短按钮，但弹窗已开 → 用焊死坐标兜底点一次
        if popup_open:
            for (xr, yr) in CLAIM_BUTTON_CANDIDATES:
                bx, by = int(W * xr), int(H * yr)
                log.info(f"OCR 未命中领取按钮，使用焊死兜底坐标 ({bx},{by}) [比例 {xr:.3f},{yr:.3f}] 点击")
                pyautogui.click(bx, by)
                time.sleep(WAIT_CLICK)
                pyautogui.press("escape")
                time.sleep(0.5)
                res2 = ocr_screen()
                if find_keyword(res2, learn["claimed_keywords"]):
                    return "success"
                log.info("兜底点击完成，标记成功（如未到账请手动确认）")
                return "success"

        if popup_open:
            # 弹窗已开但没识别出「领取」文字（可能 OCR 漏了中文），再等 1 秒复扫一次
            log.warning("弹窗已开但未识别到「领取」文字，1 秒后复扫")
            time.sleep(1.0)
            res2 = ocr_screen()
            hit2 = find_button(res2, learn["gift_btn_keywords"])
            if hit2:
                pyautogui.click(hit2[0], hit2[1])
                time.sleep(WAIT_CLICK)
                pyautogui.press("escape")
                return "success"
            log.warning("复扫仍未识别，关闭弹窗换下一个 logo 坐标")
        else:
            log.warning(f"logo 候选#{idx+1}未触发弹窗，关闭重试")

        pyautogui.press("escape")
        time.sleep(1.0)

    return "fail"


def _log_ocr_items(results: list, tag_keywords: list, cap: int = 120):
    """把 OCR 结果逐条写入日志（带坐标），命中关键词的行打标记。"""
    log.info(f"OCR 共识别 {len(results)} 条文字（逻辑坐标，可直接用于点击）：")
    for cx, cy, text, score in results[:cap]:
        tag = "  <<< 关键" if any(k in text for k in tag_keywords) else ""
        log.info(f"   ({cx:4d},{cy:4d})  {text}  [score {score:.2f}]{tag}")
    if len(results) > cap:
        log.info(f"   ...（共 {len(results)} 条，仅显示前 {cap}）")


# ========== 主流程 ==========
# ========== 启动权限自检 ==========
def preflight_permissions() -> bool:
    """快速自检：能否截图（需要屏幕录制权限）。不可用时打印明确指引并返回 False。
    点击所需的辅助功能已在日志点击行为中验证，这里只查最容易遗漏的屏幕录制。"""
    try:
        pyautogui.screenshot()
    except Exception as e:
        msg = str(e)
        if "screencapture" in msg or "exit status 1" in msg:
            log.error("【权限自检】缺少「屏幕录制」权限 → 截图/OCR 会失败，无法定位领取按钮。")
            log.error("  → 系统设置 → 隐私与安全性 → 屏幕录制 → 加入并勾选 本程序对应的 App"
                      "（WB积分领取.app 或 终端.app），然后【完全退出本程序】重跑，权限才生效。")
            return False
        log.warning(f"【权限自检】截图异常（非权限问题，继续）: {msg}")
    log.info("【权限自检】屏幕录制可用 ✅")
    return True


def main(force=False, dry=False, screenshot_only=False):
    # 🛑 快速短路：今天已领取 → 立刻停止，连截图/权限检查都不做（真正"当天零操作"）。
    #    放在最前，避免无谓唤醒时还去截屏、写日志，给你"还在跑"的错觉。
    #    （仅 --force 可绕过，用于测试或手动补领。）
    if not force and already_claimed_today():
        log.info("今日已领取，跳过 ✅（当年不再进行任何截图/点击操作）")
        sys.stdout.write("\n今日已领取，无需重复操作。\n")
        return

    log.info("=" * 50)
    log.info("WorkBuddy 每日礼包自动领取 · macOS 版 开始")
    preflight_permissions()

    if dry:
        # 两阶段校准（2026-10-12 用户指正：不点 logo 就没有弹窗，
        # 纯截图校准永远看不到「领取」按钮，故阶段2必须真点 logo 开弹窗——但只看不点领取）
        log.info("[DRY 校准·两阶段] 阶段1:主界面截图 → 阶段2:点logo开弹窗(只识别,不点领取)")
        all_tags = GIFT_BTN_KEYWORDS + CLAIMED_KEYWORDS + POPUP_KEYWORDS

        # ---- 阶段 1：主界面（用于确认 WorkBuddy 置顶 + 观察侧边栏布局）----
        activate_workbuddy()
        W, H = pyautogui.size()
        log.info(f"屏幕尺寸: {W}x{H}")
        results = ocr_screen(save_path=str(SCRIPT_DIR / "_calib_dry.png"))
        log.info("[阶段1·主界面]")
        _log_ocr_items(results, all_tags)
        wb_markers = ["仪表盘", "充值订阅", "邀请返利", "渠道状态", "个人资料", "使用文档", "兑换"]
        seen = [m for m in wb_markers if any(m in t for _, _, t, _ in results)]
        if seen:
            log.info(f"[阶段1·校验] 检测到 WorkBuddy 界面特征 {seen} → WorkBuddy 已在最前 ✅")
        else:
            log.warning("[阶段1·校验] 未识别到 WorkBuddy 界面特征 —— WorkBuddy 可能被挡住或未打开")

        # ---- 阶段 2：点 logo 开弹窗（只识别，绝不点「领取」）----
        learn = load_learn()
        log.info("[阶段2] 依次点击 logo 候选，寻找「buddy 加油站」弹窗（只识别，不点领取）")
        popup_found = False
        for idx, (xr, yr) in enumerate(learn["logo_candidates"]):
            ax, ay = int(W * xr), int(H * yr)
            log.info(f"[阶段2] 点击 logo 候选#{idx+1} @ ({ax},{ay}) [比例 {xr:.2f},{yr:.2f}]")
            pyautogui.click(ax, ay)
            time.sleep(WAIT_PANEL)
            res = ocr_screen(save_path=str(SCRIPT_DIR / f"_calib_popup_{idx+1}.png"))
            _log_ocr_items(res, all_tags)

            # 系统授权框（TCC）挡路检查：仅短文本块才算，避免聊天正文提及误判
            tcc = find_tcc_dialog(res)
            if tcc:
                log.error(f"[阶段2] 检测到系统授权弹窗挡在屏幕上: [{tcc[2]}]。"
                          "请完成授权/关闭该弹窗后重新双击校准器。本次校准中止。")
                return

            claimed = find_button(res, learn["claimed_keywords"], max_len=12)
            gift = find_button(res, learn["gift_btn_keywords"])
            popup = find_button(res, POPUP_KEYWORDS)
            if claimed:
                log.info(f"[阶段2] 弹窗显示已领取标识: [{claimed[2]}] @ ({claimed[0]},{claimed[1]})")
            if gift:
                log.info(f"[阶段2] ⭐识别到「领取」按钮: [{gift[2]}] @ ({gift[0]},{gift[1]}) —— 已记录坐标，按校准规则不点击")
            if popup:
                log.info(f"[阶段2] ✅ 弹窗（buddy 加油站）已打开！logo 正确坐标 = ({ax},{ay}) [比例 {xr:.2f},{yr:.2f}] —— 已焊入候选首位")
                # 自学习：把验证过的 logo 位置放到候选首位
                learn["logo_candidates"].insert(0, [xr, yr])
                save_learn(learn)
                popup_found = True
                pyautogui.press("escape")
                time.sleep(1.0)
                break
            log.warning(f"[阶段2] 候选#{idx+1} 未触发弹窗，Esc 关闭后换下一个")
            pyautogui.press("escape")
            time.sleep(1.0)

        if not popup_found:
            log.warning("[阶段2] 所有 logo 候选均未触发弹窗。请确认：①WorkBuddy 在主屏最前且能看到左下角 logo；"
                        "②弹窗可能被 OCR 漏识别——把 _calib_popup_*.png 发给助手人工确认。")
        log.info("[DRY 校准] 结束。产出: _calib_dry.png（主界面）+ _calib_popup_*.png（弹窗）+ 本日志。")
        return

    if screenshot_only:
        log.info("[截图模式] 仅截取当前屏幕并存图，不 OCR、不点击")
        activate_workbuddy()
        W, H = pyautogui.size()
        log.info(f"屏幕尺寸: {W}x{H}")
        img = pyautogui.screenshot()
        sp = str(SCRIPT_DIR / "_calib_screen.png")
        img.save(sp)
        log.info(f"[截图模式] 已保存到: {sp}（把它发给我，我帮你标注按钮位置）")
        return

    # 🛡️ 不打扰用户守卫：你正用电脑 / 锁屏时绝不抢鼠标（手动 --force 时跳过守卫）
    if not force and guard_user_busy():
        log.info("[守卫] 本次跳过，等待下一次周期检查（你空闲时自动补领）")
        sys.stdout.write("\n[守卫] 检测到你正在使用电脑或锁屏，已自动跳过，稍后空闲时会再试。\n")
        return

    if not force and should_run_on_boot():
        log.info("[开机补偿] 触发补偿执行")
        force = True

    if not force and already_claimed_today():
        log.info("今日已领取，跳过 ✅")
        sys.stdout.write("\n今日已领取，无需重复操作。\n")
        return

    learn = load_learn()
    log.info(f"[自学习] 领取关键词: {learn['gift_btn_keywords']}")
    log.info(f"[自学习] 已领关键词: {learn['claimed_keywords']}")

    for attempt in range(1, MAX_RETRIES + 1):
        log.info(f"--- 第 {attempt}/{MAX_RETRIES} 次尝试 ---")
        try:
            status = try_claim_once(learn)
        except Exception as e:
            log.error(f"执行异常: {e}")
            status = "fail"

        if status == "claimed":
            log.info("[OK] 今日礼包已领取（之前已领）")
            mark_claimed_today()   # 当天不再重复运行
            sys.stdout.write("\n✅ 今日礼包已领取。\n")
            save_learn(learn)
            return
        if status == "success":
            log.info("[OK] 今日礼包领取成功")
            mark_claimed_today()   # 当天不再重复运行
            sys.stdout.write("\n✅ 今日 100 Credits 礼包已领取！\n")
            save_learn(learn)
            return

        if attempt < MAX_RETRIES:
            log.warning(f"第 {attempt} 次失败，{RETRY_INTERVAL//60} 分钟后重试")
            sys.stdout.write(f"\n第 {attempt} 次失败，{RETRY_INTERVAL//60} 分钟后重试…\n")
            time.sleep(RETRY_INTERVAL)

    log.error(f"连续 {MAX_RETRIES} 次失败。可能：界面变化/OCR未识别/WorkBuddy未打开。")
    sys.stdout.write(f"\n❌ 连续 {MAX_RETRIES} 次失败，请手动领取或在 WorkBuddy 打开状态下重试。\n")


if __name__ == "__main__":
    force = "--force" in sys.argv
    dry = "--dry" in sys.argv
    screenshot_only = "--screenshot" in sys.argv
    main(force=force, dry=dry, screenshot_only=screenshot_only)
