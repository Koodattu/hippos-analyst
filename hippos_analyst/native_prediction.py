"""CPU inference with CatBoost's versioned C model evaluation API."""

import ctypes as ct

from .prediction_features import CATEGORICAL, FEATURES


def scores(library_path, model_path, groups):
    lib = ct.CDLL(library_path)
    lib.ModelCalcerCreate.argtypes = []
    lib.ModelCalcerCreate.restype = ct.c_void_p
    lib.ModelCalcerDelete.argtypes = [ct.c_void_p]
    lib.ModelCalcerDelete.restype = None
    lib.LoadFullModelFromFile.argtypes = [ct.c_void_p, ct.c_char_p]
    lib.LoadFullModelFromFile.restype = ct.c_bool
    lib.CalcModelPredictionSingle.argtypes = [
        ct.c_void_p, ct.POINTER(ct.c_float), ct.c_size_t, ct.POINTER(ct.c_char_p),
        ct.c_size_t, ct.POINTER(ct.c_double), ct.c_size_t]
    lib.CalcModelPredictionSingle.restype = ct.c_bool
    lib.GetErrorString.argtypes = []
    lib.GetErrorString.restype = ct.c_char_p

    numeric = [i for i, name in enumerate(FEATURES) if name not in CATEGORICAL]
    categorical = [i for i, name in enumerate(FEATURES) if name in CATEGORICAL]
    floats = ct.c_float * len(numeric)
    strings = ct.c_char_p * len(categorical)
    model = lib.ModelCalcerCreate()
    if not model:
        raise RuntimeError('Could not initialize CatBoost model')
    try:
        if not lib.LoadFullModelFromFile(model, str(model_path).encode('utf-8')):
            raise ValueError(lib.GetErrorString().decode(errors='replace'))
        fields = []
        for group in groups:
            field = []
            for row in group['x']:
                numbers = floats(*(row[i] for i in numeric))
                names = strings(*(str(row[i]).encode('utf-8') for i in categorical))
                value = ct.c_double()
                if not lib.CalcModelPredictionSingle(model, numbers, len(numbers), names,
                                                     len(names), ct.byref(value), 1):
                    raise ValueError(lib.GetErrorString().decode(errors='replace'))
                field.append(value.value)
            fields.append(field)
        return fields
    finally:
        lib.ModelCalcerDelete(model)
