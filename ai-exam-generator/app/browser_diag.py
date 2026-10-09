import subprocess
import time
import json
import urllib.request
import websockets
import asyncio

async def test_page():
    # Start Edge in headless mode with debugging port
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    ]
    edge_exe = None
    import os
    for p in edge_paths:
        if os.path.exists(p):
            edge_exe = p
            break
    
    if not edge_exe:
        print("No browser found")
        return

    print("Launching browser:", edge_exe)
    proc = subprocess.Popen([
        edge_exe,
        "--headless=new",
        "--remote-debugging-port=9222",
        "--disable-gpu",
        "http://localhost:8000"
    ])

    time.sleep(2)

    try:
        # Get devtools targets
        res = urllib.request.urlopen("http://127.0.0.1:9222/json")
        targets = json.loads(res.read())
        print("Targets:", len(targets))
        
        page_target = None
        for t in targets:
            if t.get("type") == "page":
                page_target = t
                break
        
        if page_target:
            ws_url = page_target.get("webSocketDebuggerUrl")
            print("Connecting to ws:", ws_url)
            async with websockets.connect(ws_url) as ws:
                # Enable Console and Runtime
                await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
                await ws.send(json.dumps({"id": 2, "method": "Console.enable"}))
                await ws.send(json.dumps({"id": 3, "method": "Page.enable"}))
                
                # Evaluate window.__ERRORS or console messages
                await asyncio.sleep(1)
                
                eval_cmd = {
                    "id": 4,
                    "method": "Runtime.evaluate",
                    "params": {
                        "expression": "JSON.stringify({errors: window.__ERRORS, vue: typeof Vue, app: Boolean(document.querySelector('#app'))})"
                    }
                }
                await ws.send(json.dumps(eval_cmd))
                
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    data = json.loads(msg)
                    if data.get("id") == 4:
                        print("EVAL RESULT:", data.get("result", {}).get("result", {}).get("value"))
                    if data.get("method") == "Runtime.exceptionThrown":
                        print("EXCEPTION THROWN:", data.get("params", {}).get("exceptionDetails", {}).get("text"))
                        print("EXCEPTION OBJ:", data.get("params", {}).get("exceptionDetails", {}).get("exception"))
                    if data.get("method") == "Console.messageAdded":
                        print("CONSOLE MESSAGE:", data.get("params", {}).get("message"))
    except Exception as e:
        print("Error during test:", e)
    finally:
        proc.kill()

asyncio.run(test_page())
