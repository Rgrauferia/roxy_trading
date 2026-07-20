# Roxy Terminal Agent

Modulo local para que Roxy ejecute tareas de terminal dentro del proyecto con permisos amplios pero supervisados.

## Que puede hacer

- Leer archivos del proyecto.
- Editar archivos del proyecto mediante scripts auditables.
- Instalar paquetes npm permitidos.
- Correr build, lint y tests.
- Crear ramas y commits.
- Analizar errores de terminal.
- Crear scripts dentro del proyecto.
- Guardar logs y reportes por tarea.

## Bloqueos

- No lee `.env` ni `.env.*`.
- No muestra API keys, tokens ni secretos conocidos.
- Bloquea `sudo`, `rm -rf`, `find -delete`, `git reset --hard`, `git clean` y rutas fuera del proyecto.
- Bloquea `node -e` y `python -c`; si Roxy necesita editar, debe crear un script auditable.
- Detiene `git push` y deploy hasta recibir aprobacion explicita.
- Bloquea operaciones con dinero real.

## Uso desde terminal

```bash
node roxy-terminal-agent/command-runner.ts '{"objective":"Revisar estado","commands":["pwd","git status --short"]}'
```

## Uso desde codigo

```js
const { runTerminalTask } = require("./roxy-terminal-agent/command-runner.ts");

const result = runTerminalTask({
  objective: "Correr pruebas",
  commands: ["pytest"],
});

console.log(result.status);
```

## Acciones que requieren aprobacion

Para permitir push de forma explicita:

```js
runTerminalTask({
  objective: "Push confirmado por Roberto",
  commands: ["git push"],
  approvedActions: ["git-push"],
});
```

Para deploy confirmado:

```js
runTerminalTask({
  objective: "Deploy confirmado por Roberto",
  commands: ["npm run deploy"],
  approvedActions: ["deploy"],
});
```

## Logs

- Logs crudos: `roxy-terminal-agent/task-logs`
- Reportes JSON: `roxy-terminal-agent/reports`
