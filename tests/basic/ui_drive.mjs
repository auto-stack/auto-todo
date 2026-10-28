// ui_drive.mjs — TODO-001 T-05 双端真实 UI 验收驱动（Playwright/Chromium）。
// 由 tests/basic/verify_basic.py 调度；不做任何存储假设，全部经由真实前端页面。
// 前置：被测环境为全新隔离数据目录（列表初始为空），由 Orchestrator 保证。
// 用法: node ui_drive.mjs <front-url> <mode>
//   mode = full      ：创建/勾选/编辑/删除/刷新持久/清已完成 全流程
//   mode = readonly  ：只读检查列表渲染（vm profile 兜底面）
// 输出：逐行 `PASS|FAIL: <step>`；末行 `SUMMARY {json}`；退出码 0/1。

// playwright 模块解析：优先本仓 node_modules，其次 PLAYWRIGHT_MODULE 环境变量
// 指向的安装入口文件（verify_basic.py 会探测 npx 缓存并传入）。
let chromium;
try {
  ({ chromium } = await import('playwright'));
} catch {
  const { pathToFileURL } = await import('node:url');
  const candidates = [process.env.PLAYWRIGHT_MODULE].filter(Boolean);
  for (const c of candidates) {
    try {
      ({ chromium } = await import(pathToFileURL(c).href));
      break;
    } catch {}
  }
}
if (!chromium) {
  console.error('FAIL: playwright module not found (set PLAYWRIGHT_MODULE)');
  process.exit(2);
}

const frontUrl = process.argv[2];
const mode = process.argv[3] || 'full';
if (!frontUrl) {
  console.error('usage: node ui_drive.mjs <front-url> [full|readonly]');
  process.exit(2);
}

const results = [];
function record(step, ok, detail) {
  results.push({ step, ok, detail: detail || '' });
  console.log(`${ok ? 'PASS' : 'FAIL'}: ${step}${detail ? ' — ' + detail : ''}`);
}

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const pageErrors = [];
  page.on('pageerror', (e) => pageErrors.push(String(e)));
  await page.goto(frontUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  // 1. 列表区存在且无演示种子
  await page.waitForSelector('h1');
  let body = await page.locator('body').innerText();
  record('ui-load', body.includes('todos'), 'front page renders');
  const hasSeed = body.includes('Learn Auto Language') || body.includes('Build a TodoMVC app');
  record('no-demo-seed', !hasSeed, hasSeed ? 'demo seed text visible' : '');

  if (mode === 'readonly') {
    console.log('SUMMARY ' + JSON.stringify({ results, pageErrors }));
    process.exit(results.every((r) => r.ok) ? 0 : 1);
  }

  const input = page.locator('input[placeholder="What needs to be done?"]');
  if ((await input.count()) !== 1) throw new Error('todo input not found');

  // 行定位器：任务行 = 含任务文本的 flex 行（checkbox + 文本 + × 同行）
  const rowOf = (text) => page.locator('div.flex.items-center.py-3').filter({ hasText: text });

  // 2. 输入 + 回车创建（真实键盘事件）
  const text1 = 'UI验收-中文"引号"';
  await input.fill(text1);
  await input.press('Enter');
  await page.waitForTimeout(800);
  body = await page.locator('body').innerText();
  record('ui-create', body.includes(text1), 'task visible after Enter');

  // 3. 再创建一条，勾选第二条完成
  const text2 = 'UI验收-second';
  await input.fill(text2);
  await input.press('Enter');
  await page.waitForTimeout(800);
  body = await page.locator('body').innerText();
  record('ui-create-2', body.includes(text2), '');

  const row2 = rowOf(text2);
  if ((await row2.count()) !== 1) throw new Error('row2 not unique: ' + (await row2.count()));
  await row2.locator('input[type="checkbox"]').check();
  await page.waitForTimeout(800);
  body = await page.locator('body').innerText();
  record('ui-toggle', body.includes('1 items left'), 'after completing one of two');

  // 4. 刷新页面 → 任务与完成态仍在（真实加载路径）
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  body = await page.locator('body').innerText();
  record('ui-persist-reload', body.includes(text1) && body.includes(text2), '');
  record('ui-persist-done', body.includes('1 items left'), 'done state survived reload');

  // 5. 删除第二条（行内 × 按钮）
  const delBtn = rowOf(text2).getByRole('button', { name: '×' });
  if ((await delBtn.count()) !== 1) throw new Error('row2 delete button not unique');
  await delBtn.click();
  await page.waitForTimeout(800);
  body = await page.locator('body').innerText();
  record('ui-delete', !body.includes(text2) && body.includes(text1), 'second removed, first kept');

  // 6. 编辑：点击文本进入编辑态，改名提交
  await page.getByText(text1).first().click();
  await page.waitForTimeout(400);
  const editBox = page.locator('input[value*="UI验收"]');
  const hasEdit = (await editBox.count()) >= 1;
  if (hasEdit) {
    await editBox.first().fill('UI验收-改名');
    await editBox.first().press('Enter');
    await page.waitForTimeout(800);
  }
  body = await page.locator('body').innerText();
  record('ui-edit', body.includes('UI验收-改名'), hasEdit ? '' : 'edit input not reached');

  // 7. 清已完成（改名后的任务先勾选完成，再清）
  const row3 = rowOf('UI验收-改名');
  if ((await row3.count()) === 1) {
    await row3.locator('input[type="checkbox"]').check();
    await page.waitForTimeout(600);
  }
  const clearBtn = page.getByRole('button', { name: 'Clear completed' });
  if ((await clearBtn.count()) === 1) {
    await clearBtn.click();
    await page.waitForTimeout(800);
  }
  body = await page.locator('body').innerText();
  record('ui-clear-completed', !body.includes('UI验收-改名'), 'completed entry removed');

  record('no-page-errors', pageErrors.length === 0, pageErrors.join(' | ').slice(0, 200));
  console.log('SUMMARY ' + JSON.stringify({ results, pageErrors }));
  process.exit(results.every((r) => r.ok) ? 0 : 1);
} finally {
  await browser.close();
}
