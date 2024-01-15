from useq import MDASequence



seq = MDASequence(grid_plan = {"columns": 2, "rows": 2})

for ev in seq.iter_events():
    print(ev)

seq = MDASequence(grid_plan = {"columns": 3, "rows": 3})

x_pos = []
y_pos = []
for ev in seq.iter_events():
    x_pos.append(ev.x_pos)
    y_pos.append(ev.y_pos)
    print(ev)


import matplotlib.pyplot as plt

plt.scatter(x_pos, y_pos)
plt.show()