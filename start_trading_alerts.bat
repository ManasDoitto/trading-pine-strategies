@echo off
cd /d "d:\Trading code-Claude"
start pythonw -m trading_exec.runner --loop --until 23:59 --log exec_data\runner.log
start pythonw -m trading_exec.trade_watch --loop --until 23:59 --log exec_data\trade_watch.log
