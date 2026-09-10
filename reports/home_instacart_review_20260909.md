# Instacart en Roxy Home — revisión de integración y comisiones

Investigación inicial: 9 de septiembre de 2026. Validación e implementación local:
10 de septiembre de 2026. La investigación inicial fue de solo lectura;
no se accedió a una cuenta autenticada de Instacart/Impact, no se inspeccionaron
valores de secretos, no se enviaron solicitudes ni se aceptaron contratos/pagos.
No confirma acceso, aprobación o ingresos de Roxy.

## Correcciones locales verificadas — 10 de septiembre

`roxy_os/home_commerce.py` ahora aplica orgánico, etiquetas dietéticas, marcas
alimentarias y revisión de alergias humanas únicamente a categorías de alimentos
humanos conocidas. PETS, limpieza y artículos no clasificados conservan su nombre
y no reciben esas preferencias; el alcance declara que sus alergias no se han
evaluado. También limpia preferencias humanas en preparaciones históricas al crear
enlaces, sin reescribir los datos guardados. Se conserva la búsqueda específica de
Renueva cuando no procede de preferencias alimentarias.

El adaptador Instacart traduce unidades españolas inequívocas a valores oficiales,
conserva la cantidad y mantiene la unidad original en el texto visible y en la
lista local. Mantiene unidades oficiales compuestas/de tamaño ya admitidas. Bolsas,
botellas y medidas sin equivalencia comprobada requieren revisión antes de llamar
al proveedor; cantidades nulas, negativas, booleanas o no finitas también se
rechazan. No infiere peso ni tamaño del envase. Se revalidaron la tabla oficial de
unidades y el contrato de listas el 10 de septiembre de 2026.
[Unidades oficiales](https://docs.instacart.com/developer_platform_api/api/units_of_measurement)
[Contrato de listas](https://docs.instacart.com/developer_platform_api/api/products/create_shopping_list_page)

Prueba local completa con intérprete `/Users/robertograu/roxy_trading/.venv/bin/python`
(solo runtime, ejecutada en Home):
`-m pytest -q tests/test_roxy_home_commerce.py` → **87 aprobadas**. Incluye 46 casos
nuevos de aislamiento, preparación histórica, compatibilidad Amazon, unidades y
payload Instacart, cantidades inválidas y ruta HTTP. La ruta exige confirmación;
una unidad ambigua devuelve 422 sin llamada externa ni entrega comercial registrada.
Todas las respuestas del proveedor en estas pruebas son dobles sintéticos; no se
realizaron llamadas comerciales, compras, cambios de cuentas ni de facturación.
No se modificaron JS principal, rutas o continuidad desde este bloque delegado.
La publicación y verificación pública corresponden al bloque coordinador; esta
sección solo acredita implementación y comprobación local.

## Decisión

Instacart Developer Platform (IDP) encaja primero en **Compra** y en el botón
de ingredientes de **Recetas humanas verificadas**. La API crea una página
comprable a partir de contenido que Roxy aporta; no es un catálogo de recetas
oficiales ni valida una preparación. Conectar IDP no resuelve las recetas
pendientes ni permite presentarlas como recetas de Instacart.
[Introducción oficial](https://docs.instacart.com/developer_platform_api/)

IDP admite además listas de limpieza, mascotas, cuidado personal y celebraciones.
Para Roxy, la ampliación útil sería reposición de productos del hogar en Compra
y productos específicos de cada mascota en Mascotas → Productos → Compra;
no trasladar una dieta humana a mascotas. En Ejercicio, enlazar al plan de comida
existente con confirmación individual, sin enviar el perfil de salud ni convertir
suplementos en requisito de entrenamiento. Estas ubicaciones son propuestas de
producto, no capacidades ya comprobadas en producción.
[Usos oficiales de listas](https://docs.instacart.com/developer_platform_api/guide/concepts/shopping_list)

## Cómo se obtienen comisiones realmente

El flujo oficial es integración de desarrollo, demostración, aprobación de clave
de producción y, opcionalmente, invitación a afiliación Impact. La afiliación
y sus condiciones se envían a participantes activos. Impact atribuye pedidos
y gestiona comisiones; una clave de API o una cuenta Impact por sí solas no
demuestran un acuerdo afiliado de Roxy.
[Actividades de lanzamiento](https://docs.instacart.com/developer_platform_api/guide/concepts/launch_activities/overview)
[Atribución y pagos](https://docs.instacart.com/developer_platform_api/guide/concepts/launch_activities/conversions_and_payments/)

No se verificó una tarifa de comisión, ventana de atribución ni precio de API
contratado para Roxy. No prometer porcentaje, ingreso mensual o gratuidad
permanente: las condiciones prevén cambios de límites y posibles cargos.
Tras configurar el ID de Impact, Instacart pide esperar 24–48 horas y verificar
los parámetros devueltos; estos se añaden automáticamente, no se deben duplicar
manualmente. Confirmar conversiones reales/canceladas, no contar clics como ventas.
[Atribución](https://docs.instacart.com/developer_platform_api/guide/concepts/launch_activities/conversions_and_payments/)
[Condiciones §4.2](https://docs.instacart.com/developer_platform_api/guide/terms_and_policies/developer_terms)

La documentación orienta a 30–40 días de media desde solicitud hasta acceso de
producción, no una garantía. Para la meta del próximo mes, no hacer depender
el lanzamiento de que Instacart apruebe a tiempo.
[Inicio oficial](https://docs.instacart.com/developer_platform_api/get_started/overview)

## Lo que ya existe en el código

- `roxy_os/home_commerce.py`: crea enlaces mediante `products/products_link`,
  usando correctamente `line_item_measurements`; conserva la URL recibida sin
  añadir parámetros de afiliación. Tiene fallback de enlace afiliado configurado.
- `roxy_os/home_price_recommendations.py`: consulta comercios cercanos por código
  postal, con caché de una hora. Solo devuelve identidad/logotipo y señala que el
  precio se confirma en Instacart. La consulta actualmente fija `country_code=US`.
- `tools/roxy_home_service.py`: prepara lista/ingredientes bajo autenticación;
  exige `confirmed:true` antes de crear el enlace. Registra entregas al comercio,
  no compras confirmadas. Renueva tiene un filtro separado de proveedores.
- Nombres de configuración: `ROXY_HOME_INSTACART_API_KEY`,
  `ROXY_HOME_INSTACART_API_URL`, `ROXY_HOME_INSTACART_RETAILERS_URL`,
  `ROXY_HOME_INSTACART_AFFILIATE_URL`, `ROXY_HOME_INSTACART_AFFILIATE_STATUS`.
  La presencia de nombres en código NO acredita configuración pública.
- Pruebas locales del diagnóstico inicial (antes de la corrección): `pytest -q tests/test_roxy_home_commerce.py -k instacart`
  → **2 aprobadas**, 39 no seleccionadas. Son pruebas con dobles, no una compra
  ni una llamada autorizada a la cuenta de producción.

## Hallazgos iniciales y mejoras antes de activar

1. **Separar preferencias alimentarias por destino — corregido localmente.** Antes, `personalize_items` añadía
   etiquetas dietéticas humanas a cualquier categoría. Reproducción sintética:
   un producto PETS «Alimento para ferret» se convierte en consulta
   «orgánico Alimento para ferret vegano». Ocurría también con detergente. Debe
   conservarse el producto específico de la mascota y no heredar la dieta humana.
   Esta reproducción no escribió datos ni llamó a proveedores.
2. **Normalizar unidades antes de enviar — corregido localmente.** El adaptador transmitía `unidad`,
   `bolsa`, `litro`, etc., sin traducción/validación. Instacart documenta `each`,
   `package`, `liter`, `gram`, etc. Mapear equivalencias inequívocas, conservar
   cantidades y pedir revisión cuando el envase sea ambiguo; no inventar gramos.
   [Unidades admitidas](https://docs.instacart.com/developer_platform_api/api/units_of_measurement)
3. **Estado honesto.** `public_providers()` llama «Listo / conexión activa» a
   cualquier clave configurada. Separar configuración, respuesta probada,
   producción aprobada, afiliación aprobada y atribución comprobada.
4. **Productos exactos y sustituciones.** La API de listas admite UPC y lo
   prioriza. Añadir UPC solo desde una ficha confirmada; no inventar SKU/UPC.
   Los filtros de marca no garantizan una fórmula exacta: si hay restricciones,
   el usuario debe revisar el producto final y sus alternativas en Instacart.
   [Contrato de listas](https://docs.instacart.com/developer_platform_api/api/products/create_shopping_list_page)
   [Límites de correspondencia](https://docs.instacart.com/developer_platform_api/faq)
5. **Reutilizar enlaces.** Cachear por contenido confirmado y caducidad, creando
   otro enlace solo cuando cambie la lista. Hoy cada checkout vuelve a llamar al
   proveedor. Añadir país explícito y pruebas US/CA; no asumir cobertura mundial.
   La búsqueda de comercios admite US/CA y no devuelve precios de productos.
   [Listas](https://docs.instacart.com/developer_platform_api/api/products/create_shopping_list_page)
   [Comercios cercanos](https://docs.instacart.com/developer_platform_api/api/retailers/get_nearby_retailers)
6. **No usar IDP para el comparador multitienda.** Las condiciones §3.4(k–l)
   restringen mostrar artículos con precio de varios comercios en una misma
   pantalla y mover/comparar cestas. El comparador de Roxy requiere otra fuente
   autorizada o permiso escrito específico; no extraer precios por scraping.
   [Condiciones de acceso](https://docs.instacart.com/developer_platform_api/guide/terms_and_policies/developer_terms)
7. **Preparar una demostración conforme.** Debe mostrar recorrido, botón de
   Instacart y página resultante con correspondencia de ingredientes. Revisar
   texto/dimensiones/logo de CTA y traducción autorizada al español; no anunciar
   alianza, entrega gratuita ni tiempo garantizado. La lista de revisión de junio
   de 2026 es más reciente que menciones históricas a Tastemakers en otras páginas.
   [Checklist actual](https://docs.instacart.com/developer_platform_api/guide/concepts/launch_activities/pre-launch_checklist)
   [Aprobación](https://docs.instacart.com/developer_platform_api/guide/concepts/launch_activities/approval_process)

## Próximo paso ejecutable

Aislamiento, unidades y payload están corregidos y probados localmente. Queda
separar los estados de configuración/verificación/aprobación, después revisar
la cuenta IDP del usuario sin revelar claves. Si no
existe acceso, preparar la solicitud y demo; cualquier envío, acuerdo o cargo
requiere autorización correspondiente. Sin producción aprobada, conservar la
lista interna y mostrar claramente la conexión pendiente. Los enlaces comerciales
deben llevar divulgación de comisión sin exportar nombres, diagnósticos, peso,
objetivos clínicos ni datos de wearables en títulos o parámetros.

Preflight de la investigación inicial leído; `git status` inicial solo `?? prototypes/`, preservado.
El helper `tools/roxy_context_handoff.py --check` no existe en este worktree y
falló por archivo ausente, limitación ya documentada y revalidada el 10 de septiembre.
En el bloque inicial solo se añadió este informe. En la continuación se preservaron
los cambios compartidos existentes y se actualizaron comercio, sus regresiones y
este informe; el coordinador administra los registros de continuidad.
