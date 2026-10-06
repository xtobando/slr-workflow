"""Small standard-library harness for argparse and interactive Rich prompt tests."""

from __future__ import annotations

import io
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from unittest.mock import patch


@dataclass
class Result:
    exit_code: int
    output: str
    exception: BaseException | None


class CliRunner:
    def invoke(self, app: Callable, args: list[str], input: str = "") -> Result:
        output = io.StringIO()
        exception = None
        exit_code = 0
        with (
            redirect_stdout(output),
            redirect_stderr(output),
            patch("sys.stdin", io.StringIO(input)),
        ):
            try:
                app(args)
            except SystemExit as error:
                exit_code = int(error.code or 0)
                exception = error
            except Exception as error:  # noqa: BLE001 - mirror a CLI process result for assertions
                exception = error
                exit_code = 1
        return Result(exit_code, output.getvalue(), exception)
