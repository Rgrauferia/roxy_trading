# Voz oficial de Roxy Home

La guía paso a paso usa la misma voz configurada en el agente oficial de Roxy en ElevenLabs. El navegador solicita el audio al servidor de Home y recibe únicamente un MP3; la clave, el identificador de voz y la llamada al proveedor nunca se exponen en JavaScript.

Home conserva una clave y presupuesto propios. En particular, `ELEVENLABS_API_KEY` pertenece a Trading y nunca se usa como respaldo en Home.

## Configuración

En **roxy-home → Environment** configura:

```text
ROXY_HOME_ELEVENLABS_API_KEY=<clave exclusiva de Roxy Home>
ROXY_HOME_ELEVENLABS_AGENT_ID=agent_6101kwchebzdf91rfk9757wq0mk4
ROXY_HOME_ELEVENLABS_VOICE_ID=
ROXY_HOME_ELEVENLABS_MODEL_ID=eleven_multilingual_v2
ROXY_HOME_ELEVENLABS_CACHE_DIR=/var/data/roxy_home/voice
```

Si `ROXY_HOME_ELEVENLABS_VOICE_ID` queda vacío, el servidor consulta el agente indicado y usa automáticamente su voz oficial. Esto permite mantener la voz sincronizada sin copiar el identificador al cliente.

## Reutilización y privacidad

- Cada lectura se almacena como MP3 usando un hash de usuario, voz, modelo y texto.
- Repetir el mismo paso reutiliza el archivo y evita un nuevo consumo de ElevenLabs.
- La ruta exige la sesión autenticada de Home y deriva el texto desde la sesión de cocina; el teléfono no puede convertir texto arbitrario.
- El estado público solo indica si la voz está disponible y nunca devuelve secretos.
