# Website design and publication handoff

[Home](../README.md) / Website

**Status: local prototype prepared; no hosted website has been deployed.** The GitHub README is the current project homepage. The site in [website/](../website/) carries the same narrative, evidence and visual language into a responsive page for later publication.

![Desktop preview of the local HumanMimic website prototype.](assets/website-preview.jpg)

## Visual direction

A quiet research publication with the clarity of a product page: warm paper, dark ink, large serif headlines, small monospaced labels, fine rules and original motion diagrams. Real experiment imagery provides the visual anchor; schematic illustrations are explicitly labeled.

The user-selected references were reviewed on November 1, 2026:

| Reference | Observed direction | Adaptation for HumanMimic |
| :--- | :--- | :--- |
| [Physical Intelligence](https://www.pi.website/) | Sparse navigation, typography-led identity, compact research entries and generous empty space | Research-first information order, small metadata, concise links to evidence |
| [Anthropic](https://www.anthropic.com/) | Warm neutral background, strong editorial hierarchy and clear grouping of research/product material | Serif display text, restrained surfaces and deliberate separation of demonstrated results from future work |

These are aesthetic references, not affiliations. No company logos, proprietary fonts, copy or illustrations were reused. The motion-study and pipeline SVGs are original repository assets.

## Tokens

The implementation lives in [styles.css](../website/styles.css). Keep these values shared with future components:

| Token | Value | Use |
| :--- | :--- | :--- |
| Paper | `#f6f3eb` | Main background |
| Ink | `#272923` | Headlines, body text and primary links |
| Muted | `#64665b` | Supporting text |
| Rule | `#cfccbf` | Dividers and boundaries |
| Terracotta | `#a15033` | Motion, emphasis and proposed-work cues |
| Sage | `#e9ecdf` | Method section |
| White | `#fffdf8` | Evidence frame |
| Display | Georgia → Times New Roman → serif | Large headings |
| Body | Arial → Helvetica → sans-serif | Reading text |
| Metadata | Courier New → monospace | Stages, dates, identifiers |
| Content width | `1248px` maximum | Desktop composition |

System fonts avoid new downloads or font-license dependencies. Whitespace and type hierarchy carry the identity; avoid adding gradients, glass effects, dashboard chrome or ornamental motion to the research narrative.

## Page structure

1. **Purpose.** A short description and an original schematic motion study.
2. **Evidence at a glance.** R1 10/10, R2 held-out 4/5, verified 8 GB platform—with scope beside the numbers.
3. **Demonstration.** One actual comparison frame, source attribution and a link to the full evidence index.
4. **Method.** The production pipeline, state feedback and an explicitly proposed R4 branch.
5. **Research question.** Reference editing, geometric screening and bounded physical verification.
6. **Complete results.** All ten R2 source outcomes, with optional debug/held-out filters and visible failures.
7. **Insights.** Short entry points to evidence-backed technical notes.
8. **Reproduce.** Repository and preparation guide.

The prototype uses semantic HTML, visible focus styles, a skip link, responsive layouts, reduced-motion support, image descriptions and a keyboard-operable result filter. Without JavaScript, every result stays visible. Wide technical diagrams/tables scroll within their own regions on small screens.

## Preview and editing

Serve the repository root, not just `website/`, so shared SVG and evidence paths resolve:

```bash
python3 -m http.server 8000 --bind 127.0.0.1
```

Visit `http://127.0.0.1:8000/website/` on the same machine. Remote access requires supported forwarding. There is no build, backend, analytics or external font service. Navigation to research documents currently points to the private GitHub repository and therefore requires repository access.

| File | Responsibility |
| :--- | :--- |
| [index.html](../website/index.html) | Narrative, evidence table and navigation |
| [styles.css](../website/styles.css) | Design tokens, typography and responsive composition |
| [script.js](../website/script.js) | Optional result filtering and accessible count updates |
| [Shared SVG assets](assets/) | Header, motion study and pipeline |
| [Preview provenance](assets/provenance.json) | Source identity and static-frame extraction |

The HTML evidence table is a static snapshot of [R2 acceptance](../evidence/r2-acceptance-20261101.json), not an automatic live feed. Update the table, counters, date, README and results document together when a new acceptance snapshot is approved. Do not edit historical evidence to fit presentation copy.

## Before a later hosted release

Choose the audience and destination explicitly; the current repository remains private. Retain source attribution and determine which demonstration media may be served publicly. Full MP4s currently live on the workstation; this prototype uses only a small static preview and does not advertise a working video player.

For static hosting, prepare a staging directory containing `website/` plus the referenced `docs/assets/` paths, preserving relative structure, or rewrite the asset references as part of packaging. Do not serve the repository root as the production document root: it includes internal execution plans and ignored local artifacts. Move documentation to accessible pages if the audience will not have private-repository access. Set canonical/social metadata only after the final URL is known.

Then verify the packaged artifact at desktop and mobile widths, test every navigation/filter control, and confirm actual deployment separately. The repository prototype and its visual review do not imply a published website.


## Repository links after rename

Current repository links in the prototype use `https://github.com/LyrineYang/humanmimic`, including document and evidence navigation. This updates navigation only; historical provenance files, source-video attribution and actual run paths retain their original values. See the [handoff synchronization guide](../REMOTE_WORK.md) for the current source version.
