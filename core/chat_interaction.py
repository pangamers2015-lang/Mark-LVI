"""Conservative chat composer detection and message interaction for Playwright."""
from __future__ import annotations

import json
import re


_CHAT_HINT = re.compile(r"(message|mensagem|chat|prompt|ask|pergunt|send|enviar)", re.I)
_SEND_HINT = re.compile(r"^(send|enviar|submit|mandar|enviar mensagem)(\\b|$)", re.I)


async def interact_with_chat(
    page,
    message: str,
    input_selector: str = "",
    send_selector: str = "",
    confirm_send: bool = False,
) -> str:
    """Fill a likely chat composer; sending requires an explicit confirmation flag."""
    message = str(message or "")
    if not message.strip():
        return json.dumps({"ok": False, "error": "empty_message"}, ensure_ascii=False)

    try:
        if input_selector:
            candidates = [page.locator(input_selector).first]
        else:
            selectors = (
                'textarea:visible',
                '[contenteditable="true"]:visible',
                '[role="textbox"]:visible',
                'input[type="text"]:visible',
                'input:not([type]):visible',
            )
            candidates = []
            for selector in selectors:
                loc = page.locator(selector)
                for index in range(min(await loc.count(), 12)):
                    candidates.append(loc.nth(index))

        ranked = []
        for loc in candidates:
            try:
                if not await loc.is_visible() or not await loc.is_enabled():
                    continue
                details = await loc.evaluate("""el => ({
                    tag: el.tagName.toLowerCase(),
                    role: el.getAttribute('role') || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    aria: el.getAttribute('aria-label') || '',
                    name: el.getAttribute('name') || '',
                    type: el.getAttribute('type') || '',
                    editable: !!el.isContentEditable
                })""")
                descriptor = " ".join(str(v) for v in details.values())
                if details["type"].lower() in ("password", "email", "search"):
                    continue
                score = 0
                if _CHAT_HINT.search(descriptor):
                    score += 5
                if details["tag"] == "textarea" or details["editable"]:
                    score += 2
                if details["role"] == "textbox":
                    score += 2
                ranked.append((score, loc, details))
            except Exception:
                continue

        if not ranked:
            return json.dumps({
                "ok": False, "error": "chat_input_not_found",
                "hint": "Provide input_selector to identify the message field."
            }, ensure_ascii=False)

        ranked.sort(key=lambda item: item[0], reverse=True)
        if not input_selector and len(ranked) > 1 and ranked[0][0] == ranked[1][0]:
            return json.dumps({
                "ok": False, "error": "ambiguous_chat_input",
                "hint": "More than one possible input was found; provide input_selector."
            }, ensure_ascii=False)

        _, composer, details = ranked[0]
        await composer.click(timeout=5_000)
        await composer.fill(message, timeout=5_000)

        if not confirm_send:
            return json.dumps({
                "ok": True, "typed": True, "sent": False,
                "message_preview": message[:500],
                "input": details,
                "next_step": "Ask the user for approval, then call again with confirm_send=true."
            }, ensure_ascii=False)

        if send_selector:
            send_button = page.locator(send_selector).first
            if not await send_button.is_visible() or not await send_button.is_enabled():
                return json.dumps({
                    "ok": False, "typed": True, "sent": False,
                    "error": "send_button_not_available"
                }, ensure_ascii=False)
            await send_button.click(timeout=5_000)
        else:
            buttons = page.locator('button:visible, [role="button"]:visible, input[type="submit"]:visible')
            matches = []
            for index in range(min(await buttons.count(), 40)):
                button = buttons.nth(index)
                try:
                    label = await button.evaluate(
                        "el => [el.innerText, el.getAttribute('aria-label'), "
                        "el.getAttribute('title'), el.getAttribute('value')].filter(Boolean).join(' ')"
                    )
                    if _SEND_HINT.search(" ".join(str(label).split())):
                        matches.append(button)
                except Exception:
                    continue
            if len(matches) != 1:
                return json.dumps({
                    "ok": False, "typed": True, "sent": False,
                    "error": "send_button_not_unique",
                    "hint": "Provide send_selector; no automatic Enter fallback is used."
                }, ensure_ascii=False)
            await matches[0].click(timeout=5_000)

        return json.dumps({
            "ok": True, "typed": True, "sent": True,
            "message_length": len(message), "input": details
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({
            "ok": False, "typed": False, "sent": False,
            "error": str(exc)[:500]
        }, ensure_ascii=False)
