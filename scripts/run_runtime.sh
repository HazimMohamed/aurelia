#!/bin/bash
cd /home/zuzu/Code/aurelia
source .env
exec python3 -m src.runtime_daemon
