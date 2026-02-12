
"""
Safe wrapper to run DrugCLIP retrieval.py on PyTorch >= 2.6.
Automatically allows necessary globals for unpickling checkpoints.
Passes all command-line arguments through to retrieval.py.
"""

import sys
import argparse
import numpy as np
import torch


safe_globals = [argparse.Namespace]

numpy_globals = [
    np.dtype,
    np.str_,
    np.int_,
    np.int32,
    np.int64,
    np.float32,
    np.float64,
    np.bool_,
    np.complex64,
    np.complex128,
    np.core.multiarray.scalar,
    np.dtypes.Float64DType
]

safe_globals.extend(numpy_globals)

torch.serialization.add_safe_globals(safe_globals)

import retrieval

retrieval.cli_main()
