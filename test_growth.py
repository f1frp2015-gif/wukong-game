#!/usr/bin/env python3
"""章节成长验证：主角伤害每章 +10（永久），Boss 血量每章 +100。"""
import sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:8123/index.html"
failures = []

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)

def dmg100(page):
    return page.evaluate("""() => {
        const d = { frozen: 0, hp: 1000, maxHp: 1000, radius: 10, x: 0, y: 0, isBoss: false };
        applyDamage(d, 100);
        return 1000 - d.hp;
    }""")

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

    # ---- 第一章：无加成 ----
    page.evaluate("startChapter(1)")
    page.wait_for_timeout(500)
    boss1 = page.evaluate("enemies.find(e => e.isBoss).maxHp")
    check("第一章 Boss 血量不变（800）", boss1 == 800, str(boss1))
    check("第一章伤害无加成", dmg100(page) == 100, "")
    check("初始 damageBonus 为 0", page.evaluate("progress.damageBonus || 0") == 0, "")

    # ---- 第二章：伤害 +10，Boss +100 ----
    page.evaluate("progress.chapterUnlocked = 3; startChapter(2)")
    page.wait_for_timeout(500)
    st2 = page.evaluate("""() => ({
        bonus: progress.damageBonus,
        boss: enemies.find(e => e.isBoss).maxHp,
        banner: banner ? banner.text : ''
    })""")
    check("进入第二章伤害 +10", st2["bonus"] == 10, str(st2))
    check("第二章 Boss 血量 +100（900→1000）", st2["boss"] == 1000, str(st2))
    check("第二章有精进提示", "伤害 +10" in st2["banner"], st2["banner"])
    check("实际伤害 = 110", dmg100(page) == 110, "")

    # ---- 第三章：伤害 +20，Boss +200 ----
    page.evaluate("progress.reachedLeiyin = true; progress.leiyinBossIndex = 0; startChapter(3)")
    page.wait_for_timeout(500)
    st3 = page.evaluate("""() => ({
        bonus: progress.damageBonus,
        boss: enemies.find(e => e.isBoss).maxHp,
        map: currentMap
    })""")
    check("进入第三章伤害 +20", st3["bonus"] == 20, str(st3))
    check("第三章 Boss 血量 +200（1700→1900）", st3["boss"] == 1900, str(st3))
    check("实际伤害 = 120", dmg100(page) == 120, "")

    # ---- 伤害加成永久且幂等：回第一章不跌、重进第三章不涨 ----
    page.evaluate("startChapter(1)")
    page.wait_for_timeout(400)
    st4 = page.evaluate("({ bonus: progress.damageBonus, boss: enemies.find(e => e.isBoss).maxHp })")
    check("回第一章伤害加成保留（+20）", st4["bonus"] == 20, str(st4))
    check("回第一章 Boss 仍是 800", st4["boss"] == 800, str(st4))
    check("实际伤害仍是 120", dmg100(page) == 120, "")
    page.evaluate("progress.reachedLeiyin = true; startChapter(3)")
    page.wait_for_timeout(400)
    check("重进第三章加成不叠加", page.evaluate("progress.damageBonus") == 20, "")

    # ---- 存档持久化 ----
    saved = page.evaluate("JSON.parse(localStorage.getItem('haWukongProgressV3')).damageBonus")
    check("damageBonus 已写入存档", saved == 20, str(saved))

    check("全程无 JS 报错", not errors, "; ".join(errors[:3]))
    browser.close()

print()
if failures:
    print(f"共 {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("全部通过 ✓")
