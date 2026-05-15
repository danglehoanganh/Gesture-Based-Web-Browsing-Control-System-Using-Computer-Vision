# TODO - Refactor remove trajectory system

## Phase 1: Backend
- [x] Update `backend/main.py`: remove imports/usage of `TrajectoryManager`, remove trajectory fields from `latest_data`, stop snapshot/append logic.

- [ ] Optimize backend WebSocket payload + reduce websocket traffic (throttle camera_frame if needed).

- [ ] Delete `backend/trajectory_manager.py`.


## Phase 2: Frontend
- [x] Update `frontend/index.html`: remove `<canvas id="trajectoryCanvas">`.

- [x] Update `frontend/style.css`: remove trajectory canvas overlay styles.

- [ ] Update `frontend/app.js`: remove trajectory renderer, remove state for `latestTrajectory`, remove parsing of `trajectory`/`trajectory_gesture`, keep cursor + gesture + click/scroll.
- [ ] Cleanup websocket listener to reduce parsing overhead.

## Phase 3: Validation
- [ ] Run backend and verify gestures still work (CLICK/SCROLL/NEXT/PREV) and realtime cursor movement.
- [ ] Open frontend and verify no canvas/trajectory related errors.
- [ ] Confirm WebSocket payload no longer contains `trajectory` fields.

