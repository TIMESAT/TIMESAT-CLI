import numpy as np

__all__ = ["assign_qa_weight"]


def assign_qa_weight(p_a, qa: np.ndarray) -> np.ndarray:
    """Map QA values to weights using rules in p_a."""
    p_a = np.asarray(p_a)
    if qa.size == 0:
        return qa
    qa_out = np.zeros_like(qa, dtype=float)
    if p_a.size == 0:
        return qa_out

    if p_a.shape[1] == 2:
        for qa_value, weight in p_a:
            mask = (qa == qa_value)
            qa_out[mask] = weight
    elif p_a.shape[1] == 3:
        for min_val, max_val, weight in p_a:
            mask = (qa >= min_val) & (qa <= max_val)
            qa_out[mask] = weight
    else:
        raise ValueError("p_a must have either 2 or 3 columns.")
    return qa_out
