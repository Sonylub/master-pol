-- Создание таблицы Users (для аутентификации)
CREATE TABLE IF NOT EXISTS Users (
    UserID SERIAL PRIMARY KEY,
    Username VARCHAR(50) UNIQUE NOT NULL,
    Password VARCHAR(255) NOT NULL,
    Email VARCHAR(100) UNIQUE,
    Role VARCHAR(20) NOT NULL DEFAULT 'partner',
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Создание таблиц (адаптировано для PostgreSQL)
CREATE TABLE IF NOT EXISTS Partners (
    PartnerID SERIAL PRIMARY KEY,
    Name VARCHAR(150) NOT NULL,
    LegalAddress VARCHAR(250),
    INN VARCHAR(12),
    DirectorFullName VARCHAR(150),
    Phone VARCHAR(20),
    Email VARCHAR(100),
    Rating DECIMAL(3,2),
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Managers (
    ManagerID SERIAL PRIMARY KEY,
    FullName VARCHAR(150) NOT NULL,
    Phone VARCHAR(20),
    Email VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Suppliers (
    SupplierID SERIAL PRIMARY KEY,
    Name VARCHAR(150) NOT NULL,
    INN VARCHAR(12),
    Phone VARCHAR(20),
    Email VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS Materials (
    MaterialID SERIAL PRIMARY KEY,
    Name VARCHAR(150) NOT NULL,
    Unit VARCHAR(20),
    Cost DECIMAL(10,2),
    QuantityInStock DECIMAL(10,2) DEFAULT 0,
    MinAllowedQuantity DECIMAL(10,2) DEFAULT 0
);

CREATE TABLE IF NOT EXISTS Supplies (
    SupplyID SERIAL PRIMARY KEY,
    SupplierID INTEGER NOT NULL REFERENCES Suppliers(SupplierID),
    MaterialID INTEGER NOT NULL REFERENCES Materials(MaterialID),
    ManagerID INTEGER NOT NULL REFERENCES Managers(ManagerID),
    Quantity DECIMAL(10,2) CHECK (Quantity > 0),
    SupplyDate TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS Products (
    ProductID SERIAL PRIMARY KEY,
    Name VARCHAR(150) NOT NULL,
    Description VARCHAR(255),
    StandardNumber VARCHAR(50),
    ManufactureTimeDays INTEGER,
    CostPrice DECIMAL(10,2),
    MinPartnerPrice DECIMAL(10,2),
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ProductComposition (
    ProductCompositionID SERIAL PRIMARY KEY,
    ProductID INTEGER NOT NULL REFERENCES Products(ProductID),
    MaterialID INTEGER NOT NULL REFERENCES Materials(MaterialID),
    Quantity DECIMAL(10,2) CHECK (Quantity > 0)
);

CREATE TABLE IF NOT EXISTS Requests (
    RequestID SERIAL PRIMARY KEY,
    PartnerID INTEGER NOT NULL REFERENCES Partners(PartnerID),
    ManagerID INTEGER NOT NULL REFERENCES Managers(ManagerID),
    ProductID INTEGER NOT NULL REFERENCES Products(ProductID),
    Quantity INTEGER CHECK (Quantity > 0),
    UnitPrice DECIMAL(10,2) CHECK (UnitPrice > 0),
    TotalPrice DECIMAL(10,2) GENERATED ALWAYS AS (Quantity * UnitPrice) STORED,
    CreatedAt TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    Status VARCHAR(50) DEFAULT 'Новая'
);

-- Функция расчёта скидки (адаптирована для PostgreSQL)
CREATE OR REPLACE FUNCTION fn_GetPartnerDiscount(p_partnerid INTEGER)
RETURNS DECIMAL(5,2)
LANGUAGE plpgsql
AS $$
DECLARE
    v_total_quantity INTEGER;
BEGIN
    SELECT COALESCE(SUM(Quantity), 0)
    INTO v_total_quantity
    FROM Requests
    WHERE PartnerID = p_partnerid AND Status = 'Выполнена';
    
    RETURN CASE
        WHEN v_total_quantity >= 1000 THEN 0.15
        WHEN v_total_quantity >= 500 THEN 0.10
        ELSE 0.05
    END;
END;
$$;

-- Функция расчёта материалов (адаптирована для PostgreSQL)
CREATE OR REPLACE FUNCTION fn_CalcRequiredMaterial(
    p_producttypeid INTEGER,
    p_materialid INTEGER,
    p_quantity INTEGER,
    p_param1 FLOAT,
    p_param2 FLOAT
)
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_defect_rate FLOAT := 0.1; -- 10% брака
    v_material_needed DECIMAL(10,2);
BEGIN
    IF p_producttypeid <= 0 OR p_materialid <= 0 OR p_quantity <= 0 OR p_param1 <= 0 OR p_param2 <= 0 THEN
        RETURN -1;
    END IF;
    
    SELECT COALESCE(SUM(pc.Quantity * p_quantity * p_param1 * p_param2 * (1 + v_defect_rate)), 0)
    INTO v_material_needed
    FROM ProductComposition pc
    WHERE pc.ProductID = p_producttypeid AND pc.MaterialID = p_materialid;
    
    RETURN CEILING(v_material_needed);
END;
$$;
