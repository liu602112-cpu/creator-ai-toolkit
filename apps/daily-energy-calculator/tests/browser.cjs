const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
(async()=>{
 const browser=await chromium.launch({channel:'msedge',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:375,height:812}});const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto(pathToFileURL(path.resolve(__dirname,'../dist/index.html')).href);
 const originalScreenshot=page.screenshot.bind(page);
 page.screenshot=async options=>{await page.evaluate(async()=>{await Promise.all(document.getAnimations().map(animation=>animation.finished.catch(()=>{})));});await page.waitForFunction(()=>!document.querySelector('.counting'));return originalScreenshot(options);};
 await page.getByRole('button',{name:'下一步'}).click();assert.equal(await page.locator('#age-error').textContent(),'请输入 18–80 范围内的年龄');
 await page.locator('[name="sex"][value="male"]').check();await page.locator('#age').fill('30');await page.locator('#height').fill('175');await page.locator('#weight').fill('70');
 await page.screenshot({path:path.resolve(__dirname,'../mobile-body.png'),fullPage:true});
 await page.getByRole('button',{name:'下一步'}).click();await page.getByRole('button',{name:'计算每日消耗'}).click();assert.equal(await page.locator('#work-error').textContent(),'请选择工作 / 日常活动类型');
 await page.locator('[name="work"][value="0"]').check();await page.locator('[name="frequency"][value="2"]').check();await page.screenshot({path:path.resolve(__dirname,'../mobile-lifestyle.png'),fullPage:true});await page.getByRole('button',{name:'计算每日消耗'}).click();
 assert.equal(await page.locator('#tdee').textContent(),'2,308');assert.equal(await page.locator('#bmr').textContent(),'1,649');assert.equal(await page.locator('#factor').textContent(),'1.40');assert.equal(await page.locator('#formula').textContent(),'Mifflin-St Jeor');
 await page.screenshot({path:path.resolve(__dirname,'../mobile-result.png'),fullPage:true});
 await page.getByRole('button',{name:'修改信息，重新计算'}).click();assert.equal(await page.locator('#weight').inputValue(),'70');await page.locator('#bodyFat').fill('20');await page.getByRole('button',{name:'下一步'}).click();assert.ok(await page.locator('[name="frequency"][value="2"]').isChecked());await page.getByRole('button',{name:'计算每日消耗'}).click();assert.equal(await page.locator('#formula').textContent(),'Katch-McArdle');assert.equal(await page.locator('#tdee').textContent(),'2,211');
 for(const width of [320,375,768,1280]){await page.setViewportSize({width,height:900});for(let step=0;step<3;step++){await page.evaluate(s=>showStep(s),step);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow at ${width} step ${step}`);}}
 await page.setViewportSize({width:1280,height:900});await page.evaluate(()=>showStep(0));await page.screenshot({path:path.resolve(__dirname,'../desktop.png'),fullPage:true});
 await page.setViewportSize({width:375,height:812});await page.addStyleTag({content:':root{font-size:32px}'});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'200% font overflow');
 assert.deepEqual(errors,[]);console.log('PASS: file-based offline flow, validation, both formulas, preserved edits, 320/375/768/1280 layouts, 200% root text, no runtime errors');
 const fs=require('node:fs');
 const shots=['mobile-body.png','mobile-lifestyle.png','mobile-result.png'].map(file=>'data:image/png;base64,'+fs.readFileSync(path.resolve(__dirname,'../'+file)).toString('base64'));
 const overview=await browser.newPage({viewport:{width:1260,height:1360},deviceScaleFactor:1});
 await overview.setContent(`<!doctype html><html lang="zh-CN"><meta charset="utf-8"><style>*{box-sizing:border-box}body{margin:0;background:#111410;color:#f1f3ed;font-family:Arial,'Microsoft YaHei',sans-serif;padding:40px}header{margin-bottom:30px}h1{font-size:32px;margin:0 0 12px}header p{color:#a8afa1;font-size:17px;margin:0}.grid{display:grid;grid-template-columns:repeat(3,375px);gap:24px}.label{font-size:19px;color:#c4f36b;margin:0 0 16px}img{display:block;width:375px;height:auto;border:1px solid #353b30;border-radius:12px}footer{font-size:14px;color:#a8afa1;margin-top:24px}</style><header><h1>每日热量消耗计算器</h1><p>完整三步流程 · 本地计算 · 自动选择公式 · 支持修改重算</p></header><div class="grid">${shots.map((src,i)=>`<section><p class="label">${['01 身体信息','02 生活方式','03 消耗结果'][i]}</p><img src="${src}"></section>`).join('')}</div><footer>示例：男性 · 30 岁 · 175 cm · 70 kg · 久坐 · 每周运动 3–4 次</footer></html>`);
 await overview.locator('img').evaluateAll(images=>Promise.all(images.map(img=>img.decode())));
 await overview.screenshot({path:path.resolve(__dirname,'../feature-overview.png'),fullPage:true});
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
