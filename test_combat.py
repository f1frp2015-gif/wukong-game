#!/usr/bin/env python3
"""战斗系统整改验证：快慢刀/狂暴/黄风阵/淬炼/四段神通/珍玩/小怪组合"""
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

    page.goto(URL)
    page.wait_for_timeout(600)
    page.evaluate("localStorage.clear()")
    page.reload()
    page.wait_for_timeout(600)

    # ---- 小怪组合化 ----
    page.evaluate("startChapter(1)")
    page.wait_for_timeout(500)
    st = page.evaluate("({ n: enemies.length, types: [...new Set(enemies.map(e => e.type))] })")
    check("黑风山小怪成群且种类混合", 10 <= st["n"] <= 18 and "wolf" in st["types"] and "snake" in st["types"], str(st))

    # ---- 快慢刀：BOSS windups 配置生效 ----
    boss = page.evaluate("enemies.find(e => e.isBoss)")
    windups = page.evaluate("enemies.find(e => e.isBoss).windups")
    check("黑风大王配置了快慢刀", windups == [30, 44, 26], str(windups))
    # 把 BOSS 拉到身边逼它出手，观察 windup 值随招式变化
    page.evaluate("""() => {
        const b = enemies.find(e => e.isBoss);
        b.x = player.x + 60; b.y = player.y; b.state = 'chase'; b.aggro = 9999;
        window.__windups = new Set();
    }""")
    for _ in range(12):
        page.wait_for_timeout(260)
        page.evaluate("""() => {
            const b = enemies.find(e => e.isBoss);
            if (b) {
                b.x = player.x + 60; b.y = player.y;
                if (b.state === 'windup') window.__windups.add(b.windup);
                if (b.state === 'idle' || b.state === 'recover') b.state = 'chase';
            }
        }""")
    seen = page.evaluate("[...window.__windups]")
    check("实战中起手时间不一（快慢刀）", len([w for w in seen if w != 32]) >= 1 and len(seen) >= 2, str(seen))

    # ---- 50% 狂暴 ----
    page.evaluate("enemies.find(e => e.isBoss).hp = enemies.find(e => e.isBoss).maxHp * 0.4")
    page.wait_for_timeout(300)
    st = page.evaluate("(() => { const b = enemies.find(e => e.isBoss); return b ? { enraged: b.enraged, cycle: b.atkCycle } : null; })()")
    check("血量过半触发狂暴并切换攻击循环", st and st["enraged"] and "aoe" in st["cycle"], str(st))

    # ---- 黄风阵 ----
    page.evaluate("setupHuangfeng(3)")  # 直接布阵黄风大圣
    page.wait_for_timeout(400)
    page.evaluate("gustTimer = 2")
    pos_before = page.evaluate("({ x: player.x, y: player.y, hp: player.hp })")
    page.wait_for_timeout(400)
    pos_after = page.evaluate("({ x: player.x, y: player.y, hp: player.hp })")
    moved = abs(pos_after["x"] - pos_before["x"]) + abs(pos_after["y"] - pos_before["y"]) > 20
    check("黄风阵：黄风扑面推移/消磨", moved or pos_after["hp"] < pos_before["hp"], f"{pos_before} -> {pos_after}")
    # 配置定风珠后风平浪静（先清空横幅，观察期间不再起黄风）
    page.evaluate("banner = null; progress.unlockedRelics.push('pearl'); progress.equippedSpells = ['pearl']; updateUnlockUI(); gustTimer = 2")
    page.wait_for_timeout(400)
    banner_txt = page.evaluate("banner ? banner.text : ''")
    check("定风珠压制黄风", "黄风" not in banner_txt, banner_txt)

    # ---- 棍棒淬炼 ----
    page.evaluate("progress.spirit = 500; spendWeapon()")
    st = page.evaluate("({ lv: progress.weaponLevel, spirit: progress.spirit })")
    check("淬炼棍棒：灵蕴换攻击", st["lv"] == 1 and st["spirit"] == 400, str(st))
    dmg = page.evaluate("""() => {
        const dummy = { frozen: 0, hp: 1000, maxHp: 1000, radius: 10, x: 0, y: 0, isBoss: false };
        applyDamage(dummy, 100);
        return 1000 - dummy.hp;
    }""")
    check("淬炼后伤害 +8%", dmg == 108, str(dmg))

    # ---- 第4级神通 ----
    page.evaluate("progress.cultivation = 5; progress.spirit = 2000")
    for _ in range(4):
        page.evaluate("spendTalent('staff')")
    rank = page.evaluate("progress.talents.staff")
    check("棍法可参悟至第4级", rank == 4, str(rank))
    page.evaluate("charge.charging = true")
    page.wait_for_timeout(2600)
    lv = page.evaluate("charge.level")
    page.evaluate("charge.charging = false; charge.level = 0")
    check("四段蓄力超额凝聚", lv > 1.05, str(lv))

    page.evaluate("progress.talents.spell = 4")
    dmg = page.evaluate("""() => {
        const dummy = { frozen: 100, hp: 1000, maxHp: 1000, radius: 10, x: 0, y: 0, isBoss: false };
        applyDamage(dummy, 100);
        return 1000 - dummy.hp;
    }""")
    check("定身必暴（含淬炼8%、四段1.5倍、首击35%）", dmg == 219, str(dmg))  # 100*1.08=108 → *1.5=162 → *1.35=218.7→219
    page.evaluate("progress.talents.body = 4; triggerPerfectDodge()")
    slow = page.evaluate("slowMoTimer")
    check("完美闪避触发时缓", slow == 90 or 80 <= slow <= 90, str(slow))

    # ---- 珍玩 ----
    page.evaluate("grantTrinket('jinchi-bead')")
    st = page.evaluate("({ has: progress.trinkets.includes('jinchi-bead'), mana: player.maxMana })")
    check("珍玩金池佛珠：法力上限+30", st["has"] and st["mana"] == 100 + 15 * 4 + 30, str(st))
    page.evaluate("progress.trinkets.push('heifeng-mane')")
    dmg = page.evaluate("""() => {
        const dummy = { frozen: 0, hp: 1000, maxHp: 1000, radius: 10, x: 0, y: 0, isBoss: true };
        applyDamage(dummy, 100);
        return 1000 - dummy.hp;
    }""")
    check("黑风鬃：对BOSS伤害+8%", dmg == 117, str(dmg))  # 100*1.08(淬炼)*1.08(鬃)=116.64→117
    page.evaluate("progress.trinkets.push('sack-shard'); player.mana = 10")
    page.evaluate("""() => {
        enemies.push({ type: 'wolf', name: '狼妖', x: player.x, y: player.y, radius: 20, hp: 0, maxHp: 40, dmg: 10,
            speed: 1.6, aggro: 260, score: 20, atk: 'lunge', isBoss: false, state: 'chase',
            wanderT: 0, wanderA: 0, windup: 0, recover: 0, flash: 0, frozen: 0, bob: 0, lungeT: 0, aoeT: 0 });
        handleKills();
    }""")
    mana = page.evaluate("player.mana")
    check("袋中残片：击杀回蓝10", 20 <= mana < 21, str(mana))

    # ---- 面板 UI ----
    page.evaluate("openTalentPanel(true)")
    page.wait_for_timeout(200)
    cards = page.eval_on_selector_all("#talent-grid .talent-card", "els => els.map(e => e.querySelector('b').textContent)")
    check("面板含淬炼与珍玩卡片", any("淬炼棍棒" in c for c in cards) and any("珍玩" in c for c in cards), str(cards))
    page.evaluate("closeTalentPanel()")

    check("全程无 JS 报错", not errors, "; ".join(errors[:3]))
    browser.close()

print()
if failures:
    print(f"共 {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("全部通过 ✓")
