# Stripe wallets & express checkout (Apple Pay / Google Pay / Link)

Most buyers pay on phones. Stripe Hosted Checkout can show **Apple Pay**,
**Google Pay**, and **Link** with almost no code — but they must be **on** in
the Dashboard.

## Code (already set)

`create_stripe_checkout_session` intentionally **does not** pass
`payment_method_types`. That keeps [dynamic payment methods](https://docs.stripe.com/payments/payment-methods/dynamic-payment-methods)
so Stripe can offer wallets when the device/browser supports them.

Link display is set to `auto` via `wallet_options`.

## What you must do in Stripe Dashboard (live mode)

1. Open [Payment methods](https://dashboard.stripe.com/settings/payment_methods)
2. Turn **ON**:
   - **Cards**
   - **Apple Pay**
   - **Google Pay**
   - **Link** (express autofill)
3. Save. Changes can take a few minutes.
4. Do a phone test:
   - **iPhone Safari** → Apple Pay / Link should appear on Stripe’s page
   - **Android Chrome** → Google Pay / Link should appear

## On-page Express Checkout (Apple Pay / Google Pay / Link)

Checkout can show wallet buttons **on noorlink.co** via Stripe Express Checkout
Element (`POST /api/checkout/payment-intent`). Fulfillment listens for
`payment_intent.succeeded` as well as `checkout.session.completed`.

### Domain verification (Apple Pay on your site)

1. [Payment methods → Apple Pay](https://dashboard.stripe.com/settings/payment_methods)
2. Add domain **`noorlink.co`** (and `www.noorlink.co` if used)
3. Turn ON Apple Pay, Google Pay, and Link

Without domain verification, wallets still work on Stripe Hosted Checkout
(`checkout.stripe.com`) after “Continue to pay”, but not as buttons on our page.

## Optional: pin a configuration

If you use multiple payment method configs, set on Railway:

```env
STRIPE_PAYMENT_METHOD_CONFIGURATION=pmc_...
```

## Test plan

1. Buy a cheap plan on an iPhone (Safari) — confirm Apple Pay button on Stripe.
2. Same on Android Chrome — confirm Google Pay.
3. Confirm webhook + QR email still fire after a wallet payment.
