SELECT d.id_despacho,
       to_char(d.fecha_hora_salida AT TIME ZONE 'UTC','YYYY-MM-DD HH24:MI:SS')
       AS fecha_hora_evaluacion,
       s.destino AS origen_retorno,
       extract(isodow FROM s.ventana_entrega AT TIME ZONE 'UTC')::int AS dia_entrega_pactada,
       CASE WHEN extract(day FROM s.ventana_entrega AT TIME ZONE 'UTC')<=15
            THEN 1 ELSE 2 END AS quincena_entrega_pactada,
       d.solicitudes_compatibles, d.proporcion_retornos_previos::float8,
       d.retorno_con_carga::int
FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
WHERE d.estado_viaje='Cerrado' AND s.origen='Callao'
AND s.destino IN ('Huancayo','Trujillo')
AND d.fecha_hora_salida IS NOT NULL AND d.retorno_con_carga IS NOT NULL
AND d.solicitudes_compatibles IS NOT NULL AND d.proporcion_retornos_previos IS NOT NULL
ORDER BY d.fecha_hora_salida,d.id_despacho;
