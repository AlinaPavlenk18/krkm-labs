-- Питання: B7. Яка динаміка добового споживання: накопичене споживання з початку місяця і ковзне середнє за 7 днів?
-- Конструкція: віконні функції SUM() OVER (накопичення) і AVG() OVER (ROWS 6 PRECEDING)
-- Інтерпретація: накопичене споживання на 31.01 — 1926,23 МВт·год (збігається з ROLLUP); ковзне середнє за 7 днів згладжує тижневий цикл будні/вихідні й після першого повного тижня тримається в межах 60,9–63,6 МВт·год/добу; спад наприкінці місяця (до 60,86) пояснюється вибуттям несправних лічильників (з 28.01 активних 38 із 43) і потеплінням, тому для порівняння днів потрібна нормалізація на активний лічильник.
WITH daily AS (
    SELECT d.date, d.day_name, sum(f.energy_kwh) AS e, avg(f.temperature_c) AS t
    FROM fact_consumption f JOIN dim_date d USING (date_key)
    GROUP BY d.date, d.day_name)
SELECT date AS дата, day_name AS день,
       round(e / 1000, 2) AS мвт_год,
       round(sum(e) OVER (ORDER BY date) / 1000, 2) AS накопичено_мвт_год,
       round(avg(e) OVER (ORDER BY date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) / 1000, 2) AS ковз_7д_мвт_год,
       round(t, 1) AS сер_темп_c
FROM daily
ORDER BY date;
