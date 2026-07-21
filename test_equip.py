#!/usr/bin/env python3
"""哈悟空法术配置功能验证脚本"""
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

    # ---- 场景 1：全新存档（默认配置 freeze/cloud/pluck）----
    page.goto(URL)
    page.wait_for_timeout(600)
    check("页面无 JS 报错", not errors, "; ".join(errors[:3]))

    bar = page.eval_on_selector_all("#skill-bar .skill",
        "els => els.filter(e => e.style.display !== 'none').map(e => e.textContent.trim())")
    print("  技能栏可见槽位:", bar)
    check("默认技能栏只显示 Q + 3 个已配置法术 + T",
          any("定身术" in s and s.startswith("1") for s in bar)
          and any("聚形散气" in s and s.startswith("2") for s in bar)
          and any("身外身法" in s and s.startswith("3") for s in bar)
          and not any("定风珠" in s for s in bar)
          and not any("避火罩" in s for s in bar), str(bar))

    # 触屏按钮
    touch_hidden = page.evaluate("""() => {
        const b = document.querySelector('.tbtn[data-act="pearl"]');
        const c = document.querySelector('.tbtn[data-act="cloud"]');
        return { pearl: b.style.display, cloud: c.style.display };
    }""")
    check("触屏未配置按钮隐藏、已配置显示", touch_hidden["pearl"] == "none" and touch_hidden["cloud"] != "none", str(touch_hidden))

    # 面板卡片：8 张，未解锁的禁用
    page.evaluate("openTalentPanel(true)")
    page.wait_for_timeout(200)
    cards = page.eval_on_selector_all("#equip-grid .talent-card",
        "els => els.map(e => ({t: e.querySelector('b').textContent, dis: e.disabled, eq: e.classList.contains('equipped'), small: e.querySelector('small').textContent}))")
    print("  面板卡片:", [(c["t"], "禁" if c["dis"] else ("选" if c["eq"] else "可")) for c in cards])
    check("面板 8 张卡片", len(cards) == 8, str(len(cards)))
    check("未解锁卡片禁用（横扫/火眼/变身/法宝）",
          all(c["dis"] for c in cards if c["t"] in ["横扫六合", "火眼金睛", "广智变身", "定风珠", "避火罩"]), str(cards))
    check("默认已配置 3 张带 equipped 样式", sum(1 for c in cards if c["eq"]) == 3, str(cards))

    # 取消配置：点定身术 → 变 2 个
    page.eval_on_selector_all("#equip-grid .talent-card", "els => els[0].click()")
    page.wait_for_timeout(100)
    eq = page.evaluate("JSON.parse(localStorage.getItem('haWukongProgressV3')).equippedSpells")
    check("点击取消定身术后剩 2 个", eq == ["cloud", "pluck"] or eq == ["pluck", "cloud"], str(eq))
    page.evaluate("closeTalentPanel()")

    # ---- 场景 2：全解锁存档，验证最多 4 个 + 法宝互斥 ----
    save = {
        "spirit": 999, "cultivation": 9, "chapterUnlocked": 3,
        "unlockedSkills": ["freeze", "cloud", "pluck", "sweep", "fire", "transform"],
        "unlockedRelics": ["pearl", "mantle"],
        "equippedSpells": ["freeze", "sweep", "fire", "transform"]
    }
    page.evaluate(f"localStorage.setItem('{SAVE_KEY}', '{json.dumps(save)}')")
    page.reload()
    page.wait_for_timeout(600)

    page.evaluate("openTalentPanel(true)")
    page.wait_for_timeout(200)
    # 已满 4 个，点定风珠应无效果
    page.eval_on_selector_all("#equip-grid .talent-card", "els => els.find(e => e.querySelector('b').textContent === '定风珠').click()")
    page.wait_for_timeout(100)
    eq = page.evaluate(f"JSON.parse(localStorage.getItem('{SAVE_KEY}')).equippedSpells")
    check("配置满 4 个时无法再加定风珠", "pearl" not in eq and len(eq) == 4, str(eq))

    # 取消火眼金睛（键位 3），再选定风珠 → 成功
    page.eval_on_selector_all("#equip-grid .talent-card", "els => els.find(e => e.querySelector('b').textContent === '火眼金睛').click()")
    page.wait_for_timeout(100)
    page.eval_on_selector_all("#equip-grid .talent-card", "els => els.find(e => e.querySelector('b').textContent === '定风珠').click()")
    page.wait_for_timeout(100)
    eq = page.evaluate(f"JSON.parse(localStorage.getItem('{SAVE_KEY}')).equippedSpells")
    check("取消一个后可配置定风珠", "pearl" in eq and len(eq) == 4, str(eq))

    # 互斥：再点避火罩 → 定风珠被顶掉
    page.eval_on_selector_all("#equip-grid .talent-card", "els => els.find(e => e.querySelector('b').textContent === '避火罩').click()")
    page.wait_for_timeout(100)
    eq = page.evaluate(f"JSON.parse(localStorage.getItem('{SAVE_KEY}')).equippedSpells")
    check("避火罩与定风珠互斥（选避火罩顶掉定风珠）", "mantle" in eq and "pearl" not in eq, str(eq))
    page.evaluate("closeTalentPanel()")

    # 技能栏键位与配置一致
    bar = page.eval_on_selector_all("#skill-bar .skill",
        "els => els.filter(e => e.style.display !== 'none').map(e => e.textContent.trim())")
    print("  技能栏可见槽位:", bar)
    check("技能栏按配置显示且键位重排",
          any(s.startswith("1") and "定身术" in s for s in bar)
          and any(s.startswith("2") and "横扫六合" in s for s in bar)
          and any(s.startswith("3") and "广智变身" in s for s in bar)
          and any(s.startswith("4") and "避火罩" in s for s in bar)
          and not any("火眼金睛" in s for s in bar), str(bar))

    # ---- 场景 3：按键施放与未配置拦截 ----
    page.evaluate("startChapter(1)")
    page.wait_for_timeout(800)
    page.keyboard.press("4")  # 避火罩（已配置）应触发
    page.wait_for_timeout(100)
    mantle_state = page.evaluate("mantle.active")
    check("按 4 施放已配置的避火罩生效", mantle_state is True, str(mantle_state))

    # 未配置的火眼金睛无法通过 castSpell 施放
    page.evaluate("castSpell('fire')")
    fire_cd = page.evaluate("skills.fire.cd")
    check("未配置法术 castSpell 被拦截", fire_cd == 0, str(fire_cd))

    # 直接调 castFire（绕过入口）会耗蓝施放——入口层已拦截，这里只确认入口逻辑
    check("页面始终无 JS 报错", not errors, "; ".join(errors[:3]))

    # ---- 场景 4：旧存档迁移（无 equippedSpells，且含 pearl+mantle）----
    old_save = {
        "spirit": 100, "cultivation": 0, "chapterUnlocked": 3,
        "unlockedSkills": ["freeze", "cloud", "pluck", "sweep", "fire", "transform"],
        "unlockedRelics": ["pearl", "mantle"]
    }
    page.evaluate(f"localStorage.setItem('{SAVE_KEY}', '{json.dumps(old_save)}')")
    page.reload()
    page.wait_for_timeout(600)
    eq = page.evaluate("progress.equippedSpells")  # 迁移结果在内存中，随下次存档落盘
    check("旧存档迁移：自动取前 4 个且不冲突", eq is not None and len(eq) == 4 and not ("pearl" in eq and "mantle" in eq), str(eq))

    errors_final = [e for e in errors]
    check("全程无 JS 报错", not errors_final, "; ".join(errors_final[:3]))
    browser.close()

print()
if failures:
    print(f"共 {len(failures)} 项失败: {failures}")
    sys.exit(1)
print("全部通过 ✓")
