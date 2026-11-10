# Signed Bitwarden popup route evidence

Source inspected: `work/extension-lab/bitwarden-2026.7.0-signed.xpi`

SHA-256: `11836eb9d2abc9914bb337b57e20c5a09cf44f24fa572f7e886384fd350a5112`

The XPI includes `popup/main.js.map` and `popup/vendor-angular.js.map` with embedded source content. Line numbers below refer to those original sources.

## How the stale route is written

- `popup/main.js.map`, `webpack:///./src/vault/popup/utils/vault-popout-window.ts:162-184`: `openFido2Popout` constructs `popup/index.html#/fido2?...sessionId=...&senderTabId=...&senderUrl=...` and opens it as the `vault_Fido2Popout_<sessionId>` single action popout.
- `popup/main.js.map`, `webpack:///./src/platform/browser/browser-popup-utils.ts:83-88`: `inPopup` returns false for a window carrying `uilocation=popout`.
- `popup/main.js.map`, `webpack:///./src/platform/browser/browser-popup-utils.ts:386-394`: the popout helper adds the `uilocation=popout` and `singleActionPopout` query parameters.
- `popup/main.js.map`, `webpack:///./src/platform/popup/view-cache/popup-router-cache.service.ts:44-50`: the service constructor reads shared popup route history and unconditionally replays each cached URL with `this.location.go(url)`. This restore has no `inPopup` or single-action-popout check.
- Same source, `:98-117`: route history writes are gated by `BrowserPopupUtils.inPopup(window)`. Thus toolbar popup routes are cached, but the later popout still restores that shared cache.
- `popup/main.js.map`, `webpack:///./src/platform/services/popup-view-cache-background.service.ts:141-155`: cached popup state is cleared two minutes after the popup-close port disconnects; it can remain available when a passkey popout opens soon after the toolbar popup.

The cached `location.go("/tabs/current")` changes the hash on the FIDO2 popout and removes its `/fido2?...` fragment parameters. The page can still display the original FIDO2 component because this call updates browser location without the default Router treating it as a `popstate` navigation.

## Why the DOM can remain while the URL changes

- `popup/main.js.map`, `webpack:///./src/popup/app-routing.module.ts:157-160` registers `fido2` as a component route. The route data does not opt out of the popup cache.
- Same source, `:852-856` configures `RouterModule.forRoot` with `useHash: true`; it does not enable Angular's experimental platform-navigation feature.
- `popup/vendor-angular.js.map`, `webpack:///../../../../../k8-fastbuild-ST-fdfa778d11ba/bin/packages/common/src/location/location.ts:165-171`: `Location.go` calls `pushState` and notifies URL-change listeners.
- Same source, `:249-253`: the bundled Location documentation states that `Location.go()` does not trigger the browser `popstate` event.
- `popup/vendor-angular.js.map`, `webpack:///../../../../../k8-fastbuild-ST-fdfa778d11ba/bin/packages/router/src/statemanager/state_manager.ts:191-209`: the default `HistoryStateManager` listener ignores non-`popstate` notifications and only forwards events whose type is `popstate` to the Router.

The observed `tabs/current` hash with FIDO2 DOM still present is therefore consistent with this cached-route replay, rather than a successful Router navigation. A real route change through the Router would deactivate the FIDO2 component.

## Source-side correction

Skip popup route-cache restoration for `BrowserPopupUtils.inPopout(window)` (at minimum, for single-action popouts). Marking `/fido2` as `doNotSaveUrl` would also avoid saving that route from a regular popup, but it does not by itself prevent an unrelated cached toolbar route from being replayed into a new popout.

Until the signed extension changes, runtime binding must not accept the rewritten `/tabs/current` URL. A viable runtime path is to observe and retain the initial strict FIDO2 URL before cache restoration, then prove the same native popup browsing context and inner window are still current and revalidate the current native sender tab/frame before clicking. If the initial URL was not captured or identity changed, fail closed. `browser.originalURI` is not sufficient provenance by itself.
