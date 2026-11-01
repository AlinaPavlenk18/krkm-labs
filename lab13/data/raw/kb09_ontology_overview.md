---
doc_id: kb09
title: Онтологія предметної області та її перенесення в граф знань
type: kb_article
date: 2026-10-12
sensitivity: public
source_url: https://github.com/AlinaPavlenk18/krkm-labs/blob/main/lab10/data/raw/kb/kb09_ontology_overview.md
license: CC BY 4.0 (Павленко А. С.)
---

# Онтологія предметної області та її перенесення в граф знань

Стаття підсумовує, як знання про прогнозування енергоспоживання формалізовано в онтології OWL (ЛР6–ЛР8) і як їх перенесено у графову базу Neo4j (ЛР9).

## Простір імен

Онтологія використовує IRI http://www.semanticweb.org/energy-forecasting# з префіксом «:». Онтологію створено в Protégé, наповнено індивідами в ЛР6, формалізовано в ЛР7 і завантажено в RDF-сховище Apache Jena Fuseki в ЛР8.

## Класи

Основні класи: Consumer (з підкласами ResidentialConsumer, CommercialConsumer, IndustrialConsumer), Meter, Measurement, WeatherCondition, ForecastModel (з підкласами StatisticalModel і MachineLearningModel), Forecast, Dispatcher і Substation. Виведені класи ManagedSubstation (підстанція, що має диспетчера) і OverloadedSubstation (завантаження ≥ 85 %) визначено в ЛР8.

## Об'єктні властивості

Ключові об'єктні властивості: hasMeter і обернена belongsToConsumer, connectedToSubstation і обернена servesConsumer, measuredByMeter, influencesMeasurement, influencesModel, trainedOnMeasurement, generatedByModel, usesForecast, managedByDispatcher, а також транзитивні upstreamOf і downstreamOf, що описують ланцюг живлення.

## Властивості даних

Властивості даних описують атомарні значення: currentLoad і nominalCapacity підстанції, region (назва області рядком), meterStatus лічильника, accuracy моделі, errorPercentage прогнозу, consumptionValue і voltage вимірювання.

## Компетентнісні питання

Онтологію перевірено вісьмома компетентнісними питаннями KQ1–KQ8 (споживачі підстанції, перевантажені підстанції, навантаження за регіонами, несправні лічильники, модель прогнозу, прогноз з найбільшою похибкою, погода в навчальних даних моделі, прогнози й підстанції диспетчера). У ЛР9 додано KQ9 (наслідки аварії підстанції) і KQ10 (прогнози, скомпрометовані несправними лічильниками).

## Зовнішні словники

У ЛР8 онтологію вирівняно з FOAF (диспетчер як foaf:Person), schema.org, PROV-O (походження прогнозу), SKOS (класифікатор категорій споживачів) і Dublin Core (метадані набору даних). У графі властивостей ці зв'язки не переносяться, бо в LPG немає глобальних IRI.

## Перенесення в граф властивостей

Під час перенесення в Neo4j класи стали мітками вузлів, підкласи — додатковими мітками, а рядкова властивість region — окремими вузлами Region. Кожну пару обернених властивостей замінено одним напрямленим зв'язком, бо в Cypher зв'язок обходиться в обидва боки. Транзитивну upstreamOf замінено зв'язком FEEDS і шляхом змінної довжини [:FEEDS*1..]. Виведений клас ManagedSubstation не матеріалізується, а виражається шаблоном запиту.

## Схема графа

Граф ЛР9 містить 9 основних міток (Consumer, Meter, Measurement, WeatherCondition, ForecastModel, Forecast, Dispatcher, Substation, Region) і 12 типів зв'язків: HAS_METER, CONNECTED_TO, RECORDED, INFLUENCES, AFFECTS_MODEL, TRAINED_ON, GENERATED, USES_FORECAST, MANAGES, FEEDS, LOCATED_IN і новий FORECAST_FOR. Після імпорту граф має 190 вузлів і 314 зв'язків.

## Що втрачається при перенесенні

У графі властивостей немає reasoner'а, тому виведення підкласів, обернених і транзитивних властивостей потрібно робити під час імпорту або в запиті. Кардинальності (наприклад, «рівно один диспетчер») перевіряються окремими запитами, а не обмеженнями схеми.

## Роль векторного індексу

Онтологія і граф відповідають на структуровані питання, але не на питання, сформульовані довільно і відповідь на які міститься в текстових документах: регламентах, картках моделей, журналах. Для них у ЛР10 будується векторне сховище з гібридним пошуком, а обрана конфігурація пошуку стане основою для ЛР11.
