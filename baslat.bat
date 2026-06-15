@echo off
echo =========================================
echo Vanta Wear VDS Server Baslatiliyor...
echo =========================================

echo [1/3] API Backend Sunucusu (Flask - PostgreSQL) Baslatiliyor...
start "Vanta Wear API (Backend)" cmd /k "C:\Users\UMUT\AppData\Local\Python\pythoncore-3.14-64\python.exe backend\server.py"

echo [2/3] Frontend Sunucusu (Musteri Ekrani) Baslatiliyor...
start "Vanta Wear Frontend" cmd /k "C:\Users\UMUT\AppData\Local\Python\pythoncore-3.14-64\python.exe -m http.server 8080"

echo [3/3] Windows Masaustu Admin Paneli Baslatiliyor...
start "Vanta Wear Admin (Desktop)" cmd /k "C:\Users\UMUT\AppData\Local\Python\pythoncore-3.14-64\python.exe admin_app.py"

echo.
echo =========================================
echo Sistem hazir!
echo.
echo Musteri Ekrani : http://localhost:8080/index.html
echo Admin Paneli   : Masaustu uygulamasindan yonetiliyor!
echo =========================================
pause
