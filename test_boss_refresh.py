#!/usr/bin/env python3
"""刷新页面后 BOSS 必现回归：各章节以各种存档状态刷新，重进后 BOSS 必须重新出现。"""
import sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:8123/index.html"
SAVE_KEY = "haWukongProgressV3"
failures = []

def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)

def scenario(page, name, setup_js, chapter, act_js=None, wait_ms=1000):
    """以给定存档状态模拟刷新，重进章节后返回场上 BOSS 列表。"""
    page.goto(URL)
    page.wait_for_timeout(400)
    page.evaluate("localStorage.clear()")
    if setup_js:
        page.reload()
        page.wait_for_timeout(500)
        page.evaluate(setup_js)
        page.reload()
        page.wait_for_timeout(500)
    page.evaluate(f"startChapter({chapter})")
    page.wait_for_timeout(300)
    if act_js:
        page.evaluate(act_js)
    page.wait_for_timeout(wait_ms)
    return page.evaluate("""() => ({
        map: currentMap,
        bosses: enemies.filter(e => e.isBoss).map(e => e.name)
    })""")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)

    # 第一章：全新存档刷新 → 黑风大王
    page.goto(URL)
    page.wait_for_timeout(400)
    page.evaluate("localStorage.clear()")
    r = scenario(page, "ch1", None, 1)
    check("第一章刷新后黑风大王在阵", "黑风大王" in r["bosses"], str(r))

    # 第二章：checkpoint=2 刷新 → 虎先锋
    r = scenario(page, "ch2", """
        progress.chapterUnlocked = 2; progress.chapter2Checkpoint = 2; persistProgress();
    """, 2)
    check("第二章刷新后虎先锋在阵", "虎先锋" in r["bosses"], str(r))

    # 第三章：雷音寺护法第3位刷新 → 不净
    r = scenario(page, "ch3-guardian", """
        progress.chapterUnlocked = 3; progress.reachedLeiyin = true;
        progress.chapter3Checkpoint = 'leiyin'; progress.leiyinBossIndex = 2; persistProgress();
    """, 3)
    check("第三章刷新后不净在阵", "不净" in r["bosses"], str(r))

    # 第三章：四护法已破刷新 → 黄眉立即现身（无需步行触发）
    r = scenario(page, "ch3-huangmei", """
        progress.chapterUnlocked = 3; progress.reachedLeiyin = true;
        progress.chapter3Checkpoint = 'leiyin'; progress.leiyinBossIndex = 4;
        progress.completedLeiyinGuardians = true; persistProgress();
    """, 3)
    check("四护法已破刷新后黄眉立即现身", "黄眉" in r["bosses"], str(r))

    # 第三章：浮屠界进度刷新 → 直接回浮屠界战妙音（不再扔回序章）
    r = scenario(page, "ch3-futu", """
        progress.chapterUnlocked = 3; progress.reachedFutu = true; persistProgress();
    """, 3)
    check("浮屠界进度刷新后妙音在阵", r["map"] == "futu" and "魔将妙音" in r["bosses"], str(r))

    # 第三章：冰湖进度刷新 → 回冰湖，亢金龙快进现身
    r = scenario(page, "ch3-icelake", """
        progress.chapterUnlocked = 3; progress.reachedIcelake = true; persistProgress();
    """, 3, None, 3500)
    check("冰湖进度刷新后亢金龙现身", r["map"] == "icelake" and "亢金龙" in r["bosses"], str(r))

    # 第四章：刷新 → 二姐立即现身
    r = scenario(page, "ch4", """
        progress.chapterUnlocked = 4; progress.completedChapter3 = true; persistProgress();
    """, 4)
    check("第四章刷新后二姐立即现身", r["map"] == "lanxi" and "二姐" in r["bosses"], str(r))

    # 第四章：蜘蛛洞存档刷新 → 回兰喜村，二姐重新出现（洞内不留人）
    r = scenario(page, "ch4-cave", """
        progress.chapterUnlocked = 4; progress.completedChapter3 = true;
        progress.reachedZhizhudong = true; progress.bossRewards = ['erjie']; persistProgress();
    """, 4)
    check("蜘蛛洞存档刷新后回兰喜村、二姐重新出现",
          r["map"] == "lanxi" and "二姐" in r["bosses"], str(r))

    # 斯哈里国阵亡复活 → 黄风岭存档点（原 bug：掉回第一章）
    page.goto(URL)
    page.wait_for_timeout(400)
    page.evaluate("localStorage.clear()")
    page.reload()
    page.wait_for_timeout(500)
    page.evaluate("progress.chapterUnlocked = 2; progress.chapter2Checkpoint = 1; startChapter(2)")
    page.wait_for_timeout(400)
    page.evaluate("""() => {
        currentMap = 'sahali';
        checkpoint = { map: 'huangfeng', bossIndex: 1 };
        ally = { kind: 'huangfeng', x: 0, y: 0 };
        gameRunning = false;
        restartGame();
    }""")
    page.wait_for_timeout(500)
    st = page.evaluate("""() => ({
        map: currentMap,
        bosses: enemies.filter(e => e.isBoss).map(e => e.name),
        ally: ally
    })""")
    check("斯哈里国阵亡于黄风岭复活", st["map"] == "huangfeng", str(st))
    check("复活后石先锋在阵", "石先锋" in st["bosses"], str(st))
    check("复活后盟友已清场", st["ally"] == None, str(st))

    check("全程无 JS 报错", not errors, "; ".join(errors[:3]))
    browser.close()

print()
if failures:
    print(f"共 {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("全部通过 ✓")
