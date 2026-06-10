#!/bin/zsh
set -euo pipefail

SRC="${HOME}/Parallels"
EXT_ROOT="/Volumes/RoxyData"
DST_PARENT="${EXT_ROOT}/MacArchive/robertograu"
DST="${DST_PARENT}/Parallels"
LOG_DIR="${EXT_ROOT}/MacArchive/migration_logs"
LOCK_DIR="/tmp/roxy_parallels_migration.lock"
INTERVAL_SECONDS="${ROXY_PARALLELS_MIGRATION_INTERVAL_SECONDS:-60}"

log() {
  printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"
}

parallels_running() {
  if command -v prlctl >/dev/null 2>&1; then
    if prlctl list -a -o status 2>/dev/null | awk '
      NR == 1 { next }
      $1 != "stopped" && $1 != "suspended" { busy = 1 }
      END { exit busy ? 0 : 1 }
    '; then
      return 0
    fi
  fi

  pgrep -fl 'prl_client_app|Parallels Desktop.app/Contents/MacOS/Parallels Desktop' >/dev/null 2>&1
}

if ! mkdir "${LOCK_DIR}" 2>/dev/null; then
  log "Otra migracion de Parallels ya esta en ejecucion."
  exit 0
fi
trap 'rmdir "${LOCK_DIR}" 2>/dev/null || true' EXIT

mkdir -p "${LOG_DIR}" "${DST_PARENT}"

exec >>"${LOG_DIR}/parallels_migration.log" 2>&1

log "Iniciando migrador de Parallels hacia ${DST}"

if [[ -L "${SRC}" ]]; then
  log "${SRC} ya es un enlace. No hay nada que migrar."
  exit 0
fi

if [[ ! -d "${SRC}" ]]; then
  log "${SRC} no existe como carpeta. No hay nada que migrar."
  exit 0
fi

while [[ ! -d "${EXT_ROOT}" ]]; do
  log "Esperando a que ${EXT_ROOT} este montado..."
  sleep "${INTERVAL_SECONDS}"
done

while parallels_running; do
  log "Parallels sigue corriendo. Esperando ${INTERVAL_SECONDS}s antes de reintentar."
  sleep "${INTERVAL_SECONDS}"
done

if [[ -e "${DST}" && ! -d "${DST}" ]]; then
  log "Destino ${DST} existe pero no es carpeta. Abortando."
  exit 2
fi

if [[ -d "${DST}" && -n "$(find "${DST}" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
  log "Destino ${DST} ya contiene archivos. Abortando para no sobrescribir datos."
  exit 2
fi

TMP_DST="${DST}.tmp.$$"
LOCAL_BACKUP="${SRC}.local-before-roxydata-$(date '+%Y%m%d%H%M%S')"

log "Copiando ${SRC} a ${TMP_DST} con ditto."
rm -rf "${TMP_DST}"
ditto --rsrc --extattr "${SRC}" "${TMP_DST}"
mv "${TMP_DST}" "${DST}"

SRC_KB="$(du -sk "${SRC}" | awk '{print $1}')"
DST_KB="$(du -sk "${DST}" | awk '{print $1}')"
log "Validacion de tamano: origen=${SRC_KB}KB destino=${DST_KB}KB"

if (( DST_KB < SRC_KB * 95 / 100 )); then
  log "El destino parece incompleto. Abortando sin tocar el origen local."
  exit 3
fi

touch "${DST}/.migrated_from_${USER}_$(date '+%Y%m%d%H%M%S')"

log "Moviendo origen local a respaldo temporal ${LOCAL_BACKUP}."
mv "${SRC}" "${LOCAL_BACKUP}"
ln -s "${DST}" "${SRC}"

if [[ ! -L "${SRC}" || ! -d "${SRC}/Windows 11.pvm" ]]; then
  log "El enlace final no valida. Restaurando origen local."
  rm -f "${SRC}"
  mv "${LOCAL_BACKUP}" "${SRC}"
  exit 4
fi

log "Enlace final creado en ${SRC}. Eliminando respaldo local para liberar espacio."
rm -rf "${LOCAL_BACKUP}"

log "Migracion de Parallels completada."
