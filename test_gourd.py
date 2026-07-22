#!/usr/bin/env python3
"""酒葫芦验证：桃子移除、腰挂酒瓶、共 7 口、存档点补满。"""
import sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:8123/index.html"
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

    page.goto(URL)
    page.wait_for_timeout(700)
    page.evaluate("localStorage.clear()")
    page.reload()
    page.wait_for_timeout(700)
    page.evaluate("startChapter(1)")
    page.wait_for_timeout(500)

    # ---- 桃子已移除 ----
    check("黑风山地图上无桃子", page.evaluate("peaches.length") == 0, "")
    page.evaluate("progress.chapterUnlocked = 2; startChapter(2)")
    page.wait_for_timeout(400)
    check("黄风岭地图上无桃子", page.evaluate("peaches.length") == 0, "")
    page.evaluate("startChapter(1)")
    page.wait_for_timeout(400)

    # ---- 初始状态 ----
    st = page.evaluate("""() => ({
        sips: gourdSips,
        badge: document.getElementById('gourd-count').textContent,
        visible: document.getElementById('btn-gourd').getBoundingClientRect().width > 0
    })""")
    check("酒葫芦初始 7 口", st["sips"] == 7, str(st))
    check("按钮角标显示 7 且可见", st["badge"] == "7" and st["visible"], str(st))

    # ---- 饮酒回血 ----
    page.evaluate("player.hp = 100; updateUI()")
    page.evaluate("drinkGourd()")
    st2 = page.evaluate("({ hp: player.hp, sips: gourdSips, badge: document.getElementById('gourd-count').textContent })")
    check("喝一口回 50 血", st2["hp"] == 150, str(st2))
    check("剩余 6 口且角标同步", st2["sips"] == 6 and st2["badge"] == "6", str(st2))

    # ---- 满血不喝 ----
    page.evaluate("player.hp = player.maxHp")
    page.evaluate("drinkGourd()")
    check("满血时不消耗", page.evaluate("gourdSips") == 6, "")

    # ---- H 键饮酒 ----
    page.evaluate("player.hp = 100")
    page.keyboard.press("h")
    page.wait_for_timeout(100)
    check("按 H 键饮酒", page.evaluate("({ hp: player.hp, sips: gourdSips })") == {"hp": 150, "sips": 5}, "")

    # ---- 点击按钮饮酒 ----
    page.evaluate("player.hp = 100")
    page.click("#btn-gourd")
    page.wait_for_timeout(100)
    check("点击酒葫芦按钮饮酒", page.evaluate("({ hp: player.hp, sips: gourdSips })") == {"hp": 150, "sips": 4}, "")

    # ---- 喝空后提示且不再回血 ----
    page.evaluate("gourdSips = 1; player.hp = 100; drinkGourd(); player.hp = 100; drinkGourd()")
    st3 = page.evaluate("({ hp: player.hp, sips: gourdSips, empty: document.getElementById('btn-gourd').classList.contains('empty'), banner: banner ? banner.text : '' })")
    check("7 口喝完后回血停止", st3["sips"] == 0 and st3["hp"] == 100, str(st3))
    check("空葫芦置灰并提示", st3["empty"] and "已空" in st3["banner"], str(st3))

    # ---- 存档点复活补满 ----
    page.evaluate("gourdSips = 2; progress.chapterUnlocked = 2; startChapter(2)")
    page.wait_for_timeout(400)
    check("进入新章节补满酒葫芦", page.evaluate("gourdSips") == 7, "")

    check("全程无 JS 报错", not errors, "; ".join(errors[:3]))
    browser.close()

print()
if failures:
    print(f"共 {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("全部通过 ✓")
