-- Питання: B2. Яка частка енергії кожного класу припадає на кожну частину доби (ніч / ранок / день / вечір)?
-- Конструкція: PIVOT (рядки — клас, стовпці — частина доби), значення — частка, %
-- Інтерпретація: профілі класів відрізняються: побутові споживачі — 38,4 % енергії ввечері, комерційні — 41,8 % удень, промислові розподілені найрівніше (найбільша частка вночі — 17,0 % — через другу зміну й вихідні). Для прогнозу це означає різні добові профілі для кожного підкласу таксономії.
WITH base AS (
    SELECT k.class_label AS клас, h.part_of_day,
           100 * f.energy_kwh / sum(f.energy_kwh) OVER (PARTITION BY k.class_label) AS pct
    FROM fact_consumption f
    JOIN dim_consumer_class k USING (class_key)
    JOIN dim_hour h USING (hour_key))
PIVOT base ON part_of_day IN ('ніч', 'ранок', 'день', 'вечір') USING round(sum(pct), 1)
ORDER BY клас;
