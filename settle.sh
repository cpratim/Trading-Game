#!/usr/bin/env bash
PORT=${1:-5002}
PRICE=${2:?Usage: ./settle.sh <port> <settlement_price>}

echo "Settling book $PORT at price $PRICE..."
curl -s -X POST "http://localhost:$PORT/admin/settle" \
  -H "Content-Type: application/json" \
  -d "{\"price\": $PRICE}" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
if not d.get('ok'):
    print('ERROR:', d.get('error'))
    sys.exit(1)
print(f'Settled at {d[\"price\"]}')
print()
print(f'  {\"Rank\":<6} {\"Name\":<24} {\"PnL\":>10}')
print(f'  {\"-\"*44}')
rank = 1
for s in d['scores']:
    if s.get('is_mm'):
        print(f'  {\"--\":<6} {s[\"name\"]:<24} {s[\"pnl\"]:>10.2f}')
    else:
        print(f'  {rank:<6} {s[\"name\"]:<24} {s[\"pnl\"]:>10.2f}')
        rank += 1
"
