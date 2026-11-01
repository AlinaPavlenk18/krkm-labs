# Нормалізація та entity linking (ЛР13, результат 5)

Сутностей після нормалізації: 131; зв'язано з вузлами графа ЛР9: 114, з термінами онтології ЛР8: 8, нових вузлів: 9.

## Правила

1. Нормалізація — `src/schema.py::canonical()` (таблиця в `docs/extraction_schema.md`, розділ 5).
2. Канонічний ID збігається з `id` вузла графа ЛР9 → зв'язок `SAME_AS` з вузлом ЛР9.
3. Методи прогнозування → клас онтології ЛР8 (`broader`): ARIMA, SARIMA, VAR → `:StatisticalModel`; LSTM, GRU → `:MachineLearningModel`.
4. Погодні змінні → властивість онтології (`exactMatch`), якщо вона є: температура → `:temperature`, хмарність → `:cloudCover`.
5. MAPE → `closeMatch :errorPercentage` (у базі знань похибка прогнозу — відносна, як у MAPE).
6. Немає відповідника в ЛР8/ЛР9 → новий вузол `XEntity` без зв'язку (рішення: не вигадувати IRI).

## Рішення щодо граничних випадків

- «№1» у переліку «моделі LSTM: №1, №2 і №3» → `ForecastModel_LSTM1` (не підстанція).
- «Consumer_5019» у проєктному документі та «споживач №5019» — одна сутність `Consumer_5019`.
- «Закарпатській області», «Закарпатська область» → `Region_Zakarpattia`; «закарпатські підстанції» не зв'язуються.
- Вологість, вітер, HDD, CDD, MAE, RMSE, sMAPE, WAPE, pinball loss — нові вузли (у ЛР8 немає; kb04 називає це прогалиною).

## Таблиця зв'язування

| Тип | Канонічний ID | Джерело зв'язку | Ціль | Вид |
|---|---|---|---|---|
| CONSUMER | Consumer_1002 | LR9 | Consumer_1002 | sameAs |
| CONSUMER | Consumer_3310 | LR9 | Consumer_3310 | sameAs |
| CONSUMER | Consumer_4521 | LR9 | Consumer_4521 | sameAs |
| CONSUMER | Consumer_5001 | LR9 | Consumer_5001 | sameAs |
| CONSUMER | Consumer_5002 | LR9 | Consumer_5002 | sameAs |
| CONSUMER | Consumer_5003 | LR9 | Consumer_5003 | sameAs |
| CONSUMER | Consumer_5004 | LR9 | Consumer_5004 | sameAs |
| CONSUMER | Consumer_5005 | LR9 | Consumer_5005 | sameAs |
| CONSUMER | Consumer_5006 | LR9 | Consumer_5006 | sameAs |
| CONSUMER | Consumer_5007 | LR9 | Consumer_5007 | sameAs |
| CONSUMER | Consumer_5008 | LR9 | Consumer_5008 | sameAs |
| CONSUMER | Consumer_5009 | LR9 | Consumer_5009 | sameAs |
| CONSUMER | Consumer_5010 | LR9 | Consumer_5010 | sameAs |
| CONSUMER | Consumer_5011 | LR9 | Consumer_5011 | sameAs |
| CONSUMER | Consumer_5012 | LR9 | Consumer_5012 | sameAs |
| CONSUMER | Consumer_5013 | LR9 | Consumer_5013 | sameAs |
| CONSUMER | Consumer_5014 | LR9 | Consumer_5014 | sameAs |
| CONSUMER | Consumer_5015 | LR9 | Consumer_5015 | sameAs |
| CONSUMER | Consumer_5016 | LR9 | Consumer_5016 | sameAs |
| CONSUMER | Consumer_5017 | LR9 | Consumer_5017 | sameAs |
| CONSUMER | Consumer_5018 | LR9 | Consumer_5018 | sameAs |
| CONSUMER | Consumer_5019 | LR9 | Consumer_5019 | sameAs |
| CONSUMER | Consumer_5020 | LR9 | Consumer_5020 | sameAs |
| CONSUMER | Consumer_5021 | LR9 | Consumer_5021 | sameAs |
| CONSUMER | Consumer_5022 | LR9 | Consumer_5022 | sameAs |
| CONSUMER | Consumer_5023 | LR9 | Consumer_5023 | sameAs |
| CONSUMER | Consumer_5024 | LR9 | Consumer_5024 | sameAs |
| CONSUMER | Consumer_5025 | LR9 | Consumer_5025 | sameAs |
| CONSUMER | Consumer_5026 | LR9 | Consumer_5026 | sameAs |
| CONSUMER | Consumer_5027 | LR9 | Consumer_5027 | sameAs |
| CONSUMER | Consumer_5028 | LR9 | Consumer_5028 | sameAs |
| CONSUMER | Consumer_5029 | LR9 | Consumer_5029 | sameAs |
| CONSUMER | Consumer_5030 | LR9 | Consumer_5030 | sameAs |
| CONSUMER | Consumer_5031 | LR9 | Consumer_5031 | sameAs |
| CONSUMER | Consumer_5032 | LR9 | Consumer_5032 | sameAs |
| CONSUMER | Consumer_5033 | LR9 | Consumer_5033 | sameAs |
| CONSUMER | Consumer_5034 | LR9 | Consumer_5034 | sameAs |
| CONSUMER | Consumer_5035 | LR9 | Consumer_5035 | sameAs |
| CONSUMER | Consumer_5036 | LR9 | Consumer_5036 | sameAs |
| CONSUMER | Consumer_5037 | LR9 | Consumer_5037 | sameAs |
| CONSUMER | Consumer_5038 | LR9 | Consumer_5038 | sameAs |
| DISPATCHER | Dispatcher_1 | LR9 | Dispatcher_1 | sameAs |
| DISPATCHER | Dispatcher_2 | LR9 | Dispatcher_2 | sameAs |
| DISPATCHER | Dispatcher_3 | LR9 | Dispatcher_3 | sameAs |
| DISPATCHER | Dispatcher_4 | LR9 | Dispatcher_4 | sameAs |
| DISPATCHER | Dispatcher_5 | LR9 | Dispatcher_5 | sameAs |
| DISPATCHER | Dispatcher_6 | LR9 | Dispatcher_6 | sameAs |
| METER | Meter_AMI10452 | LR9 | Meter_AMI10452 | sameAs |
| METER | Meter_AMI20916 | LR9 | Meter_AMI20916 | sameAs |
| METER | Meter_AMI22890 | LR9 | Meter_AMI22890 | sameAs |
| METER | Meter_AMI24755 | LR9 | Meter_AMI24755 | sameAs |
| METER | Meter_AMI26032 | LR9 | Meter_AMI26032 | sameAs |
| METER | Meter_AMI27192 | LR9 | Meter_AMI27192 | sameAs |
| METER | Meter_AMI29583 | LR9 | Meter_AMI29583 | sameAs |
| METER | Meter_AMI32391 | LR9 | Meter_AMI32391 | sameAs |
| METER | Meter_AMI33496 | LR9 | Meter_AMI33496 | sameAs |
| METER | Meter_AMI35297 | LR9 | Meter_AMI35297 | sameAs |
| METER | Meter_AMI36309 | LR9 | Meter_AMI36309 | sameAs |
| METER | Meter_AMI37120 | LR9 | Meter_AMI37120 | sameAs |
| METER | Meter_AMI38856 | LR9 | Meter_AMI38856 | sameAs |
| METER | Meter_AMI40161 | LR9 | Meter_AMI40161 | sameAs |
| METER | Meter_AMI42574 | LR9 | Meter_AMI42574 | sameAs |
| METER | Meter_AMI44704 | LR9 | Meter_AMI44704 | sameAs |
| METER | Meter_AMI45618 | LR9 | Meter_AMI45618 | sameAs |
| METER | Meter_AMI46646 | LR9 | Meter_AMI46646 | sameAs |
| METER | Meter_AMI49003 | LR9 | Meter_AMI49003 | sameAs |
| METER | Meter_AMI50424 | LR9 | Meter_AMI50424 | sameAs |
| METER | Meter_AMI52953 | LR9 | Meter_AMI52953 | sameAs |
| METER | Meter_AMI55149 | LR9 | Meter_AMI55149 | sameAs |
| METER | Meter_AMI57366 | LR9 | Meter_AMI57366 | sameAs |
| METER | Meter_AMI58264 | LR9 | Meter_AMI58264 | sameAs |
| METER | Meter_AMI58679 | LR9 | Meter_AMI58679 | sameAs |
| METER | Meter_AMI59779 | LR9 | Meter_AMI59779 | sameAs |
| METER | Meter_AMI60407 | LR9 | Meter_AMI60407 | sameAs |
| METER | Meter_AMI61552 | LR9 | Meter_AMI61552 | sameAs |
| METER | Meter_AMI62024 | LR9 | Meter_AMI62024 | sameAs |
| METER | Meter_AMI64551 | LR9 | Meter_AMI64551 | sameAs |
| METER | Meter_AMI66829 | LR9 | Meter_AMI66829 | sameAs |
| METER | Meter_AMI68034 | LR9 | Meter_AMI68034 | sameAs |
| METER | Meter_AMI69457 | LR9 | Meter_AMI69457 | sameAs |
| METER | Meter_AMI70681 | LR9 | Meter_AMI70681 | sameAs |
| METER | Meter_AMI71354 | LR9 | Meter_AMI71354 | sameAs |
| METER | Meter_AMI74134 | LR9 | Meter_AMI74134 | sameAs |
| METER | Meter_AMI76143 | LR9 | Meter_AMI76143 | sameAs |
| METER | Meter_AMI76577 | LR9 | Meter_AMI76577 | sameAs |
| METER | Meter_AMI77410 | LR9 | Meter_AMI77410 | sameAs |
| METER | Meter_AMI78591 | LR9 | Meter_AMI78591 | sameAs |
| METER | Meter_AMI80930 | LR9 | Meter_AMI80930 | sameAs |
| METER | Meter_AMI81841 | LR9 | Meter_AMI81841 | sameAs |
| METER | Meter_AMI99231 | LR9 | Meter_AMI99231 | sameAs |
| METHOD | ARIMA | LR8 | http://www.semanticweb.org/energy-forecasting#StatisticalModel | broader |
| METHOD | GRU | LR8 | http://www.semanticweb.org/energy-forecasting#MachineLearningModel | broader |
| METHOD | LSTM | LR8 | http://www.semanticweb.org/energy-forecasting#MachineLearningModel | broader |
| METHOD | SARIMA | LR8 | http://www.semanticweb.org/energy-forecasting#StatisticalModel | broader |
| METHOD | VAR | LR8 | http://www.semanticweb.org/energy-forecasting#StatisticalModel | broader |
| METRIC | MAE | — |  | новий вузол |
| METRIC | MAPE | LR8 | http://www.semanticweb.org/energy-forecasting#errorPercentage | closeMatch |
| METRIC | PINBALL | — |  | новий вузол |
| METRIC | RMSE | — |  | новий вузол |
| METRIC | WAPE | — |  | новий вузол |
| METRIC | sMAPE | — |  | новий вузол |
| MODEL | ForecastModel_ARIMA1 | LR9 | ForecastModel_ARIMA1 | sameAs |
| MODEL | ForecastModel_GRU1 | LR9 | ForecastModel_GRU1 | sameAs |
| MODEL | ForecastModel_LSTM1 | LR9 | ForecastModel_LSTM1 | sameAs |
| MODEL | ForecastModel_LSTM2 | LR9 | ForecastModel_LSTM2 | sameAs |
| MODEL | ForecastModel_LSTM3 | LR9 | ForecastModel_LSTM3 | sameAs |
| MODEL | ForecastModel_VAR1 | LR9 | ForecastModel_VAR1 | sameAs |
| REGION | Region_IvanoFrankivsk | LR9 | Region_IvanoFrankivsk | sameAs |
| REGION | Region_Lviv | LR9 | Region_Lviv | sameAs |
| REGION | Region_Rivne | LR9 | Region_Rivne | sameAs |
| REGION | Region_Ternopil | LR9 | Region_Ternopil | sameAs |
| REGION | Region_Volyn | LR9 | Region_Volyn | sameAs |
| REGION | Region_Zakarpattia | LR9 | Region_Zakarpattia | sameAs |
| SUBSTATION | Substation_1 | LR9 | Substation_1 | sameAs |
| SUBSTATION | Substation_10 | LR9 | Substation_10 | sameAs |
| SUBSTATION | Substation_11 | LR9 | Substation_11 | sameAs |
| SUBSTATION | Substation_12 | LR9 | Substation_12 | sameAs |
| SUBSTATION | Substation_2 | LR9 | Substation_2 | sameAs |
| SUBSTATION | Substation_3 | LR9 | Substation_3 | sameAs |
| SUBSTATION | Substation_4 | LR9 | Substation_4 | sameAs |
| SUBSTATION | Substation_5 | LR9 | Substation_5 | sameAs |
| SUBSTATION | Substation_6 | LR9 | Substation_6 | sameAs |
| SUBSTATION | Substation_7 | LR9 | Substation_7 | sameAs |
| SUBSTATION | Substation_8 | LR9 | Substation_8 | sameAs |
| SUBSTATION | Substation_9 | LR9 | Substation_9 | sameAs |
| WEATHER_FACTOR | CDD | — |  | новий вузол |
| WEATHER_FACTOR | CLOUD_COVER | LR8 | http://www.semanticweb.org/energy-forecasting#cloudCover | exactMatch |
| WEATHER_FACTOR | HDD | — |  | новий вузол |
| WEATHER_FACTOR | HUMIDITY | — |  | новий вузол |
| WEATHER_FACTOR | TEMPERATURE | LR8 | http://www.semanticweb.org/energy-forecasting#temperature | exactMatch |
| WEATHER_FACTOR | WIND | — |  | новий вузол |
