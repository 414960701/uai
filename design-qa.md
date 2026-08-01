# Design QA

## Source visual truth

- Reference screenshots: `/Users/ljd/.codex/attachments/b06a1777-2f04-4845-ad1a-0ec9bce01af3/image-1.png` through `image-4.png`.
- The comparison target is the reference Agent workspace pattern: a continuous white transcript, compact public activity, a quiet composer, and a secondary task rail when work is complex.

## Implementation evidence

- Browser-rendered screenshot: `/Users/ljd/Documents/UAI/design-qa-desktop.png`.
- Full comparison input: `/Users/ljd/Documents/UAI/design-qa-comparison.jpg`.
- Focused composer comparison: `/Users/ljd/Documents/UAI/design-qa-focus.jpg`.
- URL: `http://localhost:3000/?view=chat&resource=run_7965b41b1eea40d5`.
- Viewport: 1280 × 720 CSS px; browser-reported device pixel ratio 2; browser screenshot output normalized to 1280 × 720 pixels.
- Reference image used for full comparison: source `888 × 774` pixels, normalized to `826 × 720` pixels before the side-by-side comparison.
- Focused comparison uses the source composer crop at `964 × 250` and the implementation composer crop at `1280 × 250`.

## State and interactions tested

- Completed simple Agent conversation with terminal public thought collapsed.
- Confirmed the page itself stays at `scrollHeight === clientHeight === 720`; `.chat-thread` owns overflow (`scrollHeight 1677`, `clientHeight 365`, `overflow-y: auto`).
- Confirmed the send button remains inside the composer bounds (`x 1118–1202`, `y 640–676`) and is not covered.
- Confirmed ordinary Enter inserts a newline (`英文 input\n`) and does not submit; the button becomes enabled only when text exists.
- Browser console logs were empty after reload.
- No narrow screenshot was captured because the in-app Browser surface is fixed at its current viewport; narrow CSS rules were checked in source and the desktop overflow boundary remained contained.

## Findings

No actionable P0, P1, or P2 visual differences remain for the reviewed desktop state.

- The implementation keeps the transcript white and continuous, with the answer content carrying the visual weight rather than nested admin cards.
- The earlier captured conversation uses indigo `#5667d8` for action/selection; `#4c82c9` is reserved for informational/active accents and `#2f966c` remains the success color.
- The composer, mode controls, session selection, and primary action use the same blue family. Green is not used as the primary action color.
- The source screenshots show a different product shell and a green running-state treatment; those differences are intentional because UAI Forge keeps its own navigation/session rail and the requested product rule reserves green for success/healthy state.

## Focused region comparison

The composer crop was compared side-by-side in `design-qa-focus.jpg`. The implementation preserves the reference hierarchy—white input surface, compact controls, and a distinct submit action—while using the requested indigo instead of the reference's green running indicator.

## Comparison history

1. The earlier conversation captured in the browser used `#5667d8` as its action indigo, while later palette patches drifted to gray-blue variants.
2. Restored the captured CHG-0023/0025 palette values (`#5667d8`, `#4c82c9`, `#f7f8fc`, cloud-white surfaces) while keeping the CHG-0027 conversation structure.
3. Normalized legacy activity rules so active public stages use informational blue and only completed/healthy states use success green; this prevents a green base rule from leaking through Plan and reasoning surfaces.
4. Rebuilt Docker, reloaded the browser, repeated the full and focused comparisons, and rechecked composer/scroll/error behavior.

## Fidelity surfaces

- Typography: compact UI labels remain subordinate; transcript text uses the readable 14 px body scale and generous line height.
- Spacing/layout: the transcript is the main reading surface, the composer is anchored below it, and the outer page does not scroll.
- Colors/tokens: indigo is used consistently for action/selection; blue is reserved for active information; green remains semantic success; surfaces stay near-white.
- Image/asset fidelity: the target and implementation are UI surfaces without product imagery or logos requiring replacement.
- Copy/content: Agent, Plan, Todo, Trace, MCP, and Chinese control labels remain consistent with the product contract.

## Implementation checklist

- [x] Restore the earlier indigo action palette.
- [x] Rebuild the Docker frontend and verify computed colors in the browser.
- [x] Run lint, typecheck, frontend tests, backend tests, and diff checks.
- [x] Verify desktop scroll boundary, Enter behavior, send-button visibility, and browser console.
- [ ] Add a captured 390 px browser viewport regression when the browser surface exposes viewport emulation.

## Follow-up Polish

- P3: capture the same states at a narrow viewport and add the image evidence to the next acceptance update.

final result: passed
