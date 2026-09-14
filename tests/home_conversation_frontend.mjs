import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const source=fs.readFileSync(new URL('../assets/roxy_home_conversation.js',import.meta.url),'utf8');
const settle=async()=>{for(let i=0;i<20;i++)await Promise.resolve();};
function harness({recognition=true,speech,command}={}){
  const audios=[],microphones=[],spoken=[],commands=[],statuses=[],transcripts=[],revoked=[],timers=new Map(),listeners=new Map();let count=0,ends=0,valid=true;
  const document={hidden:false,addEventListener:(name,fn)=>listeners.set(name,fn),removeEventListener:name=>listeners.delete(name)};
  const window={};if(recognition)window.SpeechRecognition=class{constructor(){microphones.push(this);}start(){this.started=true;}abort(){this.aborted=true;}};
  vm.runInNewContext(source,{window,document,AbortController,URL:{createObjectURL:()=>`blob:${audios.length}`,revokeObjectURL:u=>revoked.push(u)},
    Audio:class{constructor(){audios.push(this);}pause(){this.paused=true;}async play(){this.requested=true;}},
    setTimeout:(fn,delay)=>{timers.set(++count,{fn,delay});return count;},clearTimeout:id=>timers.delete(id)});
  const controller=window.RoxyHomeConversation.create({isCurrent:()=>valid,onStatus:(...s)=>statuses.push(s),onTranscript:(...s)=>transcripts.push(s),onEnd:()=>ends++,
    requestSpeech:async(text,signal)=>{spoken.push({text,signal});return speech?speech(text,signal):{};},
    sendCommand:async(text,signal)=>{commands.push({text,signal});return command?command(text,signal):{speech:'Respuesta de Home.'};}});
  function result(text){const mic=microphones.at(-1),row=[{transcript:text}];row.isFinal=true;mic.onresult({resultIndex:0,results:[row]});mic.onend();}
  return {controller,audios,microphones,spoken,commands,statuses,transcripts,revoked,timers,result,document,ends:()=>ends,
    expire:delay=>{for(const [id,t]of[...timers])if(t.delay===delay&&timers.has(id)){timers.delete(id);t.fn();}},invalidate:()=>{valid=false;},hide:()=>{document.hidden=true;listeners.get('visibilitychange')?.();}};
}
test('a microphone turn goes only to Home and resumes listening after official playback ends',async()=>{
  const h=harness();h.controller.start();assert.equal(h.microphones.length,1);h.result('¿Qué tengo en mi lista?');await settle();
  assert.equal(h.commands[0].text,'¿Qué tengo en mi lista?');assert.equal(h.spoken[0].text,'Respuesta de Home.');assert.equal(h.microphones.length,1);
  assert.doesNotMatch(h.statuses.at(-1)[0],/hablando/);h.audios[0].onplaying();assert.match(h.statuses.at(-1)[0],/oficial hablando/);
  h.audios[0].onended();await settle();assert.equal(h.microphones.length,2);assert.equal(h.revoked.length,1);h.controller.endSession();assert.equal(h.microphones[1].aborted,true);
});
test('close aborts a pending command and never speaks its late result',async()=>{
  let resolve;const h=harness({command:()=>new Promise(r=>resolve=r)});h.controller.start();h.result('Consulta');await settle();h.controller.endSession();assert.equal(h.commands[0].signal.aborted,true);
  resolve({speech:'Resultado antiguo'});await settle();assert.equal(h.spoken.length,0);assert.equal(h.ends(),1);
});
test('identity change aborts pending speech and discards late audio',async()=>{
  let resolve;const h=harness({speech:()=>new Promise(r=>resolve=r)});const reading=h.controller.speak('Texto');h.invalidate();h.expire(200);assert.equal(h.spoken[0].signal.aborted,true);resolve({});await reading;assert.equal(h.audios.length,0);
});
test('hiding stops playback, frees its URL and settles the reading',async()=>{
  const h=harness();const reading=h.controller.speak('Texto');await settle();h.audios[0].onplaying();h.hide();await reading;assert.equal(h.audios[0].paused,true);assert.equal(h.revoked.length,1);assert.equal(h.microphones.length,0);
});
test('long spoken replies retain every word in ordered bounded chunks',async()=>{
  const h=harness(),text='Palabra completa. '.repeat(180).trim();const reading=h.controller.speak(text);await settle();
  for(let i=0;i<3;i++){h.audios[i].onplaying();h.audios[i].onended();await settle();}await reading;
  assert.equal(h.spoken.map(x=>x.text).join(' '),text);assert.ok(h.spoken.every(x=>x.text.length<=1200));assert.equal(h.ends(),1);
});
test('provider failure ends without retries or a substitute voice',async()=>{
  const h=harness({speech:()=>{throw new Error('Pago pendiente');}});await h.controller.speak('Texto');assert.equal(h.spoken.length,1);assert.equal(h.audios.length,0);assert.match(h.statuses.at(-1)[0],/Pago/);assert.equal(h.ends(),1);
});
test('unsupported or idle microphones leave typing available and never send an empty turn',()=>{
  const a=harness({recognition:false});a.controller.start();assert.match(a.statuses.at(-1)[0],/escribir/);assert.equal(a.commands.length,0);
  const b=harness();b.controller.start();b.expire(30000);assert.equal(b.microphones[0].aborted,true);assert.equal(b.commands.length,0);
});
test('an explicit goodbye ends without a backend command or another microphone',async()=>{
  const h=harness();h.controller.start();h.result('Adiós');await settle();assert.equal(h.commands.length,0);assert.equal(h.microphones.length,1);assert.equal(h.ends(),1);
});
