CREATE TABLE result AS
SELECT id::INTEGER AS id,
       upper(name) AS name,
       amount::INTEGER * 2 AS doubled_amount
FROM input.records;
