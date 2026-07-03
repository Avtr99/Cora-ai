# Design Tokens Reference for Figma

**Last Updated**: March 2026  
**Purpose**: Comprehensive design system reference for designers and developers

---

## Table of Contents
1. [Color Palette](#color-palette)
2. [Typography](#typography)
3. [Spacing & Sizing](#spacing--sizing)
4. [Shadows (Elevation)](#shadows-elevation)
5. [Border Radius](#border-radius)
6. [Icons & Assets](#icons--assets)
7. [Component Library](#component-library)

---

## Color Palette

### Brand Colors

| Token | Hex Value | Usage |
|-------|-----------|-------|
| `brand-primary-900` | `#403D85` | Primary buttons, CTAs |
| `brand-primary-700` | `#4A2AA3` | Scroll-to-top icon, strong accent |
| `brand-primary-500` | `#6F4ECB` | Hover states, active icons, secondary actions |
| `brand-primary-200` | `#E9D5FF` | Brand borders, subtle dividers |
| `brand-primary-100` | `#F3E8FF` | Light brand backgrounds, bot bubbles |


### Neutral Scale & Surfaces

| Token | Hex Value | Usage |
|-------|-----------|-------|
| `neutral-0` | `#FFFFFF` | Base background |
| `neutral-25` | `#FAFAFA` | Cards, secondary surfaces |
| `neutral-150` | `#E5E7EB` | Subtle borders, sidebar dividers |
| `neutral-200` | `#D6D6D6` | Strong borders, separators |
| `neutral-300` | `#B8BEC8` | Disabled buttons, inactive send button |
| `neutral-400` | `#6B7280` | Default icon color, input borders |
| `neutral-600` | `#6B7280` | Muted text, agent reasoning content |
| `neutral-800` | `#525252` | Secondary body text |
| `neutral-900` | `#171717` | Headings, high emphasis text |

### Text Tokens (Aliases)

| Token | References | Usage |
|-------|------------|-------|
| `text-primary` | `#171717` | Headings, key labels |
| `text-body` | `#525252` | Card and paragraph content |
| `text-muted` | `#6B7280` | Secondary labels, metadata |
| `text-disabled` | `#B8BEC8` | Disabled controls |

### Interactive States

| State | Token | Hex Value | Usage |
|-------|-------|-----------|-------|
| `interactive-default` | `neutral-400` | `#6B7280` | Default icon and link color |
| `interactive-hover` | `brand-primary-500` | `#6F4ECB` | Hover state for icons, links |
| `interactive-active` | `brand-primary-500` | `#6F4ECB` | Active navigation items |
| `interactive-disabled` | `neutral-300` | `#B8BEC8` | Disabled buttons, inactive send button |

### Chat Message Colors

| Context | Background | Text | Usage |
|---------|------------|------|-------|
| **User Message** | `transparent` | `#1A1A1A` | User message text (no bubble) |
| **Bot Message** | `transparent` | `#1A1A1A` | Bot response text (no bubble) |

### Status & Accent Tokens

| Category | Token | Hex Value | Usage |
|----------|-------|-----------|-------|
| Success | `accent-success-100` | `#DFFDD6` | Success pill backgrounds |
| Success | `accent-success-500` | `#418045` | SDG 13 indicator |
| Success | `accent-success-600` | `#496731` | Success tag text |
| Project | `accent-project-100` | `#C8E6A5` | Project quality badge backgrounds |
| Warning | `accent-warning-100` | `#FFF9E6` | Warning/alert cards |
| Warning | `accent-warning-200` | `#FFE7A3` | Warning card borders |
| Warning | `accent-warning-700` | `#F59E0B` | Alert icons |
| Trend Rising | `accent-trend-rising-100` | `#E3F6D6` | Rising badge background in `SBTImpact.tsx` |
| Trend Rising | `accent-trend-rising-500` | `#2F4F2F` | Rising badge text in `SBTImpact.tsx` |
| Trend Rising | `accent-trend-rising-icon` | `#E8F5E0` | Rising icon container in `SBTImpact.tsx` |
| Trend Declining | `accent-trend-declining-100` | `#FDE6C9` | Declining badge background in `SBTImpact.tsx` |
| Trend Declining | `accent-trend-declining-500` | `#7C2D00` | Declining badge text in `SBTImpact.tsx` |
| Trend Declining | `accent-trend-declining-icon` | `#FFE8CC` | Declining icon container in `SBTImpact.tsx` |
| Note | `accent-note-100` | `#FFFBF0` | Note background in `SBTImpact.tsx` |
| Note | `accent-note-200` | `#F5E6C3` | Note border in `SBTImpact.tsx` |
| Note | `accent-note-700` | `#92400E` | Note text in `SBTImpact.tsx` |
| Info | `accent-info-200` | `#B4DBFF` | Methodology tag backgrounds |
| Info | `accent-info-600` | `#00689D` | SDG 14 indicator |
| Info | `accent-info-700` | `#0A558C` | Methodology tag text |
| Info | `accent-info-icon` | `#D97706` | Info icon in `SBTImpact.tsx` note |
| Trend Icon | `accent-trend-icon` | `#A65B00` | Trending-down icon in `SBTImpact.tsx` |
| Purple | `accent-purple-100` | `#DBD9FF` | Purple pill backgrounds |

### Pricing Data Series Colors

| Token | Hex Value | Usage |
|-------|-----------|-------|
| `pricing-household-stroke` | `#4F46E5` | Household Devices line in `PricingChart.tsx` |
| `pricing-agriculture-stroke` | `#2098D8` | Agriculture line in `PricingChart.tsx` |
| `pricing-renewable-stroke` | `#F59E0B` | Renewable Energy line in `PricingChart.tsx` |
| `pricing-redd-stroke` | `#EF4444` | REDD+ line in `PricingChart.tsx` |

### Pricing Category Surfaces

| Category | Token | Hex Value | Usage |
|----------|-------|-----------|-------|
| Household Devices | `pricing-household-surface` | `#F3E8FF` | Card/icon background in `PricingDrivers.tsx` |
| Household Devices | `pricing-household-accent` | `#6F4ECB` | Icon color in `PricingDrivers.tsx` |
| Household Devices | `pricing-household-text` | `#403D85` | Heading text in `PricingDrivers.tsx` |
| Renewable Energy | `pricing-renewable-surface` | `#F9DBB6` | Card/icon background in `PricingDrivers.tsx` |
| Renewable Energy | `pricing-renewable-accent` | `#BF7E2B` | Icon color in `PricingDrivers.tsx` |
| Renewable Energy | `pricing-renewable-text` | `#A65B00` | Heading text in `PricingDrivers.tsx` |
| REDD+ | `pricing-redd-surface` | `#FAD1C1` | Card/icon background in `PricingDrivers.tsx` |
| REDD+ | `pricing-redd-accent` | `#A13D15` | Icon/text color in `PricingDrivers.tsx` |
| Agriculture | `pricing-agriculture-surface` | `#DBEAFE` | Card/icon background in `PricingDrivers.tsx` |
| Agriculture | `pricing-agriculture-accent` | `#294C7B` | Icon/text color in `PricingDrivers.tsx` |

> **Note**: When a component needs both semantic and base tokens, reference the semantic alias first (e.g., `text-muted` → `neutral-600`).

### Document Type Colors (Knowledge Base)

| Type | Background | Text | Usage |
|------|------------|------|-------|
| Methodologies | `#E8F4FD` | `#1E6BB8` | Methodology badges in `TypeBadge.tsx` |
| Policy | `#E8F5E9` | `#2E7D32` | Policy document badges |
| Research | `#F3E8FD` | `#6F4ECB` | Research document badges |
| Projects | `#FFF3E0` | `#E65100` | Project document badges |
| Co-benefits | `#FFF8E1` | `#B45309` | Co-benefits badges |
| PDD | `#E0F2F1` | `#00695C` | Project Developer Documentation badges |

### Notice/Alert Card Colors

| Context | Background | Border | Text | Usage |
|---------|------------|--------|------|-------|
| Research Preview | `#FFFBEB` | `#FEF3C7` | `#92400E` | TermsOfServicePopup research notice |
| Research Preview (hover) | - | `#FDE68A` | - | Hover state |
| Research Icon Container | `#FEF3C7` | `#FDE68A` | - | Alert icon background |
| Data Privacy | `#F5F3FF` | `#EDE9FE` | `#5B21B6` | TermsOfServicePopup privacy notice |
| Data Privacy (hover) | - | `#DDD6FE` | - | Hover state |
| Privacy Icon Container | `#EDE9FE` | `#DDD6FE` | - | Shield icon background |
| Cancelled Message | `#F3F0FF` | `#DAD6FF` | `#2F2A72` | ChatMessage cancelled state |

### Border Tokens

| Token | References | Usage |
|-------|------------|-------|
| `border-default` | `neutral-150` | Subtle borders, agent reasoning cards |
| `border-muted` | `neutral-400` | Input focus rings, SearchBar border |
| `border-brand` | `brand-primary-200` | Brand-specific dividers |

### Sidebar Colors

| Token | HSL Value | Computed | Usage |
|-------|-----------|----------|-------|
| **Sidebar Background** | `hsl(0, 0%, 98%)` | Off-white | Sidebar surface |
| **Sidebar Foreground** | `hsl(215, 14%, 34%)` | `#4B5563` (`neutral-800`) | Sidebar text |
| **Sidebar Primary** | `hsl(0, 0%, 10%)` | `#1A1A1A` (`neutral-900`) | Primary sidebar elements |
| **Sidebar Border** | `hsl(220, 13%, 91%)` | Light gray | Sidebar dividers |

### Gradient (SearchBar)

| Gradient | CSS Value |
|----------|-----------|
| **Glow Gradient** | `linear-gradient(135deg, rgba(147, 51, 234, 0.15) 0%, rgba(236, 72, 153, 0.15) 100%)` |

---

## Typography

### Font Families

| Family | Weights Available | Usage |
|--------|-------------------|-------|
| **Poppins** | 300, 400, 500, 600, 700 | Headings, buttons, labels, navigation |
| **Inter** | 300, 400, 500, 600 | Body text, descriptions, form fields |

**Import:**
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Poppins:wght@300;400;500;600;700&display=swap" rel="stylesheet">
```

### Heading Hierarchy (Poppins)

| Level | Font | Size | Line Height | Letter Spacing | Weight | Tailwind Class |
|-------|------|------|-------------|----------------|--------|----------------|
| **H1** | Poppins | 56px | 67px (1.196) | -1.12px | Bold (700) | `font-poppins font-bold text-[56px] leading-[67px] tracking-[-1.12px]` |
| **H2** | Poppins | 40px | 52px (1.3) | -0.4px | SemiBold (600) | `font-poppins font-semibold text-[40px] leading-[52px] tracking-[-0.4px]` |
| **H3** | Poppins | 32px | 45px (1.406) | -0.16px | SemiBold (600) | `font-poppins font-semibold text-[32px] leading-[45px] tracking-[-0.16px]` |
| **H4** | Poppins | 24px | 34px (1.417) | 0 | Medium (500) | `font-poppins font-medium text-2xl leading-[34px]` |
| **H5** | Poppins | 20px | 30px (1.5) | 0 | Medium (500) | `font-poppins font-medium text-xl leading-[30px]` |
| **H6** | Poppins | 16px | 24px (1.5) | 0.8px | SemiBold (600) | `font-poppins font-semibold text-base leading-6 tracking-[0.8px]` |

### Body Text (Inter)

| Style | Size | Line Height | Weight | Tailwind Class | Usage |
|-------|------|-------------|--------|----------------|-------|
| **Body Bold** | 16px | 22px (1.375) | SemiBold (600) | `font-inter font-semibold text-base leading-[22px]` | Emphasized text, labels |
| **Body Medium** | 16px | 26px (1.625) | Medium (500) | `font-inter font-medium text-base leading-[26px]` | Medium emphasis body |
| **Body Regular** | 16px | 26px (1.625) | Regular (400) | `font-inter font-normal text-base leading-[26px]` | Default body text |
| **Body Small Bold** | 12px | 16px (1.333) | SemiBold (600) | `font-inter font-semibold text-xs leading-4` | Small labels, badges |
| **Body Small** | 12px | 16px (1.333) | Regular (400) | `font-inter font-normal text-xs leading-4` | Captions, metadata |

### Special Text Styles

| Style | Font | Size | Line Height | Letter Spacing | Weight | Transform | Tailwind Class |
|-------|------|------|-------------|----------------|--------|-----------|----------------|
| **Button Text** | Inter | 10px | 9px | 0.1px | SemiBold (600) | - | `font-inter font-semibold text-[10px] leading-[9px] tracking-[0.1px]` |
| **Subtitle/Label** | Poppins | 10px | normal | 0 | SemiBold (600) | UPPERCASE | `font-poppins font-semibold text-[10px] leading-normal uppercase` |

### Chat Interface Typography

| Element | Font | Size | Line Height | Weight | Color | Class |
|---------|------|------|-------------|--------|-------|-------|
| **User Question** | Inter | 20px | 30px (1.5) | SemiBold (600) | #1a1a1a | `font-inter font-semibold text-xl leading-[30px]` |
| **Bot Response** | Inter | 14px | 1.6 | Regular (400) | #1a1a1a | `font-inter text-sm leading-[1.6]` |
| **Card Title** | Inter | 12px | - | SemiBold (600) | `neutral-900` (`#1A1A1A`) | `font-inter font-semibold text-xs` |
| **Card Metadata** | Inter | 12px | - | Regular (400) | `neutral-800` (`#4B5563`) | `font-inter text-xs` |
| **Tag Badge** | Inter | 11px | 15px | SemiBold (600) | varies | `font-inter font-semibold text-[11px] leading-[15px]` |
| **Agent Reasoning Label** | Inter | 11px | - | SemiBold (600) | - | `font-inter font-semibold text-[11px]` |
| **Agent Reasoning Content** | Inter | 11px | - | Regular (400) | #6B7280 | `font-inter text-[11px]` |

---

## Spacing & Sizing

### Base Unit
- **Base**: 4px (0.25rem)
- **Container Padding**: 2rem (32px)

### Common Spacing Values

| Token | Value | Usage |
|-------|-------|-------|
| `gap-1` | 4px | Tight spacing |
| `gap-1.5` | 6px | Statistics, small elements |
| `gap-2` | 8px | Default spacing |
| `gap-2.5` | 10px | Flex item spacing |
| `gap-3` | 12px | Recommendation cards, moderate spacing |
| `gap-6` | 24px | Section spacing |
| `px-4 py-2` | 16px × 8px | Standard button padding |
| `px-6 py-2.5` | 24px × 10px | Modal button padding |

### Container Widths

| Context | Max Width | Usage |
|---------|-----------|-------|
| **Chat Messages** | 680px | User questions, bot responses |
| **SearchBar (Chat)** | 800px | Chat composer variant |
| **SearchBar (Homepage)** | 708px | Large homepage variant |
| **Modal** | 512px (max-w-lg) | Welcome popup, dialogs |
| **Container 2xl** | 1400px | Main content container |

### Component Dimensions

| Component | Dimensions | Details |
|-----------|------------|---------|
| **Cora Logo** | 40px | Homepage hero |
| **Cora Logo (Modal)** | 42px | Welcome popup |
| **Send Icon** | 20px | Chat composer |
| **Navigation Icons** | 24px | Sidebar navigation |
| **Case Study Icon** | 28px | Case study components |
| **Pricing Icon** | 29px | Pricing components |
| **SDG Boxes** | 55px × 41px | SDG indicators |
| **Statistics Pills** | 58px × 22px | Project statistics |
| **Icon Container (Modal)** | 36px × 36px | Alert/info icons in cards |
| **Prompt Cards (Desktop)** | 226px × 70px | Homepage starter prompts |
| **SearchBar (Homepage)** | 708px × 100px | Large variant |
| **Tap Target (Mobile)** | 44px × 44px | Minimum touch target |

---

## Shadows (Elevation)

### Shadow Tokens

All shadows are defined as CSS custom properties in `src/index.css` and exposed as named Tailwind utilities in `tailwind.config.ts`.

| Tailwind Class | CSS Variable | Value | Usage |
|----------------|-------------|-------|-------|
| `shadow-xs` | `--shadow-xs` | `0 1px 2px rgba(0,0,0,0.05)` | Base cards, project cards, pills |
| `shadow-card` | `--shadow-card` | `0 2px 8px rgba(0,0,0,0.04)` | Prompt cards (Index), subtle elevation |
| `shadow-card-md` | `--shadow-card-md` | `0 2px 8px rgba(0,0,0,0.06)` | SearchBar large variant |
| `shadow-card-sm` | `--shadow-card-sm` | `0 2px 6px rgba(0,0,0,0.04)` | SearchBar composer variant |
| `shadow-bottom-bar` | `--shadow-bottom-bar` | `0 -4px 16px rgba(0,0,0,0.08)` | Cookie consent bottom bar |
| `shadow-modal` | `--shadow-modal` | `0 32px 64px -12px rgba(0,0,0,0.14)` | Modal dialogs, popups |
| `shadow-scroll-btn` | `--shadow-scroll-btn` | `0 2px 8px rgba(0,0,0,0.08)` | Scroll-to-top button |

### Interactive / Glow Shadows (inline only)

| Usage | Value |
|-------|-------|
| Card hover lift | `0 6px 18px rgba(17,17,26,0.08)` via `shadow-sm-hover` custom class |
| Send button glow (large) | `0 0 20px rgba(111,78,203,0.25)` |
| Send button glow (composer) | `0 0 12px rgba(111,78,203,0.2)` |
| Prompt card hover | `0 8px 16px rgba(111,78,203,0.12)` |

### Shadow Usage Patterns

| Component | Default | Hover | Active |
|-----------|---------|-------|--------|
| **Category / Project Card** | `shadow-xs` | `shadow-sm-hover + -translate-y-0.5` | - |
| **Pills** | `shadow-xs` | `shadow-sm-hover + scale-1.03` | - |
| **SearchBar (large)** | `shadow-card-md` | - | - |
| **SearchBar (composer)** | `shadow-card-sm` | - | - |
| **Prompt Cards** | `shadow-card` | glow variant | - |
| **Cookie Consent Bar** | `shadow-bottom-bar` | - | - |
| **Modals** | `shadow-modal` | - | - |
| **Scroll-to-top** | `shadow-scroll-btn` | `0 4px 12px rgba(0,0,0,0.12)` | - |

---

## Border Radius

### Radius Tokens

| Token | Value | CSS Variable | Usage |
|-------|-------|--------------|-------|
| **Base Radius** | 8px | `--radius: 0.5rem` | Base border radius |
| **lg** | 8px | `var(--radius)` | Large elements |
| **md** | 6px | `calc(var(--radius) - 2px)` | Medium elements |
| **sm** | 4px | `calc(var(--radius) - 4px)` | Small elements |

### Component-Specific Radius

| Component | Border Radius | Tailwind Class |
|-----------|---------------|----------------|
| **Recommendation Cards** | 6px | `rounded-[6px]` |
| **Statistics Pills** | 17px | `rounded-[17px]` |
| **Tag Pills** | Full | `rounded-full` |
| **Tag Badges** | 15px | `rounded-[15px]` |
| **Prompt Cards** | 15px | `rounded-xl` (12px) |
| **Map Images** | 14px | `rounded-[14px]` |
| **Modal** | 16px | `rounded-2xl` |
| **SearchBar (Homepage)** | 20px | `rounded-[20px]` |
| **SearchBar (Composer)** | 24px | `rounded-3xl` |
| **Send Button** | 12px | `rounded-xl` |
| **Modal Content Cards** | 12px | `rounded-xl` |

---

## Icons & Assets

### Icon System (IconWrapper Component)

**Location**: `src/components/icons/IconWrapper.tsx`
**Icons Directory**: `src/assets/icons/` (35 SVG icons)

The `IconWrapper` component provides a consistent API for all SVGR-generated icons:

**Props:**
- `Icon` (required): SVGR-generated icon component
- `size`: Number (default: 24px)
- `color`: Custom color (overrides state-based colors)
- `state`: `'default' | 'active' | 'selected'`
- `title`: Accessible title for screen readers
- `aria-hidden`: Hide from screen readers (decorative icons)
- `onClick`: Click handler
- `className`: Additional CSS classes

**State-based Colors:**
| State | Color | Hex |
|-------|-------|-----|
| `default` | Gray | `#6B7280` |
| `active` | Purple | `#6F4ECB` |
| `selected` | Purple | `#6F4ECB` |

**Accessibility:**
- Use `title` for meaningful icons that convey information
- Use `aria-hidden={true}` for purely decorative icons
- **Never use both together** (component throws error in development)

**Usage:**
```tsx
import { IconWrapper } from '@/components/icons/IconWrapper';
import ChatIcon from '@/assets/icons/chat.svg?react';

// Accessible icon with title
<IconWrapper Icon={ChatIcon} size={24} title="Chat" />

// Decorative icon (hidden from screen readers)
<IconWrapper Icon={ChatIcon} size={24} aria-hidden={true} />

// With state-based color
<IconWrapper Icon={ChatIcon} size={24} state="active" aria-hidden={true} />
```

### Icon Library

| Icon Name | File | Default Size | Usage |
|-----------|------|--------------|-------|
| **alert** | alert.svg | 24px | Warning indicators |
| **arrow-up** | arrow-up.svg | 20px | Send button |
| **back** | back.svg | 24px | Navigation back button |
| **book** | book.svg | 24px | Knowledge Base navigation |
| **calendar** | calender.svg | 24px | Date/time indicators, PricingDrivers |
| **chat** | chat.svg | 24px | Chat navigation |
| **check-circle** | check-circle.svg | 24px | Success indicators |
| **chevron-down** | chevron-down.svg | 16px | Dropdowns, accordions |
| **chevron-first** | chevron-first.svg | 24px | Collapsible sidebar toggle |
| **chevron-left** | chevron-left.svg | 16px | Back navigation |
| **chevron-up** | chevron-up.svg | 16px | Scroll up, collapse |
| **complex** | complex.svg | 24px | Complex topics |
| **cookie** | cookie.svg | 24px | Cookie consent |
| **cora** | cora.svg | 40px/42px | Logo, branding (fill-based) |
| **database** | database.svg | 24px | Data-related features |
| **date** | date.svg | 24px | Date indicators |
| **explore** | explore.svg | 24px | Explore Projects navigation |
| **external-link** | external-link.svg | 24px | External links |
| **globe** | globe.svg | 24px | Global/world references |
| **info** | info.svg | 16px | Information/help, SBTImpact note |
| **lightbulb** | lightbulb.svg | 24px | Tips and insights |
| **location** | location.svg | 24px | Geographic indicators, PricingDrivers |
| **mail** | mail.svg | 24px | Email/contact |
| **plus-circle** | plus-circle.svg | 24px | New chat button |
| **pricing** | pricing.svg | 29px | Pricing navigation, SBTImpact |
| **refresh** | refresh.svg | 24px | Refresh/retry actions |
| **scale** | scale.svg | 24px | Legal/compliance |
| **search** | search.svg | 20px | Search functionality |
| **shield** | shield.svg | 24px | Privacy/security |
| **tag** | tag.svg | 24px | Tags, categories |
| **target** | target.svg | 24px | Goals/targets |
| **trash** | trash.svg | 24px | Delete actions |
| **tree** | tree.svg | 24px | Nature, environmental, PricingDrivers |
| **trending-down** | trending-down.svg | 24px | Decreasing trends, SBTImpact |
| **users** | users.svg | 24px | User-related features |
| **x** | x.svg | 24px | Close/dismiss |

### Icon State Colors

| State | Color | Hex | Usage |
|-------|-------|-----|-------|
| **Default** | Gray | #99A1AF | Inactive navigation items |
| **Active/Selected** | Purple | #6F4ECB | Active navigation, hover states |
| **Disabled** | Light Gray | #B8BEC8 | Disabled send button |
| **Active Button** | White | #FFFFFF | Active send button icon |

### Logo & Favicon

| Asset | File | Size | Format | Usage |
|-------|------|------|--------|-------|
| **Cora Logo** | cora.svg | 40px | SVG (fill-based) | Homepage hero, branding |
| **Cora Logo (Large)** | cora.svg | 42px | SVG (fill-based) | Modal header |
| **Favicon** | favicon.ico | 16×16, 32×32 | ICO | Browser tab icon |

---

## Component Library

### Core UI Components

#### Buttons
- **Variants**: default, destructive, outline, secondary, ghost, link
- **Sizes**: sm (36px), default (40px), lg (44px), icon (40×40px)
- **States**: default, hover, active, disabled, loading

#### Cards
1. **Category Card**
   - Background: white
   - Border: rgba(224,224,224,1)
   - Shadow: shadow-xs
   - Hover: shadow-sm-hover, -translate-y-0.5
   
2. **Recommendation Card** (Homepage)
   - Two-column grid (desktop), stacked (mobile)
   - Icon, title, description
   - Hover: border color change, shadow
   
3. **Recommendation Card** (Chat)
   - Background: #FCFCFC
   - Border: 1px black
   - Radius: 6px
   - Title: Inter 12px semibold
   - Tag badges with category colors

#### Pills & Tags
1. **Category Pills** (Homepage)
   - Background: rgba(47,45,90,1)
   - Text: white
   - Font: Poppins
   - Radius: full
   - Hover: shadow-sm-hover, scale-1.03

2. **Tag Badges** (Cards)
   - **Project**: #C8E6A5 bg, #496731 text
   - **Methodology**: #B4DBFF bg, #0A558C text
   - **Pricing**: #FFD8B4 bg, #93370D text
   - Size: 8.5px semibold
   - Radius: 15px

#### SearchBar
1. **Large Variant** (Homepage)
   - Size: 708×100px
   - Radius: 20px
   - Border: #99A1AF
   - Glow effect with gradient background
   - Send button glow: shadow-[0_0_20px_rgba(111,78,203,0.25)]

2. **Composer Variant** (Chat)
   - Radius: 24px (rounded-3xl)
   - Border: #99A1AF
   - Background: #FEFEFE
   - Send button glow: shadow-[0_0_12px_rgba(111,78,203,0.2)]
   - Typography: Inter 12px

#### Modals
1. **Research Preview Popup**
   - Container: max-w-lg (512px), rounded-2xl, shadow-2xl
   - Backdrop: black/60 with blur
   - Content cards with colored backgrounds:
     - Research: #FFF9E6 bg, #FFE7A3 border
     - Privacy: #F3E8FF bg, #E9D5FF border
     - Terms: #FBFBFB bg, #E5E5E5 border

### Layout Components

#### Sidebar
- Width: 250px (expanded), 60px (collapsed)
- Background: gradient from-gray-50 to-white
- Animation: 200ms easeOut
- Search input with filter functionality
- Pinned/Recent sections

#### Chat Interface
- Max width: 680px (messages)
- User questions: Inter Semibold 20px, #1a1a1a
- Bot responses: Inter Regular 14px, #1a1a1a
- No bubbles, clean centered design
- Agent reasoning: collapsible accordion

### Specialized Components

#### Case Study Components
1. **CaseStudyHeader**: Title, organization, back navigation
2. **CaseStudyStrengths**: Checkmarks, SDG indicators
3. **ProjectStatistics**: Chart, highlighted pills
4. **ProjectDetails**: Map, description, external links
5. **BenefitCard**: Project benefits display

#### Pricing Components
1. **PricingChart**: Interactive line chart, Recharts
2. **PricingDrivers**: 4-card grid layout
3. **MethodologyExplanation**: Sticky sidebar info
4. **SBTImpact**: Trend comparison cards

#### Utility Components
- **ScrollToTop**: Fixed bottom-right, circular button
- **RateLimitAlert**: Warning display for query limits
- **CookieConsent**: GDPR compliance banner
- **TermsOfServicePopup**: First-time user modal

---

## Design System Guidelines

### Color Usage Rules
1. **Semantic tokens preferred**: Use `bg-card`, `text-foreground`, `border-border` instead of hex colors
2. **Contrast requirements**: Minimum 4.5:1 for body text (WCAG AA)
3. **Focus rings**: 2px purple ring `rgba(74,42,163,0.35)` with white offset

### Typography Best Practices
1. Use Poppins for headings, buttons, UI elements needing emphasis
2. Use Inter for body text, form fields, longer content
3. Maintain consistent weights across similar elements
4. Respect line height ratios for readability (minimum 1.4 for body)

### Spacing Consistency
- Use 4px base unit for all spacing
- Maintain vertical rhythm with consistent gaps
- Test responsive breakpoints: mobile, tablet, desktop

### Accessibility
- Minimum 44×44px tap targets on mobile
- Keyboard navigation support for all interactive elements
- ARIA labels for icon-only buttons
- Respect `prefers-reduced-motion` for animations
- Semantic HTML with proper heading hierarchy

---

**Notes:**
- All HSL values are defined in `src/index.css`
- Tailwind config: `tailwind.config.ts`
- Component implementations: `src/components/`
- Icon library: `src/assets/icons/`
- This document should be used as the single source of truth for all design decisions
