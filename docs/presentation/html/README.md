# Editing the Brink HTML presentation

This folder is a self-contained interactive presentation. It runs in a browser, supports keyboard
navigation and speaker notes, and contains the current final-project deck.

## Run it locally

You need Node.js 22.13 or newer.

From the Brink repository:

```powershell
cd docs/presentation/html
npm install
npm run dev
```

Open the local address printed in the terminal. Stop the server with `Ctrl+C`.

Before submitting changes, run:

```powershell
npm test
```

That command builds the production presentation and runs the rendered-page checks.

## Where to make changes

### Slide order, titles, and speaker notes

Open [`app/page.tsx`](app/page.tsx).

The `slides` array near the top controls:

- slide order;
- the small section label (`kicker`);
- slide title;
- presenter used in the optional speaker-notes panel;
- internal timing guidance; and
- the full speaker notes.

Move an entire slide object to change its order. Keep every `id` unique.

### Visible slide content

Farther down in `app/page.tsx`, `SlideContent` contains one `case` for each slide `id`.
Edit the matching case when changing diagrams, labels, screenshots, or other visible content.

For example, changes to the scheduled-jobs slide belong in:

```tsx
case "automation":
```

### Design and layout

Open [`app/globals.css`](app/globals.css) for typography, colours, spacing, diagrams, responsive
layout, and presentation controls.

The deck is designed for a 16:9 recording. Check any text-heavy change at a short presentation
size as well as a full desktop window. The CSS contains a short-height breakpoint for projectors.

### Screenshots

Product screenshots live in [`public/screenshots/`](public/screenshots/).

To replace one:

1. Keep the same filename and overwrite the image; or
2. Add a new image and update its `/screenshots/<filename>` reference in `app/page.tsx`.

Do not commit screenshots containing secrets, private account information, or access tokens.

## Presentation controls

- `←` / `→`: previous or next slide
- `O`: slide overview
- `N`: speaker notes
- `F`: fullscreen
- `Esc`: close the overview or notes

Presenter names and internal timing guidance are not displayed in the normal slide header.

## How the team should submit a change

Follow the normal Brink workflow:

```powershell
git checkout develop
git pull
git checkout -b docs/T105-presentation-update
```

Make the edit, run `npm test` from this folder, then commit and push the branch. Open a pull request
into `develop` and describe which slides changed.

Avoid editing directly on `develop` or `main`. If multiple people are changing the deck, divide the
work by slide so the same sections of `app/page.tsx` are not edited in parallel.

## Publishing

Pushing a change to GitHub does **not** automatically update the existing hosted presentation.
The repository is the shared editing source. After a pull request is merged, the presentation owner
must publish that committed version to the existing hosting project.

The hosting file in this folder deliberately contains no production project ID or credentials.
Never commit hosting tokens or replace it with a private local hosting configuration.
