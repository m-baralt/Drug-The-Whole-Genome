# Drug-The-Whole-Genome (Modified Fork)

This is a modified version of [THU-ATOM/Drug-The-Whole-Genome](https://github.com/THU-ATOM/Drug-The-Whole-Genome) with applied changes to the virtual screening DrugCLIP pipeline for improved memory efficiency and PyTorch ≥ 2.6 compatibility.
Please, refer to the original repo for all the rest of functionalities available. 

This documentation mainly aims to understand the structure of DrugCLIP and detail the modifications conducted for the virtual screening. 

## Installation

Installation instructions are available in the parent repository 

## High-level original pipeline

[Open interactive diagram](docs/pipeline_wrapper.html)

![Preview diagram](docs/pipeline.svg)

# Scripts

## retrieval.sh
Bash script for virtual screening with DrugCLIP:
1. Calls [`retrieval.py`](#retrievalpy) to run the workflow.
2. Accepts command-line arguments (CLI) for customization.
3. Sets the task to drugclip.
4. If --use-cache=true, it loads pre-computed molecular embeddings.
5. If --use-cache=false, it generates new molecular embeddings from scratch.
6. When --use-cache=false, an LMDB file containing molecule information must be provided via the --MOL_PATH argument.

## retrieval.py {#retrievalpy}
Responsibilities:
1. Parse command-line arguments (CLI).
2. Set up the task using UniCore.  
   - If `task=drugclip`, `unimol/tasks/drugclip.py` is invoked, and the [`DrugCLIP class`](#drugclip-class) is initialized.
3. Build the model corresponding to the specified architecture using the [`build_model`](#build_model) method from **DrugCLIP class**
4. Call `retrieval_multi_folds` to execute the virtual screening pipeline.

# Classes

## DrugCLIP class {#drugclipclass}

Class for `task="drugclip"`.

### Important Methods

#### `build_model()`
- Calls `unicore.models.build_model`.
- If `arch="drugclip"`, `unimol/models/drugclip.py` is invoked.  
- The [`BindingAffinityModel`](#bindingaffinitymodel) class is initialized, and its `build_model` method is called.

#### `retrieval_multi_folds`

This function orchestrates the multi-fold virtual screening process and manages caching of molecular and pocket embeddings. By default, it loops over 6 folds.

1. **Load checkpoint weights:**  
   - For each fold, the saved checkpoint weights are loaded into the pre-initialized model.

2. **Load or compute molecular embeddings:**  
   - If `use-cache=True`, precomputed molecular embeddings are loaded for the current fold.  
   - If `use-cache=False`:  
     1. [`load_mols_dataset`](#load_mols_dataset) reads the LMDB file containing molecular data.  
     2. A PyTorch `DataLoader` is created.  
     3. A batch loop is executed:  
        1. Prepare the model input: extract distances, edge types, and tokens for each sample; embed tokens with `model.mol_model.embed_tokens`.  
        2. Fuse and project distance and edge information for graph attention.  
        3. Apply `model.mol_model.encoder` to compute molecular representations.  
        4. Extract the `[CLS]` token embedding, project to lower-dimensional space using `mol_project`, and normalize to unit length.  
        5. Append embeddings to a list `mol_reps`. After all batches, convert `mol_reps` into a matrix of shape `(num_samples x embedding_size)`.  
        6. Save the molecular embeddings to cache.

3. **Load or compute pocket embeddings:**  
   1. `load_pockets_dataset` reads the LMDB file containing pocket data.  
   2. A PyTorch `DataLoader` is created.  
   3. A batch loop is executed:  
      1. Prepare the model input: extract distances, edge types, and tokens; embed tokens using `model.pocket_model.embed_tokens`.  
      2. Fuse and project distance and edge information for graph attention.  
      3. Apply `model.pocket_model.encoder` to compute pocket representations.  
      4. Extract the `[CLS]` token embedding, project to lower-dimensional space using `pocket_project`, and normalize to unit length.  
      5. Append embeddings to a list `pocket_reps`. After all batches, convert `pocket_reps` into a matrix of shape `(num_samples x embedding_size)`.

4. **Compute similarity matrices:**  
   - Multiply the `pocket_reps` matrix with the transpose of the `mol_reps` matrix to compute cosine similarities.

5. **Aggregate results across folds:**  
   - Average the similarity matrices from all folds.  
   - Apply an adjusted robust z-score normalization.  
   - For each pocket, select the maximum score across molecules (assuming different pockets correspond to different conformations of the same pocket).

6. **Save results:**  
   - Save the final scores and corresponding SMILES strings to a `.txt` file.

#### load_mols_dataset()

1. Initializes the `LMDBDataset` class, which reads LMDB files and returns all data for a single molecule when accessed by index (`dataset[idx]`).
2. Wraps it in the `AffinityMolDataset` class, which prepares and organizes the molecule data into a structured dictionary format.
3. Applies the `RemoveHydrogenDataset` class to remove hydrogen atoms from the molecule representation.
4. Uses the `NormalizeDataset` class to center the 3D coordinates of the atoms.
5. Extracts atom information, tokenizes it, and prepends (`BOS`) and appends (`EOS`) special tokens.
6. Generates unique identifiers for each edge between atoms using the `EdgeTypeDataset` class.
7. Computes pairwise distances between atoms using the `DistanceDataset` class.
8. Combines all the processed information into a single `NestedDictionaryDataset` object, ready for model input.

#### `load_pockets_dataset()`

Follows the same processing steps as `load_mols_dataset()`, but after step 3 it **crops the pocket sequence** if it contains more than a specified maximum number of atoms (default: 256).

## BindingAffinityModel

This class implements the DrugCLIP architecture for binding affinity prediction.  

- Uses the defined `drugclip_architecture` to set up the model configuration.  
- Initializes:
  - A **molecular model** using the Uni-Mol architecture (`UniMolModel` class).  
  - A **pocket model** using the Uni-Mol architecture (`UniMolModel` class).  
- The `build_model` method creates and returns an instance of the model.

# Concepts

## Edge Types
Unique IDs representing atom-type pairs

## Gaussian Basis Features
Encodes geometry into attention bias

## Cosine Similarity Retrieval
Unit-normalized embeddings → dot product

# Applied changes

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