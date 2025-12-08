@echo off
REM Generate self-signed SSL certificates for PostgreSQL (Windows)

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..
set SSL_DIR=%PROJECT_ROOT%\ssl

echo Generating self-signed SSL certificates for PostgreSQL...
echo ============================================================

REM Create SSL directory
if not exist "%SSL_DIR%" mkdir "%SSL_DIR%"
cd /d "%SSL_DIR%"

REM Check if OpenSSL is available
where openssl >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: OpenSSL is not installed.
    echo Install OpenSSL from: https://slproweb.com/products/Win32OpenSSL.html
    echo Or use WSL (Windows Subsystem for Linux)
    exit /b 1
)

REM Generate private key (2048-bit RSA)
echo 1. Generating private key...
openssl genrsa -out server.key 2048
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to generate private key
    exit /b 1
)

REM Generate certificate signing request
echo 2. Generating certificate signing request...
openssl req -new -key server.key -out server.csr -subj "/C=US/ST=State/L=City/O=IndexPilot/CN=localhost"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to generate certificate signing request
    exit /b 1
)

REM Generate self-signed certificate (valid for 1 year)
echo 3. Generating self-signed certificate...
openssl x509 -req -days 365 -in server.csr -signkey server.key -out server.crt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to generate certificate
    exit /b 1
)

REM Clean up CSR
del server.csr

echo.
echo ============================================================
echo SSL certificates generated successfully!
echo.
echo Files created:
echo   - %SSL_DIR%\server.key (private key)
echo   - %SSL_DIR%\server.crt (certificate)
echo.
echo Next steps:
echo   1. Update docker-compose.yml to enable SSL
echo   2. Uncomment SSL configuration lines
echo   3. Restart PostgreSQL: docker-compose restart postgres
echo.
echo WARNING: These are self-signed certificates for development only.
echo Do NOT use in production!
pause

