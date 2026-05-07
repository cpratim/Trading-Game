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
print(f'  {\"Rank\":<6} {\"Name\":<20} {\"PnL\":>10}')
print(f'  {\"-\"*40}')
for i, s in enumerate(d['scores'], 1):
    print(f'  {i:<6} {s[\"name\"]:<20} {s[\"pnl\"]:>10.2f}')
"
