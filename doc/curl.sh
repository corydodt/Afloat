#!/bin/bash
set -e
python formatofxreq.py input.ofx.in config.py > input.ofx
curl --data-binary @input.ofx -H "Connection: close" -H "Content-Type: application/x-ofx" https://www.eecuonline.org/scripts/isaofx.dll
