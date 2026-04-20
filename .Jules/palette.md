# Palette's UX Journal

## 2025-05-14 - Collapsed Sidebar Accessibility
**Learning:** Icon-only navigation items in collapsed sidebars are inaccessible to screen readers and confusing for users if they don't have tooltips or hidden labels.
**Action:** Always wrap icon-only buttons/links in Tooltips and ensure the label is still available in the DOM (e.g., using `sr-only`).
