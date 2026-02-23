# Drug-The-Whole-Genome (Modified Fork)

This is a modified version of [THU-ATOM/Drug-The-Whole-Genome](https://github.com/THU-ATOM/Drug-The-Whole-Genome) with applied changes to the virtual screening DrugCLIP pipeline for improved memory efficiency and PyTorch ≥ 2.6 compatibility.
Please, refer to the original repo for all the rest of functionalities available. 

This documentation mainly aims to understand the structure of DrugCLIP and detail the modifications conducted for the virtual screening. 

## Installation

Installation instructions are available in the parent repository 

## High-level original pipeline

A detailed description of DrugCLIP original virtual screening pipeline can be seen [here!](https://m-baralt.github.io/Drug-The-Whole-Genome/pipeline.html)

![Preview diagram](docs/pipeline.svg)

# Applied changes

The following changes have been made to adapt DrugCLIP virtual screening for larger molecular databases.

- `retrieval.sh` now calls `run_retrieval.py`, a safe wrapper around `retrieval.py` for **PyTorch ≥ 2.6**.  
  This wrapper ensures that required globals are registered for unpickling checkpoints generated with **PyTorch < 2.6**, and forwards all command-line arguments to `retrieval.py`.
  **Explanation:**  
  Model checkpoints were created with PyTorch < 2.6. In PyTorch ≥ 2.6, `torch.load()` defaults to `weights_only=True`, which restricts deserialization to tensor objects only. As a result, loading checkpoints containing non-tensor objects (e.g., `argparse.Namespace`) raises an error.  
  `run_retrieval.py` restores compatibility by explicitly handling this behavior.
- Handling of the `--use-cache` CLI argument in `retrieval.py` has been fixed.  
  Previously, `use-cache` was parsed as a string, meaning both `"True"` and `"False"` evaluated as truthy values.  
  It is now converted to a proper boolean via:
  ```python
  args.use_cache.lower() == "true"
  ```
- A memory-optimized implementation of `retrieval_multi_folds` has been introduced in a new file: `unimol/tasks/drugclip_modified.py`. This modified task can be used by setting `task=drugclip-new` in the `retrieval.sh` script. The changes improve scalability when screening millions of molecules.

**Key modifications:**
- Pocket embeddings are computed first and stored in `pocket_reps`.
- Molecule embeddings are processed batch-wise. Instead of storing all molecular embeddings in a large matrix of shape __(number_of_molecules × embedding_dim)__, similarity scores between pocket and molecule embeddings are computed on-the-fly for each batch.
- Similarity scores are accumulated in a dictionary keyed by molecule SMILES. This ensures correct alignment between molecules and their scores across folds without requiring full similarity matrices in memory.
- The `use-cache=True` branch has been adapted to follow the same accumulation strategy, ensuring consistent behavior between cached and non-cached execution modes.
- Similarity scores are summed across folds and averaged by dividing by the number of folds.
- The adjusted robust z-score normalization across pocket conformations and the subsequent max pooling step have been removed.
  This change:
  - avoids implicit assumptions that all input pockets belong to the same target,
  - allows users to provide unrelated proteins/pockets as input,
  - and returns raw cosine similarity scores, leaving any aggregation or normalization strategy to downstream analysis.

Returned scores correspond to cosine similarity between unit-vector normalized pocket and molecule embeddings. New thresholds to define affinity need to be defined. 