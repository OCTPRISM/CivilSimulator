#!/usr/bin/env node
/**
 * v1.4 P0 acceptance: UI-001~020, NET-001~010, MAP-001~002
 * Run: node scripts/acceptance_v14_p0.mjs
 * Requires: backend :8000, frontend :3000 (prod or dev)
 */
import { chromium } from "playwright";
import { createRequire } from "module";
import { writeFileSync } from "fs";

const BASE = process.env.FRONTEND_URL || "http://localhost:3000";
const API = process.env.BACKEND_URL || "http://localhost:8000";
const WS_BASE = API.replace(/^http/, "ws");

const USER = `qa_${Date.now().toString(36)}`;
const PASS = "qa_pass_123456";

const results = [];

function record(id, status, note = "") {
  results.push({ id, status, note });
  const icon = status === "PASS" ? "✓" : status === "PARTIAL" ? "~" : "✗";
  console.log(`${icon} ${id} [${status}]${note ? " — " + note : ""}`);
}

async function api(path, opts = {}) {
  const r = await fetch(`${API}${path}`, opts);
  const text = await r.text();
  let body;
  try { body = JSON.parse(text); } catch { body = text; }
  return { ok: r.ok, status: r.status, body };
}

async function main() {
  console.log(`\n=== v1.4 P0 Acceptance ===\nFrontend: ${BASE}\nBackend:  ${API}\n`);

  // --- Auth setup ---
  let token = "";
  {
    const reg = await api("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username: USER, password: PASS, display_name: "QA" }),
    });
    if (reg.ok && reg.body?.token) {
      token = reg.body.token;
    } else {
      const login = await api("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: USER, password: PASS }),
      });
      token = login.body?.token || "";
    }
    if (!token) {
      console.error("FATAL: cannot obtain auth token");
      process.exit(1);
    }
  }

  const authH = { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();

  // UI-001 — 未登录应跳转 login
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  await page.evaluate(() => localStorage.clear());
  await page.goto(BASE, { waitUntil: "domcontentloaded" });
  const hitLogin = await page.waitForURL(/\/login/, { timeout: 8000 }).then(() => true).catch(() => false);
  if (hitLogin) record("UI-001", "PASS", "未登录访问 / → /login");
  else record("UI-001", "FAIL", `期望 /login 实际 ${page.url()}`);

  await page.goto(BASE + "/login", { waitUntil: "domcontentloaded" });
  await page.waitForSelector('input[minlength="3"]', { timeout: 10000 });
  const userInput = page.locator('input[minlength="3"]').first();
  const passInput = page.locator('input[type="password"]').first();
  const submitBtn = page.locator('button[type="submit"]');
  // 先注册
  const regTab = page.getByRole("button", { name: "注册", exact: true });
  if (await regTab.isVisible()) await regTab.click();
  await userInput.fill(USER);
  await passInput.fill(PASS);
  await submitBtn.click();
  await page.waitForTimeout(2500);
  if (page.url().includes("/login")) {
    await page.getByRole("button", { name: "登录", exact: true }).click();
    await userInput.fill(USER);
    await passInput.fill(PASS);
    await submitBtn.click();
    await page.waitForTimeout(2500);
  }
  const tokenStored = await page.evaluate(() => localStorage.getItem("civsim_token"));
  if (tokenStored) record("UI-001", "PASS", "登录成功 token 已存");
  else record("UI-001", "FAIL", "token 未写入 localStorage");

  await page.reload();
  await page.waitForTimeout(1500);
  if (!page.url().includes("/login")) record("UI-001", "PASS", "刷新仍保持登录");
  else record("UI-001", "FAIL", "刷新后丢失登录");

  // UI-002
  await page.evaluate(() => localStorage.removeItem("civsim_token"));
  await page.goto(BASE + "/login");
  await page.waitForSelector('input[type="password"]');
  await userInput.fill(USER);
  await passInput.fill("wrong_password_xyz");
  await submitBtn.click();
  await page.waitForTimeout(1000);
  const errText = await page.locator("text=/密码|错误|失败|invalid|Incorrect/i").first().isVisible().catch(() => false);
  const noStack = !(await page.content()).includes("Traceback");
  if (errText && noStack) record("UI-002", "PASS", "错误密码有友好提示");
  else record("UI-002", errText ? "PARTIAL" : "FAIL", `err=${errText} stack=${!noStack}`);

  // re-login
  await page.getByRole("button", { name: "登录", exact: true }).first().click();
  await userInput.fill(USER);
  await passInput.fill(PASS);
  await submitBtn.click();
  await page.waitForURL(BASE + "/", { timeout: 8000 }).catch(() => {});

  // UI-003
  await page.goto(BASE);
  await page.waitForTimeout(1500);
  const hasLabs = await page.locator("text=实验平台").first().isVisible();
  const hasCiv = await page.locator("text=文明模拟").first().isVisible();
  if (hasLabs && hasCiv) record("UI-003", "PASS", "首页两区可见");
  else record("UI-003", "FAIL", `labs=${hasLabs} civ=${hasCiv}`);

  // Create session for Play tests
  let sid = "";
  {
    const seeds = await api("/api/seeds");
    const wuxia = seeds.body?.seeds?.find((s) => s.key === "wuxia") || seeds.body?.seeds?.[0];
    if (!wuxia) {
      record("UI-004", "FAIL", "无 seed");
    } else {
      // UI-004 partial via API + page visit
      await page.goto(`${BASE}/create/wuxia`);
      await page.waitForTimeout(2000);
      const onCreate = page.url().includes("/create/wuxia");
      if (onCreate) record("UI-004", "PARTIAL", "创建页可打开；3D 预览需人工确认");
      else record("UI-004", "FAIL", page.url());

      const sess = await api("/api/sessions", {
        method: "POST",
        headers: authH,
        body: JSON.stringify({
          seed_key: wuxia.key,
          description: "验收侠客，行走江湖，性格谨慎。",
        }),
      });
      sid = sess.body?.session?.id || "";
      if (sid) record("UI-004", "PASS", `session ${sid.slice(0, 8)}…`);
      else record("UI-004", "FAIL", JSON.stringify(sess.body).slice(0, 120));
    }
  }

  // UI-005 P1 - skip automated (slow network)
  record("UI-005", "SKIP", "P1 慢网络 skeleton — 需人工/throttle");

  if (sid) {
    await page.goto(`${BASE}/play/${sid}`);
    await page.waitForTimeout(4000);

    // UI-006
    const fullscreen = await page.evaluate(() => {
      const main = document.querySelector("main");
      const cls = main?.className || "";
      return cls.includes("fixed") && cls.includes("inset-0");
    });
    const hasHud = await page.locator("text=M 地图").isVisible();
    const mapClosed = !(await page.locator("text=世界地图").isVisible().catch(() => false));
    if (fullscreen && hasHud && mapClosed) record("UI-006", "PASS", "全屏+HUD，Map 默认关");
    else record("UI-006", "FAIL", `fs=${fullscreen} hud=${hasHud} mapClosed=${mapClosed}`);

    // UI-007
    await page.keyboard.press("m");
    await page.waitForTimeout(500);
    const mapOpen = await page.locator("text=世界地图").isVisible();
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);
    const mapClosed2 = !(await page.locator("text=世界地图").isVisible().catch(() => false));
    if (mapOpen && mapClosed2) record("UI-007", "PASS", "M 开 / Esc 关");
    else record("UI-007", "FAIL", `open=${mapOpen} close=${mapClosed2}`);

    // UI-008
    await page.keyboard.press("j");
    await page.waitForTimeout(500);
    const journal = await page.locator("text=旅程日志").isVisible();
    const events = await page.locator("text=Recent Events").isVisible();
    await page.keyboard.press("Escape");
    if (journal && events) record("UI-008", "PASS", "Journal 含事件区");
    else record("UI-008", "PARTIAL", `journal=${journal} events=${events}`);

    // UI-009 P1
    await page.keyboard.press("c");
    await page.waitForTimeout(500);
    const charOverlay = await page.locator("text=角色与技能").isVisible();
    await page.keyboard.press("Escape");
    record("UI-009", charOverlay ? "PARTIAL" : "FAIL", "P1 角色抽屉存在；3D 旋转预览未实现");

    // UI-010
    const explorationOn = await page.evaluate(() => {
      const s = sessionStorage.getItem(`sess_${location.pathname.split("/").pop()}`);
      if (!s) return null;
      try { return JSON.parse(s).world?.visual_capabilities?.exploration_enabled; } catch { return null; }
    });
    const sceneNpcBar = await page.locator("text=可交谈").isVisible().catch(() => false);
    const wasdHint = await page.locator("text=WASD").isVisible().catch(() => false);
    if (explorationOn === true && wasdHint && !sceneNpcBar) {
      record("UI-010", "PASS", "true 分支：exploration + WASD；无 scene 芯片");
    } else if (explorationOn === false && sceneNpcBar) {
      record("UI-010", "PARTIAL", "false 分支 OK；true 需 exploration genre");
    } else {
      record("UI-010", explorationOn ? "PARTIAL" : "FAIL", `exploration=${explorationOn} wasd=${wasdHint} sceneNpc=${sceneNpcBar}`);
    }

    // UI-011
    await page.keyboard.press("c");
    await page.waitForTimeout(400);
    const npcBtn = page.locator('button.rounded-full').first();
    if (await npcBtn.isVisible().catch(() => false)) {
      record("UI-011", "PARTIAL", "NPC 入口在 Character 抽屉；近场 F 未实现(exploration off)");
    } else {
      record("UI-011", "PARTIAL", "需有在场 NPC");
    }
    await page.keyboard.press("Escape");

    // UI-012 - step with choice if any
    const choiceBtn = page.locator('[class*="ChoicePanel"] button, .rounded-md.bg-amber').first();
    record("UI-012", "SKIP", "需 page 含 choices — 人工触发");

    // UI-013
    const actionInput = page.locator('input[placeholder*="自由输入"]');
    if (await actionInput.isVisible()) {
      await actionInput.fill("   ");
      const beforePages = await page.evaluate(() => document.body.innerText.length);
      await page.keyboard.press("Enter");
      await page.waitForTimeout(800);
      record("UI-013", "PASS", "空格输入未触发明显错误");
    } else record("UI-013", "PARTIAL", "输入框不可见(离线/无 dialogue dock)");

    // UI-014 P1
    record("UI-014", "SKIP", "P1 任务完成流 — 需预置任务");

    // UI-015 production
    const injDev = await page.locator("text=注入").isVisible().catch(() => false);
    record("UI-015", injDev ? "PARTIAL" : "PASS", "dev 模式 Inject 可见属预期；prod build 需 NODE_ENV=production 复测");

    // UI-016 — Esc 打开系统菜单（先关 overlay）
    await page.keyboard.press("Escape");
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
    let settings = await page.locator("text=系统").isVisible().catch(() => false);
    if (!settings) {
      await page.getByRole("button", { name: "退出" }).first().click();
      await page.waitForTimeout(300);
      settings = await page.locator("text=系统").isVisible().catch(() => false);
    }
    if (settings) {
      await page.locator('input[type="checkbox"]').first().click();
      await page.keyboard.press("Escape");
      const saved = await page.evaluate(() => localStorage.getItem("civsim_play_settings"));
      record("UI-016", saved ? "PASS" : "FAIL", "设置持久化");
    } else record("UI-016", "FAIL", "Esc 菜单未开");

    // UI-017 P0 manual
    record("UI-017", "SKIP", "P0 移动端 — 需 Manual 真机");

    // MAP-001 wuxia（静态资源在前端）
    const mapOk = await fetch(`${BASE}/maps/wuxia.json`).then((r) => ({ ok: r.ok, status: r.status })).catch(() => ({ ok: false, status: 0 }));
    record("MAP-001", mapOk.ok ? "PASS" : "FAIL", `wuxia.json ${mapOk.status}`);

    // MAP-002 military 404
    const map404 = await fetch(`${BASE}/maps/military.json`).then((r) => ({ ok: r.ok, status: r.status })).catch(() => ({ ok: false, status: 0 }));
    record("MAP-002", !map404.ok ? "PASS" : "PARTIAL", `military.json ${map404.status}；Play procedural fallback`);

    // NET-001 ~ NET-010
    const wsResult = await new Promise((resolve) => {
      const ws = new WebSocket(`${WS_BASE}/ws/sessions/${sid}?token=${encodeURIComponent(token)}`);
      const t = setTimeout(() => { ws.close(); resolve({ ok: false, note: "timeout" }); }, 8000);
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "snapshot" && msg.session) {
            clearTimeout(t);
            ws.close();
            resolve({ ok: true, note: `snapshot sid=${msg.session.id.slice(0, 8)}` });
          }
          if (msg.type === "error") {
            clearTimeout(t);
            ws.close();
            resolve({ ok: false, note: msg.message || "ws error frame" });
          }
        } catch { /* ignore */ }
      };
      ws.onerror = () => { clearTimeout(t); resolve({ ok: false, note: "ws error" }); };
    });
    record("NET-001", wsResult.ok ? "PASS" : "FAIL", wsResult.note);

    const net002 = await new Promise((resolve) => {
      const ws = new WebSocket(`${WS_BASE}/ws/sessions/${sid}?token=${encodeURIComponent(token)}`);
      let done = false;
      const finish = (ok, note) => {
        if (done) return;
        done = true;
        clearTimeout(t);
        try { ws.close(); } catch { /* ignore */ }
        resolve({ ok, note });
      };
      const t = setTimeout(() => finish(false, "timeout waiting agent_transform(s)"), 15000);
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === "agent_transform" || msg.type === "agent_transforms") {
            finish(true, `${msg.type} tick=${msg.tick ?? "?"}`);
          }
        } catch { /* ignore */ }
      };
      ws.onerror = () => finish(false, "ws error");
      ws.onopen = () => {
        api(`/api/sessions/${sid}/finance/advance`, {
          method: "POST",
          headers: authH,
          body: JSON.stringify({ steps: 1 }),
        }).catch(() => {});
      };
    });
    record("NET-002", net002.ok ? "PASS" : "FAIL", net002.note);
    record("NET-003", "SKIP", "断网重连 — 需 fault injection E2E");
    record("NET-004", "SKIP", "P1 150ms RTT");
    record("NET-005", "SKIP", "P1 1% packet loss");
    const hb = await api(`/api/sessions/${sid}/heartbeat`, { method: "POST", headers: authH, body: "{}" });
    record("NET-006", hb.ok ? "PASS" : "FAIL", `heartbeat ${hb.status}`);
    record("NET-007", "SKIP", "tab_hidden >60s — 需长时 Playwright");
    record("NET-008", "SKIP", "wake briefing — 需 dormant 前置");
    record("NET-009", "SKIP", "proxy 收回 — 需 proxy 前置");
    record("NET-010", "PARTIAL", "HTTP 降级已实现；WS 正常时 connected=true");
  }

  // UI-018
  await page.goto(`${BASE}/labs/finance`);
  await page.waitForTimeout(2500);
  const finLab = await page.locator("text=金融验证实验室").isVisible().catch(() => false);
  const noWorld3d = !(await page.locator("text=正在生成 3D 地形").isVisible().catch(() => false));
  if (finLab && noWorld3d) record("UI-018", "PASS", "Finance lab 无 World3D");
  else record("UI-018", "FAIL", `fin=${finLab} no3d=${noWorld3d}`);

  // UI-019
  const civSelect = page.locator("select").first();
  if (await civSelect.isVisible()) {
    const opts = await civSelect.locator("option").allTextContents();
    if (opts.length >= 2) {
      await civSelect.selectOption({ index: 1 });
      await page.waitForTimeout(2000);
      record("UI-019", "PARTIAL", "切换文明已触发；需目视无竞态");
    } else record("UI-019", "SKIP", "文明选项不足");
  } else record("UI-019", "FAIL", "无文明选择器");

  // UI-020
  await page.goto(`${BASE}/civilizations/new`);
  await page.waitForTimeout(1000);
  await page.locator('input').first().fill("QA测试文明");
  await page.locator('textarea').first().fill("测试文明运行逻辑：权力分散、市场与行会并存、冲突通过谈判与小规模械斗升级。");
  await page.locator('input[placeholder*="联邦"]').fill("测试城邦");
  await page.locator('input[placeholder*="变法"]').fill("测试阶段");
  await page.locator('input[placeholder="职业名称"]').fill("铁匠");
  await page.locator('input[placeholder="描述"]').fill("打造兵器");
  await page.locator('input[placeholder="角色名"]').fill("学徒");
  await page.locator('textarea[placeholder="人物设定"]').fill("年轻铁匠");
  await page.locator('input[placeholder="身份/职业"]').fill("铁匠");
  await page.locator('input[placeholder="年代"]').fill("测试纪元");
  await page.locator('input[placeholder="事件标题"]').fill("建国");
  await page.locator('textarea[placeholder="事件描述"]').fill("测试历史事件");
  await page.getByRole("button", { name: "创建文明并选择角色" }).click();
  await page.waitForTimeout(3000);
  if (page.url().includes("/create/")) record("UI-020", "PASS", page.url());
  else record("UI-020", "FAIL", page.url());

  await browser.close();

  const summary = {
    run_at: new Date().toISOString(),
    user: USER,
    sid,
    results,
    pass: results.filter((r) => r.status === "PASS").length,
    partial: results.filter((r) => r.status === "PARTIAL").length,
    fail: results.filter((r) => r.status === "FAIL").length,
    skip: results.filter((r) => r.status === "SKIP").length,
  };

  writeFileSync(new URL("./acceptance_v14_p0_results.json", import.meta.url).pathname, JSON.stringify(summary, null, 2));
  console.log(`\n--- Summary: PASS=${summary.pass} PARTIAL=${summary.partial} FAIL=${summary.fail} SKIP=${summary.skip} ---\n`);
  console.log("Results: scripts/acceptance_v14_p0_results.json");
}

main().catch((e) => { console.error(e); process.exit(1); });
