SELECT 
    t.*,
    a.*
FROM "transaction" t
INNER JOIN account a 
    ON t.account_pk = a.pk
WHERE t.transacted_at BETWEEN "2025-12-01" AND "2026-02-01";