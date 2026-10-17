import re

LABELS = {"Consumer", "Residential", "Commercial", "Industrial", "Meter", "Measurement",
          "WeatherCondition", "ForecastModel", "MLModel", "StatisticalModel", "Forecast",
          "Dispatcher", "Substation", "Region"}
REL_TYPES = {"HAS_METER", "CONNECTED_TO", "RECORDED", "INFLUENCES", "AFFECTS_MODEL", "TRAINED_ON",
             "GENERATED", "USES_FORECAST", "MANAGES", "FEEDS", "LOCATED_IN", "FORECAST_FOR"}
PROPS = {"id", "name", "category", "contractLimit", "address", "status", "meterType", "readingInterval",
         "consumptionValue", "voltage", "timestamp", "temperature", "cloudCover", "modelType", "accuracy",
         "trainingDate", "forecastPeriod", "errorPercentage", "predictedConsumption", "qualification",
         "shift", "nominalCapacity", "currentLoad", "source", "pagerank", "community", "confidence",
         "validFrom"}

TEMPORAL_ACCESSORS = {"year", "month", "day", "hour", "minute", "second"}

FORBIDDEN = re.compile(
    r"\b(CREATE|MERGE|SET|DELETE|DETACH|REMOVE|DROP|FOREACH|LOAD\s+CSV|CALL\s+\w+\.|GRANT|REVOKE|ALTER)\b",
    re.IGNORECASE)
MAX_LIMIT = 100


class GuardError(Exception):
    pass


def _strip_strings(q):
    return re.sub(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"", "''", q)


def check(query):
    """Повертає (безпечний_запит, список_зауважень) або піднімає GuardError."""
    notes = []
    q = query.strip().rstrip(";")
    bare = _strip_strings(q)
    if ";" in bare:
        raise GuardError("кілька інструкцій в одному запиті")
    m = FORBIDDEN.search(bare)
    if m:
        raise GuardError(f"заборонена операція запису: {m.group(1).upper()}")

    for node in re.findall(r"\(([^()]*)\)", bare):
        for lab in re.findall(r":\s*`?([A-Za-z_]\w*)`?", node.split("{")[0]):
            if lab not in LABELS:
                raise GuardError(f"невідома мітка: {lab}")
    for rel in re.findall(r"\[([^\[\]]*)\]", bare):
        head = rel.split("{")[0]
        if ":" in head and "|" in head or re.search(r":\s*[A-Z_]", head):
            types = re.findall(r"[:|]\s*`?([A-Za-z_]\w*)`?", head)
            for t in types:
                if t not in REL_TYPES:
                    raise GuardError(f"невідомий тип зв'язку: {t}")
    for prop in re.findall(r"\b[a-zA-Z_]\w*\.([a-zA-Z_]\w*)\b", bare):
        if prop not in PROPS and prop not in TEMPORAL_ACCESSORS:
            raise GuardError(f"невідома властивість: {prop}")
    lim = re.search(r"\bLIMIT\s+(\d+)\s*$", bare, re.IGNORECASE)
    if not lim:
        q = q + f" LIMIT {MAX_LIMIT}"
        notes.append("додано LIMIT 100")
    elif int(lim.group(1)) > MAX_LIMIT:
        q = re.sub(r"\bLIMIT\s+\d+\s*$", f"LIMIT {MAX_LIMIT}", q, flags=re.IGNORECASE)
        notes.append("LIMIT зменшено до 100")
    return q, notes
