# Home 221 — visible loading and recovery

Follow-up to Home220 after observing a blank public screen during slow initial
sync. A status surface outside the private application now explains loading.
When initial loading fails without an authorized cached view, it offers an
explicit retry instead of an empty screen. Login and culinary onboarding keep
their own routes; the new surface contains no private data or provider errors.
It does not bypass authentication, delete stored data or auto-resubmit changes.

Home220's daily reliability fixes remain included. 236 Python /343 Node tests
passed; JS syntax and whitespace checks passed. Versions: HTML/APP221, JS229,
SW221; CSS remains144. This is a loading-state repair, not proof that the cause
of the transient502 or slow third-party service is fixed.

Production voice remains blocked by ElevenLabs payment_issue; Muse remains a
candidate integration, not an activated backend. No secrets or budgets shared.
