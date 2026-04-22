## 2026-03-12 - [Accessible Tooltips for Collapsed Navigation]
**Learning:** For collapsed sidebars with icon-only links, combining Radix Tooltips with 'sr-only' labels provides a double-layer of accessibility. The 'sr-only' label ensures screen readers always have a textual description, while the Tooltip provides visual clarity for sighted users when hover/focus occurs.
**Action:** Always wrap icon-only navigation links in Tooltips and include an 'sr-only' span for the label text.

## 2026-03-12 - [Dev Mode Auth Bypass for Verification]
**Learning:** This repository supports a 'dev' token bypass. Setting the 'access_token' cookie to 'dev' allows immediate access to the authenticated state with a stubbed user, which is extremely useful for Playwright verification scripts.
**Action:** Use `context.add_cookies([{"name": "access_token", "value": "dev", ...}])` in Playwright scripts to bypass login screens.
