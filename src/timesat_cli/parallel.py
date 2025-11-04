from __future__ import annotations

__all__ = ["maybe_init_ray"]


def maybe_init_ray(para_check: int, ray_dir: str | None = None) -> bool:
    """
    Initialize Ray if parallelism is requested.

    Parameters
    ----------
    para_check : int
        Number of CPUs to use (if >1, Ray will be initialized).
    ray_dir : str or None, optional
        Temporary directory for Ray logs/state. If None or empty,
        Ray will use its default temp location.

    Returns
    -------
    bool
        True if Ray was initialized, False otherwise.
    """
    if para_check > 1:
        import ray
        kwargs = {"num_cpus": para_check}
        if ray_dir:  # only include if user provided a valid path
            kwargs["_temp_dir"] = ray_dir

        ray.init(**kwargs)
        return True

    return False
