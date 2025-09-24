SELECT 
  c.nome_urna as Nome_candidato,
  r.secao as Secao,
  SUM(r.votos) as Votos_recebidos,
  r.zona as Zona
FROM
  basedosdados.br_tse_eleicoes.resultados_candidato_secao as r
LEFT JOIN
  basedosdados.br_tse_eleicoes.local_secao as l
  ON CAST(r.secao as string) = CAST(l.secao as string)
LEFT JOIN
  basedosdados.br_tse_eleicoes.candidatos as c
  ON (CAST(r.sequencial_candidato as string) = cast(c.sequencial as string) 
      AND CAST(r.numero_candidato as string) = CAST(c.numero as string))
WHERE
  r.ano = 2024 and r.turno = 1 and r.sigla_uf = "PE" and r.id_municipio = "2611606" and r.cargo = "vereador"
GROUP BY
  Nome_candidato,
  Secao,
  Zona;
