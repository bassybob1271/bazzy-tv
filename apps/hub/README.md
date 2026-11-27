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

## Members skip this page

The landing page is for new visitors. When someone signs in to an app, the app sets a marker cookie for the whole
domain; bazzy.tv sees it and sends them straight to that app (before the page draws). `bazzy.tv/?home` always shows
the landing page.

```
bazzy_member=<video|live|box>; Domain=.bazzy.tv; Path=/; Max-Age=31536000; SameSite=Lax; Secure
```

Set it on sign-in, clear it (`Max-Age=0`) on sign-out. It holds no account data. Bazzy TV (the film site) does this already
(`apps/video/frontend/src/store/useStore.ts`). **It only works for apps on `*.bazzy.tv`**, which is why all three live there:
video.bazzy.tv (films), live.bazzy.tv and box.bazzy.tv. The old box.bazzy.io / live.bazzy.io addresses should
301-redirect to their bazzy.tv versions once the bazzy.tv zone sits in the same Cloudflare account as the tunnel. An app that isn't open yet (see `BAZZY_APPS` in `index.html`) never triggers the redirect.
