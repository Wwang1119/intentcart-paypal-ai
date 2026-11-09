# Validation record

## Real provider test: November 9, 2026

The complete local browser flow was tested against the actual DeepSeek API and PayPal sandbox. This record is separate from the offline mock tests.

- Input: `I need two notebooks and a desk mat, under $45.`
- Model: `deepseek-flash` using JSON output.
- Validated catalog cart: 2 × Everyday Notebook ($12.00) and 1 × Studio Desk Mat ($18.00).
- Total: **42.00 USD**, within the 45.00 USD budget.
- PayPal order: `67A47152M5777283Y`.
- Buyer approval: a generated **sandbox personal** account, paying with its **simulated PayPal balance**.
- Server-side capture: `2BK19127YU633970R`.
- Capture status: **COMPLETED**.
- PayPal capture time: `2026-11-09T15:11:11Z` (November 9, 23:11:11, GMT+8).
- The returned order reference, amount, currency, and completed capture status were checked against the stored draft before a receipt was shown.

No real money or real cards were used. Credentials and raw local evidence remain outside Git. These sandbox identifiers are test transaction references, not authentication credentials.

## English demonstration recording

A second complete provider test was recorded with an English-language, generated US sandbox personal buyer using PayPal's pre-generated fictional funding method. No real bank/card information was entered.

- Order: `2VF8317785897294A`.
- Capture: `95802116K4171093R`.
- Amount: **42.00 USD**.
- Capture status: **COMPLETED**.
- Capture time: `2026-11-09T15:50:38Z` (November 9, 23:50:38, GMT+8).

The video uses actual browser captures with edited pauses and synthetic English narration.

## Offline tests

`python3 -m unittest discover -s tests -v`: **18 passed**.

Those tests use mock responses and cover rejection and retry paths. They are not a substitute for the real provider test above.
