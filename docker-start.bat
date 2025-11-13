@echo off
chcp 65001 >nul 2>&1
REM DRIA Docker Quick Start Script (Windows)

echo ========================================
echo DRIA Docker Deployment Script
echo ========================================
echo.

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running. Please start Docker Desktop first.
    pause
    exit /b 1
)

REM Check if docker-compose is installed
docker-compose --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] docker-compose is not installed
    pause
    exit /b 1
)

REM Check environment file
if not exist ".env.docker" (
    echo [WARNING] .env.docker file does not exist
    echo [INFO] Creating from example file...
    if exist "env.docker.example" (
        copy env.docker.example .env.docker >nul
        echo [SUCCESS] .env.docker file created. Please edit it with your actual configuration.
        echo [INFO] Edit command: notepad .env.docker
        pause
        exit /b 1
    ) else (
        echo [ERROR] env.docker.example file does not exist
        pause
        exit /b 1
    )
)

REM Build images
echo.
echo [INFO] Building Docker images...
docker-compose build
if errorlevel 1 (
    echo [ERROR] Build failed
    pause
    exit /b 1
)

REM Start services
echo.
echo [INFO] Starting services...
docker-compose --env-file .env.docker up -d
if errorlevel 1 (
    echo [ERROR] Start failed
    pause
    exit /b 1
)

REM Wait for services to start
echo.
echo [INFO] Waiting for services to start...
timeout /t 5 /nobreak >nul 2>&1

REM Check service status
echo.
echo [INFO] Service status:
docker-compose ps

REM Display access information
echo.
echo [SUCCESS] Deployment completed!
echo.
echo [INFO] Access URLs:
echo    - Frontend: http://localhost
echo    - Backend API: http://localhost:8000
echo    - API Docs: http://localhost:8000/api/docs
echo    - Health Check: http://localhost:8000/api/health
echo.
echo [INFO] Common commands:
echo    - View logs: docker-compose logs -f
echo    - Stop services: docker-compose down
echo    - Restart services: docker-compose restart
echo.

pause
