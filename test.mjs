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
    if (selector === '.cd') this.cd ||= new Element();
    return this.cd;
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
if (run("progress.unlockedSkills.join(',')") !== 'freeze') throw new Error('新存档不应开局解锁全部法术');

run('startChapter(1)');
if (run('player.mana !== player.maxMana || player.stamina !== player.maxStamina')) {
  throw new Error('开局没有补满法力与气力');
}
run('player.stamina = player.maxStamina; staff.swinging = false; staff.cooldown = 0; startSwing(1);');
if (run('player.stamina') !== run('player.maxStamina - 7')) throw new Error('普通攻击没有正确消耗气力');
run("player.mana = player.maxMana; skills.freeze.cd = 0; enemies = [{ x:player.x + 10, y:player.y, hp:100, radius:20, frozen:0 }]; castFreeze();");
if (run('player.mana') !== run('player.maxMana - 25')) throw new Error('法术没有正确消耗法力');
if (!elements.get('player-hp-fill').style.width || !elements.get('player-mana-fill').style.width || !elements.get('player-stamina-fill').style.width) {
  throw new Error('左下角三资源条没有同步状态');
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

run('castTransform();');
if (!run('transform.active') || run('skills.transform.cd') !== 0) throw new Error('变身启动状态不正确');
run('for (let i = 0; i < transform.duration; i++) updateSkills();');
if (run('transform.active') || run('skills.transform.cd') <= 0) throw new Error('变身冷却没有从结束后开始');

if (!storage.has('haWukongProgressV3')) throw new Error('升级进度未写入本地存档');
if (!source.includes('FIXED_STEP') || !source.includes('frameAccumulator')) throw new Error('缺少固定时间步保护');

console.log('验收通过：三章内容、移动端基础、成长奖励、土地庙、定风珠、变身平衡与本地存档均可运行。');
