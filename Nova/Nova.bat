@echo off
pushd "%~dp0"
if not exist .deps_ok (
  echo First run - installing Nova dependencies...
  python -m pip install -r requirements.txt && echo ok> .deps_ok
)
python Nova.py
if errorlevel 1 pause
popd