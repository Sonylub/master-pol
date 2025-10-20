-- Использование базы
USE PartnerManagement_01_MasterPol;;
GO

-- Создание таблиц
CREATE TABLE Partners (
    PartnerID INT IDENTITY(1,1) PRIMARY KEY,
    Name NVARCHAR(150) NOT NULL,
    LegalAddress NVARCHAR(250),
    INN NVARCHAR(12),
    DirectorFullName NVARCHAR(150),
    Phone NVARCHAR(20),
    Email NVARCHAR(100),
    Rating DECIMAL(3,2),
    CreatedAt DATETIME DEFAULT GETDATE()
);
GO

CREATE TABLE Managers (
    ManagerID INT IDENTITY(1,1) PRIMARY KEY,
    FullName NVARCHAR(150) NOT NULL,
    Phone NVARCHAR(20),
    Email NVARCHAR(100)
);
GO

CREATE TABLE Suppliers (
    SupplierID INT IDENTITY(1,1) PRIMARY KEY,
    Name NVARCHAR(150) NOT NULL,
    INN NVARCHAR(12),
    Phone NVARCHAR(20),
    Email NVARCHAR(100)
);
GO

CREATE TABLE Materials (
    MaterialID INT IDENTITY(1,1) PRIMARY KEY,
    Name NVARCHAR(150) NOT NULL,
    Unit NVARCHAR(20),
    Cost MONEY,
    QuantityInStock DECIMAL(10,2) DEFAULT 0,
    MinAllowedQuantity DECIMAL(10,2) DEFAULT 0
);
GO

CREATE TABLE Supplies (
    SupplyID INT IDENTITY(1,1) PRIMARY KEY,
    SupplierID INT NOT NULL,
    MaterialID INT NOT NULL,
    ManagerID INT NOT NULL,
    Quantity DECIMAL(10,2) CHECK (Quantity > 0),
    SupplyDate DATETIME DEFAULT GETDATE(),
    CONSTRAINT FK_Supplies_Suppliers FOREIGN KEY (SupplierID) REFERENCES Suppliers(SupplierID),
    CONSTRAINT FK_Supplies_Materials FOREIGN KEY (MaterialID) REFERENCES Materials(MaterialID),
    CONSTRAINT FK_Supplies_Managers FOREIGN KEY (ManagerID) REFERENCES Managers(ManagerID)
);
GO

CREATE TABLE Products (
    ProductID INT IDENTITY(1,1) PRIMARY KEY,
    Name NVARCHAR(150) NOT NULL,
    Description NVARCHAR(255),
    StandardNumber NVARCHAR(50),
    ManufactureTimeDays INT,
    CostPrice MONEY,
    MinPartnerPrice MONEY,
    CreatedAt DATETIME DEFAULT GETDATE()
);
GO

CREATE TABLE ProductComposition (
    ProductCompositionID INT IDENTITY(1,1) PRIMARY KEY,
    ProductID INT NOT NULL,
    MaterialID INT NOT NULL,
    Quantity DECIMAL(10,2) CHECK (Quantity > 0),
    CONSTRAINT FK_ProductComposition_Products FOREIGN KEY (ProductID) REFERENCES Products(ProductID),
    CONSTRAINT FK_ProductComposition_Materials FOREIGN KEY (MaterialID) REFERENCES Materials(MaterialID)
);
GO

CREATE TABLE Requests (
    RequestID INT IDENTITY(1,1) PRIMARY KEY,
    PartnerID INT NOT NULL,
    ManagerID INT NOT NULL,
    ProductID INT NOT NULL,
    Quantity INT CHECK (Quantity > 0),
    UnitPrice MONEY CHECK (UnitPrice > 0),
    TotalPrice AS (Quantity * UnitPrice) PERSISTED,
    CreatedAt DATETIME DEFAULT GETDATE(),
    Status NVARCHAR(50) DEFAULT N'Новая',
    CONSTRAINT FK_Requests_Partners FOREIGN KEY (PartnerID) REFERENCES Partners(PartnerID),
    CONSTRAINT FK_Requests_Managers FOREIGN KEY (ManagerID) REFERENCES Managers(ManagerID),
    CONSTRAINT FK_Requests_Products FOREIGN KEY (ProductID) REFERENCES Products(ProductID)
);
GO

-- Функция расчёта скидки
CREATE FUNCTION fn_GetPartnerDiscount (@PartnerID INT)
RETURNS DECIMAL(5,2)
AS
BEGIN
    DECLARE @TotalQuantity INT;
    SELECT @TotalQuantity = ISNULL(SUM(Quantity), 0)
    FROM Requests
    WHERE PartnerID = @PartnerID AND Status = N'Выполнена';
    RETURN CASE
        WHEN @TotalQuantity >= 1000 THEN 0.15
        WHEN @TotalQuantity >= 500 THEN 0.10
        ELSE 0.05
    END;
END;
GO

-- Функция расчёта материалов
CREATE FUNCTION fn_CalcRequiredMaterial (
    @ProductTypeID INT,
    @MaterialID INT,
    @Quantity INT,
    @Param1 FLOAT,
    @Param2 FLOAT
)
RETURNS INT
AS
BEGIN
    DECLARE @DefectRate FLOAT = 0.1; -- 10% брака
    IF @ProductTypeID <= 0 OR @MaterialID <= 0 OR @Quantity <= 0 OR @Param1 <= 0 OR @Param2 <= 0
        RETURN -1;
    DECLARE @MaterialNeeded DECIMAL(10,2);
    SELECT @MaterialNeeded = ISNULL(SUM(pc.Quantity * @Quantity * @Param1 * @Param2 * (1 + @DefectRate)), 0)
    FROM ProductComposition pc
    WHERE pc.ProductID = @ProductTypeID AND pc.MaterialID = @MaterialID;
    RETURN CEILING(@MaterialNeeded);
END;
GO