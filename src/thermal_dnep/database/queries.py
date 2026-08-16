FEEDER_QUERY = """
SELECT
    t1.[Date],
    t2.Title AS OperatorName,
    t1.StationPGDSCode,
    t3.Voltage,
    t1.ToolPGDSCode,
    t1.H01, t1.H02, t1.H03, t1.H04, t1.H05, t1.H06,
    t1.H07, t1.H08, t1.H09, t1.H10, t1.H11, t1.H12,
    t1.H13, t1.H14, t1.H15, t1.H16, t1.H17, t1.H18,
    t1.H19, t1.H20, t1.H21, t1.H22, t1.H23, t1.H24,
    t1.Total
FROM [dbo].[StationEnergyByTool] AS t1
INNER JOIN Operators AS t2
    ON t1.OperatorId = t2.Id
INNER JOIN BasicSubstation AS t3
    ON t1.StationPGDSCode = t3.UniqueCode
WHERE
    t1.StationPGDSCode = ?
    AND t1.FormulaTypeId = 1
    AND t1.OperatorTypeId = 7
    AND t1.Complete = 1
    AND t1.StationTypeId = 1
    AND t1.StationPGDSCode IS NOT NULL
ORDER BY
    t1.[Date],
    t1.StationPGDSCode;
"""