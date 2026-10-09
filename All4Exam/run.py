import uvicorn
import webbrowser
import threading
import time
import sys

# Windows 콘솔 인코딩 대응
if sys.platform.startswith("win"):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

def open_browser():
    time.sleep(1.2)
    webbrowser.open("http://localhost:8000")

if __name__ == "__main__":
    print("=" * 60)
    print("All 4 Exam - AI 수능 국어 문제 생성기 서버를 시작합니다...")
    print("브라우저 주소: http://localhost:8000")
    print("=" * 60)
    
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
