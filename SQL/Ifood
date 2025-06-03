WITH Age_Income AS(
    SELECT Age,
    SUM(Income) AS Renda
    FROM ifood.ifood_df
    GROUP BY Age ORDER BY AGE ASC)
SELECT Age, Renda,
CASE
WHEN Age < 30 THEN 'Jovem'
WHEN Age BETWEEN 30 AND 59 THEN 'Adulto'
ELSE 'Idoso'
END AS Faixa_Etaria
FROM Age_Income 
