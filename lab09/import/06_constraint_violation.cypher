// ЛР9 · Результат 2 · Крок 4. Демонстрація порушення обмеження (запускати окремо, очікується ПОМИЛКА).

// 6.1 Спроба створити другу підстанцію з уже наявним id
CREATE (:Substation {id: 'Substation_7', name: 'Дублікат підстанції №7'});
// Очікувана відповідь сервера:
//   Neo.ClientError.Schema.ConstraintValidationFailed
//   Node(<id>) already exists with label `Substation` and property `id` = 'Substation_7'

// 6.2 Те саме через MERGE — помилки НЕМАЄ: MERGE знаходить наявний вузол (на цьому й побудована ідемпотентність)
MERGE (s:Substation {id: 'Substation_7'}) RETURN s.name, s.currentLoad;

// 6.3 (лише Enterprise, якщо виконано 01b) — порушення обмеження типу:
// CREATE (:Substation {id: 'Substation_99', nominalCapacity: 'багато'});
//   Neo.ClientError.Schema.ConstraintValidationFailed ... must be of type FLOAT
