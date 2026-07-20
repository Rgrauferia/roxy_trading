# Roxy Knowledge Autopilot

Roxy tiene una rutina autonoma para mantenerse actualizada sin supervision manual.

## Que hace

- Actualiza fuentes publicas permitidas.
- Actualiza datos macro publicos desde FRED.
- Regenera notas internas propias de Roxy.
- Procesa cualquier `.txt`, `.md` o `.pdf` legal que exista en `knowledge/inbox`.
- Reindexa fragmentos en `knowledge/processed`.
- Guarda estado y logs auditables.

## Frecuencia

El LaunchAgent `com.roxy.knowledge-autopilot` corre cada 6 horas y tambien al cargar la sesion.

## Seguridad legal

El autopiloto no descarga libros comerciales, cursos privados, paywalls ni fuentes sin permiso.
Los cursos, libros o PDFs comprados deben colocarse manualmente en `knowledge/inbox` para que Roxy los procese en el siguiente ciclo.

## Comandos

Ejecutar ahora:

```bash
node scripts/updateKnowledge.ts
```

Ver estado:

```bash
node scripts/knowledgeStatus.ts
```

Ver logs:

```bash
ls -lt knowledge/logs
cat knowledge/sources/autonomous-update-status.json
```

Detener el autopiloto:

```bash
launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.roxy.knowledge-autopilot.plist"
```

Volver a activarlo:

```bash
launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/com.roxy.knowledge-autopilot.plist"
launchctl enable "gui/$(id -u)/com.roxy.knowledge-autopilot"
```
