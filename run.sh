#!/bin/bash
cd /home/server/apps/dt-cgr
python3 scrape-dt.py
python3 scrape-cgr.py
python3 sql-export.py

