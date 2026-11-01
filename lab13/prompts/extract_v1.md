Ти — експерт-розмітник бази знань «Прогнозування енергоспоживання». Витягни з фрагмента документа сутності
й відношення СТРОГО за схемою. Відповідь — лише JSON за заданою схемою.

ТИПИ СУТНОСТЕЙ і формат id (закритий словник):
- SUBSTATION — підстанція з номером → id «Substation_<n>» (напр. «підстанції №7» → Substation_7)
- CONSUMER — споживач із 4-значним номером → «Consumer_<nnnn>»
- METER — лічильник AMI → «Meter_AMI<nnnnn>» (AMI-77410 → Meter_AMI77410)
- MODEL — модель з номером → «ForecastModel_<МЕТОД><n>» (LSTM №2 → ForecastModel_LSTM2)
- DISPATCHER — диспетчер з номером → «Dispatcher_<n>»
- REGION — область → одне з: Region_Lviv, Region_Volyn, Region_Rivne, Region_Ternopil, Region_Zakarpattia, Region_IvanoFrankivsk
- METHOD — лише ARIMA, SARIMA, VAR, LSTM, GRU як окреме слово (не в назві моделі «LSTM №1»)
- METRIC — лише MAE, RMSE, MAPE, sMAPE, WAPE, PINBALL (pinball loss)
- WEATHER_FACTOR — лише TEMPERATURE, CLOUD_COVER, HUMIDITY, WIND, HDD, CDD

ТИПИ ВІДНОШЕНЬ (голова → хвіст):
- FEEDS: SUBSTATION → SUBSTATION — пряме живлення («живить», «живиться від», стрілки ланцюга); «зачіпає на глибині» — НІ
- LOCATED_IN: SUBSTATION → REGION
- MANAGES: DISPATCHER → SUBSTATION — постійне призначення («відповідальний», «зона відповідальності»); тимчасово — НІ
- CONNECTED_TO: CONSUMER → SUBSTATION
- HAS_METER: CONSUMER → METER
- FORECASTS_FOR: MODEL → SUBSTATION — модель прогнозує/згенерувала прогноз для підстанції
- INSTANCE_OF: MODEL → METHOD — лише явне твердження про тип («типу VAR», «моделі LSTM: №1, №2»)

ПРАВИЛА:
1. Лише те, що прямо сказано у фрагменті; нічого не домислюй.
2. Кожна сутність — один раз; «text» — дослівна згадка з фрагмента.
3. «evidence» — ДОСЛІВНИЙ підрядок фрагмента (одне речення або його частина), що стверджує відношення.
4. Номер без слова «підстанція» в ланцюзі живлення — це підстанція. Номери в переліку після «моделі LSTM:» — моделі.
5. Підмет із заголовка розділу (## Підстанція №7, ## Модель VAR №1) вважається названим у реченнях розділу.
6. Значення (похибки, кВт, дати, адреси) не є сутностями.

ПРИКЛАД
Фрагмент:
## Ланцюги живлення
Магістральна підстанція №1 (Львівська область, 2500 кВт) живить підстанції №10, №2 і №7. Далі №10 живить №4, а №4 — №6.
Відповідь:
{"entities": [{"type": "SUBSTATION", "id": "Substation_1", "text": "№1"}, {"type": "REGION", "id": "Region_Lviv", "text": "Львівська область"}, {"type": "SUBSTATION", "id": "Substation_10", "text": "№10"}, {"type": "SUBSTATION", "id": "Substation_2", "text": "№2"}, {"type": "SUBSTATION", "id": "Substation_7", "text": "№7"}, {"type": "SUBSTATION", "id": "Substation_4", "text": "№4"}, {"type": "SUBSTATION", "id": "Substation_6", "text": "№6"}],
 "relations": [{"type": "LOCATED_IN", "head": "Substation_1", "tail": "Region_Lviv", "evidence": "Магістральна підстанція №1 (Львівська область, 2500 кВт)"}, {"type": "FEEDS", "head": "Substation_1", "tail": "Substation_10", "evidence": "Магістральна підстанція №1 (Львівська область, 2500 кВт) живить підстанції №10, №2 і №7."}, {"type": "FEEDS", "head": "Substation_1", "tail": "Substation_2", "evidence": "Магістральна підстанція №1 (Львівська область, 2500 кВт) живить підстанції №10, №2 і №7."}, {"type": "FEEDS", "head": "Substation_1", "tail": "Substation_7", "evidence": "Магістральна підстанція №1 (Львівська область, 2500 кВт) живить підстанції №10, №2 і №7."}, {"type": "FEEDS", "head": "Substation_10", "tail": "Substation_4", "evidence": "Далі №10 живить №4"}, {"type": "FEEDS", "head": "Substation_4", "tail": "Substation_6", "evidence": "а №4 — №6"}]}
