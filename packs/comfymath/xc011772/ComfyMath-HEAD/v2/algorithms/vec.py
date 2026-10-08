import numpy
from typing import Any, Callable, Mapping
from .types import Vec2, Vec3, Vec4
VEC2_ZERO = (0.0, 0.0)
DEFAULT_VEC2 = ('VEC2', {'default': VEC2_ZERO})
VEC3_ZERO = (0.0, 0.0, 0.0)
DEFAULT_VEC3 = ('VEC3', {'default': VEC3_ZERO})
VEC4_ZERO = (0.0, 0.0, 0.0, 0.0)
DEFAULT_VEC4 = ('VEC4', {'default': VEC4_ZERO})
VEC_UNARY_OPERATIONS: Mapping[str, Callable[[numpy.ndarray], numpy.ndarray]] = {'Neg': lambda a: -a, 'Normalize': lambda a: a / numpy.linalg.norm(a)}
VEC_TO_SCALAR_UNARY_OPERATION: Mapping[str, Callable[[numpy.ndarray], float]] = {'Norm': lambda a: numpy.linalg.norm(a).astype(float)}
VEC_UNARY_CONDITIONS: Mapping[str, Callable[[numpy.ndarray], bool]] = {'IsZero': lambda a: not numpy.any(a).astype(bool), 'IsNotZero': lambda a: numpy.any(a).astype(bool), 'IsNormalized': lambda a: numpy.allclose(a, a / numpy.linalg.norm(a)), 'IsNotNormalized': lambda a: not numpy.allclose(a, a / numpy.linalg.norm(a))}
VEC_BINARY_OPERATIONS: Mapping[str, Callable[[numpy.ndarray, numpy.ndarray], numpy.ndarray]] = {'Add': lambda a, b: a + b, 'Sub': lambda a, b: a - b, 'Cross': lambda a, b: numpy.cross(a, b)}
VEC_TO_SCALAR_BINARY_OPERATION: Mapping[str, Callable[[numpy.ndarray, numpy.ndarray], float]] = {'Dot': lambda a, b: numpy.dot(a, b), 'Distance': lambda a, b: numpy.linalg.norm(a - b).astype(float)}
VEC_BINARY_CONDITIONS: Mapping[str, Callable[[numpy.ndarray, numpy.ndarray], bool]] = {'Eq': lambda a, b: numpy.allclose(a, b), 'Neq': lambda a, b: not numpy.allclose(a, b)}
VEC_SCALAR_OPERATION: Mapping[str, Callable[[numpy.ndarray, float], numpy.ndarray]] = {'Mul': lambda a, b: a * b, 'Div': lambda a, b: a / b}

def _vec2_from_numpy(a: numpy.ndarray) -> Vec2:
    return (float(a[0]), float(a[1]))

def _vec3_from_numpy(a: numpy.ndarray) -> Vec3:
    return (float(a[0]), float(a[1]), float(a[2]))

def _vec4_from_numpy(a: numpy.ndarray) -> Vec4:
    return (float(a[0]), float(a[1]), float(a[2]), float(a[3]))
