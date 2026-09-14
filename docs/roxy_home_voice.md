# Voz oficial de Roxy Home

«Ver receta» abre el original en silencio. «Preparar con Roxy» en comidas y bebidas abre la guía y solicita su primer paso con la voz oficial. La guía común usa el servidor Home para generar MP3 y ofrece la voz del dispositivo como elección explícita. Si la oficial falla, muestra el motivo y permite reintentar sin cambiar de voz automáticamente. El lector anterior de sesiones guardadas conserva su respaldo automático, identificado como voz del dispositivo. La clave y la llamada al proveedor permanecen en el servidor.

Home conserva una clave, agente y presupuesto propios. `ELEVENLABS_API_KEY` y `ELEVENLABS_AGENT_ID` genéricos nunca se usan como respaldo en Home. No hay un identificador de agente predeterminado compartido.

## Configuración

En **roxy-home → Environment** configura:

```text
ROXY_HOME_ELEVENLABS_API_KEY=<clave exclusiva de Roxy Home>
ROXY_HOME_ELEVENLABS_AGENT_ID=<agente exclusivo de Roxy Home>
ROXY_HOME_ELEVENLABS_VOICE_ID=
ROXY_HOME_ELEVENLABS_MODEL_ID=eleven_multilingual_v2
ROXY_HOME_ELEVENLABS_CACHE_DIR=/var/data/roxy_home/voice
```

Si `ROXY_HOME_ELEVENLABS_VOICE_ID` queda vacío, el servidor consulta únicamente el agente Home indicado y usa su voz configurada. Para TTS también se puede configurar clave Home + voz Home sin agente conversacional. La conversación necesita un agente Home explícito; consulta su configuración antes de pedir acceso al micrófono.

`CONFIGURED` y `provider_health_verified: false` indican configuración local, no disponibilidad comprobada. El 13/09 Roberto confirmó resolver el pago pendiente de ElevenLabs; una síntesis breve real volvió a devolver audio (40.586 bytes). Se verificó el identificador de la voz histórica de Roxy y se configuró para TTS Home, sin copiar claves ni asignar el agente compartido. Modelo verificado: `eleven_flash_v2_5`. El agente de conversación general de Home sigue sin configurarse; esto no impide usar las preguntas de recetas mediante OpenAI y leerlas con TTS. No afirmar que el botón general Iniciar esté operativo por esta recuperación.

## Voz del dispositivo

El botón «Escuchar respuesta · voz del dispositivo» lee una respuesta escrita sólo al pulsarlo. No abre el micrófono ni inicia una conversación de ElevenLabs. Su disponibilidad y sonido dependen del navegador, volumen y voces instaladas; se prefiere una voz española local cuando el navegador la enumera. El navegador puede elegir una voz remota si no tiene una local, por lo que no se promete funcionamiento sin conexión.

Los lectores informan «hablando» sólo tras el evento de inicio de audio. El inicio silencioso tiene un plazo y un mensaje de reintento. Cerrar el lector, cambiar sesión/paso/miembro u ocultar la página cancela la lectura y descarta respuestas tardías. Un error de reproducción no equivale a un paso terminado ni inicia su temporizador.

## Reutilización y privacidad

- Cada lectura se almacena como MP3 usando un hash de usuario, voz, modelo y texto.
- Repetir el mismo paso reutiliza el archivo y evita un nuevo consumo de ElevenLabs.
- La ruta antigua deriva el texto desde la sesión de cocina. La ruta `/recipe-speech` exige además miembro, origen y referencia vigente de receta/paso; resuelve el paso original en el servidor. El modo respuesta lee el texto visible enviado por el cliente (máximo 1.200 caracteres), ligado a la receta abierta, sin tratarlo como instrucciones o una modificación del hogar. No añade preferencias ni historial. El audio puede contener información personal ya presente en esa respuesta y queda en la caché privada del miembro.
- Home reserva como máximo 200 solicitudes y 20.000 caracteres por día UTC antes de llamar a ElevenLabs, bajo bloqueo de proceso y archivo. Los intentos fallidos conservan la reserva por prudencia; estos conteos no son una factura. Repeticiones desde caché no consumen otra reserva. Contador privado persistente `/var/data/roxy_home/voice/usage.json`, sin texto ni secretos; corrupción o pérdida tras inicialización impide nuevos envíos. No se aumentan límites ni se reinicia el contador desde la UI.
- El estado público distingue configuración de salud comprobada y nunca devuelve secretos.
- Los pasos que superen el límite de 1.200 caracteres del TTS oficial se rechazan antes de llamar al proveedor; la alternativa del dispositivo recibe el texto íntegro. No se recorta silenciosamente el final de una instrucción.
- Las pruebas automáticas usan voces, audio y hogares sintéticos. No demuestran audio audible en un teléfono físico ni resuelven una suspensión del proveedor.
