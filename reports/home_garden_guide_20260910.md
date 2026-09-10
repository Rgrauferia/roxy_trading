# Jardín: guía de bienvenida y revisión — 10 de septiembre de 2026

Estado: componente implementado y probado con perfiles sintéticos. Su conexión
al formulario público, las capturas en navegador y el despliegue corresponden al
trabajo de integración; no se afirman como terminados en este informe.

## Qué hace

- Cuatro pasos: identidad, lugar/luz, raíces/recipiente, ficha antes de guardar.
- Saludo con el nombre del miembro suministrado por el cliente autenticado;
  especie elegida del catálogo, no inferida por nombre o fotografía.
- Distingue tierra/sustrato, agua y dato desconocido; drenaje sí/no/por comprobar.
- Usa los textos de cuidado del catálogo/API. Una propuesta visual pendiente
  no se presenta como especie confirmada ni recibe indicaciones específicas.
- Conserva foto e historial en la edición. El alta exige una foto real del usuario.
- Recorrido escrito completo y lectura opcional mediante voz del dispositivo.
  No es la voz contratada de ElevenLabs, ni escucha el micrófono; no llama a IA.
- Revisión cotidiana con observación escrita y foto opcional. La persona elige
  si solo revisó o también regó; la palabra “regué” en una nota no decide la acción.
- Cancelar no guarda. Guardar fallido conserva la ficha; dobles pulsaciones y
  cierre durante una solicitud pendiente están bloqueados.

## Contrato para integración

Assets: `assets/roxy_garden_guide.js`, `assets/roxy_garden_guide.css`.

```js
RoxyGardenGuide.open({
  memberName,                  // Nombre visible del miembro, no inventado.
  species,                     // key, common_name, scientific_name + textos de cuidado.
  plant: existingPlantOrNull,   // Objeto público existente, conserva su identidad.
  readPhoto,                   // Opcional: compresión validada existente de Home.
  async onSave(payload, {plantId, editing}) { /* API Home autenticada */ },
  onClose(reason) { /* 'saved' o 'cancelled' */ }
});

RoxyGardenGuide.review({
  memberName, plant, readPhoto,
  async onSave({observation, result, photo_data_url}, {plantId}) {
    // result: CHECKED o WATERED. photo_data_url puede faltar.
    // Registrar journal y completar tarea son operaciones diferentes.
  },
  onClose(reason) {}
});
```

Ambas entradas devuelven `{close(), isSaving()}`. `onSave` debe lanzar un error
si no puede confirmar el resultado. No abrir otra guía mientras se guarda.
El componente no accede a la API, al calendario, a compras, a almacenamiento
local ni a credenciales. Una solicitud ya aceptada de journal seguida de un fallo
al completar tarea no debe repetirse automáticamente en la integración.

`HomePlantStore.add_journal` ya aceptaba notas sin foto; se añaden el rechazo de
una revisión completamente vacía y la comprobación de pertenencia/existencia
antes de escribir medios. Rechaza plantas archivadas. Se preserva validación de
medios cuando sí se suministran.

## Pruebas y límites

- 20 pruebas Node en `tests/test_roxy_home_garden_guide.cjs`: modelo, DOM sintético,
  datos no confiables como texto, selección explícita, voz por gesto, guardado
  fallido, doble toque, cancelación, preservación, tierra frente a agua.
- 19 pruebas Python en `tests/test_roxy_home_garden_journal.py`: texto sin foto,
  preservación del original, entrada vacía, medio inválido, aislamiento, archivado
  y resultado explícito sin tarea. `add_journal(..., result=None)` acepta únicamente
  `CHECKED`/`WATERED` cuando se proporciona. Los clientes antiguos que solo envían
  notas/foto no obtienen un resultado inferido. Cambiar el medio tierra/agua
  conserva resultado, fotografía principal y fotografía del registro.
- Suite previa de plantas: 21/21 aprobadas después de actualizar el harness del
  helper de clima. Junto con seis casos de mango/romero y los 19 del registro,
  son 46 pruebas Python de Jardín aprobadas.
- Sintaxis JS y `git diff --check` aprobados.

No se añadieron especies nuevas, diagnósticos, fertilizantes dosificados,
notificaciones automáticas ni sensores. Un mango fuera del catálogo permanece
por identificar; no se le aplica la ficha de Pothos. Falta ampliar y verificar
ese catálogo para dar cobertura específica más amplia. No se editaron plantas,
fotos, calendarios, compras ni otros datos de producción.
