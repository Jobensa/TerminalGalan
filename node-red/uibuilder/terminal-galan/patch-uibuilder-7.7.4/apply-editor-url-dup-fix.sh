#!/usr/bin/env bash
#
# Parche uibuilder 7.7.4 — validación de URL del editor (falso duplicado).
#
# Problema: al pulsar Deploy, el editor muestra
#   "El espacio de trabajo contiene algunos nodos que no están configurados
#    correctamente: [...] (uibuilder) ¿Estás seguro de que quieres instanciar?"
# cuando el **id del nodo** contiene uno o más guiones (p. ej.
# `uib-terminal-galan-v2`), aunque su URL (`terminal-galan`) sea única.
#
# Causa: en `validateUrl()` de `resources/uibuilder.js`, uibuilder traduce los
# ids de nodos dentro de subflows con `fId.split('-')[1]` (Node-RED mangla esos
# ids como `<subflowInstanceId>-<nodeId>`). Ese split se aplicaba también a
# nodos normales cuyo id lleva guiones, truncando `uib-terminal-galan-v2` a
# `terminal`; la comparación con `this.id` fallaba y el nodo quedaba inválido.
#
# Solución: aplicar el split de subflow solo cuando el id mapeado NO es ya el
# id del propio nodo (`fId !== this.id`).
#
# Uso (desde cualquier directorio):
#   ./node-red/uibuilder/terminal-galan/patch-uibuilder-7.7.4/apply-editor-url-dup-fix.sh
#   docker compose -f docker2/compose.yaml restart node-red   # opcional
#   y recargar el editor con Ctrl+F5
#
# Este parche también está aplicado ya en el bind mount, pero se pierde si se
# reinstala/actualiza `node-red-contrib-uibuilder` (node_modules está en .gitignore).

set -euo pipefail

# Directorio real del script, para localizar el paquete aunque se llame desde otro cwd.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# .../docker2/node-red/uibuilder/terminal-galan/patch-uibuilder-7.7.4 -> docker2/
REPO_DIR="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"
UIB_JS="${REPO_DIR}/node-red/node_modules/node-red-contrib-uibuilder/resources/uibuilder.js"

if [[ ! -f "${UIB_JS}" ]]; then
    echo "ERROR: no se encontró ${UIB_JS}" >&2
    echo "       (¿está node-red-contrib-uibuilder instalado en node-red/node_modules?)" >&2
    exit 1
fi

# Detección idempotente: si ya está aplicado, no hacer nada.
if grep -q "fId !== this.id && fId.indexOf('-')" "${UIB_JS}"; then
    echo "OK: el parche ya estaba aplicado en ${UIB_JS}"
    exit 0
fi

# Debe haber exactamente 2 ocurrencias sin parchear (deployedUibInstances + editorInstances).
count="$(grep -c "if ( fId.indexOf('-') !== -1 ) {" "${UIB_JS}" || true)"
if [[ "${count}" -ne 2 ]]; then
    echo "ERROR: se esperaban 2 ocurrencias del patrón original, encontradas: ${count}" >&2
    echo "       ¿Versión de uibuilder distinta a 7.7.4? Revisar a mano." >&2
    exit 1
fi

backup="${UIB_JS}.bak-$(date +%Y%m%d_%H%M%S)"
cp "${UIB_JS}" "${backup}"
echo "Backup: ${backup}"

# Aplica el guard fId !== this.id en ambas comprobaciones (deployed y editor).
perl -i -pe "s/if \( fId\.indexOf\('-'\) !== -1 \) \{/if ( fId !== this.id \&\& fId.indexOf('-') !== -1 ) {/g" "${UIB_JS}"

if grep -q "fId !== this.id && fId.indexOf('-')" "${UIB_JS}"; then
    echo "OK: parche aplicado en ${UIB_JS}"
    echo
    echo "Siguiente paso: recargar el editor de Node-RED con Ctrl+F5 (o 'docker compose restart node-red')."
else
    echo "ERROR: el parche no se aplicó correctamente." >&2
    exit 1
fi
