# Running Ledgr for many schools (platform operator guide)

For the person who signs in as the platform operator (`SUPER_ADMIN`) and looks after every school. Everything here is
on the **Schools and billing** page. Parents are never blocked by anything on it: whatever a school's status, they can
still pay.

## The screen at a glance

| Part | What it is for |
| --- | --- |
| **Payments health** | Every school's online payments on one list, worst first. Check it every morning, and again before and during a term start. Tap a school to jump to its card. |
| **Search and filters** | Find a school by name or admin email. Filters: *Needs renewing*, *Suspended*, *Payment problems*. The list shows 20 at a time. |
| **Record payment** (on a school's card) | What the school paid *you*, and how many months it covers. This is the normal way to renew. |
| **M-Pesa setup** (on a school's card) | That school's own paybill: details, test, register addresses, mode, rotate address. |
| **Edit** | Paid-until date, learner limit, and free extensions (goodwill, no payment). |

## Adding a school

1. **Add school:** school name, the administrator's name and email, a 30-day trial. The administrator gets an email
   with a link to set their own password. If the email could not be sent the page says so; the administrator then uses
   "Forgot password" on the sign-in page.
2. The school's own staff then add classes, fee structures, students and guardians. That is theirs to do.
3. **Online M-Pesa stays off** until you set it up (below). Until then parents are told to pay at the school's paybill.

## Giving a school online M-Pesa

The school needs its **own Paybill** and a Daraja app approved by Safaricom for production ("Go Live"). That approval
is Safaricom's process, not ours, and as far as I know it can take days, so ask the school to start it early. You need
from them: consumer key, consumer secret, passkey and paybill number. A Till (Buy Goods) is not supported.

1. **M-Pesa setup**, choose *Sandbox* to rehearse or *Live* for real money, fill in the four details, **Save details**.
2. **Test connection.** This checks the key and secret only. It always asks Safaricom afresh, never a remembered token.
3. **Register paybill addresses with Safaricom.** This lets direct paybill payments reach Ledgr. As far as I know
   Safaricom lets a live paybill's addresses be registered only once, so do it once, check the result, and do not
   re-register casually. If you ever must change them, check Safaricom's Daraja portal first.
4. **Use this school's own paybill.** Only possible after a successful test.
5. **Prove it with a real payment.** Ask the bursar to pay about KES 10 for a real student, both by payment prompt and
   directly to the paybill with the admission number. Check the invoice, the receipt and the bursar's screen. Only a
   real payment proves the paybill number and passkey. Do this before telling parents.

Give **every** school its own paybill. The *server-wide paybill* option puts every such school's money into one account
(yours), and direct payments with the same admission number then cannot be told apart. Putting a second school on it
now needs you to confirm, and the health list flags it. Holding schools' fees in your own account may also have legal
consequences in Kenya: get advice before doing that.

## When a school pays you

1. Open the school's card, **Record payment**.
2. Enter the amount, how they paid, the M-Pesa code or bank reference, the date, and **how many months it covers**.
   Recording books the money and extends the paid-until date in one step. The extension adds to whichever is later,
   today or their current paid-until date, so paying early loses no days.
3. **0 months** books the money without moving the date (a deposit, for instance).
4. The same reference cannot be booked twice for a school, so a double click does not extend twice.
5. **Entered by mistake** voids a row: it stays in the book, struck through, with your reason. Voiding does **not**
   move the paid-until date back. If the date should change, change it yourself under **Edit**.

The book shows the total paid and each school's list shows when they last paid you.

## Reading Payments health

Counts only: no names, phone numbers or per-person amounts.

| It says | What it means | What to do |
| --- | --- | --- |
| *Last Safaricom problem: …* (Broken) | The last call to Safaricom for this school failed. | Open **M-Pesa setup**, read the message. Often the key or secret was changed on Safaricom's side: save the new ones and test. |
| *Direct paybill payments aren't registered yet* | Payment prompts work, but a payment made straight to the paybill will not reach Ledgr. | Click **Register paybill addresses**. |
| *N payment prompts waiting more than 15 minutes* | Prompts were sent and no answer has arrived. Normally an answer takes a minute or two. | If several schools show it at once, suspect Safaricom or your server. If one school, check its setup. The reconciliation job normally clears genuine ones. |
| *N failed payment prompts in the last 7 days* | Many prompts failed (cancelled, wrong PIN, no funds, or a setup problem). | A few are normal. A sudden jump for one school is worth a look. |
| *N payments with a different amount…* | A parent paid an amount different from the prompt. | The bursar decides these. Remind them if it sits. |
| *N direct paybill payments could not be matched* | Money arrived for a student number nobody matches. | The bursar matches them. |
| *Shares the server-wide paybill with N other schools* | See "Giving a school online M-Pesa". | Move the school to its own paybill. |
| *Online M-Pesa is off* | Not a fault: the school is not set up for it. | Nothing, unless they asked for it. |

"Last payment" is the school's most recent confirmed M-Pesa payment from a parent. A school that was busy and went quiet
is worth a phone call.

## Renewals and suspending

- A school goes `TRIAL` or `ACTIVE`, then `GRACE` (7 days after the end date), then `EXPIRED`. `EXPIRED` and
  `SUSPENDED` schools are read-only for staff. Parents can still pay.
- **Automatic reminders stop** for read-only schools, so a school that has not paid you does not keep using your SMS and
  email credits. They resume the moment the school is renewed.
- Use **Needs renewing** to see who is lapsing. Contact schools while they are in `GRACE`.
- **Suspend** only for non-payment or abuse. It takes effect for staff within about 30 seconds on every server (the
  `USER_STATE_CACHE_SECONDS` setting, never less than 15).

## Rotating a school's webhook address

Each school's address carries a private token. If you think one has leaked, open **M-Pesa setup** and use **Rotate
webhook address**. The old address stops working at once. Only that school is affected.

- It is refused if a payment prompt was sent in the last 5 minutes, so an answer is not lost. Try again shortly.
- Afterwards, direct paybill payments stop reaching Ledgr until the new addresses are registered with Safaricom
  (**Register paybill addresses**). Payment prompts from Ledgr keep working. As noted above, check the Daraja portal
  first if Safaricom will not accept a re-registration.
- Do it at a quiet time, not at term start.

## Never

- **Change `MPESA_CALLBACK_SECRET` once schools are live.** Every school's registered addresses stop working at once.
  Use per-school rotation instead.
- **Lose the encryption keys.** Back up `MESSAGE_ENCRYPTION_KEYS`: it also protects each school's saved M-Pesa details,
  and without it you would have to re-enter every school's details.
- **Edit a live school's secrets during the day.** Saving changed details switches the school back to *off* until you
  test again, so its parents lose "Pay with M-Pesa" in the meantime.
- **Run production without `ENVIRONMENT=production` and `APP_DATABASE_URL`.** Without the second, the database-level
  wall between schools is not in force.
- **Share your operator sign-in.** It can see every school. Keep two-factor on, and keep a recovery path for it.

## Troubleshooting

| Report | Check first |
| --- | --- |
| "I paid but my balance did not change" (one school) | That school's **Payments health** row and **M-Pesa setup**: mode must be *own*, with no last error. Then the bursar's reconciliation queue. |
| Same report from several schools at once | Your server (is it up, did it restart), then Safaricom's status. A platform-wide problem, not a school setup one. |
| A school says "we cannot add students / send announcements" | Its status: probably `EXPIRED` or `SUSPENDED`. Record their payment or reactivate. |
| "Pay with M-Pesa" button missing for a school | Mode is *off*, or the saved details were edited (which switches it off). Test and switch it on again. |
| Payments health fails to load | Refresh. If it keeps failing the rest of the page still works; check the server logs. |

## Before a term starts

- Look at **Payments health** the week before: fix every *Broken* and *Needs a look* school.
- Make sure every school you expect to take payments has made a real test payment this term.
- Run the load test in `backend/loadtest` against **staging**, never production, to see how many payments per minute
  your server and database handle. Ledgr remembers each school's Safaricom login for a short time, so a rush of
  payments does not double the calls to Safaricom, but only a load test tells you your real limits.
