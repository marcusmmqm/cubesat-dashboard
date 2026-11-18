@echo off
rem Gera CubeSatDashboard.exe e copia para a Area de Trabalho, junto com o
rem comandos.txt (mensagens dos botoes; pode ser editado depois).
rem Rode no Windows com duplo clique (precisa de Python 3 instalado).
setlocal
cd /d "%~dp0"

set PY=python
where py >nul 2>nul && set PY=py
%PY% --version >nul 2>nul
if errorlevel 1 goto sempython

echo === Instalando PyInstaller e pyserial ===
%PY% -m pip install --upgrade pyinstaller pyserial
if errorlevel 1 goto erro

echo === Gerando o executavel ===
%PY% -m PyInstaller --noconfirm --onefile --windowed --name CubeSatDashboard dashboard.py
if errorlevel 1 goto erro

for /f "usebackq delims=" %%D in (`powershell -NoProfile -Command "[Environment]::GetFolderPath('Desktop')"`) do set "DESK=%%D"
copy /y "dist\CubeSatDashboard.exe" "%DESK%\" >nul
if errorlevel 1 goto erro
rem nao sobrescreve um comandos.txt ja editado na Area de Trabalho
if not exist "%DESK%\comandos.txt" copy "comandos.txt" "%DESK%\" >nul

echo.
echo Pronto: "%DESK%\CubeSatDashboard.exe"
echo Mensagens dos botoes: "%DESK%\comandos.txt"
pause
exit /b 0

:sempython
echo Python nao encontrado.
echo Instale em https://www.python.org/downloads/ marcando "Add python.exe to PATH"
echo e rode este arquivo de novo.
pause
exit /b 1

:erro
echo.
echo Falhou - veja a mensagem acima.
pause
exit /b 1
