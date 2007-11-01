#!/bin/bash
set -e
python formatofxreq.py input.ofx.in config.py | curl --data-binary @- -H "Connection: close" -H "Content-Type: application/x-ofx" https://www.eecuonline.org/scripts/isaofx.dll
