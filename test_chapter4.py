#!/usr/bin/env python3
"""第四章验证：兰喜村进村、猪八戒协战、二姐变形、拖入蜘蛛洞。"""
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

    # ---- 第四章解锁与进入 ----
    btn_disabled = page.evaluate("document.getElementById('chapter4-button').disabled")
    check("未通关第三章时第四章按钮锁定", btn_disabled == True, "")
    page.evaluate("progress.chapterUnlocked = 4; startChapter(4)")
    page.wait_for_timeout(500)
    st = page.evaluate("""() => ({
        map: currentMap, phase: lanxiPhase,
        ally: ally ? ally.kind : null,
        bonus: progress.damageBonus,
        banner: banner ? banner.text : '',
        checkpoint: checkpoint ? checkpoint.map : null
    })""")
    check("进入兰喜村", st["map"] == "lanxi" and st["phase"] == "walk", str(st))
    check("猪八戒 ally 在场", st["ally"] == "bajie", str(st))
    check("第四章伤害 +30", st["bonus"] == 30, str(st))
    check("存档点为兰喜村", st["checkpoint"] == "lanxi", str(st))

    # ---- 猪八戒跟随玩家 ----
    page.evaluate("ally.x = player.x - 400; ally.y = player.y + 40")
    page.evaluate("for (let i = 0; i < 90; i++) updateAlly()")
    follow = page.evaluate("Math.abs(ally.x - (player.x - 90)) < 100")
    check("无战事时猪八戒跟随天命人", follow, "")

    # ---- 北行触发二姐 ----
    page.evaluate("player.y = 600; updateLanxi()")
    boss = page.evaluate("""() => {
        const b = enemies.find(e => e.isBoss);
        return b ? { name: b.name, hp: b.maxHp, spider: b.spiderForm } : null;
    }""")
    check("二姐现身（血量 2600+300）", boss and boss["name"] == "二姐" and boss["hp"] == 2900, str(boss))
    check("初始为人形", boss and boss["spider"] == False, "")

    # ---- 猪八戒协战伤敌 ----
    page.evaluate("""() => {
        const b = enemies.find(e => e.isBoss);
        ally.x = b.x - 60; ally.y = b.y; ally.attackCd = 0;
        for (let i = 0; i < 120; i++) { ally.x = b.x - 60; ally.y = b.y; updateAlly(); }
    }""")
    hurt = page.evaluate("enemies.find(e => e.isBoss).hp < enemies.find(e => e.isBoss).maxHp")
    check("猪八戒协战可伤二姐", hurt, "")

    # ---- 半血变形蜘蛛精 ----
    page.evaluate("enemies.find(e => e.isBoss).hp = enemies.find(e => e.isBoss).maxHp * 0.4; updateEnemies()")
    sp = page.evaluate("""() => {
        const b = enemies.find(e => e.isBoss);
        return { name: b.name, spider: b.spiderForm, radius: b.radius, banner: banner ? banner.text : '' };
    }""")
    check("二姐现出蜘蛛真身", sp["spider"] == True and "蜘蛛精" in sp["name"], str(sp))
    check("变形提示横幅", "蜘蛛真身" in sp["banner"], sp["banner"])

    # ---- 击杀后拖入蜘蛛洞 ----
    page.evaluate("enemies.find(e => e.isBoss).hp = 1; applyDamage(enemies.find(e => e.isBoss), 50); handleKills()")
    drag = page.evaluate("({ cd: dragCountdown, ally: ally, banner: banner ? banner.text : '' })")
    check("二姐亡后触发拖入倒计时", drag["cd"] > 0 and "蜘蛛洞" in drag["banner"], str(drag))
    check("猪八戒留在村外", drag["ally"] == None, "")
    page.evaluate("for (let i = 0; i < 200; i++) updateLanxi()")
    cave = page.evaluate("""() => ({
        map: currentMap,
        mobs: enemies.filter(e => !e.isBoss).length,
        types: [...new Set(enemies.map(e => e.type))],
        reached: progress.reachedZhizhudong,
        checkpoint: checkpoint ? checkpoint.map : null,
        objective: document.getElementById('objective').textContent
    })""")
    check("被拖入蜘蛛洞", cave["map"] == "zhizhudong", str(cave))
    check("洞中有小蛛妖环伺", cave["mobs"] >= 4 and "spiderling" in cave["types"], str(cave))
    check("蜘蛛洞进度已存档", cave["reached"] == True, "")
    check("存档点切换为蜘蛛洞", cave["checkpoint"] == "zhizhudong", str(cave))

    # ---- 小蛛妖可击杀 ----
    page.evaluate("enemies.forEach(e => e.hp = 0); handleKills()")
    check("小蛛妖可全部击杀", page.evaluate("enemies.length") == 0, "")

    # ---- 复活与神行 ----
    page.evaluate("restartGame()")
    page.wait_for_timeout(300)
    check("洞中死亡于蜘蛛洞复活", page.evaluate("currentMap") == "zhizhudong", "")
    ok_from = page.evaluate("TRAVEL_FROM_OK.includes('zhizhudong') && TRAVEL_FROM_OK.includes('lanxi')")
    check("兰喜村与蜘蛛洞可神行离开", ok_from, "")
    spot = page.evaluate("TRAVEL_SPOTS.some(s => s.map === 'lanxi')")
    check("地图面板含兰喜村神行点", spot, "")
    defs = page.evaluate("Boolean(MAP_DEFS.lanxi && MAP_DEFS.zhizhudong)")
    check("MAP_DEFS 收录第四章两张地图", defs, "")

    # ---- 重进第四章直达蜘蛛洞 ----
    page.evaluate("startChapter(4)")
    page.wait_for_timeout(300)
    check("重进第四章按进度直达蜘蛛洞", page.evaluate("currentMap") == "zhizhudong", "")

    # ---- 旧存档兼容：第三章已通关但 chapterUnlocked=3 → 自动补发第四章 ----
    page.evaluate("""() => {
        const legacy = { chapterUnlocked: 3, reachedKuhai: true, completedChapter3: true, bossRewards: ['huangmei'] };
        localStorage.setItem('haWukongProgressV3', JSON.stringify(legacy));
    }""")
    page.reload()
    page.wait_for_timeout(700)
    st9 = page.evaluate("""() => ({
        unlocked: progress.chapterUnlocked,
        disabled: document.getElementById('chapter4-button').disabled
    })""")
    check("旧存档自动补发第四章解锁", st9["unlocked"] >= 4 and st9["disabled"] == False, str(st9))
    page.evaluate("startChapter(4)")
    page.wait_for_timeout(300)
    check("旧存档可进入兰喜村", page.evaluate("currentMap") == "lanxi", "")

    check("全程无 JS 报错", not errors, "; ".join(errors[:3]))
    browser.close()

print()
if failures:
    print(f"共 {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("全部通过 ✓")
