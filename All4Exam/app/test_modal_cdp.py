import asyncio
import websockets
import json
import subprocess
import time
import urllib.request

async def test_all():
    proc = subprocess.Popen([
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "--headless=new",
        "--remote-debugging-port=9222",
        "--disable-gpu",
        "http://localhost:8000"
    ])
    time.sleep(2)
    try:
        res = urllib.request.urlopen("http://127.0.0.1:9222/json")
        targets = json.loads(res.read())
        page_target = [t for t in targets if t.get("type") == "page"][0]
        ws_url = page_target.get("webSocketDebuggerUrl")
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
            await asyncio.sleep(1)
            
            # Check 1: Initial state
            await ws.send(json.dumps({
                "id": 2,
                "method": "Runtime.evaluate",
                "params": {"expression": 'Boolean(document.querySelector(".fixed"))', "returnByValue": True}
            }))
            
            # Check 2: Click settings button
            await ws.send(json.dumps({
                "id": 3,
                "method": "Runtime.evaluate",
                "params": {"expression": 'document.querySelector("header button").click(); true', "returnByValue": True}
            }))
            await asyncio.sleep(0.5)
            
            await ws.send(json.dumps({
                "id": 4,
                "method": "Runtime.evaluate",
                "params": {"expression": 'Boolean(document.querySelector(".fixed"))', "returnByValue": True}
            }))
            
            # Check 3: Click Close button
            await ws.send(json.dumps({
                "id": 5,
                "method": "Runtime.evaluate",
                "params": {"expression": 'document.querySelector(".fixed button").click(); true', "returnByValue": True}
            }))
            await asyncio.sleep(0.5)
            
            await ws.send(json.dumps({
                "id": 6,
                "method": "Runtime.evaluate",
                "params": {"expression": 'Boolean(document.querySelector(".fixed"))', "returnByValue": True}
            }))
            
            while True:
                m = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(m)
                if data.get("id") == 2:
                    print("1. 초기 상태에서 모달 팝업 표시 여부 (정상=False):", data.get("result", {}).get("result", {}).get("value"))
                if data.get("id") == 4:
                    print("2. ⚙️ 설정 버튼 클릭 후 모달 팝업 표시 여부 (정상=True):", data.get("result", {}).get("result", {}).get("value"))
                if data.get("id") == 6:
                    print("3. ✕ 닫기 버튼 클릭 후 모달 팝업 닫힘 여부 (정상=False):", data.get("result", {}).get("result", {}).get("value"))
                    break
    finally:
        proc.kill()

asyncio.run(test_all())
