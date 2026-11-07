@echo off
chcp 65001 >nul
title Pont Bambu Connect - Les Impressions du Fjord
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0fjord_bambu_connect_bridge.ps1"
if errorlevel 1 echo Le pont n'a pas pu demarrer. Verifie le message ci-dessus.
pause
