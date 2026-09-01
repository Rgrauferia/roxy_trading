# Auditoría UX · Mascotas

Fecha: 2026-09-01

## Evidencia revisada

- Capturas de producción aportadas por Roberto: mascotas anidadas en Recetas, navegación densa, páginas continuas extensas y aviso `HTTP 500` al registrar un cuidado.
- Referencia visual elegida por Roberto: perfil de mascota visible, categorías compactas, una recomendación principal y filas breves.
- Implementación móvil local: `reports/qa/roxy-pets-v125-mobile.png`.

## Hallazgos y resolución

1. **P1 · Mascotas no era un módulo reconocible.** Vivía dentro de Recetas y competía con las recetas familiares. Se resolvió con una entrada `Mascotas` propia junto a `Jardín`, una ruta `#mascotas` y Recetas nuevamente exclusiva para personas.
2. **P1 · Registrar un cuidado podía terminar mostrando `HTTP 500`.** La acción refrescaba toda la aplicación, por lo que un fallo no relacionado podía ocultar un registro correcto. Se aisló el refresco al estado de Mascotas; la prueba en navegador cambió el progreso de 0/4 a 1/4 sin error.
3. **P1 · El contenido crítico quedaba enterrado en páginas muy largas.** Se priorizó un único cuidado siguiente; la rutina completa y la guía personal quedaron bajo secciones desplegables.
4. **P2 · La jerarquía del perfil era débil.** Se añadió una identidad clara de la mascota, estado de completitud y acceso directo a edición.
5. **P2 · La navegación interna era pesada.** Se sustituyó por cinco categorías visuales y cortas: Hoy, Comida, Recetas/Guías, Salud y Productos.
6. **P2 · En móvil, la navegación podía quedar fuera de vista.** La barra inferior centra el módulo activo y las cinco categorías caben en una fila a 390 px.

## Validación

- Vista móvil explícita: 390 × 844.
- Cinco categorías abiertas y verificadas.
- Cambio Recetas → Mascotas verificado; el contexto de mascota no aparece en Recetas familiares.
- Consola: sin errores ni advertencias.
- Acción `Registrar`: progreso actualizado sin `HTTP 500`.

