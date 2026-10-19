import sys
from pathlib import Path

# Thêm thư mục root vào sys.path để luôn import thống nhất 'backend.xxx'
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)
