@echo off
chcp 65001 >nul
title Stop Redis and MongoDB

echo 正在关闭 MongoDB...
taskkill /IM mongod.exe /F >nul 2>&1

echo 正在尝试优雅关闭 Redis...
REM 1. 如果有 redis-cli.exe，用 shutdown 命令优雅关闭
pushd "D:\Redis-8.4.0-Windows-x64-cygwin-with-Service"
if exist redis-cli.exe (
    redis-cli.exe -h 127.0.0.1 -p 6379 shutdown >nul 2>&1
)
popd

REM 2. 如果 Redis 是作为 Windows 服务安装的，尝试停止名为 Redis 的服务
net stop Redis >nul 2>&1

echo 正在强制结束可能存在的 Redis 进程...
REM 3. 尝试杀掉常见的 Redis 进程名（有的版本 exe 名会带版本号）
for %%P in (redis-server.exe redis-server-8.4.0.exe redis.exe) do (
    taskkill /IM "%%P" /F >nul 2>&1
)

echo 已尝试关闭 Redis 和 MongoDB