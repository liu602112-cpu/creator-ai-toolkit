'use strict';
const $=id=>document.getElementById(id);
const bodyForm=$('body-form'),lifestyleForm=$('lifestyle-form');
const workNames=['久坐','轻活动','中等体力','重体力'];
const frequencyNames=['几乎不运动','每周 1–2 次','每周 3–4 次','每周 5 次以上'];
const sideTitles=['先认识你的身体','再看看你的日常','你的每日能量参考'];
const sideCopies=['基础身体信息，帮助我们估算维持身体正常运转所需的能量。','工作中的活动和每周运动，一起决定你的每日消耗水平。','了解基础代谢与日常消耗，为认识自己的身体多一个参考。'];
const reducedMotion=window.matchMedia('(prefers-reduced-motion: reduce)');
let currentStep=0,numberFrame=0;
const activeAnimations=new Set();
function animate(element,frames,options={}){
  if(reducedMotion.matches||!element?.animate)return;
  const animation=element.animate(frames,{duration:320,easing:'cubic-bezier(.22,1,.36,1)',...options});
  activeAnimations.add(animation);
  animation.finished.catch(()=>{}).finally(()=>activeAnimations.delete(animation));
}
function finishNumbers(){
  cancelAnimationFrame(numberFrame);
  for(const id of ['tdee','bmr']){$(id).classList.remove('counting');delete $(id).dataset.display;}
}
function animateNumbers(bmr,tdee){
  finishNumbers();if(reducedMotion.matches)return;
  const targets=[[$('bmr'),Math.round(bmr)],[$('tdee'),Math.round(tdee)]];
  targets.forEach(([el])=>{el.classList.add('counting');el.dataset.display='0';});
  const start=performance.now();
  function tick(now){
    const progress=Math.min((now-start)/720,1),eased=1-Math.pow(1-progress,3);
    targets.forEach(([el,value])=>el.dataset.display=Math.round(value*eased).toLocaleString('en-US'));
    if(progress<1)numberFrame=requestAnimationFrame(tick);else finishNumbers();
  }
  numberFrame=requestAnimationFrame(tick);
}
reducedMotion.addEventListener('change',()=>{if(reducedMotion.matches){activeAnimations.forEach(animation=>animation.cancel());finishNumbers();}});
function showStep(step){
  const direction=step>=currentStep?1:-1;
  activeAnimations.forEach(animation=>animation.cancel());finishNumbers();currentStep=step;
  [bodyForm,lifestyleForm,$('result')].forEach((el,i)=>el.hidden=i!==step);
  document.querySelectorAll('.steps li').forEach((el,i)=>{if(i===step)el.setAttribute('aria-current','step');else el.removeAttribute('aria-current');});
  $('section-index').textContent=`0${step+1} / 03`;$('side-title').textContent=sideTitles[step];$('side-copy').textContent=sideCopies[step];
  [bodyForm,lifestyleForm,$('result')][step].querySelector('h2').focus({preventScroll:true});
  window.scrollTo({top:0,behavior:'instant'});
  const visible=[bodyForm,lifestyleForm,$('result')][step];
  animate(visible,[{opacity:0,transform:`translateX(${direction*14}px)`},{opacity:1,transform:'translateX(0)'}]);
  [...visible.children].forEach((el,i)=>animate(el,[{opacity:0,transform:'translateY(10px)'},{opacity:1,transform:'translateY(0)'}],{delay:Math.min(i*35,175),fill:'backwards'}));
  animate($('side-title'),[{opacity:0,transform:'translateY(6px)'},{opacity:1,transform:'translateY(0)'}]);
}
function bodyData(){return Object.fromEntries(new FormData(bodyForm));}
function displayErrors(form,errors,keys){
  keys.forEach(key=>{
    $(key+'-error').textContent=errors[key]||'';
    form.querySelectorAll(`[name="${key}"]`).forEach(input=>{input.setAttribute('aria-invalid',String(Boolean(errors[key])));input.setAttribute('aria-describedby',key+'-error');});
  });
  const first=keys.find(key=>errors[key]);if(first){const input=form.querySelector(`[name="${first}"]`);input.focus();animate(input.closest('.field,fieldset'),[{transform:'translateX(0)'},{transform:'translateX(-4px)'},{transform:'translateX(4px)'},{transform:'translateX(-2px)'},{transform:'translateX(0)'}],{duration:280,easing:'ease-out'});}
  return !first;
}
bodyForm.addEventListener('submit',event=>{event.preventDefault();if(displayErrors(bodyForm,Calculator.validateInput(bodyData()),['sex','age','height','weight','bodyFat']))showStep(1);});
function renderResult(data,work,frequency){
  const bmr=Calculator.calculateBMR(data),factor=Calculator.getActivityFactor(work,frequency),tdee=Calculator.calculateTDEE(bmr,factor);
  $('bmr').textContent=Math.round(bmr).toLocaleString('en-US');$('tdee').textContent=Math.round(tdee).toLocaleString('en-US');
  $('factor').textContent=factor.toFixed(2);$('result-work').textContent=workNames[Number(work)];$('result-frequency').textContent=frequencyNames[Number(frequency)];
  $('formula').textContent=Calculator.isBlank(data.bodyFat)?'Mifflin-St Jeor':'Katch-McArdle';showStep(2);
  animateNumbers(bmr,tdee);
  return {bmr,tdee,factor,formula:$('formula').textContent};
}
lifestyleForm.addEventListener('submit',event=>{event.preventDefault();const data=Object.fromEntries(new FormData(lifestyleForm)),errors={};if(data.work===undefined)errors.work='请选择工作 / 日常活动类型';if(data.frequency===undefined)errors.frequency='请选择每周运动频率';if(displayErrors(lifestyleForm,errors,['work','frequency']))renderResult(bodyData(),data.work,data.frequency);});
$('back').addEventListener('click',()=>showStep(0));$('edit').addEventListener('click',()=>showStep(0));
document.querySelectorAll('.choice input').forEach(input=>input.addEventListener('change',()=>animate(input.nextElementSibling,[{transform:'scale(.97)'},{transform:'scale(1.015)'},{transform:'scale(1)'}],{duration:250})));
for(const form of [bodyForm,lifestyleForm])form.addEventListener('input',event=>{const name=event.target.name;if($(name+'-error')){$(name+'-error').textContent='';form.querySelectorAll(`[name="${name}"]`).forEach(el=>el.removeAttribute('aria-invalid'));}});
if(document.modelContext?.registerTool){
  try{Promise.resolve(document.modelContext.registerTool({name:'calculate_daily_energy',description:'填写身体信息和生活方式，计算并显示每日热量消耗。',inputSchema:{type:'object',properties:{sex:{type:'string',enum:['male','female']},age:{type:'integer',minimum:18,maximum:80},height:{type:'number',minimum:120,maximum:230},weight:{type:'number',minimum:30,maximum:250},bodyFat:{type:'number',minimum:3,maximum:60},work:{type:'integer',minimum:0,maximum:3},frequency:{type:'integer',minimum:0,maximum:3}},required:['sex','age','height','weight','work','frequency'],additionalProperties:false},annotations:{readOnlyHint:false},execute(input){const errors=Calculator.validateInput(input);if(Object.keys(errors).length)throw new Error(Object.values(errors).join('；'));Calculator.getActivityFactor(input.work,input.frequency);for(const key of ['age','height','weight','bodyFat'])$(key).value=input[key]??'';bodyForm.querySelector(`[value="${input.sex}"]`).checked=true;for(const key of ['work','frequency'])lifestyleForm.querySelector(`[name="${key}"][value="${Number(input[key])}"]`).checked=true;displayErrors(bodyForm,{},['sex','age','height','weight','bodyFat']);displayErrors(lifestyleForm,{},['work','frequency']);return renderResult(input,input.work,input.frequency);}})).catch(()=>{});}catch{}
}
