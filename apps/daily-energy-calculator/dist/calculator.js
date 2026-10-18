(function(root){
  'use strict';
  const factors=[[1.20,1.30,1.40,1.50],[1.30,1.40,1.50,1.60],[1.45,1.55,1.65,1.75],[1.60,1.70,1.80,1.90]];
  const isBlank=value=>value===null||value===undefined||String(value).trim()==='';
  const isNumeric=value=>(typeof value==='number'||typeof value==='string')&&!isBlank(value)&&Number.isFinite(Number(value));
  function validateInput(input){
    const errors={};
    if(!['male','female'].includes(input.sex))errors.sex='请选择性别';
    for(const [key,min,max,label] of [['age',18,80,'年龄'],['height',120,230,'身高'],['weight',30,250,'体重'],['bodyFat',3,60,'体脂率']]){
      if(key==='bodyFat'&&isBlank(input[key]))continue;
      if(!isNumeric(input[key])||Number(input[key])<min||Number(input[key])>max)errors[key]=`请输入 ${min}–${max} 范围内的${label}`;
      else if(key==='age'&&!Number.isInteger(Number(input[key])))errors[key]='年龄请填写整数';
    }
    return errors;
  }
  function calculateBMR(input){
    if(Object.keys(validateInput(input)).length)throw new RangeError('身体信息无效');
    if(!isBlank(input.bodyFat))return 370+21.6*Number(input.weight)*(1-Number(input.bodyFat)/100);
    return 10*Number(input.weight)+6.25*Number(input.height)-5*Number(input.age)+(input.sex==='male'?5:-161);
  }
  function getActivityFactor(work,frequency){
    if(!isNumeric(work)||!isNumeric(frequency)||![0,1,2,3].includes(Number(work))||![0,1,2,3].includes(Number(frequency)))throw new RangeError('请选择工作类型和运动频率');
    return factors[Number(work)][Number(frequency)];
  }
  function calculateTDEE(bmr,factor){
    if(!Number.isFinite(bmr)||bmr<=0||!Number.isFinite(factor)||factor<=0)throw new RangeError('计算参数无效');
    return bmr*factor;
  }
  const api={validateInput,calculateBMR,getActivityFactor,calculateTDEE,isBlank};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.Calculator=api;
})(globalThis);
