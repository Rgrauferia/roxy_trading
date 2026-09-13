# Voz oficial de Roxy Home

La guía de cocina puede solicitar un MP3 al servidor de Home con la voz configurada para este producto. Si la voz oficial no está configurada, falla o no comienza a reproducirse, el lector intenta la voz del dispositivo con el texto completo del paso. El usuario puede detenerla y volver a escuchar. El navegador recibe únicamente el MP3; la clave y la llamada de síntesis al proveedor permanecen en el servidor.

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

`CONFIGURED` y `provider_health_verified: false` indican configuración local, no una llamada ni disponibilidad comprobada del proveedor. La voz conversacional existente usa el agente público de Home por WebSocket: no se configura ni verifica su aislamiento en la cuenta del proveedor mediante estas pruebas locales. El incidente público registrado el 05/09 fue `payment_issue` de ElevenLabs. Su facturación actual no se ha vuelto a comprobar y este cambio no la modifica.

## Voz del dispositivo

El botón «Escuchar respuesta · voz del dispositivo» lee una respuesta escrita sólo al pulsarlo. No abre el micrófono ni inicia una conversación de ElevenLabs. Su disponibilidad y sonido dependen del navegador, volumen y voces instaladas; se prefiere una voz española local cuando el navegador la enumera. El navegador puede elegir una voz remota si no tiene una local, por lo que no se promete funcionamiento sin conexión.

Los lectores informan «hablando» sólo tras el evento de inicio de audio. El inicio silencioso tiene un plazo y un mensaje de reintento. Cerrar el lector, cambiar sesión/paso/miembro u ocultar la página cancela la lectura y descarta respuestas tardías. Un error de reproducción no equivale a un paso terminado ni inicia su temporizador.

## Reutilización y privacidad

- Cada lectura se almacena como MP3 usando un hash de usuario, voz, modelo y texto.
- Repetir el mismo paso reutiliza el archivo y evita un nuevo consumo de ElevenLabs.
- La ruta exige la sesión autenticada de Home y deriva el texto desde la sesión de cocina; el teléfono no puede convertir texto arbitrario.
- El estado público distingue configuración de salud comprobada y nunca devuelve secretos.
- Los pasos que superen el límite de 1.200 caracteres del TTS oficial se rechazan antes de llamar al proveedor; la alternativa del dispositivo recibe el texto íntegro. No se recorta silenciosamente el final de una instrucción.
- Las pruebas automáticas usan voces, audio y hogares sintéticos. No demuestran audio audible en un teléfono físico ni resuelven una suspensión del proveedor.
