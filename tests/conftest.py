"""Keep the default test suite deterministic and offline."""

import os


os.environ["ENABLE_LLM"] = "false"
os.environ["ENABLE_AMAP"] = "false"
