#!/bin/bash

cd /home/rapha/agente_juridico

source venv/bin/activate

# roda os dois bots
./start_bot.sh &
python bot_email.py
