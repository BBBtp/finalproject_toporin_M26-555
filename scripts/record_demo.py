"""Record a local CLI demo with fixture prices, without any API calls."""

import json
import os
import pty
import select
import subprocess
import sys
import tempfile
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    "register --username demo_user --password example123",
    "login --username demo_user --password example123",
    "deposit --amount 100",
    "get-rate --from EUR --to USD",
    "buy --currency EUR --amount 20",
    "show-portfolio",
    "sell --currency EUR --amount 5",
    "show-portfolio",
    "exit",
]


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        stamp = datetime.now(UTC).isoformat()
        Path(temp_dir, "rates.json").write_text(
            json.dumps(
                {
                    "pairs": {"EUR_USD": {"rate": "1.25", "updated_at": stamp, "source": "fixture"}},
                    "last_refresh": stamp,
                }
            ),
            encoding="utf-8",
        )
        master, slave = pty.openpty()
        environment = os.environ.copy()
        environment["VALUTATRADE_DATA_DIR"] = temp_dir
        process = subprocess.Popen(
            [sys.executable, "-u", str(ROOT / "main.py")],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            cwd=ROOT,
            env=environment,
        )
        os.close(slave)
        start = time.monotonic()
        events = []

        def drain(expect_prompt: bool) -> None:
            deadline = time.monotonic() + 5
            output = ""
            while time.monotonic() < deadline:
                if not select.select([master], [], [], 0.2)[0]:
                    if not expect_prompt and process.poll() is not None:
                        return
                    continue
                try:
                    chunk = os.read(master, 65536).decode("utf-8", errors="replace")
                except OSError:
                    break
                if not chunk:
                    break
                events.append([round(time.monotonic() - start, 3), "o", chunk])
                output += chunk
                if expect_prompt and "valutatrade> " in output:
                    return
            if expect_prompt:
                raise RuntimeError("CLI did not display its prompt")

        drain(True)
        for command in COMMANDS:
            time.sleep(0.12)
            os.write(master, (command + "\n").encode())
            drain(command != "exit")
        process.wait(timeout=5)
        os.close(master)
        if process.returncode != 0:
            raise RuntimeError(f"Demo CLI exited with status {process.returncode}")
        cast = ROOT / "demo.cast"
        header = {
            "version": 2,
            "width": 100,
            "height": 30,
            "timestamp": int(time.time()),
            "env": {"TERM": "xterm-256color"},
        }
        lines = [json.dumps(header), *(json.dumps(event, ensure_ascii=False) for event in events)]
        cast.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Saved {cast} ({len(events)} terminal events)")


if __name__ == "__main__":
    main()
