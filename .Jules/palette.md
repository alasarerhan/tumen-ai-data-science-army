## 2025-05-14 - [Accessible Collapsed Sidebar]
**Learning:** Standard accessibility pattern for collapsed UI elements (like sidebars) involves wrapping icon-only links in 'Tooltip' components and using the 'sr-only' class to keep text labels accessible to screen readers.
**Action:** Always wrap icon-only navigation items in a Tooltip and provide a hidden text label for assistive technology.
## 2025-05-15 - [Settings Sub-navigation and Feedback]
**Learning:** For settings pages with sub-navigation, using `aria-current="page"` on the active sidebar link improves accessibility. Providing immediate visual feedback via toasts and loading states for destructive or persistent actions significantly enhances the "snappiness" of the UI.
**Action:** Always include ARIA labels for custom toggles and use toasts to confirm successful actions like copying keys or saving forms.
