"""Схема витягу: закритий словник типів сутностей і відношень, канонічні ідентифікатори, нормалізація."""
import re

ENTITY_TYPES = ["SUBSTATION", "CONSUMER", "METER", "MODEL", "DISPATCHER", "REGION",
                "METHOD", "METRIC", "WEATHER_FACTOR"]
# тип відношення: (тип голови, тип хвоста)
RELATION_TYPES = {
    "FEEDS": ("SUBSTATION", "SUBSTATION"),
    "LOCATED_IN": ("SUBSTATION", "REGION"),
    "MANAGES": ("DISPATCHER", "SUBSTATION"),
    "CONNECTED_TO": ("CONSUMER", "SUBSTATION"),
    "HAS_METER": ("CONSUMER", "METER"),
    "FORECASTS_FOR": ("MODEL", "SUBSTATION"),
    "INSTANCE_OF": ("MODEL", "METHOD"),
}
REGIONS = {"Львівськ": "Region_Lviv", "Волинськ": "Region_Volyn", "Рівненськ": "Region_Rivne",
           "Тернопільськ": "Region_Ternopil", "Закарпатськ": "Region_Zakarpattia",
           "Івано-Франківськ": "Region_IvanoFrankivsk"}
METHODS = ["ARIMA", "SARIMA", "VAR", "LSTM", "GRU"]
METRICS = {"MAE": "MAE", "RMSE": "RMSE", "MAPE": "MAPE", "sMAPE": "sMAPE", "WAPE": "WAPE", "pinball loss": "PINBALL"}
WEATHER = {"температур": "TEMPERATURE", "хмарніст": "CLOUD_COVER", "вологіст": "HUMIDITY",
           "вітер": "WIND", "HDD": "HDD", "CDD": "CDD"}


PREFIX = {"SUBSTATION": "Substation_", "CONSUMER": "Consumer_", "METER": "Meter_", "MODEL": "ForecastModel_",
          "DISPATCHER": "Dispatcher_", "REGION": "Region_"}
ID_RE = {"SUBSTATION": r"Substation_\d{1,2}", "CONSUMER": r"Consumer_\d{4}", "METER": r"Meter_AMI\d{5}",
         "DISPATCHER": r"Dispatcher_\d{1,2}", "MODEL": r"ForecastModel_(ARIMA|SARIMA|VAR|LSTM|GRU)\d+"}


def canonical(etype: str, value: str) -> str | None:
    """Нормалізує поверхневу форму або ID до канонічного ID (як у графі ЛР9); None — якщо не відповідає типу."""
    v = value.strip()
    m = re.match(r"^([A-Za-z]+)_", v)
    if m and etype in PREFIX and not v.startswith(PREFIX[etype]):
        return None                                   # ID іншого типу (напр. Substation_5 як CONSUMER)
    cid = _canonical(etype, v)
    if cid and etype in ID_RE and not re.fullmatch(ID_RE[etype], cid):
        return None
    return cid


def _canonical(etype: str, v: str) -> str | None:
    num = re.search(r"(\d+)", v)
    if etype == "SUBSTATION" and num:
        return f"Substation_{int(num.group(1))}"
    if etype == "CONSUMER" and num:
        return f"Consumer_{num.group(1)}"
    if etype == "METER":
        m = re.search(r"(\d{5})", v)
        return f"Meter_AMI{m.group(1)}" if m else None
    if etype == "DISPATCHER" and num:
        return f"Dispatcher_{int(num.group(1))}"
    if etype == "MODEL":
        m = re.search(r"(ARIMA|SARIMA|VAR|LSTM|GRU)\D*?(\d+)", v, re.I)
        return f"ForecastModel_{m.group(1).upper()}{m.group(2)}" if m else None
    if etype == "REGION":
        if v.startswith("Region_"):
            return v
        for stem, rid in REGIONS.items():
            if stem.lower() in v.lower():
                return rid
        return None
    if etype == "METHOD":
        for m in sorted(METHODS, key=len, reverse=True):
            if m.lower() == v.lower() or v.upper().startswith(m):
                return m
        return None
    if etype == "METRIC":
        for k, cid in METRICS.items():
            if k.lower() == v.lower() or cid.lower() == v.lower():
                return cid
        return None
    if etype == "WEATHER_FACTOR":
        if v.upper() in WEATHER.values():
            return v.upper()
        for stem, cid in WEATHER.items():
            if stem.lower() in v.lower():
                return cid
        return None
    return None

DEV_DOCS = {"kb02", "kb05", "kb06", "kb12", "gen02", "gen07"}
