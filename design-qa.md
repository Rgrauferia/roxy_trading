# Design QA: Roxy Auth Welcome Screen

Source visual: user-provided mobile login/register reference for Roxy Trading.
Prototype state: `http://localhost:8502/?auth=login` and `http://localhost:8502/?auth=register`.

Checks completed:
- Login gate renders before the dashboard when no Roxy user is authenticated.
- The screen keeps the living universe background, animated Roxy avatar, large ROXY title, language selector, login form, Apple/Google visual actions, registration link, and security note.
- Register mode includes name, username, email, password, language, remember option, and create-account action.
- Registration stores a local salted password hash in `data/roxy_users.json` at runtime and sets the session profile.
- Login accepts username or email and restores the user profile from the local user store.
- Roxy personalization verified with a temporary user: dashboard showed `Bienvenido, Carlos Rivera`, and the assistant message addressed `Carlos Rivera`.
- Mobile DOM check at 393px width: login shell width 385px, document scroll width 393px, login form 347px wide, submit button 305px wide, 2 Roxy avatar images, 2 social actions.
- Register DOM check at 393px width: register form 347px wide, required placeholders visible, submit button 305px wide, document scroll width 393px.
- Desktop DOM check at 1440px width: login shell width 700px, centered premium console, compact Roxy hero above the welcome card, form centered beneath it, no horizontal overflow.
- Intermediate desktop/zoom check at 800px width: centered premium console remains active, shell width 700px, form width 560px, no horizontal overflow.
- Desktop register check at 1440px width: register uses the same centered premium console pattern, with compact Roxy hero, centered form, and no horizontal overflow.
- Browser console error check returned no errors.
- `python3 -m py_compile streamlit_app.py` passed.

Known acceptable differences:
- Apple and Google buttons are visual entry points only until real OAuth client credentials are configured.
- Streamlit sessions reset per browser tab/reload, but registered users persist locally through the user store.

Final result: passed.
