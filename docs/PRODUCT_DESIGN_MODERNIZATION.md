# Product design modernization — beta gate

## Decision

Visual quality is a product requirement because it affects comprehension,
trust and perceived reliability. The current interface is an operational alpha,
not the visual baseline for a public release.

The redesign starts after the M2 confidence contract is stable and must finish
before Smart Departure or a public beta. This avoids redesigning ETA components
before their information hierarchy is known, while preventing visual work from
being deferred to the end of the project.

Before implementation begins, present the user with the product principles,
references and two or three visual directions. Visual code changes require this
explicit discussion and approval checkpoint.

## Scope

- define the product's visual direction and brand personality;
- create semantic design tokens for color, typography, spacing, radius, depth
  and motion;
- replace placeholder glyphs with a coherent accessible icon set;
- redesign navigation around a map-first experience and contextual bottom
  sheets;
- create modern route, vehicle, stop, ETA and confidence components;
- cover loading, empty, stale, unavailable, offline and error states;
- add skeletons, restrained motion and haptic feedback where useful;
- preserve WCAG contrast, font scaling, touch targets and screen-reader labels;
- verify compact and large Android screens, light/dark appearance and reduced
  motion;
- keep the map provider and municipal sources behind existing adapters.

## Delivery sequence

1. Audit the current alpha and benchmark contemporary mobility products.
2. Approve two or three visual directions using high-fidelity key screens.
3. Implement tokens and reusable primitives in code.
4. Redesign map, route search, favorites and ETA/confidence flows.
5. Run visual regression, accessibility and physical-device testing.

## Definition of done

- key screens share one documented component and token system;
- hierarchy makes live state, ETA uncertainty and primary actions immediately
  understandable;
- no duplicate technical identifiers or unexplained symbols reach users;
- accessibility checks and representative-device screenshots pass;
- physical-device review approves both credibility and usability before beta.
