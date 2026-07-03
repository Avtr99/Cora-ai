# Design System Documentation

Design system for the Cora VCM application. Single source of truth — one entry per concern. **`src/lib/colors.ts` is the canonical color module**; all components should import from it instead of hardcoding hex values.

---

## Design Tokens

### Typography

**Setup** — Google Fonts imported in `index.html`; Tailwind configured with `font-poppins` and `font-inter` utility classes.

```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
```

```js
// tailwind.config.ts
fontFamily: { sans: ['Inter', ...], poppins: ['Poppins', 'sans-serif'], inter: ['Inter', 'sans-serif'] }
```

#### Type Scale

| Style | Font | Size | Weight | Line-height | Tracking | Tailwind |
|---|---|---|---|---|---|---|
| H1 | Poppins | 56px | 700 | 67px | -1.12px | `font-poppins font-bold text-[56px] leading-[67px] tracking-[-1.12px]` |
| H2 | Poppins | 40px | 600 | 52px | -0.4px | `font-poppins font-semibold text-[40px] leading-[52px] tracking-[-0.4px]` |
| H3 | Poppins | 32px | 600 | 45px | -0.16px | `font-poppins font-semibold text-[32px] leading-[45px] tracking-[-0.16px]` |
| H4 | Poppins | 24px | 500 | 34px | — | `font-poppins font-medium text-2xl leading-[34px]` |
| H5 | Poppins | 20px | 500 | 30px | — | `font-poppins font-medium text-xl leading-[30px]` |
| H6 | Poppins | 16px | 600 | 24px | 0.8px | `font-poppins font-semibold text-base leading-6 tracking-[0.8px]` |
| Body-Bold | Inter | 16px | 600 | 22px | — | `font-inter font-semibold text-base leading-[22px]` |
| Body-Medium | Inter | 16px | 500 | 26px | — | `font-inter font-medium text-base leading-[26px]` |
| Body-Regular | Inter | 16px | 400 | 26px | — | `font-inter font-normal text-base leading-[26px]` |
| Body-Small Bold | Inter | 12px | 600 | 16px | — | `font-inter font-semibold text-xs leading-4` |
| Body-Small | Inter | 12px | 400 | 16px | — | `font-inter font-normal text-xs leading-4` |
| Button Label | Inter | 10px | 600 | 9px | 0.1px | `font-inter font-semibold text-[10px] leading-[9px] tracking-[0.1px]` |
| Subtitle/Label | Poppins | 10px | 600 | normal | — | `font-poppins font-semibold text-[10px] uppercase` |

---

### Colors

All tokens live in **`src/lib/colors.ts`**. Never hardcode hex values in components — import from this module.

#### CSS Variables (shadcn/ui — `src/index.css`)

Several tokens intentionally share the same value in light mode but diverge in dark mode/custom themes:
- `--secondary` / `--muted` / `--accent` → all `hsl(210 40% 96.1%)` in light mode
- `--card` / `--popover` / `--background` → all `hsl(0 0% 100%)`

#### `colors.ts` Exports

| Export | Purpose |
|---|---|
| `BRAND` | Brand purple scale: `primary900` (#403D85), `primary700` (#4A2AA3), `primary500` (#6F4ECB), `primary200` (#E9D5FF), `primary100` (#F3E8FF) |
| `NEUTRAL` | Neutral gray scale: 0 (#FFF) → 900 (#171717) |
| `TEXT` | Semantic text: `primary` #171717, `body` #525252, `muted` #6B7280, `disabled` #B8BEC8 |
| `INTERACTIVE` | States: `default` #6B7280, `hover/active` #6F4ECB, `focusRing` rgba(74,42,163,0.35) |
| `ICON_STATE` | Icon states: `default` #6B7280, `active/selected` #6F4ECB |
| `getProjectTypeColor(type)` | Returns `{ accent, bg, text }` for Forest/REDD+, Renewable, Agriculture, Cookstove/Household, Landfill/Industrial, default purple |
| `getStatusStyle(status)` | Returns `{ bg, text, dot }` for registered/active (green), completed (blue), cancelled (red), under development (amber), crediting period ended (gray) |
| `DOCUMENT_TYPE_COLORS` | Knowledge Base badge colors keyed by type (see TypeBadge section) |
| `CATEGORY_THEMES` | Pricing page icon/bg colors for Agriculture, Household Devices, Renewable Energy, REDD+ |
| `NOTICE_COLORS` | Modal notice card colors: research (amber), privacy (purple), cancelled, error |
| `TREND_COLORS` | SBTImpact badge colors: rising (green), declining (orange), note (amber) |

#### Semantic Quick Reference

| Role | Value | Usage |
|---|---|---|
| Text primary | `#171717` | Headings, key labels |
| Text body | `#525252` | Card content, descriptions |
| Text muted | `#6B7280` | Captions, metadata, section labels |
| Page bg | `#FFFFFF` | Full-page background |
| Surface base | `#FAFAFA` | Panels, alt table rows |
| Surface subtle | `#F3F4F6` | Input bg, dividers |
| Border | `#E5E7EB` | All borders (unifies #E5E5E5, #ECECF0, #E7E7E7) |
| Brand primary | `#403D85` | Buttons, main actions |
| Brand secondary | `#6F4ECB` | Hover states, active icons |
| Brand link | `#4A2AA3` | Nav links, back buttons |
| Warning bg | `#FFF9E6` | Alert / notice cards |
| Warning border | `#FFE7A3` | Alert / notice cards |
| Warning icon | `#F59E0B` | Alert icons |

---

### Spacing & Sizing

- Base unit: `0.25rem` (4px)
- Standard button padding: `px-4 py-2`
- Flex gap: `gap-2.5` (10px)
- Pill padding: `px-4 py-2`

### Border Radius

CSS variable `--radius: 0.5rem` (8px). Derived:
- `rounded-lg` → 8px, `rounded-md` → 6px, `rounded-sm` → 4px
- Custom: `rounded-[20px]` pills, `rounded-2xl` cards, `rounded-full` badges

### Elevation (Shadows)

Defined as CSS custom properties in `src/index.css` and Tailwind utilities in `tailwind.config.ts`.

| Class | Value | Use |
|---|---|---|
| `shadow-xs` | `0 1px 2px rgba(0,0,0,0.05)` | Base cards, pills |
| `shadow-card` | `0 2px 8px rgba(0,0,0,0.04)` | Prompt cards |
| `shadow-card-md` | `0 2px 8px rgba(0,0,0,0.06)` | SearchBar large |
| `shadow-card-sm` | `0 2px 6px rgba(0,0,0,0.04)` | SearchBar composer |
| `shadow-bottom-bar` | `0 -4px 16px rgba(0,0,0,0.08)` | Cookie consent bar |
| `shadow-modal` | `0 32px 64px -12px rgba(0,0,0,0.14)` | Modals |
| `shadow-scroll-btn` | `0 2px 8px rgba(0,0,0,0.08)` | Scroll-to-top button |
| `shadow-sm-hover` | `0 6px 18px rgba(17,17,26,0.08)` | Card/pill hover lift |

Glow effects (inline, single-use): send button large `0 0 20px rgba(111,78,203,0.25)`, composer `0 0 12px rgba(111,78,203,0.2)`.

### Focus Rings

Standard: `focus:outline-none focus-visible:ring-2 focus-visible:ring-[rgba(74,42,163,0.35)] focus-visible:ring-offset-2 focus-visible:ring-offset-white`

Light variant (dropdowns): `focus-visible:ring-[rgba(74,42,163,0.25)]`

Placeholder text: `placeholder:text-muted-foreground/70`

### Motion & Animation

- Standard: `transition-colors duration-200`
- Layout/sidebar: Framer Motion `{ duration: 0.2, ease: 'easeOut' }`
- Reasoning panel expand: `.reasoning-content` fades/slides in ~200ms via `details[open]` CSS; respects `prefers-reduced-motion`
- Keyframes: `accordion-down`, `accordion-up` for expandable elements

---

## Components

### Sidebar
- **File**: `src/components/layout/Sidebar.tsx`
- **Collapsed**: 60px — icon-only nav items (`w-10 h-10`), compact New Chat button
- **Expanded**: 250px — icon + label nav items (`gap-2 px-3 py-2`)
- **Animation**: Framer Motion 200ms easeOut
- **Features**: TanStack Virtual for chat list, mobile hamburger menu
- **Nav items**: Chat, Knowledge Base, Pricing, Explore Projects, About

### SearchBar
- **File**: `src/components/chat/SearchBar.tsx`
- **Large variant** (main page): blurred gradient glow behind composer — `linear-gradient(135deg, rgba(147,51,234,0.15), rgba(236,72,153,0.15))` at `opacity-40 blur-2xl z-[-1]`; send button glow `shadow-[0_0_20px_rgba(111,78,203,0.25)]`; shadow `shadow-card-md`
- **Composer variant** (chat page): compact, no gradient bg; send button glow `shadow-[0_0_12px_rgba(111,78,203,0.2)]`; shadow `shadow-card-sm`
- **Textarea**: auto-grows up to 6 lines, `resize-none`; `Enter` sends, `Shift+Enter` newline
- **Send button**: switches to Stop action during generation (lighter purple `#9B87F5`, white square icon); remains actionable to cancel; disabled only when input is empty or rate-limited
- **Tooltips**: `"Enter to send • Shift+Enter for newline"` on textarea and button

### FilterDropdown
- **File**: `src/components/ui/FilterDropdown.tsx`
- **Keyboard**: ArrowUp/Down, Enter, Escape; ARIA: `listbox`, `option`, `aria-selected`
- **Button**: `h-8 px-3 rounded-lg font-inter text-[12px] font-medium`
- **Active**: `bg-[#403D85] text-white border-[#403D85]`
- **Inactive**: `bg-white text-[#525252] border-[#E5E7EB] hover:border-[#D1D5DB]`
- **Dropdown**: `rounded-xl shadow-lg max-h-[280px] min-w-[200px]`; option hover `bg-[#FAFAFA]`, focused `bg-[#F3F4F6]`

### Pills (Category Filters)
- Base: `bg-[rgba(47,45,90,1)] text-white rounded-full px-4 py-2 font-poppins`
- Hover: darken ~10%, `shadow-sm-hover`, scale 1.03
- Active: `scale-[0.98]`; Focus: focus-primary ring; Motion: `transition-all duration-200 ease-out`

### Button (shadcn/ui)

| Variant | Description |
|---|---|
| `default` | Brand color background |
| `destructive` | Red background |
| `outline` | Transparent with border |
| `secondary` | Secondary brand bg |
| `ghost` | No bg until hover |
| `link` | Text link with underline |

| Size | Classes |
|---|---|
| `default` | `h-10 px-4 py-2` |
| `sm` | `h-9 rounded-md px-3` |
| `lg` | `h-11 rounded-md px-8` |
| `icon` | `h-10 w-10` |

### CategoryCard
- Base: white bg, `border border-[rgba(224,224,224,1)]`, `shadow-xs`, `rounded-2xl`
- Hover: `shadow-sm-hover`, `-translate-y-0.5`, icon `group-hover:scale-110`
- Accessibility: `role="button"`, Enter/Space activation, focus-primary ring

---

### TypeBadge
- **File**: `src/components/ui/TypeBadge.tsx`
- **Colors from**: `DOCUMENT_TYPE_COLORS` in `src/lib/colors.ts`
- **Styling**: `rounded-full px-3 py-1 font-inter text-[11px] font-medium`

| Type | Background | Text |
|---|---|---|
| Methodologies | `#E8F4FD` | `#1E6BB8` |
| Policy | `#E8F5E9` | `#2E7D32` |
| Research | `#F3E8FD` | `#6F4ECB` |
| Projects | `#FFF3E0` | `#E65100` |
| Co-benefits | `#FFF8E1` | `#B45309` |
| PDD | `#E0F2F1` | `#00695C` |

### DataSourcesTable
- **File**: `src/components/data-sources/DataSourcesTable.tsx`
- **Layout**: Title + subtitle → search bar → collapsible filter pills → results counter → table
- **Columns**: Document (24%), Source (16%), Type (12%), Updated (10%), Description (38%)
- **Typography**: title Poppins Semibold 20px `#1F1F1F`; subtitle Inter 15px `#5B5B7A`; headers Inter Semibold 12px `#6B7280` uppercase; cells Inter 13-14px
- **Filter pills**: active `bg-[#403D85] text-white`; inactive `bg-[#F3F4F6] text-[#5B5B7A]`; hover `bg-[#E5E7EB]`; `px-3.5 py-1.5` Inter Medium 12px; shows count
- **Search**: `h-11 w-full rounded-full border-[#E5E7EB]` placeholder `#99A1AF`
- **Table container**: `rounded-xl border border-[#E5E7EB] shadow-sm`; header `bg-[#F8F9FA]`; rows alternate white/`bg-[#FAFAFA]/50`; hover `bg-[#F3E8FF]/30`; dividers `divide-y divide-[#F3F4F6]`; cell padding `py-4 px-5`

### ProjectKPIs
- **File**: `src/components/projects/ProjectKPIs.tsx`
- **Layout**: `grid-cols-2 lg:grid-cols-4 gap-3`; cards `bg-white rounded-2xl border border-[#E5E5E5] p-4 min-h-[120px]`
- **Metrics**: Total projects, Credits issued (retirement progress bar), Registry donut, Status donut
- **Donut**: 64×64px, innerRadius 18, outerRadius 30; Registry colors `['#403D85','#2098D8','#418045','#D97706','#A13D15','#6F4ECB']`; Status colors `['#418045','#6F4ECB','#0A558C','#D97706','#9CA3AF','#A13D15']`
- **Typography**: label Inter 11px semibold `#6B7280` uppercase; value Poppins 28px semibold `#1F1F1F`

---

### Chat Interface Layout

All messages are plain text (no bubbles), centered in a **680px** max-width container.

- **User questions**: Inter Semibold 20px/30px, `#1a1a1a`
- **Bot responses**: Inter Regular 14px/1.6, `#1a1a1a`; lists `list-disc pl-6 space-y-1.5 mb-3`; paragraphs `mb-2 leading-[1.6]`
- **Auto-scroll**: new user questions scroll to "eye level" — `eyeLevelOffset = sectionRect.height * 0.15`

### ChatMessage
- **File**: `src/components/chat/ChatMessage.tsx`

| State | Styling |
|---|---|
| User | `font-inter font-semibold text-lg md:text-xl` |
| Bot pending | Animated dots, `#6B7280` |
| Bot error | `bg-red-50 border border-red-200 rounded-md`; retry `bg-red-600 hover:bg-red-700` |
| Bot cancelled | `bg-[#F3F0FF] border border-[#DAD6FF]`; from `NOTICE_COLORS.cancelled` |
| Bot success | Markdown via ChatMarkdownContent |

**Retry button** (error/cancelled): Poppins font, `text-[11px] px-2.5 py-1 rounded`; disabled with spinner while retrying (`Loader2 animate-spin`)

**Copy button**: right-aligned below response (`mt-3 flex justify-end`); default gray Copy icon → copied green Check icon (~1.5s); `h-3 w-3` icon

**Markdown lists**: `ul.list-disc.pl-6.space-y-2`; `ol.list-decimal.pl-6.space-y-2`; `li.leading-[1.6]`

### SuggestedPrompts
- **File**: `src/components/chat/SuggestedPrompts.tsx`
- **Layout**: Separated from message body/citations by a fine divider (`border-t border-surface-subtle mt-6 pt-5`) to resolve section density. Prompts flow horizontally (`flex flex-wrap gap-2`).
- **Header**: Custom brand Chat icon (`chat.svg?react`) within a soft brand-colored background badge (`w-5 h-5 rounded-md bg-brand-500/[0.08] text-brand-700`) and standard Inter uppercase text "Follow-up questions" (`font-inter text-[11px] font-semibold text-brand-700 uppercase tracking-wider`).
- **Cards (Chips)**: Wrap chips with a solid white background and clear borders:
  - Default: `border-border-ui bg-white hover:bg-gray-50 hover:shadow-sm hover:border-gray-300`
  - Disabled / Typing: `border-border-ui bg-gray-50/50 cursor-not-allowed opacity-50`
- **Hover/Tap Microinteractions**:
  - Hover matches the app's neutral card pattern (`RecommendationCard`, `CategoryCard`): subtle background shift to `gray-50`, neutral `shadow-sm`, and border darkens slightly to `gray-300`.
  - Active press triggers a physical scaling-down (`scale: 0.98`) for tactile feedback.
  - Text and arrow remain their default muted colors on hover; no brand-purple tinting, keeping the interaction subtle and consistent with surrounding UI.

### Agent Reasoning Panel
- Position: below user question, before bot response (`mb-4`)
- Trigger: plain accordion — summary Inter 11px `#6B7280`, purple lightning icon; chevron rotates 180° on open
- Content cards: white bg, `border border-[#E5E7EB]`; `rounded-md border border-gray-200 bg-white p-2.5`
- Step icon bg: `bg-[#F3F0FF]`; icon color `#6F4ECB`; bullet `w-1 h-1 rounded-full bg-[#6F4ECB]`
- Typography: 10px semibold labels, 11px regular content
- Collapsed by default; expand animation in `src/components/chat/chat-interface.css` via `details[open] .reasoning-content`; respects `prefers-reduced-motion`

### TypingIndicator
3 dots: `w-2 h-2 bg-[#6F4ECB] rounded-full animate-bounce`; delays 0ms / 150ms / 300ms; spacing `mt-4 mb-4`

### RecommendationCard
- **File**: `src/components/chat/RecommendationCard.tsx`
- **Uses React Router `Link`** to preserve chat state on navigation
- Card: `#FCFCFC bg`, black 1px border, `rounded-[6px]`; title Inter 12px semibold `#1F1F1F` line-clamp-2; meta Inter 12px `#555555`
- Tag badges: 8.5px semibold, `rounded-[15px]`; Project `#C8E6A5`/`#496731`; Methodology `#B4DBFF`/`#0A558C`; Pricing `#FFD8B4`/`#93370D`

### QuizWidget
- **File**: `src/components/chat/QuizWidget.tsx` — interactive quiz rendered inside chat

---

### Pricing Components

#### PricingChart
- **File**: `src/components/pricing/PricingChart.tsx`; Recharts (`ResponsiveContainer`, `LineChart`, `Line`, `XAxis`, `YAxis`, `Tooltip`); full-width responsive

#### MethodologyExplanation
- **File**: `src/components/pricing/MethodologyExplanation.tsx`; category-aware (Agriculture, REDD+, Renewable Energy, Household Devices); sticky positioning

#### PricingDrivers
- **File**: `src/components/pricing/PricingDrivers.tsx`; `grid-cols-2 md:grid-cols-4`
- Card: `rounded-[12px] md:rounded-[16px] border border-gray-200 bg-white px-3 md:px-5 pt-3 md:pt-5 pb-4 md:pb-6 min-h-[140px] md:min-h-[200px] shadow-sm hover:shadow-md`
- Icon container: `rounded-[10px] md:rounded-[14px] p-1.5 md:p-2 w-9 h-9 md:w-12 md:h-12`
- Category theming from `CATEGORY_THEMES` in `colors.ts`

#### SBTImpact
- **File**: `src/components/pricing/SBTImpact.tsx`; category-aware
- Badge colors from `TREND_COLORS` in `colors.ts`: rising `bg-[#E3F6D6] text-[#2F4F2F]`; declining `bg-[#FDE6C9] text-[#7C2D00]`

---

### Explore Projects

**Layout hierarchy**: KPI Bar → Search + Filters → Split View (list 35% left / detail 65% right)

#### ProjectFiltersV2
- **File**: `src/components/projects/ProjectFiltersV2.tsx`
- Primary filters (always visible): Registry, Status, Type — dropdown button `h-8 px-3 rounded-lg`; active `bg-[#403D85] text-white`; inactive `bg-white text-[#5B5B7A] border-[#E5E7EB]`
- "More filters" button opens secondary pills (Scope, Project Type, Region, Country with search); shows active badge count; active state `bg-[#F5F0FF] text-[#403D85] border-[#E9D5FF]`
- Result count: `font-inter text-[11px] text-[#6B7280]` right-aligned

#### ProjectListItem
- **File**: `src/components/projects/ProjectListItem.tsx`
- Active: `bg-[#F5F0FF] border-l-2 border-l-[#6F4ECB]`; Inactive: `bg-white border-l-transparent hover:bg-[#FAFAFA]`
- Layout: 3 rows — ID/Registry, Name, Type+Country+Credits
- Compare checkbox: `opacity-0 group-hover:opacity-100`, always visible when selected
- Typography: ID Inter 10px medium `#6B7280`; Name Poppins 13px medium line-clamp-2; Meta Inter 11px; Credits Poppins 12px semibold

#### ProjectDetailPanel
- **File**: `src/components/projects/ProjectDetailPanel.tsx`
- Full-height flex column: sticky header + scrollable content
- Sections: Credits 2×2 grid, Overview, Location, Stakeholders, Methodology, Timeline, Regulatory, Links, Description, Notes
- Credit cards: `bg-[#F8F9FA] rounded-xl p-3.5`; section headings Inter 10px semibold `#6B7280` uppercase tracking-0.6px

#### Split View Layout
- Container: `flex border border-[#E5E7EB] rounded-2xl overflow-hidden bg-white`
- Height: `calc(100vh - 260px)` min 520px
- Left panel: `w-[380px] flex-shrink-0 border-r border-[#E5E7EB] overflow-y-auto`; infinite scroll; `divide-y divide-[#F3F4F6]`
- Right panel: `flex-1 min-w-0`; hidden below `lg`
- Mobile: `fixed inset-0 z-50 bg-black/40` overlay; panel `max-w-[440px]` from right; opens on explicit tap only

#### Skeleton Components
- `KPISkeleton`: 4-column grid matching KPI bar
- `SplitViewSkeleton`: 8 list skeletons + right panel skeleton
- `ListItemSkeleton`: matches compact list item layout

---

### Case Study Components

#### CaseStudyHeader
- Back button with `useNavigate`; quality badge `bg-[#C8E6A5] rounded-full`; org text underlined linking to external registry

#### CaseStudyStrengths
- Lucide checkmarks instead of bullets; SDG boxes 55×41px — SDG 8: `#A41C43`, SDG 13: `#418045`, SDG 14: `#00689D`
- Font: Inter 10.5px / 13px line-height; `whitespace-normal` to prevent cutoff

#### ProjectStatistics
- Semi-circle chart from asset image
- Stat pills: 58×22px, `px-[10px] py-[6px] rounded-[17px]` — green `#DFFDD6`, purple `#E9D5FF`, blue `#B4DBFF`
- Font: Inter 10px values / 7.7px labels

#### ProjectDetails
- Responsive: column mobile → row desktop; map image `rounded-[14px]`; section headings uppercase `#616161`

---

### Modals & Overlays

#### TermsOfServicePopup
- **File**: `src/components/ui/TermsOfServicePopup.tsx`
- **Features**: focus trap, Escape to close, cookie persistence 365 days, shows only on `/`
- Overlay: `fixed inset-0 bg-black/60 backdrop-blur-md z-[100]`
- Dialog: `bg-white rounded-[28px] max-w-[480px] border border-[#E5E7EB] shadow-[0_32px_64px_-12px_rgba(0,0,0,0.14)]`
- Notice cards: Research `bg-[#FFFBEB] border-[#FEF3C7]` amber; Privacy `bg-[#F5F3FF] border-[#EDE9FE]` purple (from `NOTICE_COLORS`)
- Primary button: `bg-[#403D85] hover:bg-[#6F4ECB] text-white rounded-xl px-6 py-2.5`

#### ScrollToTop
- Fixed `bottom-6 right-6`; white circle, `shadow-scroll-btn`; brand purple `#4A2AA3` arrow; appears after 300px scroll; `aria-label` for accessibility

---

### IconWrapper
- **File**: `src/components/icons/IconWrapper.tsx`
- **Icons**: `src/assets/icons/` — 40 stroke-based (outline) SVGs
- **Props**: `Icon` (required), `size` (default 24), `color`, `state ('default'|'active'|'selected')`, `title`, `aria-hidden`, `onClick`
- **State colors** (from `ICON_STATE`): default `#6B7280`, active/selected `#6F4ECB`
- **Accessibility**: use `title` for meaningful icons OR `aria-hidden={true}` for decorative — never both

**Available icons**: alert, arrow-up, back, book, calendar, chat, check-circle, chevron-down, chevron-first, chevron-left, chevron-up, complex, cookie, cora, database, date, explore, external-link, file, globe, info, lightbulb, list, location, mail, map, plus-circle, pricing, refresh, scale, search, shield, sidebar-close, sidebar-open, tag, target, trash, tree, trending-down, users, x

```tsx
import { IconWrapper } from '@/components/icons/IconWrapper';
import ChatIcon from '@/assets/icons/chat.svg?react';

<IconWrapper Icon={ChatIcon} size={24} title="Chat" />           // meaningful
<IconWrapper Icon={ChatIcon} size={24} aria-hidden={true} />    // decorative
<IconWrapper Icon={ChatIcon} size={24} state="active" aria-hidden={true} />
```

---

## Patterns

### Accessibility
- Minimum tap target: **44×44px** for all interactive controls (`min-w-[44px] min-h-[44px]`)
- Focus rings: standard purple ring on all focusable elements (see Focus Rings token)
- After retry: scroll updated message into view — `scrollIntoView({ behavior: 'smooth', block: 'center' })`; bubble accepts `tabIndex={-1}`
- Motion: all transitions respect `@media (prefers-reduced-motion: reduce)`

### Responsive Design
- Container centered with `2rem` padding; custom `2xl` breakpoint at `1400px`
- Split view right panel hidden below `lg`; mobile gets sheet-style drawer
- Sidebar collapses to icon-only on mobile (hamburger toggle)

### Mobile — Sticky Composer & Safe Areas
- Chat composer fixed to bottom: `paddingBottom: 'calc(1rem + env(safe-area-inset-bottom, 0px))'`
- Scroll area: `paddingBottom: 'calc(6rem + env(safe-area-inset-bottom, 0px))'`

### Content Rendering (Markdown)
- **Links**: sanitized URLs; external open with `target="_blank" rel="noopener noreferrer"`; style `text-purple-700 underline break-words inline-flex items-center gap-1` + external-link icon
- **Images**: `loading="lazy" decoding="async" max-w-full h-auto max-h-80 object-contain rounded-md border border-gray-100`

---

**Last Updated**: March 2026
