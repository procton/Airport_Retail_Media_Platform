# WOW demo script: under one minute

This is the short presentation path for the required cross-role cause and
effect. Rehearse it with the backend paused at the start so the presenter can
control the timing.

## Before the audience arrives

1. Start the app with `docker compose up --build`.
2. Open the dashboard, choose **Retailer**, and click **↔ Split**. The passenger
   screen is now on the left and the retailer dashboard is on the right.
3. Click **⚡ Inject**, choose **Reset day**, then **⏱ Jump** to
   `2026-10-14T14:10:00Z`. Pause the clock.
4. Keep Gate 42 / `scr-058` selected. The screen should be ready for the
   worked-example delay.

## Live presentation (target: 45–60 seconds)

1. Say: “Here is the same airport state seen by the passenger, airline, and
   retailer.” Switch briefly to **Airline Rep** if needed to show the flight
   and gate context; return to the split view.
2. In **⚡ Inject**, select `XY501 → DXB`, choose **Delay**, enter `45`, and
   click **Apply**. Within two seconds point out the delayed flight, increased
   Gate-42 audience, and the perfume offer replacing the previous slot.
3. Point to the passenger QR and say: “The delay changed the offer, not just a
   counter.” Scan it with a phone and open the claim page.
4. Tap **Redeem** on the phone. Return attention to the retailer panel and show
   the redemption notification and attributed revenue.
5. Switch to **Retailer → Campaigns** and run the second WOW beat: enter
   `Festive sweets, 20% off, families flying domestic` in **Creative assistant**,
   then click **Draft ad**. Show the English and configured second-language
   previews.
6. Select an approved campaign in **Forecast tomorrow** and show the ranked
   three slots with predicted impressions and redemptions.

## Optional 15-second resilience beat

Open **⚡ Inject**, select a screen, click **Screen offline**, and show the
screen-health state/fallback. Click **Screen online** to restore it. This is a
separate operational proof and should not interrupt the main claim story.

## Recovery

If the QR is absent, reset and repeat the jump/injection sequence at 14:10.
For a phone, set `AIRP_CLAIM_BASE_URL` to the computer's reachable LAN URL; a
QR must never contain `localhost` or `127.0.0.1`.
