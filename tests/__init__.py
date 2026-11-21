"""测试包引导。

在 ``python3 -I`` 下运行 unittest 时，工作目录不会自动进入
``sys.path``；这里显式加入项目根目录，使 ``analysis`` 包可被
测试导入，且不依赖任何环境变量或第三方框架。
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
