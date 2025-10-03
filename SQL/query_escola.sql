-- Matriculas tratadas e dummies
WITH
matriculas_tratadas AS (
    SELECT
        UNIDADE_DE_ENSINO,
        -- Conversão de variáveis categóricas em dummies
        CASE WHEN SEXO = 'M' THEN 1 ELSE 0 END AS sexo_m,
        CASE WHEN SEXO = 'F' THEN 1 ELSE 0 END AS sexo_f,
        CASE WHEN ETNIA = 'BRANCA' THEN 1 ELSE 0 END AS etnia_branca,
        CASE WHEN ETNIA = 'PRETA' THEN 1 ELSE 0 END AS etnia_preta,
        CASE WHEN ETNIA = 'PARDA' THEN 1 ELSE 0 END AS etnia_parda,
        CASE WHEN ETNIA = 'INDÍGENA' THEN 1 ELSE 0 END AS etnia_indigena,
        CASE WHEN ETNIA = 'AMARELA' THEN 1 ELSE 0 END AS etnia_amarela
        -- coloque aqui outras colunas de matriculas que não foram dropadas
    FROM matriculas),

-- Agrupamento de alunos
alunos AS (
    SELECT
        LOWER(TRIM(UNIDADE_DE_ENSINO)) AS unidade_de_ensino,
        SUM(sexo_m) AS sexo_m,
        SUM(sexo_f) AS sexo_f,
        SUM(etnia_preta) AS etnia_preta,
        SUM(etnia_branca) AS etnia_branca,
        SUM(etnia_amarela) AS etnia_amarela,
        SUM(etnia_indigena) AS etnia_indigena,
        SUM(etnia_parda) AS etnia_parda
	FROM matriculas_tratadas
    GROUP BY LOWER(TRIM(UNIDADE_DE_ENSINO))),

-- Unidades tratadas
unidades_tratadas AS (
    SELECT
        LOWER(TRIM(escola)) AS escola,
        inep,
        quadra_coberta,
        quadra_descoberta,
		CAST(latitude AS FLOAT) AS latitude,
        CAST(longitude AS FLOAT) AS longitude
    FROM unidades),

-- Merge unidades + alunos
undmat AS (
    SELECT 
        u.*,
        a.sexo_m, a.sexo_f,
        a.etnia_branca, a.etnia_preta, a.etnia_parda, a.etnia_indigena, a.etnia_amarela,
		COALESCE(CAST(u.inep AS CHAR), a.unidade_de_ensino) AS inep_final
    FROM unidades_tratadas u
    LEFT JOIN alunos a 
        ON LOWER(TRIM(u.escola)) = LOWER(TRIM(a.unidade_de_ensino))
    WHERE COALESCE(u.inep, a.unidade_de_ensino) IS NOT NULL),

-- Escolas tratadas
escolas_tratadas AS (
    SELECT 
        CO_ENTIDADE,
        LOWER(TRIM(NO_ENTIDADE)) AS no_entidade
    FROM escolas
),

-- Merge escolas + unidades/matrículas
escpl AS (
    SELECT 
        u.*,
        e.no_entidade,
        COALESCE(u.quadra_coberta, u.quadra_descoberta) AS quadra
    FROM undmat u
    INNER JOIN escolas_tratadas e 
        ON u.inep_final = e.CO_ENTIDADE
    WHERE u.latitude IS NOT NULL AND u.longitude IS NOT NULL)

-- Resultado final
SELECT * 
FROM escpl;
