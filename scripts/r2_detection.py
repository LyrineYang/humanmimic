"""CPU detector scheduling validated against the full original debug cache."""

INTRA_THREADS = 8
INTER_THREADS = 1


def load_cpu_detector(checkpoint):
    import onnxruntime as ort
    from unittest.mock import patch
    from gem.common.detectors import YOLOXONNX

    constructor = ort.SessionOptions

    def fixed_options():
        options = constructor()
        options.intra_op_num_threads = INTRA_THREADS
        options.inter_op_num_threads = INTER_THREADS
        return options

    # The pinned constructor has no options argument. Scope the factory to its
    # construction inside this isolated worker; restore it before inference.
    with patch.object(ort, "SessionOptions", fixed_options):
        return YOLOXONNX(checkpoint, device="cpu")
