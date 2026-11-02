SELECT semana_inicio::text, c.nombre AS corredor,
       feriados_semana, dias_segunda_quincena,
       toneladas_estimadas::float8 AS toneladas_semana
FROM pronostico_demanda p JOIN corredor c USING(id_corredor)
WHERE p.es_historico=TRUE AND p.feriados_semana IS NOT NULL
AND p.dias_segunda_quincena IS NOT NULL
ORDER BY p.semana_inicio,c.nombre;
