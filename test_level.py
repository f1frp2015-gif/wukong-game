#!/usr/bin/env python3
"""等级系统验证：经验/升级收益/HUD 经验条、Boss 相对缩放、破绽伤害。"""
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
        const d = { frozen: 0, hp: 100000, maxHp: 100000, radius: 10, x: 0, y: 0, isBoss: false, state: 'chase' };
        applyDamage(d, 100);
        return 100000 - d.hp;
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
    page.evaluate("startChapter(1)")
    page.wait_for_timeout(500)

    # ---- 初始状态 ----
    st = page.evaluate("""() => ({
        lv: progress.level, xp: progress.xp,
        lvText: document.getElementById('player-level-text').textContent,
        xpText: document.getElementById('player-xp-text').textContent
    })""")
    check("初始 Lv.1 经验 0", st["lv"] == 1 and st["xp"] == 0, str(st))
    check("HUD 显示 Lv.1 与经验需求", st["lvText"] == "Lv.1" and "/110" in st["xpText"], str(st))

    # ---- 升级过程与收益 ----
    page.evaluate("grantXp(50)")
    check("经验累积未升级", page.evaluate("({ lv: progress.level, xp: progress.xp })") == {"lv": 1, "xp": 50}, "")
    page.evaluate("grantXp(60)")
    st2 = page.evaluate("""() => ({
        lv: progress.level, xp: progress.xp, maxHp: player.maxHp, hp: player.hp,
        banner: banner ? banner.text : ''
    })""")
    check("满 110 升到 Lv.2", st2["lv"] == 2 and st2["xp"] == 0, str(st2))
    check("升级生命上限 +6 且当前血同步", st2["maxHp"] == 306 and st2["hp"] == 306, str(st2))
    check("升级横幅提示", "等级提升" in st2["banner"] and "Lv.2" in st2["banner"], st2["banner"])
    check("等级攻击 +2", dmg100(page) == 102, "")

    # ---- 连升多级 ----
    page.evaluate("grantXp(1000)")
    st3 = page.evaluate("({ lv: progress.level, xp: progress.xp, maxHp: player.maxHp })")
    check("连升至 Lv.5（180+270+380）", st3["lv"] == 5 and st3["xp"] == 170, str(st3))
    check("Lv.5 生命上限 324", st3["maxHp"] == 324, str(st3))
    check("Lv.5 攻击 +8", dmg100(page) == 108, "")

    # ---- 存档持久化 ----
    saved = page.evaluate("(() => { const s = JSON.parse(localStorage.getItem('haWukongProgressV3')); return { lv: s.level, xp: s.xp }; })()")
    check("等级经验写入存档", saved["lv"] == 5 and saved["xp"] == 170, str(saved))

    # ---- 小怪/Boss 击杀给经验 ----
    xp0 = page.evaluate("progress.xp")
    page.evaluate("""() => {
        const mob = enemies.find(e => !e.isBoss);
        if (mob) { mob.hp = 0; handleKills(); }
    }""")
    check("击杀小怪得经验", page.evaluate("progress.xp") > xp0, "")

    # ---- 破绽伤害（重置等级便于计算） ----
    page.evaluate("progress.level = 1; progress.damageBonus = 0")
    brk = page.evaluate("""() => {
        const d = { frozen: 0, hp: 100000, maxHp: 100000, radius: 30, x: 0, y: 0, isBoss: true, state: 'recover' };
        applyDamage(d, 100);
        return 100000 - d.hp;
    }""")
    check("Boss 收招破绽受伤 ×1.6", brk == 160, str(brk))
    chk = page.evaluate("""() => {
        const d = { frozen: 0, hp: 100000, maxHp: 100000, radius: 30, x: 0, y: 0, isBoss: true, state: 'chase' };
        applyDamage(d, 100);
        return 100000 - d.hp;
    }""")
    check("Boss 常态受伤无加成", chk == 100, str(chk))

    # ---- Boss 相对缩放 ----
    sc = page.evaluate("""() => {
        progress.level = 1;
        const hp1 = bossScaledHp(800), dmg1 = bossScaledDmg(40);
        progress.level = 6;
        const hp6 = bossScaledHp(800), dmg6 = bossScaledDmg(40);
        progress.level = 1;
        return { hp1, dmg1, hp6, dmg6 };
    }""")
    check("Lv.1 Boss 不缩放", sc["hp1"] == 800 and sc["dmg1"] == 40, str(sc))
    check("Lv.6 Boss 血量 +20% 攻击 +10%", sc["hp6"] == 960 and sc["dmg6"] == 44, str(sc))

    # ---- 读档后属性不回落 ----
    page.evaluate("progress.level = 5; persistProgress()")
    page.reload()
    page.wait_for_timeout(700)
    page.evaluate("startChapter(1)")
    page.wait_for_timeout(400)
    check("读档后 Lv.5 生命上限生效", page.evaluate("player.maxHp") == 324, "")

    check("全程无 JS 报错", not errors, "; ".join(errors[:3]))
    browser.close()

print()
if failures:
    print(f"共 {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("全部通过 ✓")
