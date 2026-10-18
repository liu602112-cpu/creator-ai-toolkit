import fs from 'node:fs/promises';import assert from 'node:assert/strict';import {spawnSync} from 'node:child_process';
const d=JSON.parse(await fs.readFile('dist/data.json','utf8'));
assert.equal(d.schemaVersion,1);assert.ok(d.reviews.length);assert.ok(d.lessons.length);
const ids=new Set();for(const l of d.lessons){assert.ok(!ids.has(l.id),'Duplicate lesson '+l.id);ids.add(l.id);for(const k of ['id','date','title','category','kind','summary','event','cause','action','rule','evidence','scope'])assert.ok(typeof l[k]==='string'&&l[k].trim(),`Missing ${k} in ${l.id}`)}
for(const r of d.reviews){assert.match(r.date,/^\d{4}-\d{2}-\d{2}$/);assert.ok(r.lessonIds.every(id=>ids.has(id)));assert.ok(r.featured.every(id=>ids.has(id)));assert.ok(r.versions.length)}
assert.ok(d.preferences.every(p=>['长期','本片'].includes(p.scope)));assert.ok(d.checklist.every(p=>p.items.length));
for(const p of ['dist/app.js','tools/serve.mjs']){const r=spawnSync(process.execPath,['--check',p],{encoding:'utf8'});assert.equal(r.status,0,r.stderr)}
const html=await fs.readFile('dist/index.html','utf8');for(const ref of ['styles.css','app.js']){assert.ok(html.includes(ref));await fs.access('dist/'+ref)}
const pub=(await fs.readdir('dist')).sort();assert.deepEqual(pub,['app.js','data.json','index.html','styles.css']);
const serialized=JSON.stringify(d);assert.ok(!/[A-Za-z]:[\\/]|sk-[A-Za-z0-9]{12}|Bearer [A-Za-z0-9]/.test(serialized),'Public data contains private local path or secret');
console.log(JSON.stringify({status:'passed',reviews:d.reviews.length,lessons:d.lessons.length,preferences:d.preferences.length,assets:pub}));
