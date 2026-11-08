from __future__ import annotations

import asyncio
import json
import queue
import threading
import time
from pathlib import Path

import keyring
import sounddevice as sd
import webview
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parent
UI = ROOT / "ui" / "index.html"
SERVICE = "JarvisVoice"
ACCOUNT = "gemini-api-key"
MODEL = "models/gemini-3.1-flash-live-preview"
MIC_RATE = 16_000
SPEAKER_RATE = 24_000
CHUNK = 1_024
SYSTEM_PROMPT = (
    "Você é Jarvis, um assistente de conversa por voz. "
    "Converse em português brasileiro, de forma natural, clara e objetiva. "
    "Nesta versão você não possui ferramentas e não controla o computador. "
    "Se pedirem uma ação no computador, explique brevemente que essa capacidade "
    "ainda não está disponível. Não afirme que executou ações."
)


class AudioPlayer:
    def __init__(self) -> None:
        self.chunks: queue.Queue[bytes] = queue.Queue(maxsize=80)
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def put(self, data: bytes) -> None:
        for offset in range(0, len(data), 2_400):
            part = data[offset:offset + 2_400]
            try:
                self.chunks.put_nowait(part)
            except queue.Full:
                break

    def clear(self) -> None:
        while True:
            try:
                self.chunks.get_nowait()
            except queue.Empty:
                return

    def close(self) -> None:
        self.stop_event.set()

    def _run(self) -> None:
        try:
            with sd.RawOutputStream(
                samplerate=SPEAKER_RATE, channels=1, dtype="int16",
                blocksize=1_200
            ) as stream:
                while not self.stop_event.is_set():
                    try:
                        stream.write(self.chunks.get(timeout=0.1))
                    except queue.Empty:
                        continue
        except Exception as exc:
            print(f"[audio output] {exc}")


class JarvisApi:
    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._player: AudioPlayer | None = None

    def _ui(self, state: str) -> None:
        try:
            if webview.windows:
                webview.windows[0].evaluate_js(
                    f"window.jarvisState({json.dumps(state)})"
                )
        except Exception:
            pass

    def has_key(self) -> bool:
        return bool(keyring.get_password(SERVICE, ACCOUNT))

    def save_key(self, value: str) -> bool:
        value = value.strip()
        if not value:
            raise ValueError("A chave Gemini não pode ficar vazia.")
        keyring.set_password(SERVICE, ACCOUNT, value)
        return True

    def start(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        key = keyring.get_password(SERVICE, ACCOUNT)
        if not key:
            raise RuntimeError("Configure a chave Gemini primeiro.")
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._thread_main, args=(key,), daemon=True
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._player:
            self._player.close()

    def _thread_main(self, key: str) -> None:
        try:
            asyncio.run(self._conversation(key))
        except Exception as exc:
            print(f"[Jarvis] {type(exc).__name__}: {exc}")
            self._ui("erro")

    async def _conversation(self, key: str) -> None:
        client = genai.Client(api_key=key)
        self._player = AudioPlayer()
        while not self._stop.is_set():
            self._ui("pensando")
            try:
                config = {
                    "response_modalities": ["AUDIO"],
                    "input_audio_transcription": {},
                    "output_audio_transcription": {},
                    "system_instruction": SYSTEM_PROMPT,
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {"voice_name": "Aoede"}
                        }
                    },
                }
                async with client.aio.live.connect(
                    model=MODEL, config=config
                ) as session:
                    loop = asyncio.get_running_loop()
                    incoming: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)

                    def on_audio(indata, frames, timing, status) -> None:
                        block = bytes(indata)
                        def enqueue() -> None:
                            if incoming.full():
                                try:
                                    incoming.get_nowait()
                                except asyncio.QueueEmpty:
                                    pass
                            incoming.put_nowait(block)
                        loop.call_soon_threadsafe(enqueue)

                    with sd.RawInputStream(
                        samplerate=MIC_RATE, channels=1, dtype="int16",
                        blocksize=CHUNK, callback=on_audio
                    ):
                        self._ui("ouvindo")
                        sender = asyncio.create_task(
                            self._send_audio(session, incoming)
                        )
                        receiver = asyncio.create_task(
                            self._receive_audio(session)
                        )
                        done, pending = await asyncio.wait(
                            {sender, receiver},
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        for task in pending:
                            task.cancel()
                        await asyncio.gather(*pending, return_exceptions=True)
                        for task in done:
                            task.result()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[Jarvis Live] {type(exc).__name__}: {exc}")
                self._ui("erro")
                await asyncio.sleep(4)
        if self._player:
            self._player.close()

    async def _send_audio(
        self, session, incoming: asyncio.Queue[bytes]
    ) -> None:
        while not self._stop.is_set():
            block = await incoming.get()
            await session.send_realtime_input(
                audio=types.Blob(
                    data=block, mime_type=f"audio/pcm;rate={MIC_RATE}"
                )
            )

    async def _receive_audio(self, session) -> None:
        async for response in session.receive():
            if self._stop.is_set():
                return
            content = response.server_content
            if content and getattr(content, "interrupted", False):
                self._player.clear()
                self._ui("ouvindo")
            if response.data:
                self._player.put(response.data)
                self._ui("falando")
            if content and getattr(content, "turn_complete", False):
                self._ui("ouvindo")


def main() -> None:
    api = JarvisApi()
    webview.create_window(
        "JARVIS", UI.as_uri(), js_api=api,
        width=1100, height=820, min_size=(720, 560),
        background_color="#000000"
    )
    try:
        webview.start(debug=False)
    finally:
        api.stop()


if __name__ == "__main__":
    main()
