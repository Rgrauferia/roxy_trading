# Voz real en la vista local 204 — 14/09/2026

El aviso de voz no disponible era causado por la fixture 8770: eliminaba la
configuración de proveedores y bloqueaba todas las solicitudes externas. No fue
prueba de otro pago pendiente ni de un fallo actual de ElevenLabs.

La fixture ahora mantiene su modo sin red por defecto y admite --voice-config
para conectar sólo los guiones fijos de voz oficial. Se leyó exclusivamente la
configuración TTS del servicio roxy-home en Render (clave, voz y modelo), sin
modificar variables ni desplegar. Archivo temporal 0600 en directorio0700, fuera
del repositorio, consumido y eliminado al iniciar. No se copiaron secretos de
Trading, Study ni otros productos y no se enviaron al frontend de Home.

El transporte de la prueba permite únicamente POST al endpoint HTTPS exacto de
esa voz de ElevenLabs, modelo esperado y textos de guiones fijos: recorrido,
casa, cocina, jardín y ejercicios. No permite redirecciones, otro proveedor,
otra voz ni respuestas privadas. Cupo adicional y separado de esta prueba:
40solicitudes/10000caracteres al día; caché y contador propios de la fixture.
No cambia el cupo de producción ni el plan del proveedor.

Antes del reinicio se preservaron7archivos de la fixture, byteidénticos, en una
copia privada. Se restauraron los datos en la nueva fixture; el nombre Casa de
prueba y sus elecciones se mantuvieron. Se inició de nuevo la sesión sintética.

Verificación real por CUA: Entrada, Mi casa y Mi movimiento generaron audio de
ElevenLabs. La UI mostró Roxy · voz original y rhw-speaking; después llegó al
estado final de la narración. Repetir usó caché. Cambiar de escena inició la voz
sin otra pulsación de Escuchar. Tres archivos MP3,3solicitudes/525caracteres en
el contador local tras la comprobación. No prueba del altavoz físico del Mac.
13pruebas nuevas aprobadas de aislamiento/red/configuración; git diff --check OK.

Servidor8770: PID63912, sesión37666, datos temporales
/var/folders/d9/j1tl468d4cd8y2zsrx53vj000000gn/T/roxy-login-qa-qhuwco8j.
Copia preservada:
/var/folders/d9/j1tl468d4cd8y2zsrx53vj000000gn/T/roxy-home-204-preserved-rjo1eclw.
Pestaña3 marcada como entrega, abierta en Mi movimiento con voz disponible.
No commit, push o deploy. Público continúa203. Vídeo con labios sigue pendiente.

## Consulta de Runway

Roberto preguntó qué integrar, sin pedir todavía una instalación o generación.
Documentación oficial consultada14/09:

- Character Script to Video acepta imagen de Roxy y audio propio para vídeo hablado:
  https://help.runwayml.com/hc/en-us/articles/51285026291219-Character-Script-to-Video
- Characters permite avatar conversacional en tiempo real:
  https://docs.dev.runwayml.com/characters/
- LiveKit permite conservar el agente y el TTS propios; Runway recibe audio y entrega
  vídeo del avatar: https://docs.dev.runwayml.com/characters/livekit/
- También existe integración directa con agentes ElevenLabs:
  https://docs.dev.runwayml.com/characters/elevenlabs/

Propuesta pendiente de decisión: clips de bienvenida reutilizables y avatar en
vivo para conversación, conservando identidad, voz, agente Home y controles de
acciones. La integración directa ElevenLabs administra la conversación allí;
para preservar el agente Responses actual de Home debe evaluarse la vía LiveKit.
Runway no está conectado; no se instaló plugin, no se creó cuenta, no se generó
vídeo ni se gastaron créditos de Runway. La interactividad y el guardado se
implementan en Home, no se obtienen automáticamente al generar un vídeo.
