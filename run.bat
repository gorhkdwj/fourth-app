@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo  카페 VoC 대시보드 실행
echo ============================================
echo.
echo [1/2] 데이터 재생성 + 검증...
py src\run_pipeline.py
if errorlevel 1 (
  echo.
  echo [중단] 파이프라인 실패 - 위 메시지를 확인하세요.
  pause
  exit /b 1
)
echo.
echo [2/2] 대시보드를 띄웁니다. 브라우저가 자동으로 열립니다.
echo        끝내려면 이 창에서 Ctrl + C 를 누르세요.
echo.
py -m streamlit run app.py
pause
