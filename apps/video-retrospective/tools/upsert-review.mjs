import fs from 'node:fs/promises';import assert from 'node:assert/strict';import {spawnSync} from 'node:child_process';
// Agent-reviewed structured content only. Never import raw conversations into dist.
const input=process.argv[2];assert.ok(input,'Provide a reviewed JSON patch path');
const patch=JSON.parse(await fs.readFile(input,'utf8'));const target='dist/data.json';const original=await fs.readFile(target,'utf8');const d=JSON.parse(original);
function merge(key,id){if(!patch[key])return;assert.ok(Array.isArray(patch[key]));for(const item of patch[key]){const i=d[key].findIndex(x=>x[id]===item[id]);if(i<0)d[key].push(item);else d[key][i]=item;}}
merge('reviews','date');merge('lessons','id');merge('preferences','title');
for(const key of ['workflow','checklist','actions','evidence'])if(patch[key])d[key]=patch[key];
if(patch.updatedAt)d.updatedAt=patch.updatedAt;d.reviews.sort((a,b)=>b.date.localeCompare(a.date));
const updated=JSON.stringify(d,null,2)+'\n';if(updated===original){console.log(JSON.stringify({changed:false}));process.exit(0)}
await fs.writeFile(target+'.tmp',updated);await fs.rename(target+'.tmp',target);
const result=spawnSync(process.execPath,['tools/validate.mjs'],{encoding:'utf8'});if(result.status!==0){await fs.writeFile(target,original);throw new Error(result.stderr)}
console.log(JSON.stringify({changed:true,validation:JSON.parse(result.stdout)}));
