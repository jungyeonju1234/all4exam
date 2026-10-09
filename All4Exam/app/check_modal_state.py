import asyncio
import websockets
import json
import subprocess
import time
import urllib.request

async def test_err():
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
            await asyncio.sleep(1)
            
            js = """
            (() => {
                const modal = document.querySelector('.fixed.inset-0');
                const errDiv = document.querySelector('div[style*="background:#ef4444"]');
                return {
                    modalExists: Boolean(modal),
                    modalDisplay: modal ? window.getComputedStyle(modal).display : 'none',
                    errDivText: errDiv ? errDiv.textContent : null,
                    htmlSnippet: document.body.innerHTML.substring(0, 300)
                };
            })()
            """
            
            await ws.send(json.dumps({
                "id": 3,
                "method": "Runtime.evaluate",
                "params": {"expression": js, "returnByValue": True}
            }))
            
            while True:
                m = await asyncio.wait_for(ws.recv(), timeout=2.0)
                data = json.loads(m)
                if data.get("id") == 3:
                    res_val = data.get("result", {}).get("result", {}).get("value")
                    print("MODAL EXISTS:", res_val.get("modalExists"))
                    print("MODAL DISPLAY:", res_val.get("modalDisplay"))
                    print("ERR DIV:", res_val.get("errDivText"))
                    break
    finally:
        proc.kill()

asyncio.run(test_err())
