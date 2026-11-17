@echo off
chcp 65001 >nul
rem Офлайн-установка зависимостей Call Viewer под Python 3.12 (Windows x64).
rem Запуск: install.bat [путь к python.exe 3.12]
rem По умолчанию используется "py -3.12".

setlocal
set "HERE=%~dp0"
if "%~1"=="" (set PY=py -3.12) else (set PY="%~1")

%PY% -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version" || (
    echo Нужен Python 3.12. Укажите путь: install.bat C:\Python312\python.exe
    exit /b 1
)

%PY% -m venv "%HERE%venv" || exit /b 1
"%HERE%venv\Scripts\python.exe" -m pip install --no-index --find-links="%HERE%wheels" -r "%HERE%requirements.txt" || exit /b 1

echo.
echo Готово: %HERE%venv
endlocal
