# Mascotas: auditoría y mejora por especie

Fecha: 2026-09-05. Exclusivamente Roxy Home. Candidata 163.

## Evidencia y cambios

Auditoría visual de producción antes de editar: Bella y Luna presentes; recetas de Bella incluían conservación, peso e hidratación; productos repetían familias genéricas junto a variantes concretas; algunas imágenes oficiales estaban pendientes. Historial sin entradas no demostraba vacunación al día.

Capturas exactas locales: /tmp/roxy-pet-audit-20260905/recipes-before.jpg, history-before.jpg, products-before.jpg y ferret-recipes-after.jpg. Se inspeccionó interfaz y DOM, no solo las capturas.

- Recetas: ya no incluye feeding_guide. Los protocolos se muestran en Información.
- Cuestionario de hábitat: 14 grupos registrables, campos propios para agua, terrario y aves. Sin mediciones inventadas ni conexión ficticia a sensores. Valida unidades, cero, NaN, infinitos y campos de otra especie.
- Betta: volumen, ciclado, filtro, mediciones y compañeros; avisos ante amoniaco/nitrito y volumen menor que el objetivo. No se certifica convivencia ni se calcula capacidad universal por litro.
- Aves: canarios y psitácidas separados de nectarívoros, minas y especies sin cobertura revisada. Las crías no heredan recetas adultas. No se dan pellets de otro loro a un lori.
- Reptiles: observaciones de gradiente, humedad, termostato y UVB. Referencias específicas de gecko leopardo; no copiadas a otras especies.
- Historial: no descarta silenciosamente la entrada 101; conserva hasta 1000 y luego pide resolver capacidad. Próximas fechas registradas, exportaciones existentes y directorios externos.
- Importación: texto, captura o URL; enlazada por ID a una mascota del hogar. Perfil de salud sanitizado para Responses API, razonamiento Terra en pet imports, sin fotos médicas ni contexto privado humano. Revisión y confirmación antes de guardar; compra requiere acción aparte. No se lee contenido privado de Instagram ni se inventa un video inaccesible.
- Puertas deterministas: sin dietas completas, crías, especie sin cobertura, condiciones o instrucciones veterinarias. Ingredientes nuevos/sin equivalencia revisada se rechazan. Esto no es validación veterinaria ni evaluación completa de todas las cantidades o preparaciones posibles.
- Fotos: ferret tiene 8 recetas con 8 imágenes individuales existentes/generadas, no collages. Cuatro nuevas imágenes, prompts en home_pet_artwork_20260905.md. Las ilustraciones no indican porciones.
- Productos: se eliminan familias duplicadas cuando hay variante concreta, se filtra freshwater ante agua marina/salobre y se evita transferir productos terrestres a camarones. No hay garantía de alérgenos sin etiqueta completa.
- Se distingue carga/fallo de carga de hogar vacío.

## Pruebas

335 pruebas aprobadas: 282 Home y 53 de lista de compras; node --check JS y SW aprobados. Pruebas cubren propiedad del hogar, separación de perfiles, persistencia, médico >100, importación sin datos humanos, restricciones y archivos de imagen.

La prueba real de añadir Marshall High Back Litter Pan reveló que “Pan” lo clasificaba como panadería pese a category=PETS. Se corrigió en servidor y frontend; el segundo intento y la vista Compra confirmaron Mascotas. No se compró nada ni se añadió a la lista de producción.

Interacción local con seis perfiles sintéticos: periquito, canario, lori, betta, gecko y ferret. Aves guardó vuelo/destete; betta guardó agua y mostró alertas; gecko guardó temperaturas/termostato. Datos conservados al reiniciar servidor. Ferret muestra 8 recetas completas. Lori no recibe recetas de psitácidas. Ningún perfil sintético se añadió a producción.

Historial: se guardó vacuna ficticia con próximo control y se descargó el TXT real. Se verificó su contenido en el archivo descargado; el evento download del navegador agotó tiempo aunque la descarga sí se completó. Archivo de evidencia movido fuera de Descargas al directorio temporal de auditoría. Captura móvil history-after.jpg sin desbordamiento.

## Fuentes de cuidado consultadas

- [RSPCA Australia: betta](https://kb.rspca.org.au/categories/companion-animals/fish/how-should-i-care-for-my-siamese-fighting-fish): referencia de espacio y convivencia.
- [RSPCA: peces](https://www.rspca.org.uk/adviceandwelfare/pets/fish/environment): dimensiones, crecimiento y referencia para goldfish.
- [RSPCA: gecko leopardo](https://www.rspca.org.uk/adviceandwelfare/pets/other/leopardgecko): entorno y diferencias juvenil/adulto.
- [RSPCA: entorno de aves](https://www.rspca.org.uk/adviceandwelfare/pets/birds/environment), [dieta](https://www.rspca.org.uk/adviceandwelfare/pets/birds/diet).
- [VCA: canarios](https://vcahospitals.com/know-your-pet/canaries-feeding), [loris](https://vcahospitals.com/central-park/know-your-pet/lories-and-lorikeets-feeding).
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs): documentación revisada; sigue el normalizador/validación existente, no afirmar un nuevo schema estricto implementado.

## Afiliaciones y servicios: situación honesta

[Petco](https://www.petco.com/affiliate) ofrece solicitud gratuita mediante Impact y enlaces de seguimiento. Su página principal de afiliados se prefiere a FAQ históricos que mencionan CJ. No se ha enviado solicitud ni aceptado contrato. El acceso a feed/API, imágenes autorizadas y condiciones de almacenamiento debe confirmarse tras aprobación.

[PetSmart Creators](https://www.petsmartcreators.com/) publica un programa para creadores sujeto a acuerdo y divulgación de la relación comercial. No constituye evidencia de una API pública de catálogo ni de aprobación de Roxy. FAQ de 2020 no se usa para afirmar el estado actual.

[AAV](https://www.aav.org/default.aspx), [ARAV](https://arav.org/) y [AAHA](https://www.aaha.org/for-pet-parents/) permiten buscar recursos/atención; son directorios independientes, no afiliación, reserva ni telemedicina integradas.

Siguiente paso comercial requiere Roberto: revisar identidad del solicitante y condiciones, confirmar envío y aceptar personalmente acuerdos aplicables. No se compartieron historiales, perfiles ni claves.

## Pendientes — no declarar cobertura universal ni módulo terminado

- Recuperar foto/perfil original de Luna; no sobrescribir a Bella/Luna con datos de prueba.
- Completar/inspeccionar imágenes de Bella y demás especies y fotografías oficiales de productos; cifras antiguas 125/683 faltantes no son métricas actuales.
- Aumentar catálogo revisado por especie; registrar cualquier animal no significa que tenga recetas/productos validados. Los alimentos caseros no son adecuados para todas las especies.
- Diseñar acuario como unidad compartida con lista estructurada de habitantes y revisión de compatibilidad; no hay matriz universal ni dimensionado automático fiable todavía.
- Más especies exactas de aves, reptiles, anfibios/invertebrados y mamíferos requieren fuentes/revisión antes de nuevos rangos.
- Verificación veterinaria del contenido y cantidades antes de afirmar seguridad clínica; no basta un filtro de nombres.
- La importación necesita disponibilidad y presupuesto de OpenAI; tests con cliente falso no equivalen a comprobar todos los enlaces de Instagram.
- Aprobar afiliaciones/feeds y atender aviso de pago fallido de Render. Nada contratado en este bloque.
