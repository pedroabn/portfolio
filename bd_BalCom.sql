CREATE VIEW db_completa_imp AS
SELECT calendario,
imp.CO_NCM, 
imp.CO_PAIS, 
SG_UF_NCM, 
imp.CO_VIA,
CO_URF, 
QT_ESTAT, 
KG_LIQUIDO, 
VL_FOB,
VL_FRETE, 
VL_SEGURO,
VL_Total,
pais.NO_PAIS,
ncm.NO_NCM_POR,
ncm.CO_CGCE_N3,
ncm_cgce.NO_CGCE_N3,
via.NO_VIA
FROM imp
JOIN pais ON imp.CO_PAIS = pais.CO_PAIS
JOIN via ON imp.CO_VIA = via.CO_VIA
JOIN ncm ON imp.CO_NCM = ncm.CO_NCM
JOIN ncm_cgce ON ncm.CO_CGCE_N3 = ncm_cgce.CO_CGCE_N3;


CREATE VIEW db_completa_exp AS
SELECT 
CONCAT_WS('/', '01', LPAD(exp.CO_MES, 2, '0'), exp.CO_ANO) AS calendario,
exp.CO_NCM, 
exp.CO_PAIS, 
SG_UF_NCM, 
exp.CO_VIA,
CO_URF, 
QT_ESTAT, 
KG_LIQUIDO, 
VL_FOB,
pais.NO_PAIS,
ncm.NO_NCM_POR,
ncm.CO_CGCE_N3,
ncm_cgce.NO_CGCE_N3,
via.NO_VIA
FROM exp
JOIN pais ON exp.CO_PAIS = pais.CO_PAIS
JOIN via ON exp.CO_VIA = via.CO_VIA
JOIN ncm ON exp.CO_NCM = ncm.CO_NCM
JOIN ncm_cgce ON ncm.CO_CGCE_N3 = ncm_cgce.CO_CGCE_N3;