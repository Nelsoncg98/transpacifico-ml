SELECT d.id_despacho, c.nombre AS corredor, s.origen, s.destino,
       round(p.peso_neto_kg/1000,2)::float8 AS peso_carga_tn,
       extract(isodow FROM d.fecha_hora_salida AT TIME ZONE 'UTC')::int AS dia_salida,
       extract(hour FROM d.fecha_hora_salida AT TIME ZONE 'UTC')::int AS hora_salida,
       round((extract(epoch FROM (pod.fecha_hora_real-d.fecha_hora_salida))/60)::numeric,2)
       ::float8 AS duracion_viaje_min
FROM despacho d JOIN solicitud_carga s USING(id_solicitud)
JOIN corredor c USING(id_corredor)
JOIN LATERAL (
    SELECT peso_neto_kg FROM pesaje_bascula
    WHERE id_despacho=d.id_despacho AND resultado='Conforme'
    ORDER BY fecha_hora DESC,id_pesaje DESC LIMIT 1
) p ON TRUE
JOIN pod_entrega pod USING(id_despacho)
WHERE d.estado_viaje='Cerrado' AND d.fecha_hora_salida IS NOT NULL
AND pod.fecha_hora_real>d.fecha_hora_salida
ORDER BY d.id_despacho;
