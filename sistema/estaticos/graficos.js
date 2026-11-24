/* Gráficos dinámicos e interacciones ligeras de Transpacífico S.A.C. (Chart.js 4). */
(() => {
  "use strict";

  // Paleta corporativa sobria alineada con CSS industrial (grafito + petróleo).
  const PALETA = {
    petroleo: "#0f766e",
    petroleoSuave: "rgba(15, 118, 110, 0.14)",
    grafito: "#1e293b",
    acero: "#475569",
    esmeralda: "#15803d",
    esmeraldaSuave: "rgba(21, 128, 61, 0.14)",
    ambar: "#b45309",
    rojo: "#be123c",
    gris: "#64748b",
    borde: "#e2e8f0",
  };

  const leerJson = (id) => {
    const nodo = document.getElementById(id);
    if (!nodo) return null;
    try {
      return JSON.parse(nodo.textContent);
    } catch {
      return null;
    }
  };

  const configurarBase = () => {
    if (!window.Chart) return false;
    Chart.defaults.font.family = "Inter, system-ui, -apple-system, 'Segoe UI', sans-serif";
    Chart.defaults.color = "#334155";
    Chart.defaults.plugins.tooltip.backgroundColor = "#0f172a";
    Chart.defaults.plugins.tooltip.padding = 10;
    Chart.defaults.plugins.tooltip.cornerRadius = 6;
    return true;
  };

  /* 1. Panel Operativo (/): desempeño por corredor y situación de flota conmutable */
  const iniciarPanelInicio = () => {
    const datos = leerJson("datos-graficos-inicio");
    if (!datos || !configurarBase()) return;

    const ctxCorredor = document.getElementById("lienzo-corredores");
    if (ctxCorredor && Array.isArray(datos.por_corredor)) {
      const etiquetas = datos.por_corredor.map((c) => `Corredor ${c.corredor}`);
      new Chart(ctxCorredor, {
        type: "bar",
        data: {
          labels: etiquetas,
          datasets: [
            {
              label: "Cumplimiento OTIF (%)",
              data: datos.por_corredor.map((c) => c.otif),
              backgroundColor: PALETA.esmeralda,
              borderRadius: 5,
            },
            {
              label: "Ocupación FOF (%)",
              data: datos.por_corredor.map((c) => c.fof),
              backgroundColor: PALETA.grafito,
              borderRadius: 5,
            },
            {
              label: "Retorno con carga (%)",
              data: datos.por_corredor.map((c) => c.retorno_carga),
              backgroundColor: PALETA.petroleo,
              borderRadius: 5,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            y: { beginAtZero: true, max: 100, ticks: { callback: (v) => `${v}%` } },
          },
          plugins: {
            tooltip: {
              callbacks: {
                afterTitle: (items) => {
                  const fila = datos.por_corredor[items[0].dataIndex];
                  return `Viajes cerrados evaluados: ${fila.viajes.toLocaleString("es-PE")}`;
                },
                label: (ctx) => `${ctx.dataset.label}: ${ctx.parsed.y.toFixed(2)} %`,
              },
            },
          },
        },
      });
    }

    const ctxEstados = document.getElementById("lienzo-estados");
    if (ctxEstados) {
      const coloresEstado = {
        "Tractos disponibles": PALETA.petroleo,
        "Solicitudes pendientes": PALETA.ambar,
        "Viajes programados": "#334155",
        Programado: "#334155",
        "En patio": "#d97706",
        "En tránsito": "#0f766e",
        "En destino": "#0284c7",
        Cerrado: PALETA.esmeralda,
        Cancelado: "#94a3b8",
      };
      let graficoEstados = null;
      const pintarEstados = (modo) => {
        const serie =
          modo === "historico"
            ? datos.por_estado || []
            : datos.operacion_activa || datos.por_estado || [];
        if (graficoEstados) graficoEstados.destroy();
        graficoEstados = new Chart(ctxEstados, {
          type: "bar",
          data: {
            labels: serie.map((e) => e.estado),
            datasets: [
              {
                label: "Registros",
                data: serie.map((e) => e.cantidad),
                backgroundColor: serie.map((e) => coloresEstado[e.estado] || PALETA.gris),
                borderRadius: 5,
              },
            ],
          },
          options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            scales: { x: { beginAtZero: true, ticks: { precision: 0 } } },
            plugins: {
              legend: { display: false },
              tooltip: {
                callbacks: {
                  label: (ctx) => ` ${ctx.parsed.x.toLocaleString("es-PE")} registros`,
                },
              },
            },
          },
        });
      };
      pintarEstados("activa");
      document.querySelectorAll("[data-modo-estados]").forEach((boton) => {
        boton.addEventListener("click", () => {
          document
            .querySelectorAll("[data-modo-estados]")
            .forEach((b) => b.classList.remove("activo-chip"));
          boton.classList.add("activo-chip");
          pintarEstados(boton.dataset.modoEstados || "activa");
        });
      });
    }
  };

  /* 2. Demanda Semanal OE2 (/demanda): selector de lunes guiado + serie histórica Prophet */
  const iniciarDemanda = () => {
    const campoSemana = document.getElementById("campo-semana-oe2");
    const avisoLunes = document.getElementById("aviso-lunes-oe2");
    const btnRestaurarSemana = document.getElementById("btn-restaurar-semana-oe2");
    if (campoSemana) {
      const textoBaseLunes = avisoLunes ? avisoLunes.textContent : "";
      campoSemana.addEventListener("change", () => {
        if (!campoSemana.value) return;
        const [anio, mes, dia] = campoSemana.value.split("-").map(Number);
        const fecha = new Date(Date.UTC(anio, mes - 1, dia));
        const diaSem = fecha.getUTCDay();
        if (diaSem !== 1) {
          const diff = diaSem === 0 ? -6 : 1 - diaSem;
          fecha.setUTCDate(fecha.getUTCDate() + diff);
          const lunesIso = fecha.toISOString().slice(0, 10);
          campoSemana.value = lunesIso;
          if (avisoLunes) {
            avisoLunes.textContent = `Se ajustó automáticamente al lunes ${lunesIso} correspondiente a la semana elegida.`;
          }
        } else if (avisoLunes) {
          avisoLunes.textContent = textoBaseLunes;
        }
      });
      if (btnRestaurarSemana) {
        btnRestaurarSemana.addEventListener("click", () => {
          const sug = campoSemana.dataset.sugerida || "";
          if (sug) campoSemana.value = sug;
          if (avisoLunes) avisoLunes.textContent = textoBaseLunes;
        });
      }
    }

    const datos = leerJson("datos-serie-demanda");
    const lienzo = document.getElementById("lienzo-demanda-oe2");
    if (!datos || !lienzo || !configurarBase()) return;

    let grafico = null;
    const renderizar = (ultimasSemanas) => {
      const hist = ultimasSemanas > 0 ? datos.historial.slice(-ultimasSemanas) : datos.historial;
      const mapa = new Map();
      hist.forEach((h) => mapa.set(h.semana, { hist: h, pron: null }));
      (datos.recientes || []).forEach((r) => {
        const entrada = mapa.get(r.semana) || { hist: null, pron: null };
        entrada.pron = r;
        mapa.set(r.semana, entrada);
      });
      if (datos.actual && datos.actual.semana) {
        const entrada = mapa.get(datos.actual.semana) || { hist: null, pron: null };
        entrada.pron = datos.actual;
        mapa.set(datos.actual.semana, entrada);
      }

      const semanas = Array.from(mapa.keys()).sort();
      const serieHist = semanas.map((s) => (mapa.get(s).hist ? mapa.get(s).hist.toneladas : null));
      const seriePron = semanas.map((s) => (mapa.get(s).pron ? mapa.get(s).pron.toneladas : null));
      const serieMin = semanas.map((s) => (mapa.get(s).pron ? mapa.get(s).pron.minimo : null));
      const serieMax = semanas.map((s) => (mapa.get(s).pron ? mapa.get(s).pron.maximo : null));

      if (grafico) grafico.destroy();
      grafico = new Chart(lienzo, {
        type: "line",
        data: {
          labels: semanas,
          datasets: [
            {
              label: "Histórico observado (t)",
              data: serieHist,
              borderColor: PALETA.grafito,
              backgroundColor: PALETA.petroleoSuave,
              borderWidth: 2,
              pointRadius: 2.5,
              pointHoverRadius: 6,
              tension: 0.2,
            },
            {
              label: "Pronóstico Prophet (t)",
              data: seriePron,
              borderColor: PALETA.petroleo,
              backgroundColor: PALETA.petroleo,
              pointRadius: 6,
              pointHoverRadius: 8,
              showLine: false,
            },
            {
              label: "Límite superior intervalo",
              data: serieMax,
              borderColor: "rgba(15,118,110,0.35)",
              borderDash: [4, 4],
              pointRadius: 3,
              fill: false,
            },
            {
              label: "Límite inferior intervalo",
              data: serieMin,
              borderColor: "rgba(15,118,110,0.35)",
              backgroundColor: PALETA.petroleoSuave,
              borderDash: [4, 4],
              pointRadius: 3,
              fill: "-1",
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: {
            tooltip: {
              callbacks: {
                title: (items) => `Semana del lunes ${items[0].label} · Corredor ${datos.corredor}`,
                afterBody: (items) => {
                  const registro = mapa.get(items[0].label);
                  const extras = [];
                  if (registro && registro.hist) {
                    extras.push(
                      `Feriados: ${registro.hist.feriados} · Días 2da quincena: ${registro.hist.dias_quincena}`
                    );
                  }
                  if (registro && registro.pron) {
                    extras.push(
                      `Intervalo estimado: ${registro.pron.minimo.toFixed(2)} – ${registro.pron.maximo.toFixed(2)} t`
                    );
                  }
                  return extras;
                },
              },
            },
          },
          scales: {
            y: { title: { display: true, text: "Toneladas semanales (t)" } },
          },
        },
      });
    };

    renderizar(32);
    document.querySelectorAll("[data-rango-demanda]").forEach((boton) => {
      boton.addEventListener("click", () => {
        document
          .querySelectorAll("[data-rango-demanda]")
          .forEach((b) => b.classList.remove("activo-chip"));
        boton.classList.add("activo-chip");
        renderizar(Number(boton.dataset.rangoDemanda || "0"));
      });
    });
  };

  /* 3. Carga de Retorno OE3 (/retornos): autollenado SQL editable, restaurar y gráficos */
  const iniciarRetornos = () => {
    const selViaje = document.getElementById("selector-viaje-oe3");
    const campoSol = document.getElementById("campo-oe3-solicitudes");
    const campoTasa = document.getElementById("campo-oe3-tasa");
    const textoBase = document.getElementById("texto-base-oe3");
    const btnRestaurarOe3 = document.getElementById("btn-restaurar-oe3");

    const actualizarAvisoOe3 = () => {
      if (!selViaje || !selViaje.options.length || !textoBase) return;
      const opt = selViaje.options[selViaje.selectedIndex];
      if (!opt || !opt.value) return;
      const solBase = opt.dataset.solicitudes ?? "0";
      const tasaBase = opt.dataset.tasaPct ?? "50";
      const fuente = opt.dataset.fuente || "SQL";
      const modificado =
        (campoSol && campoSol.value !== String(solBase)) ||
        (campoTasa && campoTasa.value !== String(tasaBase));
      textoBase.innerHTML = modificado
        ? `Simulación manual activa (base SQL: <strong>${solBase}</strong> ofertas · <strong>${tasaBase} %</strong>, ${fuente}). Pulsa restaurar para volver al dato real.`
        : `Base SQL del tramo: <strong>${solBase}</strong> ofertas abiertas · <strong>${tasaBase} %</strong> de retorno con carga (${fuente}) — puedes editar para simular otro escenario.`;
    };

    const aplicarBaseOe3 = () => {
      if (!selViaje || !selViaje.options.length) return;
      const opt = selViaje.options[selViaje.selectedIndex];
      if (!opt || !opt.value) return;
      if (campoSol && opt.dataset.solicitudes !== undefined) {
        campoSol.value = opt.dataset.solicitudes;
      }
      if (campoTasa && opt.dataset.tasaPct !== undefined) {
        campoTasa.value = opt.dataset.tasaPct;
      }
      actualizarAvisoOe3();
    };

    if (selViaje) {
      selViaje.addEventListener("change", aplicarBaseOe3);
      if (campoSol) campoSol.addEventListener("input", actualizarAvisoOe3);
      if (campoTasa) campoTasa.addEventListener("input", actualizarAvisoOe3);
      if (btnRestaurarOe3) btnRestaurarOe3.addEventListener("click", aplicarBaseOe3);
      actualizarAvisoOe3();
    }

    document.querySelectorAll("[data-seleccionar-viaje]").forEach((boton) => {
      boton.addEventListener("click", () => {
        if (selViaje && boton.dataset.idViaje) {
          selViaje.value = boton.dataset.idViaje;
        }
        if (campoSol && boton.dataset.solicitudes !== undefined) {
          campoSol.value = boton.dataset.solicitudes;
        }
        if (campoTasa && boton.dataset.tasaPct !== undefined) {
          campoTasa.value = boton.dataset.tasaPct;
        }
        actualizarAvisoOe3();
        const formOe3 = document.getElementById("form-oe3");
        if (formOe3) formOe3.scrollIntoView({ behavior: "smooth", block: "nearest" });
      });
    });

    const datos = leerJson("datos-serie-retornos");
    if (!datos || !configurarBase()) return;

    const ctxActual = document.getElementById("lienzo-retorno-actual");
    if (ctxActual && datos.actual) {
      new Chart(ctxActual, {
        type: "bar",
        data: {
          labels: ["Con carga de retorno", "Retorno en vacío"],
          datasets: [
            {
              label: "Probabilidad estimada (%)",
              data: [datos.actual.probabilidad, datos.actual.vacio],
              backgroundColor: [PALETA.petroleo, "#94a3b8"],
              borderRadius: 6,
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          scales: { x: { min: 0, max: 100, ticks: { callback: (v) => `${v}%` } } },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                title: () =>
                  `Despacho #${datos.actual.id_despacho} · ${datos.actual.destino} → Callao`,
                label: (ctx) => ` ${ctx.parsed.x.toFixed(1)} % (${datos.actual.nivel})`,
              },
            },
          },
        },
      });
    }

    const ctxRecientes = document.getElementById("lienzo-retornos-recientes");
    if (ctxRecientes && Array.isArray(datos.recientes) && datos.recientes.length) {
      new Chart(ctxRecientes, {
        type: "bar",
        data: {
          labels: datos.recientes.map((r) => `#${r.id_despacho} (${r.destino})`),
          datasets: [
            {
              label: "Probabilidad de retorno con carga (%)",
              data: datos.recientes.map((r) => r.probabilidad),
              backgroundColor: datos.recientes.map((r) =>
                r.nivel === "Alta"
                  ? PALETA.esmeralda
                  : r.nivel === "Media"
                  ? PALETA.ambar
                  : PALETA.rojo
              ),
              borderRadius: 5,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: { y: { min: 0, max: 100, ticks: { callback: (v) => `${v}%` } } },
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const r = datos.recientes[ctx.dataIndex];
                  return ` ${r.destino} → Callao: ${r.probabilidad.toFixed(1)} % · Oportunidad ${r.nivel}`;
                },
              },
            },
          },
        },
      });
    }
  };

  /* 4. Validación 80/20 de Modelos (/modelos): OE1, OE2 y OE3 con tooltips detallados */
  const iniciarModelos = () => {
    const ev = leerJson("datos-evaluaciones-ml");
    if (!ev || !configurarBase()) return;

    // OE1: Dispersión Real vs Predicho con filtro por corredor
    const ctxOe1Real = document.getElementById("lienzo-oe1-dispersion");
    if (ctxOe1Real && ev.oe1 && Array.isArray(ev.oe1.puntos) && ev.oe1.puntos.length) {
      let graficoOe1 = null;
      const pintarOe1 = (corredorFiltro) => {
        const filtrados = corredorFiltro
          ? ev.oe1.puntos.filter((p) => p.corredor === corredorFiltro)
          : ev.oe1.puntos;
        const valores = filtrados.flatMap((p) => [p.real, p.predicha]);
        const minV = Math.min(...valores, 450);
        const maxV = Math.max(...valores, 750);

        if (graficoOe1) graficoOe1.destroy();
        graficoOe1 = new Chart(ctxOe1Real, {
          type: "scatter",
          data: {
            datasets: [
              {
                label: "Viajes del conjunto de prueba (20%)",
                data: filtrados.map((p) => ({ x: p.real, y: p.predicha, meta: p })),
                backgroundColor: "rgba(15, 118, 110, 0.62)",
                borderColor: PALETA.petroleo,
                pointRadius: 4,
                pointHoverRadius: 7,
              },
              {
                type: "line",
                label: "Ajuste ideal (y = x)",
                data: [
                  { x: minV, y: minV },
                  { x: maxV, y: maxV },
                ],
                borderColor: PALETA.rojo,
                borderDash: [5, 5],
                borderWidth: 1.5,
                pointRadius: 0,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
              x: { title: { display: true, text: "Duración observada en SQL (min)" } },
              y: { title: { display: true, text: "Duración predicha XGBoost (min)" } },
            },
            plugins: {
              tooltip: {
                filter: (item) => item.datasetIndex === 0,
                callbacks: {
                  title: (items) => {
                    const m = items[0].raw.meta;
                    return `Viaje #${m.id_despacho} · ${m.ruta} (${m.corredor})`;
                  },
                  label: (ctx) => {
                    const m = ctx.raw.meta;
                    const dif = (m.predicha - m.real).toFixed(1);
                    return [
                      `Observada: ${m.real.toFixed(1)} min | Predicha: ${m.predicha.toFixed(1)} min (Δ ${dif} min)`,
                      `Peso neto: ${m.peso_tn} t · Hora salida UTC: ${m.hora_salida}:00`,
                    ];
                  },
                },
              },
            },
          },
        });
      };
      pintarOe1("");
      const selOe1 = document.getElementById("filtro-oe1-corredor");
      if (selOe1) selOe1.addEventListener("change", () => pintarOe1(selOe1.value));
    }

    // OE1: Importancia de variables
    const ctxOe1Imp = document.getElementById("lienzo-oe1-importancia");
    if (ctxOe1Imp && ev.oe1 && Array.isArray(ev.oe1.importancia) && ev.oe1.importancia.length) {
      new Chart(ctxOe1Imp, {
        type: "bar",
        data: {
          labels: ev.oe1.importancia.map((i) => i.variable),
          datasets: [
            {
              label: "Importancia relativa (%)",
              data: ev.oe1.importancia.map((i) => i.porcentaje),
              backgroundColor: PALETA.grafito,
              borderRadius: 5,
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (ctx) => ` ${ctx.parsed.x.toFixed(2)} %` } },
          },
        },
      });
    }

    // OE2: Prueba 20% por corredor con selector interactivo
    const ctxOe2 = document.getElementById("lienzo-oe2-prueba");
    if (ctxOe2 && ev.oe2) {
      let graficoOe2 = null;
      const pintarOe2 = (corredor) => {
        const filas = ev.oe2[corredor] || [];
        if (!filas.length) return;
        if (graficoOe2) graficoOe2.destroy();
        graficoOe2 = new Chart(ctxOe2, {
          type: "line",
          data: {
            labels: filas.map((f) => f.semana),
            datasets: [
              {
                label: "Toneladas observadas (SQL)",
                data: filas.map((f) => f.real),
                borderColor: "#475569",
                borderWidth: 2,
                pointRadius: 3.5,
              },
              {
                label: "Pronóstico Prophet (20% prueba)",
                data: filas.map((f) => f.predicha),
                borderColor: PALETA.petroleo,
                backgroundColor: PALETA.petroleoSuave,
                borderWidth: 2.5,
                pointRadius: 4,
              },
            ],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
              tooltip: {
                callbacks: {
                  title: (items) => `Semana ${items[0].label} · Corredor ${corredor}`,
                  afterBody: (items) => {
                    const f = filas[items[0].dataIndex];
                    return [
                      `Intervalo Prophet: ${f.minimo.toFixed(1)} – ${f.maximo.toFixed(1)} t`,
                      `Feriados: ${f.feriados} · Días 2da quincena: ${f.dias_quincena}`,
                    ];
                  },
                },
              },
            },
          },
        });
      };
      const corredoresDisp = Object.keys(ev.oe2);
      if (corredoresDisp.length) pintarOe2(corredoresDisp[0]);
      const selOe2 = document.getElementById("filtro-oe2-corredor");
      if (selOe2) selOe2.addEventListener("change", () => pintarOe2(selOe2.value));
    }

    // OE3: Curva ROC e Importancia de variables
    const ctxOe3Roc = document.getElementById("lienzo-oe3-roc");
    if (ctxOe3Roc && ev.oe3 && Array.isArray(ev.oe3.roc) && ev.oe3.roc.length) {
      new Chart(ctxOe3Roc, {
        type: "line",
        data: {
          datasets: [
            {
              label: "Curva ROC Árbol de Decisión",
              data: ev.oe3.roc.map((p) => ({ x: p.fpr, y: p.tpr, umbral: p.umbral })),
              borderColor: PALETA.petroleo,
              backgroundColor: PALETA.petroleoSuave,
              fill: true,
              borderWidth: 2.5,
              pointRadius: 3,
            },
            {
              label: "Clasificador aleatorio",
              data: [
                { x: 0, y: 0 },
                { x: 1, y: 1 },
              ],
              borderColor: "#94a3b8",
              borderDash: [5, 5],
              pointRadius: 0,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          scales: {
            x: { type: "linear", min: 0, max: 1, title: { display: true, text: "Tasa Falsos Positivos (FPR)" } },
            y: { min: 0, max: 1, title: { display: true, text: "Sensibilidad / Recall (TPR)" } },
          },
          plugins: {
            tooltip: {
              filter: (item) => item.datasetIndex === 0,
              callbacks: {
                label: (ctx) =>
                  ` TPR: ${(ctx.parsed.y * 100).toFixed(1)}% · FPR: ${(ctx.parsed.x * 100).toFixed(1)}% (umbral ${ctx.raw.umbral})`,
              },
            },
          },
        },
      });
    }

    const ctxOe3Imp = document.getElementById("lienzo-oe3-importancia");
    if (ctxOe3Imp && ev.oe3 && Array.isArray(ev.oe3.importancia) && ev.oe3.importancia.length) {
      new Chart(ctxOe3Imp, {
        type: "bar",
        data: {
          labels: ev.oe3.importancia.map((i) => i.variable),
          datasets: [
            {
              label: "Importancia en el árbol (%)",
              data: ev.oe3.importancia.map((i) => i.porcentaje),
              backgroundColor: PALETA.acero,
              borderRadius: 5,
            },
          ],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: { callbacks: { label: (ctx) => ` ${ctx.parsed.x.toFixed(2)} %` } },
          },
        },
      });
    }
  };

  /* 5. Ayudas de formulario alimentadas 100% desde catálogos JSON de SQL */
  const iniciarAyudasFormulario = () => {
    // 5A. Solicitudes: sincroniza corredor -> pares válidos [origen, destino] sin nombres fijos.
    const mapaRutas = leerJson("datos-mapa-rutas");
    const formSol = document.querySelector('form[action^="/solicitudes"]');
    if (mapaRutas && formSol) {
      const selCorredor = formSol.querySelector('select[name="id_corredor"]');
      const selOrigen = formSol.querySelector('select[name="origen"]');
      const selDestino = formSol.querySelector('select[name="destino"]');
      const esNuevo = formSol.getAttribute("action") === "/solicitudes";

      if (selCorredor && selOrigen && selDestino) {
        const ajustarDesdeCorredor = () => {
          const pares = mapaRutas[String(selCorredor.value)] || [];
          if (!pares.length) return;
          const parActual = pares.find(
            ([orig, dest]) => orig === selOrigen.value && dest === selDestino.value
          );
          if (!parActual) {
            const coincOrigen = pares.find(([orig]) => orig === selOrigen.value);
            if (coincOrigen) {
              selDestino.value = coincOrigen[1];
            } else {
              selOrigen.value = pares[0][0];
              selDestino.value = pares[0][1];
            }
          }
        };

        const ajustarDesdeOrigen = () => {
          const pares = mapaRutas[String(selCorredor.value)] || [];
          const coinc = pares.find(([orig]) => orig === selOrigen.value);
          if (coinc) {
            selDestino.value = coinc[1];
          }
        };

        selCorredor.addEventListener("change", ajustarDesdeCorredor);
        selOrigen.addEventListener("change", ajustarDesdeOrigen);
        if (esNuevo) ajustarDesdeCorredor();
      }
    }

    // 5B. Programación de viajes: autocompleta odómetro real al seleccionar otro tractocamión.
    const formViaje = document.querySelector('form[action="/viajes"]');
    if (formViaje) {
      const selTracto = formViaje.querySelector('select[name="id_tracto"]');
      const inputOdo = formViaje.querySelector('input[name="odometro"]');
      if (selTracto && inputOdo) {
        inputOdo.addEventListener("input", () => {
          inputOdo.dataset.editado = "1";
        });
        selTracto.addEventListener("change", () => {
          const opt = selTracto.options[selTracto.selectedIndex];
          const ultimo = Number(opt?.dataset?.odometro || 0);
          if (!inputOdo.dataset.editado && ultimo > 0) {
            inputOdo.value = String(ultimo);
          }
        });
      }
    }

    // 5C. Botones "Usar hora actual" en cálculo OE1 (salida prevista o lectura en ruta).
    document.querySelectorAll("[data-restaurar-ahora]").forEach((boton) => {
      boton.addEventListener("click", () => {
        const campo = boton.dataset.restaurarAhora;
        const entrada = document.querySelector(`#oe1-eta input[name="${campo}"]`);
        if (!entrada) return;
        try {
          const partes = new Intl.DateTimeFormat("en-CA", {
            timeZone: "America/Lima",
            year: "numeric",
            month: "2-digit",
            day: "2-digit",
            hour: "2-digit",
            minute: "2-digit",
            hour12: false,
          }).formatToParts(new Date());
          const mapa = Object.fromEntries(partes.map((p) => [p.type, p.value]));
          const hora24 = mapa.hour === "24" ? "00" : mapa.hour;
          entrada.value = `${mapa.year}-${mapa.month}-${mapa.day}T${hora24}:${mapa.minute}`;
        } catch {
          if (entrada.dataset.ahora) entrada.value = entrada.dataset.ahora;
        }
      });
    });
  };

  document.addEventListener("DOMContentLoaded", () => {
    iniciarPanelInicio();
    iniciarDemanda();
    iniciarRetornos();
    iniciarModelos();
    iniciarAyudasFormulario();
  });
})();
