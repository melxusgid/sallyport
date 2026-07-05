#!/bin/bash
# Sallyport curl demo — shows the full workflow
# Requires: Sallyport running on localhost:9378

SAL=http://localhost:9378
echo "=== 1. Health check ==="
curl -s $SAL/health | python3 -m json.tool

echo -e "\n=== 2. Start browser (Fortress stealth engine) ==="
curl -s -X POST $SAL/browser/start \
  -H "Content-Type: application/json" \
  -d '{"channel":"stable"}' | python3 -m json.tool

echo -e "\n=== 3. Open a tab ==="
RESP=$(curl -s -X POST $SAL/tabs \
  -H "Content-Type: application/json" \
  -d '{"url":"https://bot.sannysoft.com","wait_ms":4000}')
echo "$RESP" | python3 -m json.tool
TAB_ID=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['tab_id'])")
echo "Tab ID: $TAB_ID"

echo -e "\n=== 4. Get snapshot ==="
curl -s "$SAL/tabs/$TAB_ID/snapshot" | python3 -m json.tool

echo -e "\n=== 5. Evaluate JS ==="
curl -s -X POST "$SAL/tabs/$TAB_ID/evaluate" \
  -H "Content-Type: application/json" \
  -d '{"expression":"navigator.userAgent"}' | python3 -m json.tool

echo -e "\n=== 6. Close tab ==="
curl -s -X DELETE "$SAL/tabs/$TAB_ID" | python3 -m json.tool

echo -e "\n=== 7. Stop browser ==="
curl -s -X POST $SAL/browser/stop | python3 -m json.tool

echo -e "\nDone."
