# WebSocket contract

The backend exposes one shared stream at `/ws`. Clients receive JSON objects
with this envelope:

```json
{"topic":"presence.zone","data":{"zone_id":"T2-1-gates","passenger_count":120}}
```

The connection first receives a `state.resync` snapshot containing the current
simulation timestamp, run id, and control state. It then receives event
messages as they occur. If no event arrives for 15 seconds, the server sends a
`heartbeat` with the current simulation timestamp. Clients should reconnect
and wait for a new `state.resync` after a disconnect or run reset.

## Topics

| Topic | Purpose | Typical data |
|---|---|---|
| `state.resync` | hydrate/resynchronize a client | `at`, `run_id`, `control` |
| `state.control` | play/pause/speed/clock update | `playing`, `speed`, `at` |
| `controls` | control acknowledgement/event | control action details |
| `screens.playlist` / `screen.playlist` | playback or re-plan update | slots, screen, latency |
| `presence.zone` | current zone presence projection | serialized `ZonePresence` |
| `flight.update` | canonical flight state changed | flight view |
| `screen.state` | screen online/degraded state | `screen_id`, `online`, `at` |
| `campaign.status` | approval or run-again status change | campaign id/status |
| `media-rules` | admin rule configuration changed | bounded media rules |
| `redemption.live` | redemption notification | token, timestamp, mode |
| `incidents` | incident tracker update | incident payload |
| `heartbeat` | transport keepalive | `at` |

Unknown topics must be ignored by clients for forward compatibility. Event
delivery is best-effort: slow subscribers may miss intermediate updates and
must use REST state endpoints or the next `state.resync` to recover.
