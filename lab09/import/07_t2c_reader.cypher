// ЛР9 · Результат 5 · C3. Окремий користувач лише для читання для text-to-Cypher.
// Виконувати в базі system (Neo4j Browser: :use system). Ролі доступні в Enterprise Edition
// (локальні БД Neo4j Desktop). Пароль задайте свій і НЕ зберігайте його в репозиторії.
CREATE USER t2c_reader IF NOT EXISTS SET PASSWORD $t2cPassword CHANGE NOT REQUIRED;
GRANT ROLE reader TO t2c_reader;
SHOW USER t2c_reader PRIVILEGES;
// Перевірка: від імені t2c_reader запит  CREATE (:Substation {id:'X'})  має завершитися помилкою
//   Neo.ClientError.Security.Forbidden: Create node with labels 'Substation' on database 'neo4j' is not allowed for user 't2c_reader' ...