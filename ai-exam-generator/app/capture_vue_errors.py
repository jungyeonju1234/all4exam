import asyncio
import websockets
import json
import subprocess
import time
import urllib.request

async def capture_vue_errors():
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
            await ws.send(json.dumps({"id": 2, "method": "Console.enable"}))
            
            # Listen to all console events
            logs = []
            
            # Send a trigger to get any unhandled errors
            await ws.send(json.dumps({
                "id": 3,
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "Boolean(window.__app_mounted)",
                    "returnByValue": True
                }
            }))
            
            for _ in range(10):
                try:
                    m = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    data = json.loads(m)
                    if data.get("method") == "Console.messageAdded":
                        logs.append(data.get("params", {}).get("message"))
                    if data.get("method") == "Runtime.consoleAPICalled":
                        logs.append(data.get("params", {}).get("args"))
                    if data.get("method") == "Runtime.exceptionThrown":
                        logs.append(data.get("params", {}))
                except asyncio.TimeoutError:
                    break
            
            print("Captured logs count:", len(logs))
            for l in logs:
                print("LOG:", l)
    finally:
        proc.kill()

asyncio.run(capture_vue_errors())
