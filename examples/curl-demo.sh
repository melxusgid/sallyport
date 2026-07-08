#!/bin/bash
# Sallyport curl demo — shows the full workflow with all endpoints
# Requires: Sallyport running on localhost:9378

SAL=http://localhost:9378
echo "=== 1. Health check ==="
curl -s $SAL/health | python3 -m json.tool

echo -e "\n=== 2. Start browser (Fortress stealth engine) ==="
curl -s -X POST $SAL/browser/start \
  -H "Content-Type: application/json" \
  -d '{"channel":"stable"}' | python3 -m json.tool

echo -e "\n=== 3. Open a tab with smart wait ==="
RESP=$(curl -s -X POST $SAL/tabs \
  -H "Content-Type: application/json" \
  -d '{"url":"https://bot.sannysoft.com","wait_for":"networkidle","timeout_ms":15000}')
echo "$RESP" | python3 -m json.tool
TAB_ID=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin)['tab_id'])")
echo "Tab ID: $TAB_ID"

echo -e "\n=== 4. Get snapshot ==="
curl -s "$SAL/tabs/$TAB_ID/snapshot" | python3 -m json.tool | head -50

echo -e "\n=== 5. Get raw HTML source ==="
curl -s "$SAL/tabs/$TAB_ID/source" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(f'HTML: {d[\"html_length\"]} chars')
print(d['html'][:300])
"

echo -e "\n=== 6. Evaluate JS ==="
curl -s -X POST "$SAL/tabs/$TAB_ID/evaluate" \
  -H "Content-Type: application/json" \
  -d '{"expression":"navigator.userAgent"}' | python3 -m json.tool

echo -e "\n=== 7. Scroll down ==="
curl -s -X POST "$SAL/tabs/$TAB_ID/scroll" \
  -H "Content-Type: application/json" \
  -d '{"direction":"down","amount":600}' | python3 -m json.tool

echo -e "\n=== 8. Screenshot ==="
curl -s -X POST "$SAL/tabs/$TAB_ID/screenshot" \
  -H "Content-Type: application/json" \
  -d '{"full_page":false}' | python3 -c "
import json,sys
d=json.load(sys.stdin)
if d.get('success'):
    b64 = d['result']['image_base64']
    print(f'Screenshot: {len(b64)} bytes base64')
else:
    print(f'FAIL: {d}')
"

echo -e "\n=== 9. List open tabs ==="
curl -s "$SAL/tabs" | python3 -m json.tool

echo -e "\n=== 10. Navigate existing tab ==="
curl -s -X POST "$SAL/tabs/$TAB_ID/navigate" \
  -H "Content-Type: application/json" \
  -d '{"url":"https://example.com"}' | python3 -m json.tool

echo -e "\n=== 11. Close tab ==="
curl -s -X DELETE "$SAL/tabs/$TAB_ID" | python3 -m json.tool

echo -e "\n=== 12. Stop browser ==="
curl -s -X POST $SAL/browser/stop | python3 -m json.tool

echo -e "\nDone."
