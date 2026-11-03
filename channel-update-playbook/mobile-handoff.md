# Mobile and owner-dependent checks

These are outstanding tasks, not completed setup. Use the actual accounts in [channels.md](channels.md).

## Instagram profile link

Instagram's desktop editor explicitly says profile links can only be edited in the mobile app. In the Instagram app, open **@boldstonesculpture → Edit profile → Links → Add external link**. Use title **Shop Wall Sculptures** and:

`https://boldstonesculpture.com/?utm_source=instagram&utm_medium=organic_social&utm_campaign=wall_sculptures&utm_content=profile`

Open it from the public profile and verify the sculpture collection loads.

## Stories and Wall Sculptures highlight

Create a Story with a photograph of a precisely identified sculpture, add its exact catalogue product sticker where available and a website link sticker. Use the actual product URL with `utm_source=instagram&utm_medium=organic_social&utm_campaign=wall_sculptures&utm_content=story_COMPONENTID_DATE`. Publish, then save it into a **Wall Sculptures** highlight. Start with current product photographs rather than the unrelated older archive stories inspected on 31 October.

The Facebook Story published on 31 October has a product link, but Business Suite explicitly says its web-link feature is Facebook-only. It does not establish that Instagram has a linked Story or highlight.

## Existing posts, Reels and product tags

Open a relevant post in the Instagram app, choose **Edit → Tag products** if available, and select the exact component and finish. Never tag both panels when the picture shows only one. The desktop edit UI inspected on 31 October offered people tags but not product tags. Create a Reel only from suitable approved footage/images; verify product-tag availability in the account's Reel publishing screen.

A new Ammonite Petite II (Right) - White post was published with the exact catalogue tag selected in Business Suite:

https://www.instagram.com/boldstonesculpture/p/DfLJ6kVFxt2/

On a physical phone, tap the product tag and verify **Ammonite Petite II (Right) - White**, SKU **BOLD-EFBAEB31C2B1**, the current website price and the right-hand-panel website page. Then add to cart and reach checkout. This mobile tag-to-checkout route remains unverified; a successful desktop publication does not pass it.

## Purchase tracking

GA4 observed product, cart and checkout events on 31 October. No order was submitted. The earlier test-mode proposal is superseded: native Meta purchase tracking is suppressed for test orders, so that approach cannot verify Meta purchases. Keep live checkout unchanged and reconcile a genuine completed order against both platforms. A charged test purchase would need specific payment authorisation first. See [the purchase-test boundary](test-matrix.md#purchase-test-boundary). Do not manufacture purchase events.

Meta Test Events showed no fresh event cards during the inspected test. Exact event-to-catalogue matching and purchase/source attribution remain unverified. Re-test consent, exact content IDs and the in-app browser route rather than treating old catalogue-match percentages as current evidence.

## Other pending decisions

- Google Customer Reviews: the add-on is enabled, but its agreement and order-data sharing require approval. No agreement was accepted.
- Returns: the public page says requests within 30 days and the customer pays actual return postage. Checkout still says “No refunds”. [The proposed checkout summary](checkout-return-policy-proposed.txt) awaits confirmation before changing purchase terms.
- Loyalty, promotions and Wallet: no real rewards scheme, discount offer or gift-card programme was supplied. Enabling the Promotions add-on did not create a customer offer.
