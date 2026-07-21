import vm from 'node:vm';
import { readFile } from 'node:fs/promises';

const html = await readFile(new URL('index.html', import.meta.url), 'utf8');
const match = html.match(/<script>([\s\S]*?)<\/script>/);
if (!match) throw new Error('未找到内嵌游戏脚本');
const source = match[1];
const referencedIds = [...source.matchAll(/getElementById\('([^']+)'\)/g)].map(item => item[1]);
for (const id of referencedIds) {
  if (!html.includes(`id="${id}"`)) throw new Error(`页面缺少脚本所需元素：${id}`);
}

class ClassList {
  constructor(names = []) { this.values = new Set(names); }
  add(...names) { names.forEach(name => this.values.add(name)); }
  remove(...names) { names.forEach(name => this.values.delete(name)); }
  contains(name) { return this.values.has(name); }
  toggle(name, force) {
    if (force === true) this.values.add(name);
    else if (force === false) this.values.delete(name);
    else if (this.values.has(name)) this.values.delete(name);
    else this.values.add(name);
  }
}

class Element {
  constructor(id = '') {
    this.id = id;
    this.style = {};
    this.classList = new ClassList(id === 'start-menu' ? ['modal', 'visible'] : []);
    this.textContent = '';
    this.innerHTML = '';
    this.disabled = false;
    this.children = [];
    this.cd = null;
  }
  addEventListener() {}
  appendChild(child) { this.children.push(child); }
  querySelector(selector) {
    this._qs ||= {};
    return this._qs[selector] ||= new Element();
  }
}

const elements = new Map();
for (const id of html.matchAll(/id="([^"]+)"/g)) elements.set(id[1], new Element(id[1]));

const gradient = { addColorStop() {} };
const ctx = new Proxy({}, {
  get(target, key) {
    if (key === 'createLinearGradient' || key === 'createRadialGradient') return () => gradient;
    if (key === 'measureText') return () => ({ width: 80 });
    if (!(key in target)) target[key] = () => {};
    return target[key];
  },
  set(target, key, value) { target[key] = value; return true; }
});
const canvas = elements.get('game');
canvas.width = 1280;
canvas.height = 720;
canvas.getContext = () => ctx;

const storage = new Map();
const document = {
  getElementById(id) {
    if (!elements.has(id)) elements.set(id, new Element(id));
    return elements.get(id);
  },
  createElement() { return new Element(); },
  querySelectorAll() { return []; },
  body: new Element('body')
};
const window = { addEventListener() {}, innerWidth: 1280, innerHeight: 720 };
const sandbox = {
  console,
  document,
  window,
  navigator: { maxTouchPoints: 0 },
  localStorage: {
    getItem: key => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value)
  },
  requestAnimationFrame() { return 1; },
  performance: { now: () => 0 },
  structuredClone,
  Math,
  JSON,
  Object,
  Set
};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
const run = code => vm.runInContext(code, sandbox);

if (run("progress.unlockedStances.join(',')") !== 'chop') throw new Error('新存档不应开局解锁全部棍式');
if (run("progress.unlockedSkills.join(',')") !== 'freeze,cloud,pluck') throw new Error('新存档应默认拥有定身、聚形散气与身外身法');

run('startChapter(1)');
if (run('player.mana !== player.maxMana || player.stamina !== player.maxStamina')) {
  throw new Error('开局没有补满法力与气力');
}

// 聚形散气期间敌人脱锁且允许蓄力，真正出棍后才显形。
run("staff.swinging = false; staff.cooldown = 0; dodge.active = false; skills.cloud.cd = 0; player.mana = player.maxMana; enemies = [{ x:player.x + 80, y:player.y, hp:100, maxHp:100, radius:20, state:'chase', lungeT:4, aoeT:4 }]; castCloudStep();");
if (!run('stealth.active') || run("enemies[0].state") !== 'idle' || run('enemies[0].lungeT + enemies[0].aoeT') !== 0) {
  throw new Error('聚形散气没有进入隐身并让敌人脱锁');
}
run('const hiddenHp = player.hp; hurtPlayer(50); startCharge(); for (let i = 0; i < 20; i++) updatePlayer();');
if (run('player.hp') !== run('hiddenHp') || !run('stealth.active && charge.charging && charge.level > 0')) {
  throw new Error('隐身期间不能安全蓄力');
}
run('charge.level = .5; player.stamina = player.maxStamina; releaseCharge();');
if (run('stealth.active') || !run('staff.swinging')) throw new Error('隐身重击出手后没有正常显形');
run('staff.swinging = false; staff.cooldown = 0; staff.attack = null; charge.charging = false; enemies = [];');

// 身外身法必须生成 5～6 个分身，并复制当前棍势主动攻击。
run("skills.pluck.cd = 0; player.mana = player.maxMana; stanceIdx = 2; castPluckOfMany();");
if (run('monkeyClones.length') < 5 || run('monkeyClones.length') > 6) throw new Error('身外身法没有召出 5～6 个分身');
run("enemies = [{ name:'分身木桩', type:'golem', x:player.x + 90, y:player.y, hp:1000, maxHp:1000, radius:24, frozen:0, flash:0, isBoss:false }]; for (const c of monkeyClones) { c.x = player.x + 15; c.y = player.y; c.attackCd = 0; } for (let i = 0; i < 20; i++) updateMonkeyClones();");
if (run('enemies[0].hp') >= 1000 || !run("monkeyClones.some(c => c.attackKind === 'thrust')")) {
  throw new Error('分身没有复制戳棍并造成伤害');
}
run("const cloneEchoHp = enemies[0].hp; echoCloneSkill('fire');");
if (run('enemies[0].hp') >= run('cloneEchoHp')) throw new Error('分身没有同步施放本体法术');
run('for (const c of monkeyClones) drawMonkeyClone(c); monkeyClones = []; pluck.timer = 0; enemies = []; stanceIdx = 0; player.mana = player.maxMana; player.stamina = player.maxStamina;');

// 三种重棍蓄力必须具有各自的移动规则与动作时序。
run("staff.swinging = false; staff.cooldown = 0; dodge.active = false; dodge.cooldown = 0; stanceIdx = 0; player.x = 1000; keys['d'] = true; startCharge(); updatePlayer();");
if (run('player.x') <= 1000 || run('chargeLocksMovement()')) throw new Error('劈棍蓄力时不能移动');
run("charge.charging = false; staff.swinging = false; staff.cooldown = 0; stanceIdx = 1; player.x = 1000; startCharge(); updatePlayer();");
if (run('player.x') !== 1000 || !run('chargeLocksMovement()')) throw new Error('立棍蓄力时仍能移动');
run('const lockedStance = stanceIdx; cycleStance(); startDodge(1, 0);');
if (run('stanceIdx') !== 1 || run('dodge.active')) throw new Error('立棍蓄力可切换棍势或闪避移动');
run("charge.charging = false; staff.cooldown = 0; stanceIdx = 2; player.x = 1000; startCharge(); updatePlayer();");
if (run('player.x') !== 1000 || !run('chargeLocksMovement()')) throw new Error('戳棍蓄力时仍能移动');
run("charge.charging = false; keys['d'] = false; stanceIdx = 0; staff.swinging = false; staff.cooldown = 0; player.stamina = player.maxStamina; charge.charging = true; charge.level = .75; releaseCharge();");
if (run('CHOP_AIR_SPINS') !== 2 || run('staff.attack.duration') !== 34 || run('staff.attack.hitDelay') !== 28) {
  throw new Error('劈棍重击没有完整的空中两周旋转时序');
}
run('staff.timer = Math.round(staff.duration / 2); drawPlayer();');
run("staff.swinging = false; staff.cooldown = 0; staff.attack = null; charge.charging = true; charge.level = .65; stanceIdx = 1; drawPlayer(); charge.charging = false; stanceIdx = 0; player.stamina = player.maxStamina;");

if (run('LIGHT_COMBO.length') !== 5) throw new Error('轻棍连招不是完整五段');
run('combo.count = 0; combo.timer = 0; staff.swinging = false; staff.cooldown = 0; staff.queued = false; startSwing(1);');
if (run('staff.attack.stage') !== 1 || run('staff.attack.name') !== '劈棍') throw new Error('轻棍第一段启动异常');
if (run('player.stamina') !== run('player.maxStamina - 6')) throw new Error('轻棍没有正确消耗气力');
for (let stage = 2; stage <= 5; stage++) {
  run('startSwing(1); for (let i = 0; i < 26 && staff.attack.stage < ' + stage + '; i++) updateStaff();');
  if (run('staff.attack.stage') !== stage) throw new Error(`轻棍第 ${stage} 段没有正确衔接`);
}
if (run('staff.attack.name') !== '腾空跳劈' || run('staff.attack.kind') !== 'vault') throw new Error('轻棍终结段不是跳劈');
run('staff.swinging = false; staff.cooldown = 0; staff.queued = false; combo.timer = 0; startSwing(1);');
if (run('staff.attack.stage') !== 1) throw new Error('轻棍连招超时后没有重置');
run("player.mana = player.maxMana; skills.freeze.cd = 0; enemies = [{ x:player.x + 10, y:player.y, hp:100, radius:20, frozen:0 }]; castFreeze();");
if (run('player.mana') !== run('player.maxMana - 25')) throw new Error('法术没有正确消耗法力');
if (!elements.get('player-hp-fill').style.width || !elements.get('player-mana-fill').style.width || !elements.get('player-stamina-fill').style.width) {
  throw new Error('左下角三资源条没有同步状态');
}

// 所有攻击类型必须保留可见的出手帧，不能在造成伤害后立即回到静态。
for (const attackType of ['melee', 'lunge', 'ranged', 'aoe']) {
  run(`enemies = [{ type:'wolf', name:'动作测试', x:player.x + 500, y:player.y, radius:20, hp:100, maxHp:100, dmg:10, speed:1, aggro:9999, isBoss:false, atk:'${attackType}', attackAlt:0, heavy:false, state:'windup', windup:1, windupMax:32, recover:0, flash:0, frozen:0, bob:0, attackDirX:-1, attackDirY:0, lungeT:0, aoeT:0 }]; updateEnemies();`);
  if (run('enemies[0].attackAnimT') <= 0 || run('enemies[0].lastAttack') !== attackType) {
    throw new Error(`${attackType} 攻击没有可见的出手动作帧`);
  }
  run('drawEnemy(enemies[0]);');
}

// 所有 Boss 与小怪的角色绘制都必须接入统一攻击动作层。
for (const [type, isBoss, radius] of [
  ['boss', true, 34], ['jinchi', true, 30], ['shaguo', true, 28],
  ['shixian', true, 36], ['huxian', true, 30], ['huangfeng', true, 32],
  ['fuban', true, 40], ['kanglong', true, 34], ['miaoyin', true, 44],
  ['buneng', true, 35], ['bubai', true, 31], ['bujing', true, 36], ['bukong', true, 33],
  ['wolf', false, 20], ['snake', false, 14], ['golem', false, 26], ['rat', false, 15]
]) {
  run(`(() => { const e = { type:'${type}', name:'攻击动作验收', x:player.x, y:player.y, radius:${radius}, hp:100, maxHp:100, dmg:10, speed:1, aggro:9999, isBoss:${isBoss}, atk:'melee', lastAttack:'melee', attackAlt:1, heavy:false, state:'windup', windup:16, windupMax:32, recover:0, flash:0, frozen:0, bob:0, attackDirX:1, attackDirY:0, attackAnimT:0, attackAnimMax:16, lungeT:0, aoeT:0 }; drawEnemy(e); })()`);
}
if (run("ATTACK_LABELS.melee + ATTACK_LABELS.lunge + ATTACK_LABELS.ranged + ATTACK_LABELS.aoe") !== '挥击突进施法砸地') {
  throw new Error('攻击动作标识不完整');
}

run('ringBell(bells[0]); ringBell(bells[1]); ringBell(bells[2]);');
if (!run("progress.unlockedSkills.includes('sweep')")) throw new Error('三钟探索未解锁横扫六合');

run("enemies = [{ name:'金池长老', type:'jinchi', hp:0, isBoss:true, radius:30 }]; handleKills();");
if (!run("progress.unlockedSkills.includes('transform') && progress.unlockedRelics.includes('mantle')")) throw new Error('金池奖励链不完整');

run("enemies = [{ name:'黑风大王', type:'boss', hp:0, isBoss:true, radius:34 }]; handleKills();");
if (run('progress.chapterUnlocked') !== 2 || !run("progress.unlockedStances.includes('vault')")) throw new Error('第一章通关未解锁第二章与立棍');

run('progress.spirit = 1000; progress.cultivation = 3; spendTalent("staff");');
if (run('progress.talents.staff') !== 1) throw new Error('土地庙参悟未生效');

run('startChapter(2)');
run("enemies = [{ name:'沙国王父子', type:'shaguo', hp:0, isBoss:true, radius:28 }]; handleKills();");
if (!run("progress.unlockedSkills.includes('fire')") || run('progress.chapter2Checkpoint') !== 1) throw new Error('第二章Boss奖励或存档点未推进');

run("currentMap = 'sahali'; enemies = [{ name:'蝜蝂', type:'fuban', hp:0, isBoss:true, radius:40 }]; handleKills();");
if (!run("progress.unlockedRelics.includes('pearl')")) throw new Error('黄袍员外支线未解锁定风珠');

run("currentMap = 'huangfeng'; chapter2BossIdx = 3; enemies = [{ name:'黄风大圣', type:'huangfeng', hp:0, isBoss:true, radius:32 }]; handleKills();");
if (run('progress.chapterUnlocked') !== 3 || !source.includes('enterFutu')) throw new Error('第二章未正确衔接远端第三章');

run("currentMap = 'futu'; enemies = [{ name:'魔将妙音', type:'miaoyin', hp:0, maxHp:2400, isBoss:true, radius:44 }]; handleKills();");
if (run('kuhaiCountdown') <= 0 || run('progress.completedChapter3')) throw new Error('击败妙音后仍被当作第三章终点');
run('introCountdown = 0; futuCountdown = 0; sahaliCountdown = 0; pearlCountdown = 0; nextBossCountdown = 0;');
run('for (let i = 0; i < 220; i++) updateBells();');
if (run("currentMap") !== 'kuhai' || !run('progress.reachedKuhai') || run("progress.chapter3Checkpoint") !== 'kuhai') {
  throw new Error('妙音战后未正确抵达苦海并保存进度');
}
if (!run("objectiveEl.textContent.includes('苦海北岸')")) throw new Error('苦海场景缺少任务指引');
run('draw();');

run("kuhaiPhase = 'explore'; player.y = 300; updateKuhai();");
if (run("currentMap") !== 'leiyin' || run("enemies[0].name") !== '不能' || !run('progress.reachedLeiyin')) {
  throw new Error('苦海未正确衔接小雷音寺与不能战');
}
for (const [index, name, type] of [
  [0, '不能', 'buneng'], [1, '不白', 'bubai'], [2, '不净', 'bujing'], [3, '不空', 'bukong']
]) {
  if (run("enemies[0].name") !== name || run('leiyinBossIdx') !== index) throw new Error(`${name} 没有按顺序出现`);
  run('draw(); enemies[0].hp = 0; handleKills();');
  if (!run(`progress.bossRewards.includes('${type}')`)) throw new Error(`${name} 击败奖励未记录`);
  if (index < 3) {
    if (run('nextLeiyinBossCountdown') <= 0) throw new Error(`${name} 战后未准备下一场`);
    run('for (let i = 0; i < 170; i++) updateBells();');
  }
}
if (!run('progress.completedLeiyinGuardians') || run('progress.leiyinBossIndex') !== 4 || !run("objectiveEl.textContent.includes('四护法已破')")) {
  throw new Error('不能、不白、不净、不空连战未正确完成');
}

run('castTransform();');
if (!run('transform.active') || run('skills.transform.cd') !== 0) throw new Error('变身启动状态不正确');
run('for (let i = 0; i < transform.duration; i++) updateSkills();');
if (run('transform.active') || run('skills.transform.cd') <= 0) throw new Error('变身冷却没有从结束后开始');

if (!storage.has('haWukongProgressV3')) throw new Error('升级进度未写入本地存档');
if (!source.includes('FIXED_STEP') || !source.includes('frameAccumulator')) throw new Error('缺少固定时间步保护');
if (!html.includes('border-radius: 50%') || !source.includes('Math.cos(ang)')) {
  throw new Error('技能按钮未围绕攻击键呈半圆布局');
}

console.log('验收通过：聚形散气隐身蓄力、5～6个身外身分身与技能同步、半圆技能键、三棍势蓄力移动与新动作、小雷音寺四护法连战、Boss 与小怪攻击动作、三章苦海衔接、左下角三资源条、五段轻棍、移动端基础、成长奖励、土地庙、定风珠、变身平衡与本地存档均可运行。');
