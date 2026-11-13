# Design

## Brief: a bench instrument

The page is the faceplate of a bench instrument: matte, light, cool grey, with graphite legends and quiet controls. The board replay is the one lit screen on it, like the display of an oscilloscope. Colour and light live inside that screen. Everything around it stays calm.

This pass is about feel, not content. The layout and the order of information stay as they were. If something in this system makes a screen busier than before, it gets cut.

### Colour

| Name | Hex | Role |
| --- | --- | --- |
| Enclosure | `#E3E5E0` | Page background. A cool, slightly green grey, like an instrument case. Not white, not cream. |
| Key | `#EEF0EC` | Raised surfaces: fields, select triggers, segment and tab tracks, open rows, the code editor. Lines are `#C4C8C1`. |
| Graphite | `#202427` | Text, primary keys, the selected segment, the tab indicator. Secondary text is `#5A615D` (5.0:1). There is no third grey for text. |
| Screen | `#121816` | Only the replay screen: board, transport, signal trace. Text on it is `#C9D1CC`, secondary `#8A958F`. |
| Trace | `#E8C15A` | Channel 1 yellow: lit outputs, the playhead, the scrubber fill. Only inside the screen. |
| Pass, Fail | `#1E6B43`, `#B0382F` on the faceplate; `#5CC98A`, `#F0766B` on the screen | Verdicts only. |

Focus is a 2 px probe-cyan ring (`#1C6884`) with a 2 px offset, the same everywhere. Contrast: graphite on enclosure 12.3:1, secondary text 5.0:1, pass 5.1:1, fail 4.8:1, trace on screen 10.5:1.

### Type

- **Geist** for all interface text. Weights 400, 500, 600.
- **Geist Mono** only for measured values (`23×`, `5.20 s`, `304 mV`) and code (the editor, diffs, logs). Never for labels or metadata. Mono means "this was measured". Geist Mono shares Geist's metrics, so a readout sits inside a sentence without jumping. Readouts use tabular figures.
- Both self-hosted from npm.
- Scale: 12 secondary, 14 body and UI, 16 lead, 20 section, 28 verdict, plus 48 for the product name on the landing page only. At most three sizes on one screen. Line height 1.5 for body, 1.2 for headings. Lines under 72 characters.

### Space and shape

- Spacing on a 4 px base: 4, 8, 12, 16, 24, 32, 48, 64.
- Radii show hierarchy: keys and fields 6 px, the screen 12 px with a 1 px inset bezel, list rows 0.
- No shadows on the faceplate. No gradients. No glows: a lit output is a flat lit colour.

### Layout

Left-aligned single column, max 960 px of content, as before. The transport (play, scrubber, time, speed) moves inside the screen, the way a scope keeps its controls beside the display.

```text
 Hexorcist   Break  Build  History                       deepseek-chat
 ─────────────────────────────────────────────────────────────────────
 Thermostat without hysteresis                              1 min 27 s
 ✓ 2 bugs found, both fixed and verified

 [ Threshold hover with noise (A0)  ⌄ ]               [ Before | After ]
 ╭──────────────────────────── screen ───────────────────────────────╮
 │                          fan D9                                    │
 │                     ┌── Uno board ──┐                              │
 │                     └───────────────┘                              │
 │                         gauge A0                                   │
 │  ▶  ━━━━━━━━━━━━━●──────────────────────────  5.20 / 8.00 s   1×   │
 ╰────────────────────────────────────────────────────────────────────╯
 Before the fix D9 switched 23 times in 5 s. After it, 0 times in 8 s.

 ›  No hysteresis, fan chatters at threshold      23× in 5 s    Fixed
 ›  Disconnected sensor leaves the fan off                      Fixed

 Scenarios   Checks   Containment   Compare   Logs
 ━━━━━━━━━
```

- **Containment run.** It has no board, so its hero is a row of six indicator lamps (guard, LLM, network, secrets, timeout kill, containers removed) under the verdict, on a small screen of their own. That screen replaces the board screen, so there is still only one lit surface per page.
- **Live run.** The five stages are a row of lamps: off, lit and breathing while running, steady when done, red on failure.
- **Code editor.** Stays on the faceplate: Key background, a quiet low-contrast syntax theme. It is not a second screen.

### Principles

1. **One lit screen on a quiet faceplate.** The screen is the only dark surface and the only place with colour beyond pass and fail. Boldness is spent there.
2. **Controls behave like keys.** They press (scale 0.97, 120 ms). Selections move a physical indicator: the Before/After segment slides, the tab underline slides. Rows and expanders open by height and fade. Nothing appears from nothing. Motion only answers the user, except the live stepper, which reports progress.
3. **Measurements are readouts, labels are words.** Measured values carry a unit, use mono with tabular figures, and tick up once when they first appear. Labels are sentence-case Geist. No middle-dot meta strings, no arrows in text, no all-caps eyebrows, no decoration that carries no information.

### Motion

- Curves: `--ease-out: cubic-bezier(0.23, 1, 0.32, 1)` for things that enter or respond, `--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1)` for things that move on screen (indicators). Never ease-in.
- Durations: press 120 ms, hover and colour 150 ms, tooltips 150 ms, indicators 200 ms, expand and collapse 200 ms, select menus 180 ms, counters 450 ms. Exit is faster than enter.
- Only transform and opacity animate, except expand and collapse, which animate height.
- Hover effects only under `(hover: hover) and (pointer: fine)`.
- `prefers-reduced-motion: reduce`: indicators jump, rows open without height animation, counters show the final value, the breathing lamp holds still. Opacity fades stay.
- Keyboard actions are not animated beyond the indicator moving.

### Controls

No browser-default control is left. Radix UI primitives keep keyboard and screen reader behaviour: Select (scenario, pin, pin type), Tabs (preset examples, detail tabs), ToggleGroup (Before/After), Checkbox, Tooltip, Collapsible (bug rows, expanders). Scrollbars are thin and toned only inside scrolling panels.

**Scrubber.** A custom `role="slider"` on the screen. Arrow keys move 100 ms (Shift: 1 s), Page Up and Page Down move 1 s, Home and End jump to the ends. Pointer capture while dragging, updates coalesced to one per animation frame, the thumb and fill move with transform only, and the value text reads as time for screen readers.

### Rejected as too default

- Near-black `#0b0b0d` with one periwinkle accent (the previous look): item 2 on the list of generated-design tells.
- Green-on-black phosphor CRT: the hacker-terminal cliché, and green is reserved for pass.
- PCB-green surfaces and copper-trace decoration: kitsch, and it competes with the board.
- Beige vintage instrument faceplate: drifts into the warm-cream tell.
- Seven-segment or LCD fonts for readouts: gimmick.
- IBM Plex (previous), Inter, Space Grotesk: default dev-tool choices. Martian Mono for readouts was considered; a third family and its width were not worth it.
- Mono for small labels, `A · B · C` meta strings, `→` in text, identical rounded cards with soft shadows, gradients and glows, spring bounce, staggered entrances.

## Design skill sources

Downloaded file by file at pinned commits into `.cursor/skills/` (gitignored, project-scoped only). No installer was used.

| Skill | Repository | Path | Commit | Files (SHA-256) |
| --- | --- | --- | --- | --- |
| frontend-design | [anthropics/skills](https://github.com/anthropics/skills) | `skills/frontend-design` | `2c5958ecac7cee2b583967a2c4981d0f4a75c579` | `SKILL.md` (`d91970639e9f5c37682ac7ab60094d35f1c7c1f38d731bd56396563aee10c1d3`), `LICENSE.txt` (`0d542e0c8804e39aa7f37eb00da5a762149dc682d7829451287e11b938e94594`) |
| emil-design-eng | [emilkowalski/skill](https://github.com/emilkowalski/skill) | `skills/emil-design-eng` | `f7ce8c02d6e3c8f0d980a44c57bcc41a40254349` | `SKILL.md` (`965cc3108047a1f68e504977ae7816c66115b202a32e7509c0b8305314839c54`) |

vercel-labs web-design-guidelines was skipped because it fetches remote rules at runtime.
