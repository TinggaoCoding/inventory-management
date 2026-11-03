---
name: vue-component-analyzer
description: Analyze Vue 3 component structure and suggest concrete optimizations for rendering performance and code reuse (composables, shared components, slots, provide/inject, lazy loading, shallowRef, list keys, watchers, Pinia usage). Use this whenever the user asks to review, audit, refactor, speed up or clean up Vue/.vue files or a Vue 3 app, complains that a Vue page is slow, laggy or re-renders too much, asks where duplicated logic could become a composable or shared component, or wants a component-tree/architecture review of a Vue project, even if they never say "analyze" or "optimize".
---

# Vue component analyzer

Goal: find the few changes in a Vue 3 codebase that buy the most performance or remove the most
duplication, and say exactly where and how. A short ranked list the user can act on beats an
exhaustive lint dump. Anything a linter (eslint-plugin-vue) already reports is low value unless it
causes a real bug.

## 1. Scope and context

- Target: the files/folder the user named; otherwise every `.vue` file under `src/` (skip
  `node_modules`, `dist`, generated files).
- Read `package.json` first. Note Vue version (3.5+ changes props destructuring), Pinia, Vue Router,
  VueUse, Nuxt, UI libraries, lodash/moment/chart libs. If it is Vue 2, say this skill targets Vue 3
  and limit advice to what still applies.
- List what already exists in `composables/`, `utils/`, `components/` (base/shared) and stores.
  The best reuse suggestion is often "use the thing you already have"; never propose a new
  composable that duplicates an existing one or a VueUse function that is already installed.
- If the user described a symptom ("laggy when filtering", "slow first load"), rank findings by
  how much they explain that symptom.

## 2. Map the structure

Before judging, build a quick picture (grep imports of `.vue`, `defineProps`, `defineEmits`,
`useXxxStore`, `use[A-Z]`, `provide`/`inject`):

- parent → child tree for the target area
- per component: lines, props, emits, stores and composables used, async/lazy or not
- where the same data flows down through more than two levels

Read the files you report on in full. A finding based on a grep hit without reading the
surrounding code is often wrong (the key is set two lines down, the watcher is needed, etc.).

## 3. Performance checks

Flag these only when the code actually does them; explain the cost in one line.

| Pattern | Why it hurts | Typical fix |
|---|---|---|
| `v-for` without `:key`, or `:key="index"` on a list that is filtered, sorted, or edited | wrong DOM reuse, state bleeds between rows, full re-patch | stable id key |
| `v-if` and `v-for` on the same element | in Vue 3 `v-if` runs first and cannot see the loop item; often a bug, always wasted work | filter in a `computed`, or `<template v-for>` wrapper |
| function/method call or `.filter/.map/.sort` in the template | reruns on every render of the component | `computed` |
| `watch` that only derives state, or `watch(..., { deep: true })` on a large object/array | duplicate state, deep traversal on every change | `computed`; watch a specific getter |
| big data or third-party instances (chart, map, editor, SDK client) in `ref`/`reactive` | deep proxying of objects that never need reactivity | `shallowRef`, `markRaw` |
| listeners, intervals, observers, sockets created without `onUnmounted` cleanup | memory leaks, duplicate handlers after navigation | cleanup hook, or VueUse `useEventListener`/`useIntervalFn` if installed |
| route components or rarely shown heavy components imported eagerly | larger initial bundle | `() => import()` in the router, `defineAsyncComponent` for modals/charts |
| full-library imports (`import _ from 'lodash'`, moment) | bundle size | per-function import, native `Intl`/`Array` methods |
| lists of hundreds+ rows rendered in full | DOM size, slow patches | virtual list (VueUse `useVirtualList` or existing lib) or pagination |
| destructuring a Pinia store without `storeToRefs`, or destructuring props on Vue < 3.5 | lost reactivity: a bug, not just slowness | `storeToRefs(store)`, `toRefs(props)` / `props.x` |
| new object/array/function literal passed as a prop to a list-row child | child re-renders every parent render | hoist constant, `computed`, or pass primitives |
| frequent toggling with `v-if` of an expensive subtree / expensive tab switches | remount cost | `v-show`, `<KeepAlive>` |

`v-once`, `v-memo` and manual memoization are last resorts: suggest them only for a measured or
obviously large static/hot subtree, and say why.

## 4. Reuse checks

- **Same logic in 2+ components** (fetch + loading + error, pagination, form validation, debounced
  search, local-storage sync): extract one composable. Show its signature and which files switch
  to it. Prefer an existing composable or VueUse function.
- **Near-identical components** (same template shape, different labels/colors/one extra field):
  merge into one with props and slots. Show the merged prop/slot API.
- **Repeated template blocks** in one or several components: extract a component, or a slot if
  the variation is markup.
- **Prop drilling** through more than two levels for the same value: `provide`/`inject` (typed
  `InjectionKey`) for subtree context, a Pinia store for app-wide state.
- **Mixins** or Options-API leftovers sharing logic: convert to composables.
- **Oversized components** (roughly 300+ lines, or several unrelated responsibilities): name the
  pieces to split out, not just "too big".

Don't suggest an abstraction for something used once. Two near-copies is the minimum, and the
merged version must be simpler than the copies combined.

## 5. Report

Reply in chat, in this shape:

```
## Vue analysis: <target>

<one or two sentences: what was analyzed (N components), the biggest win>

### High impact
1. **<short title>** — `src/views/ProductList.vue:42`
   Problem: <what the code does, one or two lines>
   Why: <cost or bug it causes>
   Fix:
   ```vue
   <minimal before/after or the new code>
   ```

### Medium impact
...

### Low impact
...

### Component map
<compact tree of the analyzed area, only if it helps explain reuse or prop-drilling findings>
```

Rules for the report:
- Rank by real-world impact: correctness bugs (lost reactivity, broken keys) and things that
  explain the user's symptom first, then bundle size and render cost, then tidiness.
- Every finding has a `file:line` and a concrete fix. No finding without a location.
- Group repeated instances of one issue into one finding listing all locations.
- Keep code snippets minimal: the changed lines, not whole files.
- If an area is fine, say so in one line instead of inventing issues.
- End by offering to apply the high-impact fixes. Do not edit files unless the user asks.
