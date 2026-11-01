# Сирий вихід LLM (СР12)

- дата: 2026-10-31T12:30:48
- модель: qwen2.5:7b
- параметри: temperature 0, seed 42, num_ctx 8192, num_predict 2000
- підказка: prompts/schema_v1.md
- токени: 612 вхід / 867 вихід; час 95.8 с

---

### 1) Зерно таблиці фактів
Таблиця фактів буде містити інформацію про фактичне споживання електроенергії, прогнози моделей VAR та LSTM, а також інформацію про версію моделі, дату навчання та точність прогнозу.

### 2) Виміри з атрибутами та ієрархіями
- **Дата**: дата прогнозу та фактичного споживання
- **Підстанція**: ID підстанції, назва підстанції, область
- **Модель**: ID моделі (VAR або LSTM), назва моделі
- **Версія**: версія моделі
- **Дата навчання**: дата останнього навчання моделі
- **Точність**: точність прогнозу (WAPE)

### 3) Міри з одиницями і типом адитивності
- **WAPE**: одиниці споживання електроенергії (кВт*год), адитивна
- **Абсолютна похибка**: одиниці споживання електроенергії (кВт*год), адитивна

### 4) Політика SCD для кожного виміру
- **Дата**: не змінюється
- **Підстанція**: не змінюється
- **Модель**: не змінюється
- **Версія**: нова версія замінює попередню
- **Дата навчання**: нова дата замінює попередню
- **Точність**: нова точність замінює попередню

### 5) DDL для DuckDB

```sql
CREATE TABLE Fact_Electricity_Prediction (
    FactID BIGINT PRIMARY KEY,
    Date DATE NOT NULL,
    SubstationID INTEGER NOT NULL,
    SubstationName TEXT NOT NULL,
    Region TEXT NOT NULL,
    ModelID INTEGER NOT NULL,
    ModelName TEXT NOT NULL,
    Version TEXT NOT NULL,
    TrainingDate DATE NOT NULL,
    ActualConsumption INTEGER NOT NULL,
    VARPrediction INTEGER,
    LSTMPrediction INTEGER,
    WAPE VARBINARY, -- Store WAPE as binary to handle decimal precision
    AbsoluteError INTEGER
);

-- Example of a foreign key constraint (assuming there are separate tables for Substations, Models, and Regions)
CREATE TABLE Substations (
    SubstationID INTEGER PRIMARY KEY,
    SubstationName TEXT NOT NULL,
    Region TEXT NOT NULL
);

CREATE TABLE Models (
    ModelID INTEGER PRIMARY KEY,
    ModelName TEXT NOT NULL
);

CREATE TABLE Regions (
    Region TEXT PRIMARY KEY
);

-- Example of a foreign key constraint
ALTER TABLE Fact_Electricity_Prediction
ADD CONSTRAINT FK_Substation
FOREIGN KEY (SubstationID) REFERENCES Substations(SubstationID);

ALTER TABLE Fact_Electricity_Prediction
ADD CONSTRAINT FK_Model
FOREIGN KEY (ModelID) REFERENCES Models(ModelID);

ALTER TABLE Fact_Electricity_Prediction
ADD CONSTRAINT FK_Region
FOREIGN KEY (Region) REFERENCES Regions(Region);
```

Ця схема дозволяє зберігати інформацію про фактичне споживання, прогнози моделей VAR та LSTM, а також інформацію про версію моделі, дату навчання та точність прогнозу.
