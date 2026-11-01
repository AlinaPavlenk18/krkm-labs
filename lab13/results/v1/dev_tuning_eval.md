### llm_dev.jsonl · dev

| Зріз | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| ALL | 0.904 | 0.774 | 0.834 | 113 | 12 | 33 |
| ENTITIES | 0.955 | 0.736 | 0.831 | 64 | 3 | 23 |
| RELATIONS | 0.845 | 0.831 | 0.838 | 49 | 9 | 10 |
| articles | 0.821 | 0.786 | 0.803 | 55 | 12 | 15 |
| registers | 1.000 | 0.763 | 0.866 | 58 | 0 | 18 |
| articles·RELATIONS | 0.700 | 0.840 | 0.764 | 21 | 9 | 4 |
| registers·RELATIONS | 1.000 | 0.824 | 0.903 | 28 | 0 | 6 |
| CONNECTED_TO | 0.000 | 0.000 | 0.000 | 0 | 0 | 4 |
| CONSUMER | 1.000 | 0.400 | 0.571 | 2 | 0 | 3 |
| DISPATCHER | 0.667 | 1.000 | 0.800 | 6 | 3 | 0 |
| FEEDS | 0.833 | 1.000 | 0.909 | 10 | 2 | 0 |
| FORECASTS_FOR | 0.947 | 0.818 | 0.878 | 18 | 1 | 4 |
| HAS_METER | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |
| INSTANCE_OF | 0.778 | 0.778 | 0.778 | 7 | 2 | 2 |
| LOCATED_IN | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| MANAGES | 0.733 | 1.000 | 0.846 | 11 | 4 | 0 |
| METER | 1.000 | 0.250 | 0.400 | 1 | 0 | 3 |
| METHOD | 1.000 | 0.444 | 0.615 | 4 | 0 | 5 |
| MODEL | 1.000 | 0.692 | 0.818 | 9 | 0 | 4 |
| REGION | 0.000 | 0.000 | 0.000 | 0 | 0 | 2 |
| SUBSTATION | 1.000 | 0.913 | 0.955 | 42 | 0 | 4 |
| WEATHER_FACTOR | 0.000 | 0.000 | 0.000 | 0 | 0 | 2 |
FP приклади: [('kb02', 'R', 'INSTANCE_OF', 'ForecastModel_ARIMA1', 'ARIMA'), ('kb02', 'R', 'INSTANCE_OF', 'ForecastModel_GRU1', 'GRU'), ('kb05', 'E', 'DISPATCHER', 'Dispatcher_5'), ('kb05', 'R', 'FORECASTS_FOR', 'ForecastModel_GRU1', 'Substation_7'), ('kb06', 'E', 'DISPATCHER', 'Dispatcher_1'), ('kb06', 'E', 'DISPATCHER', 'Dispatcher_2'), ('kb06', 'R', 'FEEDS', 'Substation_1', 'Substation_4'), ('kb06', 'R', 'MANAGES', 'Dispatcher_1', 'Substation_11')]
FN приклади: [('gen02', 'E', 'METER', 'Meter_AMI27192'), ('gen02', 'E', 'METER', 'Meter_AMI66829'), ('gen02', 'E', 'METER', 'Meter_AMI77410'), ('gen02', 'E', 'METHOD', 'ARIMA'), ('gen02', 'E', 'METHOD', 'GRU'), ('gen02', 'E', 'METHOD', 'LSTM'), ('gen02', 'E', 'METHOD', 'VAR'), ('gen02', 'E', 'MODEL', 'ForecastModel_LSTM1')]

### llm_dev_replay_validator_v2.jsonl · dev

| Зріз | P | R | F1 | TP | FP | FN |
|---|---|---|---|---|---|---|
| ALL | 0.969 | 0.856 | 0.909 | 125 | 4 | 21 |
| ENTITIES | 1.000 | 0.839 | 0.912 | 73 | 0 | 14 |
| RELATIONS | 0.929 | 0.881 | 0.904 | 52 | 4 | 7 |
| articles | 0.937 | 0.843 | 0.887 | 59 | 4 | 11 |
| registers | 1.000 | 0.868 | 0.930 | 66 | 0 | 10 |
| articles·RELATIONS | 0.846 | 0.880 | 0.863 | 22 | 4 | 3 |
| registers·RELATIONS | 1.000 | 0.882 | 0.938 | 30 | 0 | 4 |
| CONNECTED_TO | 1.000 | 0.250 | 0.400 | 1 | 0 | 3 |
| CONSUMER | 1.000 | 0.400 | 0.571 | 2 | 0 | 3 |
| DISPATCHER | 1.000 | 1.000 | 1.000 | 6 | 0 | 0 |
| FEEDS | 0.833 | 1.000 | 0.909 | 10 | 2 | 0 |
| FORECASTS_FOR | 1.000 | 0.818 | 0.900 | 18 | 0 | 4 |
| HAS_METER | 1.000 | 1.000 | 1.000 | 1 | 0 | 0 |
| INSTANCE_OF | 0.818 | 1.000 | 0.900 | 9 | 2 | 0 |
| LOCATED_IN | 1.000 | 1.000 | 1.000 | 2 | 0 | 0 |
| MANAGES | 1.000 | 1.000 | 1.000 | 11 | 0 | 0 |
| METER | 1.000 | 0.250 | 0.400 | 1 | 0 | 3 |
| METHOD | 1.000 | 0.667 | 0.800 | 6 | 0 | 3 |
| MODEL | 1.000 | 1.000 | 1.000 | 13 | 0 | 0 |
| REGION | 1.000 | 0.500 | 0.667 | 1 | 0 | 1 |
| SUBSTATION | 1.000 | 0.957 | 0.978 | 44 | 0 | 2 |
| WEATHER_FACTOR | 0.000 | 0.000 | 0.000 | 0 | 0 | 2 |
FP приклади: [('kb02', 'R', 'INSTANCE_OF', 'ForecastModel_ARIMA1', 'ARIMA'), ('kb02', 'R', 'INSTANCE_OF', 'ForecastModel_GRU1', 'GRU'), ('kb06', 'R', 'FEEDS', 'Substation_1', 'Substation_4'), ('kb12', 'R', 'FEEDS', 'Substation_1', 'Substation_4')]
FN приклади: [('gen02', 'E', 'METER', 'Meter_AMI27192'), ('gen02', 'E', 'METER', 'Meter_AMI66829'), ('gen02', 'E', 'METER', 'Meter_AMI77410'), ('gen02', 'E', 'METHOD', 'ARIMA'), ('gen02', 'E', 'METHOD', 'GRU'), ('gen02', 'E', 'WEATHER_FACTOR', 'TEMPERATURE'), ('gen02', 'R', 'FORECASTS_FOR', 'ForecastModel_LSTM3', 'Substation_1'), ('gen02', 'R', 'FORECASTS_FOR', 'ForecastModel_LSTM3', 'Substation_6')]

