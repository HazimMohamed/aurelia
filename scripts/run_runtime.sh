#!/bin/bash
cd /home/zuzu/Code/aurelia
source .env
exec python3 -m src.samsara.runtime_daemon
