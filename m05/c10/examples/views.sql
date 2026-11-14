CREATE OR REPLACE VIEW m05_c10.v_cost_daily AS
SELECT date_trunc('day', ts)                     AS day,
       tenant_id,
       feature,
       tier,
       count(*)                                   AS calls,
       count(*) FILTER (WHERE status <> 'ok')     AS failed_calls,
       sum(prompt_tokens)                         AS prompt_tokens,
       sum(output_tokens)                         AS output_tokens,
       sum(cost_usd)                              AS cost_usd
FROM m05_c10.usage_events
GROUP BY 1, 2, 3, 4;
