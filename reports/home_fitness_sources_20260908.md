# Roxy Home · Ejercicio: fuentes y permisos

Comprobado el **8 de septiembre de 2026**. Investigación para la primera implementación; no constituye contrato, revisión médica, autorización de contenido ni despliegue. No se crearon cuentas, contrataron planes, enviaron formularios o mensajes, copiaron cuestionarios ni descargaron medios. Este bloque no modifica rutas, navegación ni datos personales.

## Qué podemos ofrecer ahora

Enlaces externos claramente identificados a CDC y CSEP, explicación del alcance de bienestar, preferencias voluntarias y una interfaz sin métricas ficticias. Ninguno de esos enlaces acredita un plan individual. Las fichas técnicas, cribado operativo y plantillas de entrenamiento necesitan su revisión y permisos propios. El registro `roxy_os/fitness/sources.py` no activa proveedores ni contiene ejercicios o preguntas clínicas.

## Verificación por fuente

### CDC: educación general, no dosis inicial automática

La página oficial distingue actividad aeróbica —150 minutos moderados semanales, 75 vigorosos o combinación equivalente— del fortalecimiento al menos dos días. También explica que puede repartirse la actividad y que algo es mejor que nada. La cifra semanal no debe transformarse en una sesión obligatoria inicial o en una prescripción para todas las personas. Fecha visible del artículo: 20/12/2023; comprobado vigente en la consulta actual. En esta fase enlazar al original inglés, sin reproducir fotos. [CDC, Adult Activity](https://www.cdc.gov/physical-activity-basics/guidelines/adults.html).

### CSEP: falta licencia de software

El Get Active Questionnaire es una parte del proceso preparticipación, no una certificación automática. La página ofrece documentos en inglés y francés y rutas separadas para embarazo/posparto. Los dos PDF enlazados llevan copyright **2017**; la carpeta URL de 2021 no acredita una edición clínica 2021. No se encontró versión española oficial en la lista consultada; no traducir ni inventar equivalencia. [CSEP, recurso](https://csep.ca/2021/01/20/pre-screening-for-physical-activity/), [cuestionario oficial](https://csep.ca/wp-content/uploads/2021/05/GETACTIVEQUESTIONNAIRE_ENG.pdf), [documento complementario](https://csep.ca/wp-content/uploads/2021/05/GAQREFDOC_ENG.pdf).

La política permite cierta distribución completa, sin modificaciones y con crédito, pero exige permiso escrito para publicaciones a la venta. **La reproducción dentro de software requiere aprobación, un CSEP Licensing Agreement y tasas.** Descargar gratis no habilita copiar sus preguntas en Roxy ni convertirlas en reglas. La traducción tampoco queda aprobada. Conservar solo enlace externo hasta autorización y revisión profesional; ninguna tasa se ha pagado. [Política de permisos CSEP, fecha visible 10/12/2025](https://csep.ca/contact-us/permissions/).

### wger: API pública real, cobertura desigual

Documentación consultada **2.7**: catálogo público sin autenticación; datos del usuario requieren autenticación. Dos GET anónimos, limitados y sin perfil real respondieron HTTP 200: [licencias, límite 20](https://wger.de/api/v2/license/?limit=20) y [una ficha de metadatos](https://wger.de/api/v2/exerciseinfo/?limit=1). No se hizo copia masiva. [Documentación oficial API](https://wger.readthedocs.io/en/latest/api/api.html).

La muestra observada ID 9 tenía nombre/instrucciones inglesas, autor y CC-BY-SA 4; **cero imágenes y cero videos**. La respuesta enumeraba 876 registros en ese instante, no 876 fichas revisadas o traducidas. El directorio devolvió CC-BY-SA 3, CC-BY 4, CC-BY-SA 4, CC0 y ODbL: no asumir una sola licencia por proveedor. Estos resultados son diagnóstico, no ejercicios publicados ni recomendados.

La documentación distingue software **AGPL 3+**, datos iniciales **CC-BY-SA 3.0** y recursos visuales con procedencia propia. Una integración debe registrar por separado ID/versión de ficha, traducción y medio, atribución, enlace y obligaciones de cada licencia. Una imagen ausente no se reemplaza por otra variante o por una imagen generada como demostración. Consultar revisión legal antes de autoalojar o combinar bases; no se ha hecho ninguna migración. [Licencias oficiales de wger](https://wger.readthedocs.io/en/latest/).

### MuscleWiki: candidato comercial, no conectado

La página mensual anuncia BASIC gratis (500 llamadas solo Playground), TESTING **US$10/mes**, 1.000 llamadas, inglés; GROWTH **US$39.99/mes**, 30.000 llamadas y español, sin endpoints de rutinas/workouts. Son precios publicados, no cotización ni presupuesto autorizado. No cuenta, clave o suscripción obtenida para Roxy en este bloque. [Planes oficiales](https://api.musclewiki.com/).

Términos fechados **12/08/2026**: uso del contenido dentro de la aplicación, sin redistribuirlo como API competidora; metadatos hasta 30 días, videos solo búfer transitorio, sin rehosting o almacenamiento permanente. Mantener su marca y el crédito legal requerido. Entrenar modelos necesita permiso escrito aparte. La licencia no garantiza exactitud ni idoneidad individual. [Condiciones oficiales](https://api.musclewiki.com/api-terms).

La FAQ precisa miniaturas solo en caché privada de cliente hasta 24 horas, bodymaps con `no-store`, y que cada solicitud de stream/rango consume cuota. Los términos agrupan imágenes con hasta 24 horas: la implementación propuesta aplicará la condición más restrictiva y los headers reales, no una caché compartida. La clave permanente seguirá en servidor; los tokens de medios son credenciales temporales que no deben registrarse. Roxy no ha llamado a endpoints de pago ni reproducido sus videos. [FAQ oficial](https://api.musclewiki.com/faq).

## Puertas antes de activar planes

1. Revisión profesional documentada de población, cribado propio/licenciado, contraindicaciones, plantillas y cambios de estado. Una fuente consultada no cambia `PROPOSED` a `CLINICALLY_APPROVED`.
2. Catálogo por variante exacta con derechos, contenido completo y aprobador; medios opcionales donde realmente existan. No completar huecos con IA.
3. Autorización individual y privacidad; datos del miembro no compartidos por pertenecer al mismo hogar. No exportar información de salud a enlaces comerciales.
4. Probar fallos, caché, baja/revocación, cuotas, unidades y duración antes de activar un proveedor. Sin fuente vigente o revisión requerida, ofrecer estado honesto y educación externa, no rutina sustituta inventada.

Continuidad inicial leída completa; check de handoff intentado y ausente en Home, como ya documentado. Se preserva `prototypes/` y no se toca Trading/Crypto.
