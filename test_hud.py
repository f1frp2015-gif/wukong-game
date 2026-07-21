#!/usr/bin/env python3
"""HUD 改版验证：极简顶部、血条移位、半圆技能键、设置每章一次"""
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

    # ---- 顶部精简 ----
    st = page.evaluate("""() => ({
        h1: getComputedStyle(document.querySelector('h1')).display,
        score: getComputedStyle(document.getElementById('score-board')).display,
        objTop: document.getElementById('objective').getBoundingClientRect().top,
        objColor: getComputedStyle(document.getElementById('objective')).color
    })""")
    check("游戏名与得分已隐藏", st["h1"] == "none" and st["score"] == "none", str(st))
    check("章节提示在顶部且浅色半透明", st["objTop"] < 30 and "0.55" in st["objColor"], str(st))

    # ---- 血条在方向区右侧 ----
    res = page.evaluate("document.getElementById('player-resources').getBoundingClientRect().left")
    check("血条位于方向区右侧（left≈172）", 150 <= res <= 195, str(res))

    # ---- 半圆技能键 ----
    pos = page.evaluate("""() => {
        const atk = document.getElementById('btn-attack').getBoundingClientRect();
        const cx = atk.left + atk.width / 2, cy = atk.top + atk.height / 2;
        const out = { cx, cy, slots: [] };
        for (const id of ['skill-freeze', 'skill-cloud', 'skill-pluck']) {
            const el = document.getElementById(id);
            if (el.style.display === 'none') continue;
            const r = el.getBoundingClientRect();
            out.slots.push({ id, x: r.left + r.width / 2 - cx, y: r.top + r.height / 2 - cy, w: r.width });
        }
        return out;
    }""")
    ok_arc = len(pos["slots"]) == 3 and all(
        110 < ((s["x"] ** 2 + s["y"] ** 2) ** 0.5) < 165 and s["y"] < 0 and s["w"] == 64 for s in pos["slots"])
    check("已配置技能围绕攻击键呈半圆（左上弧、半径~135）", ok_arc, str(pos["slots"]))

    # ---- 点击技能按钮施放 ----
    page.evaluate("player.mana = 100; enemies.push({type:'wolf',name:'狼妖',x:player.x+50,y:player.y,radius:20,hp:40,maxHp:40,dmg:10,speed:1.6,aggro:260,score:20,atk:'lunge',isBoss:false,state:'chase',wanderT:0,wanderA:0,windup:0,recover:0,flash:0,frozen:0,bob:0,lungeT:0,aoeT:0})")
    page.click("#skill-freeze")
    page.wait_for_timeout(150)
    cd = page.evaluate("skills.freeze.cd")
    check("点击技能按钮成功施放", cd > 0, str(cd))

    # ---- 攻击键可点击 ----
    page.click("#btn-attack")
    page.wait_for_timeout(100)
    swinging = page.evaluate("staff.swinging || staff.cooldown > 0")
    check("攻击键点击挥棍", swinging, str(swinging))

    # ---- 设置：每章一次 ----
    page.click("#settings-btn")
    page.wait_for_timeout(150)
    check("设置面板打开", page.evaluate("document.getElementById('settings-panel').classList.contains('visible')"), "")
    stance_txt = page.evaluate("document.getElementById('settings-stance').textContent")
    check("设置显示当前棍式", "劈棍" in stance_txt, stance_txt)
    page.click("#settings-stance")
    page.wait_for_timeout(100)
    page.click("text=继续修行")
    page.wait_for_timeout(100)
    used = page.evaluate("settingsUsed")
    check("关闭设置后消耗本章机会", used == True, str(used))
    page.click("#settings-btn")
    page.wait_for_timeout(150)
    st2 = page.evaluate("({ open: document.getElementById('settings-panel').classList.contains('visible'), banner: banner ? banner.text : '' })")
    check("第二次打开被拒并提示", not st2["open"] and "机缘已尽" in st2["banner"], str(st2))
    # 看地图不消耗（P 仍可自由开关）
    page.keyboard.press("p")
    page.wait_for_timeout(150)
    map_open = page.evaluate("document.getElementById('map-panel').classList.contains('visible')")
    page.keyboard.press("p")
    check("地图仍可自由查看", map_open, "")
    # 新章节复位
    page.evaluate("startChapter(1)")
    page.wait_for_timeout(300)
    check("重开章节后设置机会复位", page.evaluate("settingsUsed") == False, "")

    check("全程无 JS 报错", not errors, "; ".join(errors[:3]))
    browser.close()

print()
if failures:
    print(f"共 {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("全部通过 ✓")
