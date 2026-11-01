-- Питання: B4. Яке пікове годинне навантаження кожної підстанції відносно номінальної потужності і яке її місце в області?
-- Конструкція: агрегування до (підстанція, година) + MAX + віконна RANK() OVER (PARTITION BY область)
-- Інтерпретація: 4 підстанції мають пікове завантаження ≥ 85 % номіналу (№12 — 120,2 %, №8 — 103,0 %, №9 — 99,4 %, №5 — 91,1 %), тобто відповідають класу :OverloadedSubstation онтології; №12 у Львівській області перевантажена через промислового споживача Consumer_5019 (349,3 кВт) на підстанції номіналом 250 кВт. Найменше завантажені №6 і №4 (лише побутові споживачі).
WITH hourly AS (
    SELECT substation_key, date_key, hour_key, sum(energy_kwh) AS load_kw
    FROM fact_consumption GROUP BY ALL),
peak AS (
    SELECT substation_key, max(load_kw) AS peak_kw, avg(load_kw) AS avg_kw
    FROM hourly GROUP BY substation_key)
SELECT s.region_name AS область, s.substation_name AS підстанція,
       s.nominal_capacity_kw AS номінал_квт,
       round(p.peak_kw, 1) AS пік_квт,
       round(100 * p.peak_kw / s.nominal_capacity_kw, 1) AS завантаження_pct,
       round(p.avg_kw / p.peak_kw, 2) AS коеф_навантаження,
       RANK() OVER (PARTITION BY s.region_name ORDER BY p.peak_kw / s.nominal_capacity_kw DESC) AS ранг_в_області
FROM peak p JOIN dim_substation s USING (substation_key)
ORDER BY завантаження_pct DESC;
