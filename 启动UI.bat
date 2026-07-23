@echo off
cd /d "%~dp0"
echo Starting Type Quality Eval UI...
echo Browser will open at http://localhost:8501
echo.
"C:\Users\BLWH-PC-0035\AppData\Local\Programs\Python\Python313\python.exe" -m streamlit run app.py
pause
