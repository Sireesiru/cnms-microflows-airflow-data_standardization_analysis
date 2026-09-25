import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cnms_qr_sample_tracking.app import main, exception_hook

sys.excepthook = exception_hook

if __name__ == "__main__":
    main()
