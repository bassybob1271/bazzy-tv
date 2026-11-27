# Bazzy TV landing page (bazzy.tv)

Static front door with links to Bazzy Video, Bazzy Live and BazzyBox. No build step.

**Where each link points** is set at the bottom of `index.html` (`APPS`). Flip `open: true` when an address is live
(it switches the card badge from "Opening soon" to "Open").

## Put it on bazzy.tv (Cloudflare Pages — free)

In the Cloudflare account that holds the **bazzy.tv** zone:

1. **Workers & Pages → Create → Pages → Connect to Git**, pick `bassybob1271/bazzy-tv`.
2. Build settings: framework **None**, build command **empty**, build output directory **`apps/hub`**.
3. After the first deploy: **Custom domains → Set up a custom domain → `bazzy.tv`**, then again for `www.bazzy.tv`.
   Cloudflare adds the DNS records itself. Your Google Workspace mail records (MX/TXT) are untouched.

Every push to `main` redeploys the page.
