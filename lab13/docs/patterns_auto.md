# Асоціативні правила (автоматичний звіт)

Транзакцій (розділів із ≥ 2 сутностями): 132; предметів: 127; поріг: спільних розділів ≥ 3, confidence ≥ 0.6, lift > 1.

| X → Y | nXY | support | conf | lift | p (перест.) | механізм у графі | lift статті / реєстри | 95 % ДІ lift | документи |
|---|---|---|---|---|---|---|---|---|---|
| Meter_AMI27192 → Meter_AMI66829 | 3 | 0.0227 | 0.6 | 19.8 | 0.001 | — | 36.0 / 16.0 | 10.48–66.0 | gen02, gen04, kb15 |
| Meter_AMI66829 → Meter_AMI27192 | 3 | 0.0227 | 0.75 | 19.8 | 0.001 | — | 36.0 / 16.0 | 8.8–66.0 | gen02, gen04, kb15 |
| Consumer_3310 → Meter_AMI77410 | 5 | 0.0379 | 0.833 | 15.71 | 0.001 | HAS_METER | 6.75 / 32.0 | 8.25–44.0 | gen03, gen04, kb05, kb14, kb15 |
| Meter_AMI77410 → Consumer_3310 | 5 | 0.0379 | 0.714 | 15.71 | 0.001 | HAS_METER | 6.75 / 32.0 | 8.8–44.0 | gen03, gen04, kb05, kb14, kb15 |
| GRU → LSTM | 3 | 0.0227 | 0.75 | 14.14 | 0.001 | — | 9.0 / None | 6.73–44.0 | kb01, kb02 |
| Dispatcher_1 → ForecastModel_LSTM1 | 3 | 0.0227 | 0.75 | 11.0 | 0.002 | — | None / 10.29 | 5.28–26.4 | gen01, gen05 |
| Consumer_5011 → Substation_9 | 3 | 0.0227 | 1.0 | 11.0 | 0.001 | — | 6.0 / 16.0 | 6.95–18.86 | gen03, gen04, kb15 |
| Region_Zakarpattia → Substation_9 | 8 | 0.0606 | 0.727 | 8.0 | 0.001 | LOCATED_IN | 6.0 / 10.0 | 5.24–14.67 | gen01, gen03, kb06, kb11, kb15 |
| Substation_9 → Region_Zakarpattia | 8 | 0.0606 | 0.667 | 8.0 | 0.001 | LOCATED_IN | 6.0 / 10.0 | 5.0–15.09 | gen01, gen03, kb06, kb11, kb15 |
| Dispatcher_2 → ForecastModel_VAR1 | 5 | 0.0379 | 0.625 | 7.5 | 0.001 | — | 18.0 / 6.1 | 3.67–14.67 | gen01, gen05, kb15 |
| Dispatcher_1 → Substation_7 | 4 | 0.0303 | 1.0 | 7.33 | 0.002 | MANAGES | None / 8.0 | 5.08–12.0 | gen01, gen05, gen07 |
| Consumer_4521 → Substation_7 | 3 | 0.0227 | 1.0 | 7.33 | 0.001 | CONNECTED_TO | 6.0 / 8.0 | 4.89–12.0 | gen03, gen04, kb12 |
| Region_Ternopil → Substation_4 | 6 | 0.0455 | 1.0 | 6.95 | 0.001 | LOCATED_IN | 4.5 / 8.73 | 4.89–12.0 | gen01, gen03, kb15 |
| Consumer_5038 → Substation_1 | 4 | 0.0303 | 1.0 | 6.95 | 0.001 | CONNECTED_TO | 4.5 / 8.73 | 4.89–11.0 | gen03, gen04, kb05, kb15 |
| Consumer_1002 → Substation_12 | 3 | 0.0227 | 1.0 | 6.6 | 0.002 | CONNECTED_TO | 5.14 / 7.38 | 4.55–10.15 | gen03, gen04, kb12 |
| Consumer_5019 → Substation_12 | 3 | 0.0227 | 1.0 | 6.6 | 0.01 | — | 5.14 / 7.38 | 4.55–10.15 | gen03, gen04, prj10 |
| CLOUD_COVER → TEMPERATURE | 10 | 0.0758 | 1.0 | 6.0 | 0.001 | — | None / 6.0 | 4.26–10.15 | gen06 |
| Region_Rivne → Substation_3 | 6 | 0.0455 | 0.667 | 5.87 | 0.001 | LOCATED_IN | None / 5.82 | 3.14–10.15 | gen01, gen03 |
| Dispatcher_6 → Substation_4 | 5 | 0.0379 | 0.833 | 5.79 | 0.001 | MANAGES | 4.5 / 6.98 | 2.85–10.15 | gen01, gen05, gen07, kb15 |
| Meter_AMI27192 → Substation_8 | 3 | 0.0227 | 0.6 | 5.66 | 0.012 | — | None / 7.2 | 2.03–12.0 | gen02, gen03, gen04 |
| Dispatcher_4 → Substation_10 | 5 | 0.0379 | 0.714 | 5.55 | 0.001 | MANAGES | None / 5.27 | 2.75–10.15 | gen01, gen05, gen07 |
| Dispatcher_3 → Substation_5 | 6 | 0.0455 | 1.0 | 5.5 | 0.001 | MANAGES | 3.6 / 6.86 | 4.26–8.8 | gen01, gen05, gen07, kb15 |
| Dispatcher_6 → Substation_6 | 4 | 0.0303 | 0.667 | 5.5 | 0.004 | MANAGES | None / 6.4 | 2.57–10.0 | gen01, gen05, gen07 |
| Consumer_5009 → Substation_5 | 3 | 0.0227 | 1.0 | 5.5 | 0.008 | — | 3.6 / 6.86 | 4.0–8.25 | gen03, gen04, kb15 |
| Consumer_5031 → Substation_5 | 3 | 0.0227 | 1.0 | 5.5 | 0.006 | — | 3.6 / 6.86 | 4.0–8.25 | gen03, gen04, kb15 |
| Dispatcher_4 → Substation_1 | 5 | 0.0379 | 0.714 | 4.96 | 0.002 | MANAGES | None / 6.23 | 2.44–8.46 | gen01, gen05, gen07 |
| Dispatcher_2 → ForecastModel_LSTM2 | 5 | 0.0379 | 0.625 | 4.85 | 0.002 | — | 4.5 / 6.1 | 2.2–8.8 | gen01, gen05, kb15 |
| Dispatcher_2 → Substation_11 | 5 | 0.0379 | 0.625 | 4.58 | 0.002 | MANAGES | 5.14 / 4.99 | 2.2–8.25 | gen01, gen05, gen07, kb15 |
| Consumer_3310 → Substation_5 | 5 | 0.0379 | 0.833 | 4.58 | 0.002 | CONNECTED_TO | 2.7 / 6.86 | 2.48–7.33 | gen03, gen04, kb12, kb14, kb15 |
| VAR → TEMPERATURE | 3 | 0.0227 | 0.75 | 4.5 | 0.019 | — | 4.0 / 6.0 | 2.1–8.25 | gen02, kb02, kb04 |
| Meter_AMI77410 → Substation_5 | 5 | 0.0379 | 0.714 | 3.93 | 0.002 | — | 1.8 / 6.86 | 1.96–6.29 | gen02, gen03, gen04, kb14, kb15 |
