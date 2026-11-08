"""Record a local CLI demo with fixture prices, without any API calls."""

import json
import os
import pty
import select
import subprocess
import sys
import tempfile
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    "register --username demo_user --password 1234",
    "login --username demo_user --password 1234",
    "deposit --amount 10000",
    "update-rates",
    "show-rates --top 2",
    "show-rates --currency RUB",
    "get-rate --from BTC --to USD",
    "buy --currency BTC --amount 0.05",
    "show-portfolio",
    "sell --currency BTC --amount 0.01",
    "show-portfolio",
    "buy --currency BTC --amount 10",
    "get-rate --from ABC --to USD",
    "exit",
]


def demo_shell() -> None:
    """Run the real CLI with deterministic API clients for the recording."""
    sys.path.insert(0, str(ROOT))
    from valutatrade_hub.cli.interface import CLI, run_repl
    from valutatrade_hub.logging_config import configure_logging
    from valutatrade_hub.parser_service.updater import RatesUpdater

    class FixtureClient:
        def __init__(self, name: str, rates: dict[str, Decimal]) -> None:
            self.name = name
            self.rates = rates

        def fetch_rates(self) -> dict[str, Decimal]:
            return self.rates

    clients = [
        FixtureClient(
            "coingecko", {"BTC_USD": Decimal("59337.21"), "ETH_USD": Decimal("3720"), "SOL_USD": Decimal("145.12")}
        ),
        FixtureClient(
            "exchangerate", {"EUR_USD": Decimal("1.0786"), "GBP_USD": Decimal("1.25"), "RUB_USD": Decimal("0.01016")}
        ),
    ]
    configure_logging()
    run_repl(CLI(updater=RatesUpdater(clients=clients)))


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        master, slave = pty.openpty()
        environment = os.environ.copy()
        environment["VALUTATRADE_DATA_DIR"] = temp_dir
        process = subprocess.Popen(
            [sys.executable, "-u", str(Path(__file__).resolve()), "--demo-shell"],
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
    if sys.argv[1:] == ["--demo-shell"]:
        demo_shell()
    else:
        main()
