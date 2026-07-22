#!/usr/bin/env python3
"""黄眉三阶段终局战验证脚本"""
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

SEED = {
    "spirit": 999, "cultivation": 0, "chapterUnlocked": 3,
    "unlockedSkills": ["freeze", "cloud", "pluck", "sweep", "fire", "transform"],
    "unlockedRelics": ["pearl", "mantle"],
    "reachedKuhai": True, "reachedLeiyin": True,
    "leiyinBossIndex": 4, "completedLeiyinGuardians": True,
    "chapter3Checkpoint": "leiyin"
}

def seed(page):
    page.evaluate(f"localStorage.setItem('{SAVE_KEY}', '{json.dumps(SEED)}')")
    page.reload()
    page.wait_for_timeout(600)
    page.evaluate("startChapter(3)")
    page.wait_for_timeout(600)

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    # ============ 流程一：完整三阶段通关 ============
    page.goto(URL)
    page.wait_for_timeout(600)
    seed(page)
    # 四护法已破的存档重进：黄眉立即现身（保证刷新后 BOSS 必现）
    cm = page.evaluate("currentMap")
    hm0 = page.evaluate("({ n: enemies.filter(e => e.type === 'huangmeiboss').length, phase: huangmeiFight.phase })")
    check("雷音寺开局黄眉立即现身（一阶段）", cm == "leiyin" and hm0["n"] == 1 and hm0["phase"] == 1, f"{cm} {hm0}")
    boss_bar = page.evaluate("document.getElementById('boss-hp').style.display")
    check("BOSS 血条显示", boss_bar != "none", boss_bar)

    # 压血到 55% 以下 → 人种袋
    page.evaluate("enemies.find(e => e.type === 'huangmeiboss').hp = 1400")
    page.wait_for_timeout(300)
    st = page.evaluate("({ phase: huangmeiFight.phase, saved: huangmeiFight.savedHp, hm: enemies.filter(e => e.type === 'huangmeiboss').length })")
    check("黄眉 55% 血触发入袋（黄眉退场、血量保存）", st["phase"] == 2 and st["hm"] == 0 and 1390 <= st["saved"] <= 1410, str(st))
    page.wait_for_timeout(3200)  # sackCountdown 150 帧
    cm = page.evaluate("currentMap")
    macaque = page.evaluate("enemies.filter(e => e.type === 'macaque').length")
    check("进入人种袋，赤尻马猴守袋", cm == "renzhongdai" and macaque == 1, f"{cm} macaque={macaque}")
    checkpoint_map = page.evaluate("checkpoint && checkpoint.map")
    check("袋中存档点仍为雷音寺", checkpoint_map == "leiyin", str(checkpoint_map))

    # 击杀赤尻马猴 → 破袋回殿，黄眉狂暴回归
    page.evaluate("enemies.find(e => e.type === 'macaque').hp = 0; handleKills()")
    page.wait_for_timeout(200)
    page.wait_for_timeout(3400)  # exitSackCountdown 170 帧
    st = page.evaluate("({ cm: currentMap, phase: huangmeiFight.phase, hm: enemies.filter(e => e.type === 'huangmeiboss').map(e => ({ hp: e.hp, enraged: e.enraged, speed: e.speed })) })")
    check("破袋回殿，黄眉真身以保存血量狂暴回归",
          st["cm"] == "leiyin" and st["phase"] == 3 and len(st["hm"]) == 1
          and st["hm"][0]["hp"] == 1400 and st["hm"][0]["enraged"] and st["hm"][0]["speed"] > 1.6, str(st))

    # 击杀黄眉 → 通关
    page.evaluate("enemies.find(e => e.type === 'huangmeiboss').hp = 0; handleKills()")
    page.wait_for_timeout(300)
    done = page.evaluate("progress.completedChapter3")
    check("黄眉击杀 → completedChapter3", done == True, str(done))
    page.wait_for_timeout(4800)  # victoryCountdown 240 帧
    overlay = page.evaluate("({ show: document.getElementById('overlay').style.display, title: document.getElementById('overlay-title').textContent, msg: document.getElementById('overlay-msg').textContent })")
    check("胜利结算画面（三章俱破）",
          overlay["show"] == "block" and "功德圆满" in overlay["title"] and "三章俱破" in overlay["msg"], str(overlay))
    saved_done = page.evaluate(f"JSON.parse(localStorage.getItem('{SAVE_KEY}')).completedChapter3")
    check("通关已写入存档", saved_done == True, str(saved_done))

    # 通关后重进雷音寺不再触发黄眉
    page.evaluate("returnToMenu()")
    page.wait_for_timeout(300)
    page.evaluate("startChapter(3)")
    page.wait_for_timeout(400)
    page.evaluate("player.y = 700")
    page.wait_for_timeout(400)
    hm = page.evaluate("enemies.filter(e => e.type === 'huangmeiboss').length")
    check("通关后重进不再触发黄眉", hm == 0, str(hm))

    # ============ 流程二：袋中死亡复活 ============
    page.evaluate(f"localStorage.setItem('{SAVE_KEY}', '{json.dumps(SEED)}')")
    page.reload()
    page.wait_for_timeout(600)
    page.evaluate("startChapter(3)")
    page.wait_for_timeout(500)
    page.evaluate("player.y = 700")
    page.wait_for_timeout(300)
    page.evaluate("enemies.find(e => e.type === 'huangmeiboss').hp = 1400")
    page.wait_for_timeout(3200)
    check("再次进入人种袋", page.evaluate("currentMap") == "renzhongdai", page.evaluate("currentMap"))
    page.evaluate("gameOver(false); restartGame()")
    page.wait_for_timeout(600)
    st = page.evaluate("({ cm: currentMap, phase: huangmeiFight.phase, running: gameRunning })")
    check("袋中死亡 → 雷音寺复活、黄眉直接现身再战", st["cm"] == "leiyin" and st["phase"] == 1 and st["running"], str(st))
    hm = page.evaluate("enemies.filter(e => e.type === 'huangmeiboss').length")
    check("复活后黄眉已现身（无需步行触发）", hm == 1, str(hm))

    check("全程无 JS 报错", not errors, "; ".join(errors[:3]))
    browser.close()

print()
if failures:
    print(f"共 {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("全部通过 ✓")
