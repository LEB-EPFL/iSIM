
Full dict for a MDASequence
autofocus_plan: null
axis_order:
- t
- p
- g
- z
- c
channels:
- acquire_every: 1
  camera: null
  config: Cy5
  do_stack: true
  exposure: 100.0
  group: Channel
  z_offset: 0.0
- acquire_every: 1
  camera: null
  config: DAPI
  do_stack: true
  exposure: 100.0
  group: Channel
  z_offset: 0.0
grid_plan:
  columns: 1
  fov_height: 512.0
  fov_width: 512.0
  mode: row_wise_snake
  overlap:
  - 0.0
  - 0.0
  relative_to: center
  rows: 1
keep_shutter_open_across: []
metadata:
  pymmcore_widgets:
    version: 0.5.3
stage_positions:
- name: null
  sequence: null
  x: 0.0
  y: 0.0
  z: 0.0
time_plan:
  interval: 0:00:01
  loops: 1
  prioritize_duration: false
z_plan:
  bottom: 0.0
  go_up: true
  step: 1.0
  top: 20.0