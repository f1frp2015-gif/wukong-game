#!/usr/bin/env python3
"""哈悟空地图/传送功能验证脚本"""
import json, sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:8123/index.html"
SAVE_KEY = "haWukongProgressV3"
failures = []

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    # 新存档开始第一章
    page.goto(URL)
    page.wait_for_timeout(600)
    page.evaluate("localStorage.clear()")
    page.reload()
    page.wait_for_timeout(600)
    page.evaluate("startChapter(1)")
    page.wait_for_timeout(500)

    # ---- P 键开关地图 ----
    page.keyboard.press("p")
    page.wait_for_timeout(150)
    visible = page.evaluate("document.getElementById('map-panel').classList.contains('visible')")
    paused = page.evaluate("modalOpen")
    check("按 P 打开地图并暂停", visible and paused, f"visible={visible} modalOpen={paused}")
    title = page.evaluate("document.getElementById('map-title').textContent")
    check("黑风山地图标题", "黑风山" in title, title)
    dots = page.eval_on_selector_all("#map-box .map-dot", "els => els.map(e => e.textContent)")
    check("黑风山地标（入口+黑风大王）", any("入口" in d for d in dots) and any("黑风大王" in d for d in dots), str(dots))
    me = page.eval_on_selector_all("#map-box .map-player", "els => els.length")
    check("玩家位置标记存在", me == 1, str(me))

    # ---- 新存档神行：只有黑风山可用，其余禁用 ----
    travel = page.eval_on_selector_all("#map-travel button", "els => els.map(e => ({t: e.textContent, dis: e.disabled}))")
    print("  神行按钮:", [(b["t"], b["dis"]) for b in travel])
    check("新存档神行全部禁用（黑风山为当前，其余未解锁）",
          len(travel) == 4 and all(b["dis"] for b in travel), str(travel))

    # ---- 图内传送：点击地图 25%,25% 处 → 世界坐标约 (600,450) ----
    page.click("#map-box", position={"x": 160, "y": 120})  # box 宽 640 高 480
    page.wait_for_timeout(150)
    pos = page.evaluate("({x: player.x, y: player.y})")
    closed = page.evaluate("!document.getElementById('map-panel').classList.contains('visible')")
    check("点击地图瞬移到对应坐标", abs(pos["x"] - 600) < 5 and abs(pos["y"] - 450) < 5, str(pos))
    check("传送后地图关闭并恢复游戏", closed and page.evaluate("modalOpen") == False and page.evaluate("gameRunning") == True, "")

    # ---- 边缘 clamp：点击角落不应越界 ----
    page.keyboard.press("p")
    page.wait_for_timeout(100)
    page.click("#map-box", position={"x": 1, "y": 1})
    page.wait_for_timeout(100)
    pos = page.evaluate("({x: player.x, y: player.y})")
    check("边缘点击 clamp 在界内", pos["x"] >= 60 and pos["y"] >= 60, str(pos))

    # ---- 解锁后四个枢纽全开，神行到黄风岭 ----
    page.evaluate(f"""() => {{
        const s = JSON.parse(localStorage.getItem('{SAVE_KEY}') || '{{}}');
        s.chapterUnlocked = 3; s.reachedKuhai = true; s.reachedLeiyin = true;
        localStorage.setItem('{SAVE_KEY}', JSON.stringify(s));
    }}""")
    page.reload()
    page.wait_for_timeout(600)
    page.evaluate("startChapter(1)")
    page.wait_for_timeout(400)
    page.keyboard.press("p")
    page.wait_for_timeout(150)
    travel = page.eval_on_selector_all("#map-travel button", "els => els.map(e => ({t: e.textContent, dis: e.disabled}))")
    print("  解锁后神行按钮:", [(b["t"], b["dis"]) for b in travel])
    check("解锁后黄风岭/苦海/雷音可神行",
          not travel[1]["dis"] and not travel[2]["dis"] and not travel[3]["dis"] and travel[0]["dis"], str(travel))

    page.eval_on_selector_all("#map-travel button", "els => els[1].click()")
    page.wait_for_timeout(800)
    cm = page.evaluate("currentMap")
    boss_names = page.evaluate("enemies.filter(e => e.isBoss).map(e => e.name)")
    running = page.evaluate("gameRunning && !modalOpen")
    check("神行到黄风岭且 BOSS 已生成", cm == "huangfeng" and len(boss_names) > 0, f"{cm} {boss_names}")
    check("神行后游戏正常运行", running, "")

    # ---- 从黄风岭神行回黑风山 ----
    page.keyboard.press("p")
    page.wait_for_timeout(150)
    page.eval_on_selector_all("#map-travel button", "els => els[0].click()")
    page.wait_for_timeout(600)
    check("神行回黑风山", page.evaluate("currentMap") == "forest", page.evaluate("currentMap"))

    # ---- 剧情区域禁用神行：进禅院检查 ----
    page.evaluate("enterTemple()")
    page.wait_for_timeout(300)
    page.keyboard.press("p")
    page.wait_for_timeout(150)
    travel = page.eval_on_selector_all("#map-travel button", "els => els.map(e => e.disabled)")
    check("禅院（剧情区域）神行全部禁用", all(travel), str(travel))
    title = page.evaluate("document.getElementById('map-title').textContent")
    check("禅院地图标题", "观音禅院" in title, title)
    page.keyboard.press("p")
    page.wait_for_timeout(100)

    # ---- P 在菜单/土地庙时不乱开 ----
    page.evaluate("openTalentPanel(false)")
    page.wait_for_timeout(100)
    page.keyboard.press("p")
    page.wait_for_timeout(100)
    check("土地庙打开时 P 不开地图", not page.evaluate("document.getElementById('map-panel').classList.contains('visible')"), "")
    page.evaluate("closeTalentPanel()")

    check("全程无 JS 报错", not errors, "; ".join(errors[:3]))
    browser.close()

print()
if failures:
    print(f"共 {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("全部通过 ✓")
