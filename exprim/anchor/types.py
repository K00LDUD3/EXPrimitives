from enum import Enum, auto


class Device(str, Enum):
    CPU = "cpu"
    CUDA = "cuda"
    MPS = "mps"


class Precision(str, Enum):
    FP32 = "float32"
    FP16 = "float16"
    BF16 = "bfloat16"
    INT8 = "int8"
    INT16 = "int16"


class LogLevel(str, Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# NOTE: type aliases
Seed = int
RunID = str
Hz = float
Seconds = float

