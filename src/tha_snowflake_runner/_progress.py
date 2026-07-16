import shutil


def tqdm_ncols(max_cols: int = 85) -> int:
    return min(shutil.get_terminal_size(fallback=(max_cols, 24)).columns, max_cols)
