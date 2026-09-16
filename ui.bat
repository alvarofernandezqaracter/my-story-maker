@echo off
rem Abre la interfaz web (seccion 19) sin depender de que Python este en el PATH.
rem
rem Existe porque en Windows una consola hereda el entorno de quien la abrio, y
rem una ventana anterior a la instalacion de Python no ve su carpeta por mucho
rem que el registro la tenga. Aqui se busca el interprete a mano y se comprueba
rem que arranca, que es lo que distingue a Python del stub de la Microsoft
rem Store: ese existe, esta en el PATH y no ejecuta nada.
rem
rem Acepta los mismos argumentos que el comando: ui.bat --puerto 9000
setlocal
cd /d "%~dp0"

set "PY="

rem 1. El lanzador oficial, que es lo que instala Python en Windows.
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"

rem 2. Una instalacion de usuario, sea cual sea la version.
if not defined PY (
  for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%~fD\python.exe" (
      "%%~fD\python.exe" -c "import sys" >nul 2>&1 && set "PY=%%~fD\python.exe"
    )
  )
)

rem 3. Lo que haya en el PATH, solo si de verdad ejecuta.
if not defined PY (
  python -c "import sys" >nul 2>&1 && set "PY=python"
)

if not defined PY (
  echo.
  echo No encuentro ningun Python 3 que funcione.
  echo.
  echo   - Si lo tienes instalado, cierra la sesion de Windows y vuelve a entrar:
  echo     las consolas abiertas arrastran el PATH de antes de instalarlo.
  echo   - Si no, instalalo con:  winget install Python.Python.3.13
  echo.
  exit /b 1
)

echo Interprete: %PY%
%PY% -m novela ui %*
