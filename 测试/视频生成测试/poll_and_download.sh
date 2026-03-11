#!/bin/bash
API="https://yhgrok.xuhuanai.cn"
KEY="V378STSBi6jAC9Gk"
DIR="G:/涛项目/claude版/测试/视频生成测试"

declare -A TASKS
TASKS["01_内室对峙_冷光门口"]="f7e3104b-f709-4a0d-9258-ddff5d6cbe82"
TASKS["02_柳枝发钗_温柔坠落"]="e97c80b5-cec4-4c30-b6d3-e8203da240f3"
TASKS["03_沈词崩溃_庭院摊牌"]="15a0a895-6f91-4336-a605-e8476c65528a"

DONE=0
TOTAL=${#TASKS[@]}

while [ $DONE -lt $TOTAL ]; do
  for NAME in "${!TASKS[@]}"; do
    TID="${TASKS[$NAME]}"
    [ "$TID" = "done" ] && continue

    RESP=$(curl -s "$API/v1/videos/$TID" -H "Authorization: Bearer $KEY")
    STATUS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status','unknown'))" 2>/dev/null)
    PROGRESS=$(echo "$RESP" | python3 -c "import sys,json; print(json.load(sys.stdin).get('progress',0))" 2>/dev/null)

    if [ "$STATUS" = "completed" ]; then
      URL=$(echo "$RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('video_url') or d.get('url') or d.get('output',{}).get('url',''))" 2>/dev/null)
      echo "[DONE] $NAME -> $URL"
      curl -sL "$URL" -o "$DIR/${NAME}.mp4"
      echo "[SAVED] $DIR/${NAME}.mp4"
      TASKS[$NAME]="done"
      DONE=$((DONE+1))
    elif [ "$STATUS" = "failed" ]; then
      echo "[FAIL] $NAME: $RESP"
      TASKS[$NAME]="done"
      DONE=$((DONE+1))
    else
      echo "[WAIT] $NAME: status=$STATUS progress=$PROGRESS%"
    fi
  done

  [ $DONE -lt $TOTAL ] && sleep 10
done

echo "=== ALL DONE ==="
ls -lh "$DIR"/*.mp4 2>/dev/null
