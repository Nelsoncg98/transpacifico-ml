#!/usr/bin/env bash
# Render Linux: preparar Graphviz para dibujar los árboles de XGBoost.
set -eu

# 1. Reutilizar dot si ya está instalado. En caso contrario, descargarlo aparte.
if ! command -v dot >/dev/null 2>&1; then
  carpeta_graphviz="$PWD/.graphviz"
  mkdir -p "$carpeta_graphviz/listas/partial" "$carpeta_graphviz/cache/archives/partial"
  opciones_apt=(
    -o "APT::Sandbox::User=$(id -un)"
    -o "Dir::State::lists=$carpeta_graphviz/listas"
    -o "Dir::Cache=$carpeta_graphviz/cache"
    -o "Debug::NoLocking=1"
  )
  # Descargar desde los repositorios oficiales del servidor, sin instalar en el sistema.
  apt-get "${opciones_apt[@]}" update
  apt-get "${opciones_apt[@]}" --download-only --no-install-recommends -y install graphviz
  for paquete in "$carpeta_graphviz/cache/archives/"*.deb; do
    [ -f "$paquete" ] || continue
    dpkg-deb --extract "$paquete" "$carpeta_graphviz/programa"
  done
  # 2. Usar los ejecutables y bibliotecas descargados solo en este proceso de construcción.
  bibliotecas="$carpeta_graphviz/programa/usr/lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH)"
  export PATH="$carpeta_graphviz/programa/usr/bin:$PATH"
  export LD_LIBRARY_PATH="$bibliotecas${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
  export GVBINDIR="$bibliotecas/graphviz"
  dot -c
fi

# 3. Ejecutar el entrenamiento solicitado con Graphviz disponible para sus gráficos.
exec "$@"
