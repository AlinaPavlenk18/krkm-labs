-- Питання: B5. Хто зі споживачів перевищував договірний ліміт і скільки годин — окремо для кожної версії ліміту (SCD 2)?
-- Конструкція: з'єднання з версією виміру SCD 2 + агрегат із FILTER + віконний ранг для топ-списку
-- Інтерпретація: Consumer_3310 до зміни договору (ліміт 120 кВт) перевищував ліміт 86 годин (максимум 151,9 кВт); після підвищення ліміту до 150 кВт з 16.01 — 0 годин (максимум 148,8 кВт). Без SCD 2 (лише поточний ліміт 150) перевищення були б втрачені. Інші перевищення — поодинокі (≤ 3 год) у побутових споживачів у морозні вечори.
WITH hourly AS (   -- споживач із двома лічильниками: спершу сума за годину
    SELECT consumer_key, date_key, hour_key, sum(energy_kwh) AS load_kw
    FROM fact_consumption GROUP BY ALL),
per_version AS (
    SELECT c.consumer_id, k.class_label, c.valid_from, c.valid_to, c.contract_limit_kw,
           count(*) FILTER (WHERE h.load_kw > c.contract_limit_kw) AS over_h,
           max(h.load_kw) AS max_kw
    FROM hourly h
    JOIN dim_consumer c USING (consumer_key)
    JOIN dim_consumer_class k USING (class_key)
    GROUP BY ALL)
SELECT consumer_id AS споживач, class_label AS клас, valid_from AS діє_з, valid_to AS діє_до,
       contract_limit_kw AS ліміт_квт, over_h AS годин_перевищення, round(max_kw, 1) AS макс_квт
FROM per_version
WHERE consumer_id = 'Consumer_3310'
   OR consumer_id IN (SELECT consumer_id FROM per_version WHERE consumer_id <> 'Consumer_3310'
                      ORDER BY over_h DESC, consumer_id LIMIT 5)
ORDER BY consumer_id = 'Consumer_3310' DESC, over_h DESC, consumer_id;
