# IntentCart

**From a sentence to a checkout, with a human in control.**

IntentCart is a lightweight AI shopping assistant built for the 2026 PayPal AI Hackathon. A cloud language model turns a natural-language request into structured shopping intent. Python validates the products, computes the exact total from a fixed catalog, and creates a PayPal **sandbox** order only after the shopper confirms the review screen. After sandbox approval, the server captures the order and verifies the actual capture status, amount, currency, and reference before showing a receipt.

This is a local hackathon prototype. All products are fictional demo items; there is no fulfillment. **No real money, real payment accounts at checkout, or real cards are used.** PayPal production endpoints are not configurable.

## Run in one command

Requires **Python 3.11+** and an internet connection. No pip packages, frontend build, database server, or local model are needed.

```sh
git clone https://github.com/Wwang1119/intentcart-paypal-ai.git
cd intentcart-paypal-ai
cp .env.example .env
```

Fill in `.env` using your own sandbox and AI credentials, then run:

```sh
python3 app.py
```

Open **http://127.0.0.1:8000/** in your browser. Use that exact host (not `localhost`), and use the same browser throughout the payment flow. Stop with Ctrl+C. Restart after changing `.env`.

## Configure PayPal sandbox

1. Sign in to [PayPal Developer](https://developer.paypal.com/dashboard/) with your PayPal developer account. Your developer login is separate from the fictional sandbox buyer/seller identities.
2. Select **Sandbox**, then **Apps & Credentials**. Create a REST app named `IntentCart` associated with a **sandbox business** account.
3. Copy its **sandbox Client ID** and **sandbox Secret** into `.env`:

   ```dotenv
   PAYPAL_CLIENT_ID=your_sandbox_client_id
   PAYPAL_CLIENT_SECRET=your_sandbox_secret
   LLM_API_KEY=your_cloud_model_api_key
   LLM_BASE_URL=https://api.deepseek.com
   LLM_MODEL=deepseek-flash
   PORT=8000
   ```

4. Under **Testing Tools → Sandbox Accounts**, locate or create a **Personal** sandbox account for the buyer and a **Business** sandbox account for the seller. Use distinct accounts.
5. Select the sandbox personal account's **View/Edit Account** action to obtain its generated test email and password. Use **only these sandbox credentials** on `www.sandbox.paypal.com` during checkout.
6. Use the sandbox buyer's simulated balance. Do not enter real card details or sign in as a real buyer. The demo requests no shipping address.

The app obtains a server-side OAuth access token from `https://api-m.sandbox.paypal.com/v1/oauth2/token`, then uses Orders v2 create, show, and capture endpoints on the same sandbox host. Checkout returns to the exact local origin printed at startup; no webhook or public hosting is required for this flow.

Official references: [sandbox accounts](https://developer.paypal.com/sandbox-testing/accounts), [Orders v2 create](https://developer.paypal.com/api/orders/v2/orders-create), [Orders v2 capture](https://developer.paypal.com/api/orders/v2/orders-capture).

## Configure AI

Create an API key in your own [DeepSeek platform account](https://platform.deepseek.com/) and store it in `LLM_API_KEY`. `deepseek-flash` is the default model. The implementation calls `/chat/completions` with JSON output; another compatible HTTPS provider can be configured with `LLM_BASE_URL` and `LLM_MODEL`.

The model receives the shopping prompt and the four-product demo catalog. It never receives PayPal secrets, access tokens, sandbox buyer credentials, or payment information. Cloud model usage is billed by your provider; no local model runs. [DeepSeek JSON output documentation](https://api-docs.deepseek.com/guides/json_mode/).

## The complete demo flow

1. Enter: **“I need two notebooks and a desk mat, under $45.”**
2. AI extracts two `notebook` units and one `desk-mat` unit. The server prices the items at **$42.00 USD** from its own catalog and checks the budget.
3. Review the quantities and exact total. Click **Confirm & continue to PayPal**.
4. On **PayPal sandbox**, sign in with the sandbox **personal buyer** and approve the simulated payment.
5. PayPal returns to IntentCart. The server checks the order, captures an approved payment, and verifies the receipt. A successful capture displays **COMPLETED**, the PayPal order ID, and the capture ID.

Alternative request: **“One canvas tote and a pen set, under $30.”** The catalog total is **$24.00 USD**. An insufficient budget or unavailable product produces a clarification instead of a payable cart. These examples describe intended inputs and catalog arithmetic; they do not assert that a real provider test has been completed.

## Why the AI cannot set the price

The AI's output is limited to catalog product IDs, integer quantities, an optional USD budget, and a clarification. Unknown products, duplicate lines, extra model fields (including prices), invalid quantities, and malformed or truncated JSON are rejected. Product prices and totals are calculated using Python `Decimal`. The browser submits an opaque draft ID rather than its own total.

The review button authorizes creation of the exact stored order. PayPal handles buyer approval. IntentCart does not expose an autonomous payment tool to the language model.

## Payment reliability and privacy

- PayPal API calls and approval links are restricted to sandbox hosts. There is no live-mode switch.
- A browser session owns each draft/order. Cross-session captures are rejected.
- The server uses stable PayPal request IDs and stores order/receipt state in local SQLite. Repeated create/capture requests reuse the same order. A completed capture can be recovered after a response interruption.
- A receipt is shown only when the actual capture is `COMPLETED` and its order ID, reference, currency, and amount match the stored draft. Pending/declined captures do not appear as success.
- The server binds to `127.0.0.1`; requests use host/origin checks and CSRF protection. It serves only four explicit public asset paths, plus the app API.
- `.env`, local SQLite data, credentials, recordings, and screenshots in `.local/` are ignored by Git. No payer profile details are retained in receipts. Request logs omit query strings and provider response bodies.

This intentionally small local demo is not a production storefront: no inventory reservations, shipping, taxes, refunds, webhooks, multi-user deployment, or reconciliation worker are included. Production use would require a separate security and operational design.

## Tests

```sh
python3 -m unittest discover -s tests -v
```

The 18 automated tests cover catalog pricing and budgets, malformed AI output, sandbox-only approval links, session ownership, idempotent create/capture, incomplete and mismatched receipts, interrupted-response recovery, CSRF/origin checks, and secret-file isolation. **Tests mock AI/PayPal responses; they are not proof of an actual sandbox transaction.**

For real end-to-end testing, use the complete browser flow above with your own configured credentials. Verify the capture ID in the sandbox business account's activity. Do not mark payment testing complete based on unit tests alone.

## Troubleshooting

| Problem | Action |
| --- | --- |
| Setup needed | Fill `.env`, save it, and restart `python3 app.py`. The app never substitutes fake AI or payments. |
| Provider rejects credentials | Ensure the PayPal app is in **Sandbox**, and the AI key is valid with available provider credit. |
| Sandbox sign-in fails | Use the **sandbox personal** credentials from Testing Tools, not the developer login or sandbox business seller. |
| Payment canceled | No capture is requested by the cancellation route. Generate another cart to try again. |
| Verification pending or network error | Keep the same browser and use **Verify sandbox payment** again. The server checks PayPal before retrying capture. |
| Session expired or order unavailable | Return in the original browser. Avoid private-window changes or clearing cookies during checkout. |
| Port already in use | Change `PORT` in `.env` and restart; open the exact printed URL. |

## Files and license

`app.py` contains the server, AI adapter, validation, PayPal adapter, and SQLite state. `web/` contains the English interface. `tests/` contains offline contracts. `docs/` contains the project narrative and demo storyboard.

Built by **Wang Yexiang**. Source released under the [MIT License](LICENSE).
