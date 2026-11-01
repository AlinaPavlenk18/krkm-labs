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
1. Лише те, що прямо сказано у фрагменті; нічого не домислюй і не виводь за ланцюжком.
2. Сутність — лише з ЯВНИМ номером або кодом у тексті (№7, №3310, AMI-77410, LSTM №2, диспетчер №4) або назвою
   зі словника. «Диспетчер», «5 диспетчерів», «43 лічильники» — НЕ сутності. Не вигадуй номерів.
3. «text» — найкоротша дослівна згадка з фрагмента з тим самим регістром: «№9», «AMI-77410», «LSTM №2», «Закарпатській області».
4. «evidence» — КОРОТКИЙ дослівний підрядок фрагмента (до 15 слів), у якому названо обидві сутності
   (або одну, якщо друга — підмет із заголовка розділу). Не переписуй цілі абзаци.
5. Номер без слова «підстанція» в ланцюзі живлення — це підстанція. Номери в переліку після «моделі LSTM:» — моделі.
6. Підмет із заголовка розділу (## Підстанція №7, ## Модель VAR №1) вважається названим у реченнях розділу.
7. Значення (похибки, точність, кВт, дати, адреси) не є сутностями; METRIC — лише назви метрик (MAE, MAPE…).

ТИПОВІ ПОМИЛКИ — НЕ РОБИ ТАК:
- «аварія на підстанції №1 зачіпає №4 на глибині 2», «на глибині 2 від №1 розташована №4» — це НЕ FEEDS(№1, №4).
- «Модель ARIMA №1 прогнозує …» — це НЕ INSTANCE_OF (назва моделі не є твердженням про тип); INSTANCE_OF лише «типу ARIMA» або «моделі LSTM: №1, №2».
- «Регламент поширюється на всіх диспетчерів» — це НЕ MANAGES (немає конкретного диспетчера і підстанції).
- «тимчасово події на №9 обробляє диспетчер №5» — це НЕ MANAGES.

ПРИКЛАД
Фрагмент:
## Ланцюги живлення
Магістральна підстанція №1 (Львівська область, 2500 кВт) живить підстанції №10, №2 і №7. Далі №10 живить №4, а №4 — №6.
Відповідь:
{"entities": [{"type": "SUBSTATION", "id": "Substation_1", "text": "№1"}, {"type": "REGION", "id": "Region_Lviv", "text": "Львівська область"}, {"type": "SUBSTATION", "id": "Substation_10", "text": "№10"}, {"type": "SUBSTATION", "id": "Substation_2", "text": "№2"}, {"type": "SUBSTATION", "id": "Substation_7", "text": "№7"}, {"type": "SUBSTATION", "id": "Substation_4", "text": "№4"}, {"type": "SUBSTATION", "id": "Substation_6", "text": "№6"}],
 "relations": [{"type": "LOCATED_IN", "head": "Substation_1", "tail": "Region_Lviv", "evidence": "підстанція №1 (Львівська область"}, {"type": "FEEDS", "head": "Substation_1", "tail": "Substation_10", "evidence": "№1 (Львівська область, 2500 кВт) живить підстанції №10"}, {"type": "FEEDS", "head": "Substation_1", "tail": "Substation_2", "evidence": "№1 (Львівська область, 2500 кВт) живить підстанції №10, №2"}, {"type": "FEEDS", "head": "Substation_1", "tail": "Substation_7", "evidence": "№1 (Львівська область, 2500 кВт) живить підстанції №10, №2 і №7"}, {"type": "FEEDS", "head": "Substation_10", "tail": "Substation_4", "evidence": "Далі №10 живить №4"}, {"type": "FEEDS", "head": "Substation_4", "tail": "Substation_6", "evidence": "а №4 — №6"}]}
