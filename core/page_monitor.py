"""DOM-change monitoring for Playwright pages.

The monitor observes visible page text, not screenshots or form-field values.
It waits for a meaningful text change and then a short quiet period so streamed
responses can finish before their text is returned to the assistant.
"""
from __future__ import annotations

import json


async def wait_for_page_change(
    page,
    timeout_ms: int = 30_000,
    quiet_ms: int = 900,
    selector: str = "body",
    max_chars: int = 8_000,
) -> str:
    """Wait for visible text to change, then return a stable text snapshot."""
    timeout_ms = max(1_000, min(int(timeout_ms), 60_000))
    quiet_ms = max(200, min(int(quiet_ms), 5_000))
    max_chars = max(500, min(int(max_chars), 20_000))
    selector = str(selector or "body").strip() or "body"

    result = await page.evaluate(
        """async ({selector, timeoutMs, quietMs, maxChars}) => {
            const target = document.querySelector(selector);
            if (!target) {
                return {changed: false, error: "selector_not_found",
                        text: "", url: location.href, title: document.title};
            }
            const read = () => (target.innerText || target.textContent || "")
                .replace(/\\u00a0/g, " ").trim();
            const initial = read();
            const started = Date.now();

            return await new Promise(resolve => {
                let quietTimer = null;
                let finished = false;
                const finish = (changed, reason) => {
                    if (finished) return;
                    finished = true;
                    observer.disconnect();
                    if (quietTimer !== null) clearTimeout(quietTimer);
                    clearTimeout(timeoutTimer);
                    resolve({
                        changed,
                        reason,
                        text: read().slice(0, maxChars),
                        url: location.href,
                        title: document.title,
                        elapsed_ms: Date.now() - started
                    });
                };
                const check = () => {
                    if (read() === initial) return;
                    if (quietTimer !== null) clearTimeout(quietTimer);
                    quietTimer = setTimeout(() => finish(true, "text_changed"),
                                            quietMs);
                };
                const observer = new MutationObserver(check);
                observer.observe(target, {
                    subtree: true, childList: true, characterData: true
                });
                const timeoutTimer = setTimeout(
                    () => finish(false, "timeout"), timeoutMs
                );
                check();
            });
        }""",
        {
            "selector": selector,
            "timeoutMs": timeout_ms,
            "quietMs": quiet_ms,
            "maxChars": max_chars,
        },
    )
    return json.dumps(result, ensure_ascii=False)
