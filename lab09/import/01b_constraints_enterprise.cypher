// НЕОБОВ'ЯЗКОВО. Обмеження існування та типу властивостей доступні лише в Enterprise Edition
// Відповідають обмеженням SHACL з ЛР8 (SubstationShape: nominalCapacity minCount 1, xsd:double).
CREATE CONSTRAINT substation_capacity_exists IF NOT EXISTS FOR (s:Substation) REQUIRE s.nominalCapacity IS NOT NULL;
CREATE CONSTRAINT substation_capacity_type   IF NOT EXISTS FOR (s:Substation) REQUIRE s.nominalCapacity IS :: FLOAT;
