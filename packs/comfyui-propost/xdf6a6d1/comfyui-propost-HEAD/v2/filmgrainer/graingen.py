from PIL import Image
import random
import numpy as np

def _makeGrayNoise(width, height, power, rng):
    buffer = np.zeros([height, width], dtype=int)

    for y in range(0, height):
        for x in range(0, width):
            buffer[y, x] = rng.gauss(128, power)
    buffer = buffer.clip(0, 255)
    return Image.fromarray(buffer.astype(dtype=np.uint8))

def _makeRgbNoise(width, height, power, saturation, rng):
    buffer = np.zeros([height, width, 3], dtype=int)
    intens_power = power * (1.0 - saturation)
    for y in range(0, height):
        for x in range(0, width):
            intens = rng.gauss(128, intens_power)
            buffer[y, x, 0] = rng.gauss(0, power) * saturation + intens
            buffer[y, x, 1] = rng.gauss(0, power) * saturation + intens
            buffer[y, x, 2] = rng.gauss(0, power) * saturation + intens

    buffer = buffer.clip(0, 255)
    return Image.fromarray(buffer.astype(dtype=np.uint8))


def grainGen(width, height, grain_size, power, saturation, seed = 1):
    # A grain_size of 1 means the noise buffer will be made 1:1
    # A grain_size of 2 means the noise buffer will be resampled 1:2
    noise_width = int(width / grain_size)
    noise_height = int(height / grain_size)
    rng = random.Random(seed)

    if saturation < 0.0:
        print("Making B/W grain, width: %d, height: %d, grain-size: %s, power: %s, seed: %d" % (
            noise_width, noise_height, str(grain_size), str(power), seed))
        img = _makeGrayNoise(noise_width, noise_height, power, rng)
    else:
        print("Making RGB grain, width: %d, height: %d, saturation: %s, grain-size: %s, power: %s, seed: %d" % (
            noise_width, noise_height, str(saturation), str(grain_size), str(power), seed))
        img = _makeRgbNoise(noise_width, noise_height, power, saturation, rng)

    # Resample
    if grain_size != 1.0:
        img = img.resize((width, height), resample = Image.LANCZOS)

    return img

