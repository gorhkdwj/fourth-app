@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  새 피드백 CSV 추가 (append + 중복 제거)
echo ============================================
echo.
set "CSV=%~1"
if "%CSV%"=="" set /p "CSV=새 피드백 CSV 경로를 입력(또는 이 창에 파일을 끌어다 놓기): "
if "%CSV%"=="" (
  echo 경로가 없습니다. 종료합니다.
  pause
  exit /b 1
)
py src\ingest.py "%CSV%"
echo.
echo 분류가 필요한 신규 행이 있으면, 분류 Skill로 classifications.csv를 채운 뒤
echo run.bat 를 실행하세요. (분류가 모두 끝났으면 바로 run.bat 실행)
pause
