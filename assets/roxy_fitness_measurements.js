/* Optional member-owned measurements. Never infer health or send these values to providers. */
((scope) => {
  'use strict';
  const PREFIX='/api/fitness/v1/me/measurements';
  const PURPOSE='fitness_measurements',CONSENT_VERSION='fitness-measurements-v1';
  const UUID=/^[a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12}$/i;
  const LB_TO_KG=.45359237;
  let state=null,active=true;
  const copy=value=>JSON.parse(JSON.stringify(value));
  const zoneOK=value=>{try{return typeof value==='string'&&value.length<=64&&!!new Intl.DateTimeFormat('es',{timeZone:value});}catch(_){return false;}};
  const dateOK=value=>{if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(value))return false;const date=new Date(value+'T12:00:00Z');return Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===value;};
  function today(zone,now=new Date()) {const parts=new Intl.DateTimeFormat('en-CA',{timeZone:zoneOK(zone)?zone:'UTC',year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(now),part=name=>parts.find(p=>p.type===name).value;return `${part('year')}-${part('month')}-${part('day')}`;}
  const number=value=>typeof value==='number'&&Number.isFinite(value);
  function normalized(measurement){
    if(!measurement||!UUID.test(measurement.id)||!dateOK(measurement.date)||!zoneOK(measurement.timezone))throw new Error('Revisa la fecha y la zona horaria de tu medición.');
    const {weight,height}=measurement;
    if(weight===null&&height===null)throw new Error('Añade el peso, la estatura o ambos. Los dos son opcionales.');
    let weight_kg=null,height_cm=null;
    if(weight!==null){if(!weight||!number(weight.value)||!['kg','lb'].includes(weight.unit))throw new Error('Revisa el peso y su unidad.');weight_kg=weight.value*(weight.unit==='lb'?LB_TO_KG:1);if(weight_kg<1||weight_kg>1000)throw new Error('Revisa el peso y su unidad.');}
    if(height!==null){
      if(!height)throw new Error('Revisa la estatura y su unidad.');
      if(height.unit==='cm'&&number(height.value))height_cm=height.value;
      else if(height.unit==='ft_in'&&Number.isInteger(height.feet)&&height.feet>=0&&height.feet<=9&&number(height.inches)&&height.inches>=0&&height.inches<12)height_cm=(height.feet*12+height.inches)*2.54;
      else throw new Error('Revisa la estatura y su unidad. Usa pulgadas entre 0 y menos de 12.');
      if(height_cm<30||height_cm>300)throw new Error('Revisa la estatura y su unidad.');
    }
    return {weight_kg:weight_kg===null?null:Number(weight_kg.toFixed(6)),height_cm:height_cm===null?null:Number(height_cm.toFixed(6))};
  }
  function snapshot(payload){
    if(!payload||!Number.isInteger(payload.version)||payload.version<0||!Array.isArray(payload.measurements)||payload.measurements.length>500||JSON.stringify(payload).length>700000)throw new Error('No pude verificar tus mediciones guardadas.');
    if(typeof payload.eligible!=='boolean'||payload.eligibility_reason!==(payload.eligible?null:'adult_profile_required'))throw new Error('No pude verificar si tu perfil puede guardar mediciones.');
    if(payload.consent!==null&&(!payload.consent||payload.consent.purpose!==PURPOSE||payload.consent.text_version!==CONSENT_VERSION||typeof payload.consent.granted!=='boolean'))throw new Error('No pude verificar el permiso para guardar tus mediciones.');
    if(payload.measurements.length&&payload.consent?.granted!==true)throw new Error('Tus mediciones no tienen un permiso de guardado vigente.');
    const ids=new Set(),dates=new Set();
    for(const row of payload.measurements){const canonical=normalized(row);if(ids.has(row.id)||dates.has(row.date)||canonical.weight_kg!==row.weight_kg||canonical.height_cm!==row.height_cm||!['recorded_at','updated_at'].every(key=>typeof row[key]==='string'&&Number.isFinite(Date.parse(row[key]))))throw new Error('Una medición guardada no se pudo verificar.');ids.add(row.id);dates.add(row.date);}
    return copy(payload);
  }
  function draftMeasurement(draft,rows=[],now=new Date()){
    const parse=value=>String(value).trim()===''?null:Number(value);
    const weightValue=parse(draft.weight),cm=parse(draft.cm),feet=parse(draft.feet),inches=parse(draft.inches);
    const weight=weightValue===null?null:{value:weightValue,unit:draft.weightUnit};
    let height=null;
    if(draft.heightUnit==='cm'&&cm!==null)height={value:cm,unit:'cm'};
    if(draft.heightUnit==='ft_in'&&(feet!==null||inches!==null)){if(feet===null||inches===null)throw new Error('Completa pies y pulgadas, o deja los dos vacíos.');height={unit:'ft_in',feet,inches};}
    const row={id:draft.id,date:draft.date,timezone:draft.timezone,weight,height};normalized(row);
    if(row.date>today(row.timezone,now))throw new Error('La fecha no puede estar en el futuro.');
    if(rows.some(existing=>existing.id!==row.id&&existing.date===row.date))throw new Error('Ya tienes una medición para esta fecha. Corrígela desde el historial o elige otra fecha.');
    if(rows.length>=500&&!rows.some(existing=>existing.id===row.id))throw new Error('Has llegado a 500 mediciones. Puedes exportar tus datos y administrar el historial.');
    return row;
  }
  const format=value=>new Intl.NumberFormat('es',{maximumFractionDigits:2}).format(value);
  const dateLabel=date=>new Intl.DateTimeFormat('es',{day:'numeric',month:'short',year:'numeric',timeZone:'UTC'}).format(new Date(date+'T12:00:00Z'));
  const weightLabel=row=>row?.weight?`${format(row.weight.value)} ${row.weight.unit}`:'Sin peso registrado';
  const heightLabel=row=>row?.height?(row.height.unit==='cm'?`${format(row.height.value)} cm`:`${row.height.feet} pies · ${format(row.height.inches)} pulg`):'Sin estatura registrada';
  function weightDelta(row,rows){
    if(!row?.weight)return null;
    const previous=rows.filter(item=>item.date<row.date&&item.weight).sort((a,b)=>b.date.localeCompare(a.date))[0];
    if(!previous)return null;
    const diff=(row.weight_kg-previous.weight_kg)/(row.weight.unit==='lb'?LB_TO_KG:1),rounded=Number(diff.toFixed(2));
    return {value:rounded,unit:row.weight.unit,previous_date:previous.date,label:`${rounded>0?'+':''}${format(rounded)} ${row.weight.unit}`};
  }
  const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined&&text!==null)node.textContent=text;if(cls)node.className=cls;return node;};
  const btn=(text,fn,cls='fxm-button')=>{const node=el('button',text,cls);node.type='button';node.addEventListener('click',fn);return node;};
  const current=(owner,revision=owner.revision)=>state===owner&&active&&!document.hidden&&owner.revision===revision&&owner.root?.isConnected!==false;
  function cancel(owner){owner.controller?.abort();owner.controller=null;owner.revision++;owner.busy=false;}
  function clearPrivate(owner){cancel(owner);owner.saved=null;owner.draft=null;owner.review=null;owner.confirm=null;owner.loaded=false;owner.blocked=false;owner.conflict=false;owner.uncertain=false;owner.error='';owner.notice='';owner.keys.clear();owner.root.replaceChildren();}
  function focus(owner,selector){owner.root.querySelector(selector)?.focus({preventScroll:true});}
  async function request(owner,path,method='GET',payload){
    const controller=new AbortController();owner.controller=controller;
    const headers={Accept:'application/json','Content-Type':'application/json','X-Roxy-Fitness-Member':owner.identity};
    if(method!=='GET'){headers['X-Roxy-Fitness-Request']='1';const fingerprint=JSON.stringify([path,method,payload]);if(!owner.keys.has(fingerprint))owner.keys.set(fingerprint,scope.crypto.randomUUID());headers['Idempotency-Key']=owner.keys.get(fingerprint);}
    let timer;
    try{return await Promise.race([(async()=>{
      const response=await fetch(path,{method,headers,credentials:'same-origin',cache:'no-store',signal:controller.signal,body:payload===undefined?undefined:JSON.stringify(payload)});
      const data=await response.json().catch(()=>({}));
      if(!response.ok){const error=new Error(typeof data.detail==='string'?data.detail:data.detail?.message||'No pude completar esta operación.');error.status=response.status;error.code=data.detail?.code;throw error;}return data;
    })(),new Promise((_,reject)=>{timer=setTimeout(()=>{controller.abort();reject(new Error('La conexión tardó demasiado. Comprueba el guardado antes de repetir.'));},12000);})]);}
    finally{clearTimeout(timer);if(owner.controller===controller)owner.controller=null;}
  }
  function fail(owner,error){
    owner.error=error.name==='TypeError'?'No pude conectar con tus mediciones. Revisa la conexión y vuelve a intentarlo.':error.status===503?'El guardado privado de mediciones todavía no está disponible. Puedes volver a comprobarlo.':error.status===409?'Tus mediciones cambiaron en otra sesión. Vuelve a cargarlas antes de guardar para conservar esos cambios.':error.message;
    if(error.status===401||error.status===403){owner.saved=null;owner.draft=null;owner.review=null;owner.confirm=null;owner.loaded=false;owner.blocked=true;owner.error='La sesión cambió. Vuelve a entrar en tu perfil para consultar tus mediciones.';}
    if(error.status===409)owner.conflict=true;
  }
  async function load(owner){
    if(!current(owner)||owner.busy)return;
    if(!owner.identity){owner.blocked=true;owner.error='Entra en tu perfil personal para consultar tus mediciones.';draw(owner);return;}
    cancel(owner);const revision=owner.revision;owner.busy=true;owner.error='';owner.blocked=false;draw(owner);
    try{const saved=snapshot(await request(owner,PREFIX));if(!current(owner,revision))return;owner.saved=saved;owner.loaded=true;owner.conflict=false;owner.uncertain=false;}
    catch(error){if(current(owner,revision)&&error.name!=='AbortError')fail(owner,error);}
    finally{if(current(owner,revision)){owner.busy=false;draw(owner);}}
  }
  function reload(owner){if(!current(owner)||owner.busy)return;owner.saved=null;owner.loaded=false;owner.draft=null;owner.review=null;owner.confirm=null;void load(owner);}
  function newDraft(owner,row=null){
    if(!current(owner)||owner.busy||owner.uncertain||owner.conflict||owner.saved?.eligible!==true)return;
    owner.confirm=null;owner.review=null;owner.error='';owner.notice='';
    owner.draft={id:row?.id||scope.crypto.randomUUID(),date:row?.date||today(owner.timezone),timezone:row?.timezone||owner.timezone,weight:row?.weight?.value??'',weightUnit:row?.weight?.unit||owner.weightUnit,heightUnit:row?.height?.unit||owner.heightUnit,cm:row?.height?.unit==='cm'?row.height.value:'',feet:row?.height?.unit==='ft_in'?row.height.feet:'',inches:row?.height?.unit==='ft_in'?row.height.inches:'',editing:!!row,consent:false};
    draw(owner);focus(owner,'.fxm-form-title');
  }
  async function save(owner){
    if(!current(owner)||owner.busy||owner.blocked||owner.conflict||owner.uncertain||owner.saved?.eligible!==true||!owner.review)return;
    if(!owner.draft.consent){owner.error='Confirma que autorizas guardar estas mediciones en tu perfil personal.';draw(owner);return;}
    const revision=owner.revision;owner.busy=true;owner.error='';owner.notice='';draw(owner);
    try{
      if(owner.saved.consent?.granted!==true){const result=await request(owner,PREFIX+'/consent','POST',{expected_version:owner.saved.version,consent:{purpose:PURPOSE,text_version:CONSENT_VERSION,granted:true}});if(!current(owner,revision))return;owner.saved=snapshot(result);}
      const result=await request(owner,PREFIX,'PUT',{expected_version:owner.saved.version,measurement:owner.review});if(!current(owner,revision))return;
      owner.saved=snapshot(result);owner.notice=owner.draft.editing?'Tu medición quedó corregida en tu perfil.':'Tu medición quedó guardada en tu perfil.';owner.draft=null;owner.review=null;owner.keys.clear();
    }catch(error){if(current(owner,revision)&&error.name!=='AbortError'){fail(owner,error);owner.uncertain=!error.status||error.status>=500;}}
    finally{if(current(owner,revision)){owner.busy=false;draw(owner);}}
  }
  async function remove(owner){
    if(!current(owner)||owner.busy||owner.blocked||owner.conflict||owner.uncertain||!owner.confirm)return;
    const revision=owner.revision,id=owner.confirm.id;owner.busy=true;owner.error='';draw(owner);
    try{const result=await request(owner,id?PREFIX+'/'+encodeURIComponent(id):PREFIX,'DELETE',{expected_version:owner.saved.version,confirm_delete:true});if(!current(owner,revision))return;owner.saved=snapshot(result);owner.confirm=null;owner.keys.clear();owner.notice=id?'La medición fue eliminada de tu perfil.':'Tus mediciones fueron eliminadas y el permiso de guardado fue retirado.';}
    catch(error){if(current(owner,revision)&&error.name!=='AbortError'){fail(owner,error);owner.uncertain=!error.status||error.status>=500;}}
    finally{if(current(owner,revision)){owner.busy=false;draw(owner);}}
  }
  async function exportData(owner){
    if(!current(owner)||owner.busy)return;const revision=owner.revision;owner.busy=true;owner.error='';draw(owner);
    try{const data=await request(owner,PREFIX+'/export');if(!current(owner,revision))return;if(data?.format!=='roxy-home-fitness-measurements-v1'||data.scope!=='authenticated_member_only')throw new Error('No pude verificar la exportación de tus mediciones.');snapshot(data.data);
      const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),link=el('a');link.href=url;link.download='mis-mediciones-roxy.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);owner.notice='Descarga preparada con tus mediciones guardadas.';
    }catch(error){if(current(owner,revision)&&error.name!=='AbortError')fail(owner,error);}
    finally{if(current(owner,revision)){owner.busy=false;draw(owner);}}
  }
  function inputField(label,value,type,onChange){const wrapper=el('label',label),input=el('input');input.type=type;input.value=value;input.setAttribute('aria-label',label);input.addEventListener('input',()=>onChange(input.value));wrapper.append(input);return {wrapper,input};}
  function selectField(label,value,choices,onChange){const wrapper=el('label',label),select=el('select');select.setAttribute('aria-label',label);for(const [key,text] of choices){const option=el('option',text);option.value=key;option.selected=key===value;select.append(option);}select.value=value;select.addEventListener('change',()=>onChange(select.value));wrapper.append(select);return wrapper;}
  function drawForm(owner,wrap){
    const draft=owner.draft,title=el('h4',draft.editing?'Corregir medición':'Añadir una medición','fxm-form-title');title.tabIndex=-1;wrap.append(title);
    if(owner.review){
      const review=el('section',null,'fxm-review');review.append(el('h5','Revisa antes de guardar'),el('p',dateLabel(owner.review.date),'fxm-review-date'),el('p',weightLabel(owner.review)),el('p',heightLabel(owner.review)),el('p',`Zona horaria: ${owner.review.timezone}`,'fxm-caption'));
      const label=el('label',null,'fxm-consent'),check=el('input');check.type='checkbox';check.checked=draft.consent;check.addEventListener('change',()=>draft.consent=check.checked);label.append(check,el('span','Autorizo guardar mi peso y/o estatura solo en mi perfil personal para consultar mi evolución.'));review.append(label,el('p','Puedes descargar, corregir o eliminar tus mediciones y retirar este permiso desde aquí.','fxm-caption'));
      const actions=el('div',null,'fxm-actions');actions.append(btn(draft.editing?'Guardar corrección':'Guardar medición',()=>void save(owner),'fxm-button fxm-primary'),btn('Volver a editar',()=>{owner.review=null;owner.error='';draw(owner);}));review.append(actions);wrap.append(review);return;
    }
    wrap.append(el('p','Elige lo que quieras registrar. Puedes añadir solo peso, solo estatura o ambos.','fxm-caption'));
    const form=el('form',null,'fxm-form');form.setAttribute('aria-label','Mi medición privada');
    const date=inputField('Fecha de medición',draft.date,'date',value=>draft.date=value);date.input.required=true;date.input.max=today(draft.timezone);
    const zone=inputField('Zona horaria de la medición',draft.timezone,'text',value=>draft.timezone=value);zone.input.required=true;zone.input.maxLength=64;zone.input.readOnly=true;
    const dates=el('div',null,'fxm-field-grid');dates.append(date.wrapper,zone.wrapper);form.append(dates);
    const fields=el('div',null,'fxm-field-grid');
    const weight=el('fieldset',null,'fxm-fieldset');weight.append(el('legend','Peso · opcional'));
    const weightInput=inputField('Peso',draft.weight,'number',value=>draft.weight=value);weightInput.input.step='any';weightInput.input.min='0';weightInput.input.inputMode='decimal';
    weight.append(weightInput.wrapper,selectField('Unidad de peso',draft.weightUnit,[['kg','Kilogramos (kg)'],['lb','Libras (lb)']],value=>{draft.weightUnit=value;}));
    const height=el('fieldset',null,'fxm-fieldset');height.append(el('legend','Estatura · opcional'),selectField('Unidad de estatura',draft.heightUnit,[['cm','Centímetros (cm)'],['ft_in','Pies y pulgadas']],value=>{draft.heightUnit=value;draw(owner);}));
    if(draft.heightUnit==='cm'){const cm=inputField('Estatura en centímetros',draft.cm,'number',value=>draft.cm=value);cm.input.step='any';cm.input.inputMode='decimal';height.append(cm.wrapper);}
    else{const values=el('div',null,'fxm-height-values'),feet=inputField('Pies',draft.feet,'number',value=>draft.feet=value),inches=inputField('Pulgadas',draft.inches,'number',value=>draft.inches=value);feet.input.step='1';feet.input.min='0';feet.input.max='9';inches.input.step='any';inches.input.min='0';inches.input.max='11.99';inches.input.inputMode='decimal';values.append(feet.wrapper,inches.wrapper);height.append(values);}
    fields.append(weight,height);form.append(fields,el('p','Son datos que tú introduces. Roxy muestra el historial sin asignar metas de peso.','fxm-caption'));
    const actions=el('div',null,'fxm-actions'),submit=el('button','Revisar medición','fxm-button fxm-primary');submit.type='submit';actions.append(submit,btn('Cancelar',()=>{owner.draft=null;owner.review=null;owner.error='';draw(owner);}));form.append(actions);
    form.addEventListener('submit',event=>{event.preventDefault();event.stopPropagation();if(!current(owner)||owner.busy)return;try{owner.review=draftMeasurement(draft,owner.saved.measurements);owner.error='';}catch(error){owner.error=error.message;}draw(owner);});wrap.append(form);
  }
  function drawHistory(owner,wrap){
    const rows=[...owner.saved.measurements].sort((a,b)=>b.date.localeCompare(a.date));
    if(!rows.length){const empty=el('div',null,'fxm-empty');empty.append(el('span','A TU RITMO','fxm-eyebrow'),el('h4','El primer registro lo eliges tú.'),el('p','Aquí verás tus mediciones cuando decidas guardarlas. Puedes seguir usando Ejercicio sin añadir peso ni estatura.'));wrap.append(empty);}
    else{
      const latestWeight=rows.find(row=>row.weight),latestHeight=rows.find(row=>row.height),summary=el('div',null,'fxm-summary');
      for(const [label,row,value] of [['Último peso',latestWeight,weightLabel(latestWeight)],['Última estatura',latestHeight,heightLabel(latestHeight)]]){const cell=el('div',null,'fxm-stat');cell.append(el('span',label),el('strong',value),el('small',row?dateLabel(row.date):'Puedes añadirlo cuando quieras'));summary.append(cell);}
      wrap.append(summary);
      const delta=weightDelta(latestWeight,rows);if(delta)wrap.append(el('p',`${delta.label} desde tu registro con peso del ${dateLabel(delta.previous_date)}. Es la diferencia entre los valores que introdujiste.`,'fxm-delta'));
      const tableWrap=el('div',null,'fxm-table-wrap'),table=el('table',null,'fxm-table');table.append(el('caption',`Historial · ${rows.length} ${rows.length===1?'medición':'mediciones'}`));const head=el('thead'),headRow=el('tr');for(const label of ['Fecha','Peso','Estatura','Tus registros']){const th=el('th',label);th.setAttribute('scope','col');headRow.append(th);}head.append(headRow);table.append(head);const body=el('tbody');
      for(const row of rows){const tr=el('tr'),date=el('th',dateLabel(row.date));date.setAttribute('scope','row');tr.append(date);const weight=el('td',row.weight?weightLabel(row):'—');const delta=weightDelta(row,rows);if(delta)weight.append(el('small',`${delta.label} desde ${dateLabel(delta.previous_date)}`,'fxm-table-delta'));tr.append(weight,el('td',row.height?heightLabel(row):'—'));const actions=el('td',null,'fxm-row-actions');const edit=btn('Corregir',()=>newDraft(owner,row),'fxm-button fxm-text');edit.disabled=owner.saved.eligible!==true;edit.setAttribute('aria-label',`Corregir medición del ${dateLabel(row.date)}`);const removeButton=btn('Eliminar',()=>{owner.confirm={id:row.id,date:row.date};owner.error='';draw(owner);focus(owner,'.fxm-confirm');},'fxm-button fxm-text');removeButton.setAttribute('aria-label',`Eliminar medición del ${dateLabel(row.date)}`);actions.append(edit,removeButton);tr.append(actions);body.append(tr);}table.append(body);tableWrap.append(table);wrap.append(tableWrap);
    }
    if(owner.saved.eligible===true)wrap.append(btn('Añadir medición',()=>newDraft(owner),'fxm-button fxm-primary'));
    else{const message=el('div',null,'fxm-eligibility');message.append(el('p','Completa primero tus preferencias de Ejercicio y confirma que tienes 18 años o más.','fxm-caption'));if(typeof owner.onPreferences==='function')message.append(btn('Configurar mis preferencias',()=>{if(current(owner)&&!owner.busy)owner.onPreferences();}));wrap.append(message);}
    if(rows.length||owner.saved.consent?.granted){const data=el('details',null,'fxm-data');data.append(el('summary','Administrar mis mediciones'),el('p','Estos registros pertenecen a tu perfil personal. Eliminar las mediciones conserva tu plan y tus actividades.','fxm-caption'));const actions=el('div',null,'fxm-actions');actions.append(btn('Descargar mis mediciones',()=>void exportData(owner)),btn('Retirar permiso y borrar mediciones',()=>{owner.confirm={all:true};owner.error='';draw(owner);focus(owner,'.fxm-confirm');},'fxm-button fxm-text'));data.append(actions);wrap.append(data);}
  }
  function draw(owner){
    if(state!==owner||!owner.root)return;owner.root.replaceChildren();if(!active||document.hidden)return;
    const wrap=el('section',null,'fxm-shell');wrap.setAttribute('aria-label','Mis mediciones privadas');wrap.setAttribute('aria-busy',String(owner.busy));owner.root.append(wrap);
    const heading=el('header',null,'fxm-heading');heading.append(el('p','SOLO EN TU PERFIL · TÚ DECIDES','fxm-eyebrow'),el('h3','Tu evolución, a tu ritmo'),el('p','Un espacio para tus registros de peso y estatura. Añadirlos es opcional.','fxm-caption'));wrap.append(heading);
    if(owner.busy){const status=el('p','Comprobando tus mediciones…','fxm-status');status.setAttribute('role','status');wrap.append(status);}
    if(owner.error){const error=el('p',owner.error,'fxm-error');error.setAttribute('role','alert');wrap.append(error);if(owner.uncertain||owner.conflict||!owner.loaded)wrap.append(btn(owner.uncertain?'Comprobar guardado':'Volver a cargar mediciones',()=>reload(owner)));}
    if(owner.notice){const notice=el('p',owner.notice,'fxm-status');notice.setAttribute('role','status');wrap.append(notice);}
    if(owner.loaded&&owner.saved&&!owner.blocked&&!owner.conflict&&!owner.uncertain){
      if(owner.confirm){const box=el('section',null,'fxm-confirm');box.tabIndex=-1;box.setAttribute('role','group');box.append(el('h4',owner.confirm.id?'¿Eliminar esta medición?':'¿Retirar el permiso y borrar tus mediciones?'),el('p',owner.confirm.id?`Se eliminará el registro del ${dateLabel(owner.confirm.date)}.`:'Se eliminarán todos tus registros de peso y estatura de este perfil y se retirará el permiso de guardarlos.'),el('p','Tu plan y tus actividades se conservan.','fxm-caption'));const actions=el('div',null,'fxm-actions');actions.append(btn(owner.confirm.id?'Sí, eliminar medición':'Sí, retirar y borrar',()=>void remove(owner),'fxm-button fxm-danger'),btn('Conservar mis mediciones',()=>{owner.confirm=null;draw(owner);}));box.append(actions);wrap.append(box);}
      else if(owner.draft)drawForm(owner,wrap);else drawHistory(owner,wrap);
    }
    if(owner.busy)wrap.querySelectorAll('button,input,select').forEach(node=>node.disabled=true);
  }
  function mount(root,options={}){
    if(!root)return;const identity=options.identity||'';
    if(!state||state.identity!==identity){if(state)clearPrivate(state);state={root,identity,revision:0,controller:null,busy:false,loaded:false,saved:null,draft:null,review:null,confirm:null,keys:new Map(),error:'',notice:'',blocked:false,conflict:false,uncertain:false};}
    else if(state.root!==root)state.root.replaceChildren();
    state.root=root;state.onPreferences=options.onPreferences;state.timezone=zoneOK(options.timezone)?options.timezone:'UTC';state.weightUnit=options.weightUnit==='lb'?'lb':'kg';state.heightUnit=options.heightUnit==='ft_in'?'ft_in':'cm';draw(state);if(active&&!state.loaded&&!state.busy&&!state.error)void load(state);
  }
  function setActive(value){const next=value===true;if(next===active)return;active=next;if(state){clearPrivate(state);if(next&&!document.hidden)void load(state);}}
  function clear(){if(state)clearPrivate(state);state=null;}
  scope.RoxyFitnessMeasurements={mount,setActive,clear};
  if(typeof document!=='undefined')document.addEventListener('visibilitychange',()=>{if(!state)return;if(document.hidden)clearPrivate(state);else if(active)void load(state);});
  scope.addEventListener?.('pagehide',clear);
  if(typeof module!=='undefined')module.exports={today,dateOK,zoneOK,normalized,snapshot,draftMeasurement,weightDelta};
})(typeof window!=='undefined'?window:globalThis);
