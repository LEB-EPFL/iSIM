import numpy as np
import time
import matplotlib.pyplot as plt

np.random.seed(42)
img = np.random.normal(3000, 500, (2048, 2048)).astype(np.uint16)

for a in range(1000000):
    pos = np.random.randint(0, 2048, 2)
    img[pos[0], pos[1]] = np.random.normal(10000, 500, 1)

t0 = time.perf_counter()
hist = np.bincount(img.ravel(), minlength=2**16)
t1 = time.perf_counter()
print("bincount", t1 - t0)

bin_size = 50
bins = np.arange(0, 2**16, bin_size)
t2 = time.perf_counter()
binned = np.digitize(img.ravel(), bins)
hist2 = np.bincount(binned, minlength=len(bins))
print("digitize", time.perf_counter() - t1)
hist2 = hist2/bin_size


hist[0] = hist[-1] = 0
plt.step(np.arange(2**16), hist)
plt.step(bins, hist2)
plt.show()