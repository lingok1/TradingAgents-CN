@echo off
chcp 65001 >nul
title Start Redis and MongoDB

REM 启动 Redis
pushd "D:\Redis-8.4.0-Windows-x64-cygwin-with-Service"
start "" cmd /c start.bat
popd

REM 启动 MongoDB
pushd "D:\MongoDB\Server\8.2\bin"
start "" mongod.exe --dbpath "D:\MongoDB\Server\8.2\data"
popd

echo 已尝试启动 Redis 和 MongoDB
