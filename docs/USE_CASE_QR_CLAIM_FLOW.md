# Tester runbook: Gate-42 QR claim journey

This runbook verifies the mandatory end-to-end path:

```text
pause → jump to 14:10 → inject XY501 delay → perfume campaign wins
→ QR appears at Gate 42 → phone opens claim page → redeem
→ retailer sees redemption and attributed revenue
```

The scenario uses the labelled organizer worked example. Its fixed promo
window is `2026-10-14 13:00–15:40 UTC`; use `14:10`, not `16:00`, because
XY501 has already departed at 16:00.

## Prerequisites

- Start from the repository root.
- Rebuild the application after code or seed changes:

  ```bash
  docker compose up --build --force-recreate
  ```

- For a phone on the same LAN, configure the claim URL before starting:

  ```bash
  AIRP_CLAIM_BASE_URL=http://YOUR-LAN-IP:8000/claim \
  docker compose up --build --force-recreate
  ```

- Open the dashboard using the same reachable address, for example:
  `http://192.168.1.50:8000`.
- Confirm the phone and computer are on the same network.

The QR must not contain `localhost` or `127.0.0.1` when it is intended for a
phone. Existing persistent volumes are repaired at startup if the worked-
example promo row is missing.

## UI test steps

1. Open the dashboard and select **Passenger Screen**.
2. Set the simulation speed to **1×**.
3. Click **Pause**. The button must now read **Play**.
4. Click **⚡ Inject** to open the injection controls.
5. Click **Reset day** in the expanded Inject controls.
6. Click **⏱ Jump** and enter:

   ```text
   2026-10-14T14:10:00Z
   ```

   Click **Jump to time**.
7. In the expanded Inject controls, select:
   - Flight: `XY501 → DXB (gate 42)`
   - Event: `Delay`
   - Minutes: `45`
8. Click **Apply**.
9. Select screen `scr-058 · T2-1-gates · gate 42`.
10. If **Why this ad?** is open, close it.

## Expected checkpoints

The passenger screen should show:

- Perfume creative: `Duty-free perfume — 15% off while delayed`.
- A non-zero crowd profile, approximately the worked-example profile:
  holiday 58%, family 31%, business 22%, international 57%, dwell 52 min.
- A visible QR code and “Scan to claim” call to action.
- Simulation clock fixed at `14:10` while paused.

If the screen shows house content, or the profile shows `0 pax`, the delay
event did not produce the required scenario state. Do not continue to phone
testing; repeat the reset/jump/inject sequence.

## Phone claim and redemption

1. Scan the QR with the phone camera.
2. Open the detected claim link.
3. Confirm the mobile claim page shows the offer, promo code, expiry, and no
   identity/device collection message.
4. Press **Claim code** once.
5. Confirm the page changes to **Claim recorded** and shows the promo code.
6. Switch back to the dashboard and select **Retailer**.
7. Confirm the live redemption notification and attributed revenue update.
8. Pressing **Claim code** again must report the existing redemption rather
   than create a second one.

## Troubleshooting

| Observation | Meaning/action |
|---|---|
| House content / `0 pax` | Jump or delay state is wrong; repeat at `14:10` and apply the XY501 delay. |
| Perfume creative but no QR | Rebuild/restart so startup can repair the scenario promo row; refresh the browser. |
| “Why this ad?” covers the creative | Click **Close** or **Hide**; it is an explanatory overlay. |
| QR URL contains `localhost` | Restart with `AIRP_CLAIM_BASE_URL=http://YOUR-LAN-IP:8000/claim`. |
| Phone cannot open the link | Use the computer’s LAN IP, confirm both devices share a network, and check port 8000 access. |
| Claim page says invalid/expired | Verify the simulation remains on the same run and before `15:40`; reset and repeat if needed. |
| Retailer does not update | Confirm the redemption completed, then allow the WebSocket notification a few seconds to arrive. |

## Automated coverage

The backend claim contract is covered by `backend/tests/test_claims.py`:

```bash
.venv/bin/pytest -q backend/tests/test_claims.py
```

The tests cover the Gate-42 QR-bearing screen and reachable claim route
(`test_gate42_qr_contains_reachable_claim_route`), scan/page-open, redemption
idempotency, family sharing, simulated-token blocking, unknown tokens, and run
reset invalidation. The external phone QR scan has also been manually verified
on the deployed reviewer endpoint.
