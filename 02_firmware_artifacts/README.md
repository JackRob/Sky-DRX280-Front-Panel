# Panel diagnostic artifacts

The UF2 files in this directory are diagnostic/reference images used during reverse engineering. They are not universal firmware for every Pico family or panel revision.

Before flashing or wiring a new project, verify:

- Pico family and flash target.
- GP16/GP17 signal assignment.
- Panel logic-rail voltage.
- Level-translator topology, pull-ups and enable state.
- Ground continuity and connector orientation.

Adapt the source and test procedure for your own hardware. A successful result on the documented board is not proof that another revision is wired the same way.
