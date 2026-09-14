# Roxy Home — continuidad recuperada y prueba real de recetas

Fecha local: 13/09/2026, America/New_York. El ledger del servidor usa 14/09 UTC.

## Punto de continuación verificado

- Worktree vigente: `/Users/robertograu/.codex/worktrees/roxy-home-renueva`.
- Rama local: `codex/roxy-home-renueva`; publicación: `origin/codex/roxy-home-nfc`.
- HEAD local/remoto: `190ead3a3bef890ba1d62ca44763df1e2c404f2a`.
- Público: https://roxy-home.onrender.com/lista#recetas, versión 199.
- `/health` HTTP 200/ok; HTML público idéntico byte a byte al archivo local.
- La tarea antigua «Roxy Home — Nexo clima 3D» y su checkout 106 no son la
  última implementación. El worktree temporal que mencionaba ya no existe.
- Nexo integrado es trabajo anterior conservado; no se reconstruyó ni publicó
  una versión vieja. Las notas de versiones 162–198 son evidencia histórica.

## Recuperación del proveedor

Roberto confirmó haber recargado saldo API. La consulta de sólo lectura en el
Web Shell del servicio exclusivo Home encontró **cero reservas pendientes**, tres
solicitudes, tres recibos y 2490 tokens de salida contabilizados. Dos recibos
previos de 1200 son provisiones conservadoras sin usage medido; el tercero
registra 893 tokens de entrada/90 de salida. Este bloque no liquidó, borró,
reinició ni incrementó límites. La resolución anterior ya estaba hecha al leer.

Prueba pública autenticada: Recetas → Bebidas → Café vietnamita con leche
condensada → Paso a paso con Roxy, paso 1 de 4. Gustos optativos desmarcados,
sin micrófono ni lectura hablada. Tres solicitudes nuevas, sin reintentos SDK:

1. «¿Qué significa phin en este paso?» recibió el aviso de validación de salida:
   «La explicación propone cambios o afirmaciones fuera de este acompañante».
   El texto crudo de esta primera respuesta no se capturó; no está demostrada
   la causa semántica exacta ni que fuera un falso positivo. Consumo registrado:
   893 entrada/107 salida. No fue un nuevo error de saldo.
2. Un diagnóstico acotado en un proceso separado del servidor usó la misma
   receta pública, identidad sintética de diagnóstico y ledger normal. Capturó
   una explicación del phin y ejecutó el validador original sin relajarlo.
   Respuesta válida, 893 entrada/91 salida. Ningún parche en el servicio vivo.
3. «¿Qué es el filtro phin que menciona este paso?» en la UI pública mostró
   una explicación real bajo «Explicación de Roxy · IA», referencias a pasos
   1 y 2 y el control Escuchar explicación. La guía conservó el paso 1 y el
   texto original. 897 entrada/89 salida. Captura del navegador inspeccionada.

Resultado del ledger: seis solicitudes/seis recibos, salida 2777, ninguna reserva
pendiente. Uso de este bloque: **2683 entrada + 287 salida = 2970 tokens**,
modelo `gpt-5.6-luna`. Estimación guardada de texto: USD 0.000881 por estas tres
solicitudes; no es factura ni incluye las dos provisiones previas desconocidas.
No cambios a claves, facturación, miembros, recetas, fotos, Compra o permisos.
Sólo el ledger de consumo se actualizó a través del flujo normal de IA.

## Continuidad y conservación

Se corrigió `next_step` que seguía describiendo 193 y la anotación de Turnstile
sin configurar, ya superada por la entrega de hoy. El texto anterior del paso
193 permanece en `handoff_20260913.historical_next_step_193`. La recuperación
por códigos se distingue de correo o recuperación retroactiva inexistentes.
Se agregó `tools/roxy_context_handoff.py`, propio de Home y de sólo consulta:
valida producto, informe, versión HTML/JS y concordancia del siguiente paso.
No importa herramientas/memoria Trading ni consulta claves o proveedores.

El respaldo previo conserva los tres documentos que ya estaban modificados y
un manifiesto SHA-256 de 4789 archivos, incluidos 3758 del prototipo:
`/var/folders/d9/j1tl468d4cd8y2zsrx53vj000000gn/T/roxy-home-handoff-20260913-lm0vsz7o`.
La comparación final sólo permite cambios de este bloque en los dos archivos de
continuidad existentes. El informe 199 anterior y todos los archivos del
prototipo permanecen byte a byte iguales al inicio. Ningún archivo previo borrado.

## Pruebas y alcance restante

- 256 pruebas Python de contabilidad, conversación/API, conservación de recetas,
  almacenamiento y temporizadores: aprobadas.
- 187 pruebas Node de guía y temporizadores: aprobadas.
- 6 pruebas nuevas del checker Home: aprobadas, incluyendo producto incorrecto,
  versiones divergentes, notas antiguas, informe ausente y JSON ilegible.
- `node --check assets/roxy_list.js`, `git diff --check` y checker Home: correctos.

Las pruebas automatizadas usan proveedores y datos sintéticos. La evidencia real
es la prueba pública detallada arriba; no certifica voz física ni toda la app.
Pendiente mejorar y evaluar rechazos de respuestas válidas/errores de explicación
sin debilitar el vínculo con la receta. El primer rechazo queda explícito, no
se presenta como solucionado por una segunda respuesta exitosa.
Siguen pendientes catálogo revisado en español, ejercicio completo y validación
de alta real; no se abrió el registro. No se hizo commit/push ni redeploy por
estas herramientas/notas locales. Home queda abierto con la respuesta comprobada;
la pestaña temporal de Render fue cerrada.
