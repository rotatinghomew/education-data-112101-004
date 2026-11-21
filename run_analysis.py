#!/usr/bin/env python3
"""项目根目录下的可重跑入口。

推荐以隔离模式运行，避免工作目录中的同名模块干扰导入：

    python3 -I run_analysis.py --data-dir data --output-dir outputs

脚本仅把自身所在目录加入 sys.path，随后调用 analysis.cli。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from analysis.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
