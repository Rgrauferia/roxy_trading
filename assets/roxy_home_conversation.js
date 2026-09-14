(() => {
  'use strict';
  // The microphone supplies one turn to Home's authenticated command endpoint.
  // ElevenLabs only reads its answer; no second LLM, tools or shared agent.
  function create({isCurrent, sendCommand, requestSpeech, onStatus, onTranscript, onEnd}) {
    let ended=false, generation=0, recognition=null, controller=null, audio=null, url=null, timer=null, watcher=null, settleAudio=null;
    const current=()=>!ended&&!document.hidden&&isCurrent();
    const status=(text,error=false)=>{if(current())onStatus(text,error);};
    function cleanup(){
      generation++;clearTimeout(timer);timer=null;controller?.abort();controller=null;
      settleAudio?.(false);settleAudio=null;
      if(recognition){recognition.onstart=null;recognition.onresult=null;recognition.onend=null;recognition.onerror=null;try{recognition.abort();}catch(_){}recognition=null;}
      if(audio){audio.onplaying=null;audio.onended=null;audio.onerror=null;audio.pause();audio=null;}
      if(url){URL.revokeObjectURL(url);url=null;}
    }
    function endSession(){if(ended)return;ended=true;cleanup();clearTimeout(watcher);document.removeEventListener('visibilitychange',visibility);onEnd?.();}
    function visibility(){if(document.hidden)endSession();}
    function watch(){if(!current()){endSession();return;}watcher=setTimeout(watch,200);}
    function fail(message){status(message,true);endSession();}
    document.addEventListener('visibilitychange',visibility);watch();
    function chunks(text){
      let remaining=String(text||'').trim();const rows=[];
      if(!remaining||remaining.length>12000)throw new Error('La respuesta completa está por escrito; es demasiado larga para esta lectura.');
      while(remaining){let size=Math.min(1200,remaining.length);if(size<remaining.length){const boundary=remaining.lastIndexOf(' ',size);if(boundary>600)size=boundary;}rows.push(remaining.slice(0,size));remaining=remaining.slice(size).trim();}
      return rows;
    }
    async function speak(text,resume=false){
      if(!current()){endSession();return;}
      cleanup();const token=generation;
      try{
        for(const chunk of chunks(text)){
          if(!current()||token!==generation)return;
          controller=new AbortController();status('Preparando la voz oficial de Roxy…');
          timer=setTimeout(()=>fail('La voz tardó demasiado. Puedes reintentar la lectura.'),25000);
          const blob=await requestSpeech(chunk,controller.signal);
          if(!current()||token!==generation)return;
          clearTimeout(timer);controller=null;
          url=URL.createObjectURL(blob);audio=new Audio(url);
          const played=await new Promise((resolve,reject)=>{
            settleAudio=resolve;
            const player=audio;let started=false;
            timer=setTimeout(()=>reject(new Error('El navegador no inició el audio. Pulsa Escuchar con Roxy.')),6000);
            player.onplaying=()=>{if(!current()||token!==generation)return;started=true;clearTimeout(timer);timer=setTimeout(()=>reject(new Error('La lectura se interrumpió. Puedes repetirla.')),180000);status('Roxy · voz oficial hablando');};
            player.onended=()=>resolve(started);
            player.onerror=()=>reject(new Error('No se pudo reproducir el audio. Puedes reintentar.'));
            Promise.resolve(player.play()).catch(reject);
          });
          if(!current()||token!==generation)return;
          clearTimeout(timer);settleAudio=null;audio.onplaying=null;audio.onended=null;audio.onerror=null;audio=null;URL.revokeObjectURL(url);url=null;
          if(!played)throw new Error('La lectura no llegó a comenzar. Puedes reintentar.');
        }
        if(!current()||token!==generation)return;
        if(resume)listen();else{status('Lectura terminada.');endSession();}
      }catch(error){if(current()&&token===generation)fail(error?.message||'No se pudo conectar la voz oficial.');}
    }
    function listen(){
      if(!current()){endSession();return;}
      const Recognition=window.SpeechRecognition||window.webkitSpeechRecognition;
      if(!Recognition){fail('Este navegador no permite dictado. Puedes escribir y escuchar la respuesta con la voz oficial.');return;}
      cleanup();const token=generation;let transcript='';
      recognition=new Recognition();recognition.lang='es-ES';recognition.continuous=false;recognition.interimResults=false;
      recognition.onstart=()=>{if(current()&&token===generation)status('Roxy te escucha · habla en español');};
      recognition.onresult=event=>{if(!current()||token!==generation)return;for(let i=event.resultIndex;i<event.results.length;i++){if(event.results[i].isFinal)transcript+=event.results[i][0].transcript+' ';}};
      recognition.onerror=event=>{if(current()&&token===generation)fail(event.error==='not-allowed'?'Activa el permiso de micrófono del sitio o escribe tu mensaje.':'No pude oírte. Pulsa Iniciar para intentarlo de nuevo.');};
      recognition.onend=async()=>{
        if(!current()||token!==generation)return;clearTimeout(timer);recognition=null;
        const command=transcript.trim();if(!command){status('No escuché un mensaje. Puedes iniciar de nuevo o escribir.');endSession();return;}
        if(/^(?:adi[oó]s|terminar|termina la conversaci[oó]n|hasta luego)[.!]?$/i.test(command)){status('Conversación terminada.');endSession();return;}
        if(command.length>1000){fail('El mensaje es muy largo. Escríbelo o dicta una frase más corta.');return;}
        onTranscript(command,'Tú');status('Roxy está pensando…');
        controller=new AbortController();timer=setTimeout(()=>fail('Roxy tardó demasiado. Revisa el resultado antes de repetir una acción.'),45000);
        try{
          const result=await sendCommand(command,controller.signal);
          if(!current()||token!==generation)return;clearTimeout(timer);controller=null;
          const answer=String(result.speech||result.message||'No recibí una respuesta.');onTranscript(answer,'Roxy');await speak(answer,true);
        }catch(error){if(current()&&token===generation)fail(error?.message||'No pude responder. Puedes escribir el mensaje.');}
      };
      try{status('Esperando el permiso y la apertura del micrófono…');recognition.start();timer=setTimeout(()=>{if(current()&&token===generation){status('Micrófono detenido. Pulsa Iniciar cuando quieras continuar.');endSession();}},30000);}
      catch(_){fail('No se pudo abrir el micrófono. Puedes escribir y escuchar la respuesta.');}
    }
    return {start:listen,speak,endSession};
  }
  window.RoxyHomeConversation=Object.freeze({create});
})();
