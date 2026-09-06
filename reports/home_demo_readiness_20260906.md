# Roxy Home — preparación de demo, 6 de septiembre de 2026

## Estado

Registro abierto a cualquiera aprobado por Roberto durante esta sesión; cada
participante debe tener un hogar privado y 5 días de prueba. La demo todavía no
se abrió. No se cambiaron pagos, claves, acuerdos ni otros productos Roxy.

## Bloque 166 implementado

- Capacidades por perfil: pestaña Recetas/importación solo cuando existe una
  preparación compatible; no se mezclan protocolos de cuidado con platos.
- “Ferret” es el nombre visible; se conservan identidad, títulos internos para
  resolver imágenes, archivos, fotos, ID y datos médicos existentes.
- Acuario: población estructurada por especie, cantidad, sexo y tamaño adulto;
  revisión de discrepancias, dos machos betta y mezcla betta/goldfish. No hay
  certificado automático de compatibilidad ni regla universal de litros por pez.
- Pitón bola: información específica con fuente RSPCA; frecuencia orientativa por
  etapa, sin recetas caseras ni programación automática de alimentación diaria.
- La orientación general no se etiqueta como ficha exacta. Las fichas conocidas
  se restringen a su especie (un perro no hereda información de Maine Coon).
- Error reproducido en navegador: dejar `residents` vacío guardaba `null` y
  provocaba HTTP 500 al recargar el acuario. Corregido y cubierto por pruebas.
- Recetas humanas: las 463 propuestas pendientes se separan del recetario de
  entrada. No se borraron ni se marcaron como revisadas. Conservan bloqueo de
  cocina y Compra hasta revisión.
- Recetas, sesiones de cocina y semanas no se eliminan silenciosamente al pasar
  100/100/20. Límites explícitos 1000/2000/260, sin expulsar registros anteriores.
- Nexo: códigos WMO 80–82 son lluvia, no nieve; radar con 13 fotogramas, validación
  de origen/fechas y timeout. Tráfico Google opcional, según cobertura.
- GPS: solicitud fresca de alta precisión, margen visible y círculo de precisión;
  no declara entrada/salida si el margen cruza el límite. No sustituye la posición
  actual por una muestra anterior. Sin activar permisos de ningún usuario.

## Evidencia local

- `tests/test_roxy_home_demo_readiness.py`: matriz de todas las opciones de especie,
  identidad, restricciones médicas, acuario, campos vacíos, conservación de datos,
  precisión y orden temporal del GPS, lluvia/nieve y fotogramas.
- Suite Home + compras: 502 pruebas aprobadas; JS/SW pasan `node --check`.
- Navegador: 17 perfiles sintéticos, separados de producción, recorriendo Productos
  y presencia de Recetas. Acuario guardado y recuperado tras recarga, advertencia
  de dos machos betta visible, feedback de guardado sin HTTP 500.
- Catálogos observados (no certificación clínica): perro 10, gato 9, Ferret 8,
  betta 8, gecko 8, pitón 7, periquito 7, canario 7, lori 1, conejo 8, cobaya 7,
  hámster 7, chinchilla 8, ajolote 6, tarántula 8, cerdo miniatura 7, desconocida 0.
- Evidencia visual: `/tmp/roxy-demo-proof.rF8h6c/01-snake.png`.

## Aún impide considerar completa la demo

1. Registro público, aislamiento, vencimiento y límites antifraude/consumo deben
   implementarse y comprobarse antes de activarlo. No compartir la clave de Home.
2. ElevenLabs devolvió `payment_issue`; requiere que Roberto resuelva facturación.
3. 463 recetas humanas pendientes; fotos restantes y correspondencia plato-foto
   requieren revisión. La cuarentena de Aderezo César se mantiene.
4. Cobertura exacta de todas las especies y variedad de productos con fotos no
   completas. El lori ilustra un hueco real; no sustituir por dieta de otras aves.
5. Falta completar comprobaciones de integraciones/calendario/Renueva/Jardín.

## Colaboraciones: fuentes oficiales comprobadas, no acuerdos cerrados

- [Petco afiliados](https://www.petco.com/affiliate): solicitud mediante Impact.
  Es afiliación por referencias, no prueba de acceso aprobado a catálogo/API.
- [PetSmart Creators](https://www.petsmartcreators.com/): programa de creadores con
  aceptación de condiciones y divulgación. No se envió solicitud ni se aceptó contrato.
- [AAV Find-a-Vet](https://www.aav.org/general/custom.asp?page=FindAVet2): enlace
  directo desde Historial para aves; no transmite el expediente automáticamente.
- [ARAV](https://arav.org/): recursos para veterinarios de reptiles/anfibios; no
  relación comercial ni citas integradas confirmadas.
- [RSPCA peces](https://www.rspca.org.uk/en/adviceandwelfare/pets/fish/company) y
  [RSPCA Victoria](https://rspcavic.org/learn/fish): convivencia y requisitos de agua.
- [RSPCA pitón bola](https://www.rspca.org.uk/adviceandwelfare/pets/other/royalpython),
  ficha vinculada desde el perfil; [VCA serpientes](https://vcahospitals.com/know-your-pet/snakes-feeding).
- [Google TrafficLayer](https://developers.google.com/maps/documentation/javascript/trafficlayer):
  cobertura regional y refresco periódico, no instantáneo.
- [RainViewer](https://www.rainviewer.com/api/weather-maps-api.html): observaciones
  de las últimas dos horas; no pronóstico de nubes ni radar fabricado.
