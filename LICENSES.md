# Licences and attributions

Bima Sarthi is an independent project, not affiliated with IRDAI, LIC or any insurer.

| Component | Licence / terms | Notes |
|---|---|---|
| This project's code and rule cards | MIT (see `LICENSE`) | Copyright (c) 2026 Parth Rait |
| Glimmer (reading and extraction model) | Apache License 2.0 | Weights are downloaded from Hugging Face; they are not redistributed in this repository. Check the model card of the exact checkpoint used. |
| Muse Spark Open (rephrasing, hosted demo, baseline) | Muse Model License | Built with Muse Spark Open. Used through Baseten. Follow the licence's attribution and use terms; the weights are not redistributed here. |
| Indian Kanoon judgment data | Indian Kanoon API terms | "powered by IKanoon" must be shown wherever judgment data is displayed (the gallery and the evaluation case table). Judgment text is not republished in this repository; published evaluation results carry case identifiers and our own verdicts only. |
| IRDAI regulations and circulars, Insurance Ombudsman Rules, CIO and IRDAI annual reports | Public records of the regulator / government | Quoted verbatim and cited with source, page and SHA-256. Each stored file is listed in the `source` table with its `licence_note`. |
| Insurer policy wordings and Customer Information Sheets | Published by the insurers on their own sites | Used only for the clause index and the uniformity check. |
| Aceternity UI components (LiquidGlass, ChromaticImage, Carousel, DraggableCard; and, from 2 Nov 2026 phase 3a, ParallaxHeroImages, FileUpload, Lamp, Timeline, CloudShader) | MIT (author Manu Arora) | Installed from the shadcn registry into `frontend/src/components/ui/`; our changes are listed in `docs/FRONTEND_PHASE2_PLAN.md` section 12 (first four) and `DESIGN.md`, "Aceternity components" (all nine); pristine copies are in `frontend/vendor/aceternity-originals/`. FileUpload depends on react-dropzone (MIT), pinned in `frontend/package.json`. |
| Frontend libraries: React, Vite, Tailwind CSS 4.3.3, motion 14.9.0, react-router 8.5.1, @tabler/icons-react 3.50.0, clsx, tailwind-merge | MIT | Exact versions are pinned in `frontend/package.json`. class-variance-authority 0.7.1 is Apache-2.0. |
| Fonts: Fraunces, Newsreader, Source Sans 3, IBM Plex Mono, Noto Sans Devanagari, Noto Serif Devanagari | SIL Open Font License 1.1 | Self-hosted through `@fontsource`; nothing is loaded from a CDN. |
| Artwork in `frontend/src/assets/art` | MIT (this project) | Original SVG made for this project; no stock photography. |
| Third-party Python and JavaScript dependencies | Their own licences | See `pyproject.toml` and `uv.lock`. |

Not a legal or medical document: see the disclaimer in `README.md`.
