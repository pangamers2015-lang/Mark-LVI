from __future__ import annotations

import asyncio
import queue
import threading
import time
from typing import Callable

import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types
from echo_guard import EchoGuard
from barge_in import BargeInDetector
from knowledge_base import load_system_context

LIVE_MODEL = "gemini-3.8-live"
INPUT_RATE = 16_000
OUTPUT_RATE = 24_000
BLOCK = 1024


class LiveVoice:
    """Gemini Live adapter: continuous microphone PCM, streamed speech and captions."""

    def __init__(self, api_key: str, emit: Callable[[dict], None]):
        self.api_key = api_key
        self.emit = emit
        self._thread = None
        self._loop = None
        self._session = None
        self._stop = threading.Event()
        self._speaking = threading.Event()
        self._turn_complete = True
        self._connected = threading.Event()
        self._mic_queue = None
        self._stop_event = None
        self._output = queue.Queue(maxsize=100)
        self._pending = bytearray()
        self._barge_blocks = 0
        self._barge_audio = []
        self._echo = EchoGuard()
        self._barge = BargeInDetector()
        self._interrupted = False
        self._ptt_held = threading.Event()
        self._auto_capture = threading.Event()
        self._barge_pending = threading.Event()
        self._auto_silence_blocks = 0
        self._mic_stream = None
        self._speaker_stream = None
        self._mic_callback = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def connected(self) -> bool:
        return self._connected.is_set()

    def start(self):
        if self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._thread_main, daemon=True, name="yon-live-voice")
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._ptt_held.clear()
        self._auto_capture.clear()
        if self._loop and self._loop.is_running() and self._stop_event is not None:
            self._loop.call_soon_threadsafe(self._stop_event.set)
        self._stop_audio()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=5.0)

    def hold_to_talk(self, held: bool):
        held = bool(held)
        if held:
            if self._ptt_held.is_set():
                return
            self._ptt_held.set()
            if self._speaking.is_set():
                self.interrupt()
            try:
                self._start_microphone()
            except Exception:
                self._ptt_held.clear()
                raise
            self.emit({"type": "voice_state", "state": "listening"})
            return
        if not self._ptt_held.is_set():
            return
        self._ptt_held.clear()
        self._stop_microphone()
        if self._loop and self._loop.is_running() and self._mic_queue is not None:
            self._loop.call_soon_threadsafe(self._queue_end_marker)
        self.emit({"type": "voice_state", "state": "thinking"})

    def _queue_end_marker(self):
        if self._mic_queue is None:
            return
        if self._mic_queue.full():
            try:
                self._mic_queue.get_nowait()
                self._mic_queue.task_done()
            except asyncio.QueueEmpty:
                pass
        self._mic_queue.put_nowait(None)

    def interrupt(self):
        self._interrupted = True
        self._stop_audio()
        self._echo.reset()
        self._barge.reset()
        self.emit({"type": "voice_state", "state": "listening"})

    def send_text_now(self, text: str):
        if not self.connected or not self._loop:
            raise RuntimeError("A sessão de voz ainda está conectando.")
        future = asyncio.run_coroutine_threadsafe(self._send_text(text), self._loop)
        future.add_done_callback(lambda f: self.emit({"type": "voice_error", "text": str(f.exception())}) if f.exception() else None)

    async def _send_text(self, text: str):
        if self._session:
            await self._session.send_client_content(
                turns={"role": "user", "parts": [{"text": text}]}, turn_complete=True
            )

    def _thread_main(self):
        while not self._stop.is_set():
            try:
                asyncio.run(self._run())
            except Exception as exc:
                if not self._stop.is_set():
                    self.emit({"type": "voice_error", "text": str(exc)[:600]})
                    self.emit({"type": "voice_state", "state": "reconnecting"})
                    time.sleep(3)
            else:
                if not self._stop.is_set():
                    self.emit({"type": "voice_state", "state": "reconnecting"})
                    time.sleep(3)
            finally:
                self._connected.clear()
                self._session = None
                self._loop = None
        self.emit({"type": "voice_state", "state": "stopped"})

    async def _run(self):
        self._loop = asyncio.get_running_loop()
        self._mic_queue = asyncio.Queue(maxsize=100)
        self._stop_event = asyncio.Event()
        if self._stop.is_set():
            self._stop_event.set()
        client = genai.Client(api_key=self.api_key, http_options={"api_version": "v1beta"})
        config = {
            "response_modalities": ["AUDIO"],
            "input_audio_transcription": {},
            "output_audio_transcription": {},
            "system_instruction": load_system_context() + (
                "\\n\\nNa conversa por voz, use frases naturais e curtas. "
                "Não responda antes de o usuário concluir a ideia. Se a fala estiver ambígua, "
                "peça para repetir apenas o trecho necessário. Não invente ferramentas disponíveis."
            ),
            "speech_config": {"voice_config": {"prebuilt_voice_config": {"voice_name": "Orus"}}},
        }
        self.emit({"type": "voice_state", "state": "connecting"})
        async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
            self._session = session
            self._connected.set()
            self.emit({"type": "voice_state", "state": "idle"})
            try:
                self._open_audio()
                tasks = [
                    asyncio.create_task(self._send_audio(session)),
                    asyncio.create_task(self._receive(session)),
                    asyncio.create_task(self._stop_event.wait()),
                ]
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                for task in done:
                    if task is not tasks[2]:
                        exc = task.exception()
                        if exc:
                            raise exc
            finally:
                self._close_audio()
                self._session = None
                self._connected.clear()

    def _open_audio(self):
        def mic_callback(indata, frames, timing, status):
            pcm = bytes(indata)
            if not self._loop or self._mic_queue is None:
                return
            # Explicit push-to-talk always wins and streams only while held.
            if self._ptt_held.is_set():
                self._loop.call_soon_threadsafe(self._queue_mic, pcm)
                return
            # After a voice interruption, keep forwarding the user's utterance
            # until a short silence marks its end.
            if self._auto_capture.is_set():
                samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
                level = float(np.sqrt(np.mean(samples * samples))) / 32768.0 if samples.size else 0.0
                self._loop.call_soon_threadsafe(self._queue_mic, pcm)
                if level < 0.012:
                    self._auto_silence_blocks += 1
                    if self._auto_silence_blocks >= 12:
                        self._loop.call_soon_threadsafe(self._end_auto_capture)
                else:
                    self._auto_silence_blocks = 0
                return
            # While Yon speaks, analyse microphone audio locally. Nothing is
            # sent to Gemini unless EchoGuard distinguishes the user's voice
            # from the sound coming back through the speakers.
            if self._speaking.is_set() and not self._barge_pending.is_set():
                try:
                    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32)
                    level = float(np.sqrt(np.mean(samples * samples))) / 32768.0 if samples.size else 0.0
                    user_speech = self._echo.is_user_speech(pcm, INPUT_RATE, level)
                    confirmed = self._echo.ready_for_barge_in and user_speech
                    captured = self._barge.observe(pcm, confirmed, self._echo.required_blocks)
                    if captured:
                        self._barge_pending.set()
                        self._loop.call_soon_threadsafe(self._barge_in, captured)
                except Exception:
                    self._barge.reset()

        def speaker_callback(outdata, frames, timing, status):
            needed = frames * 2
            while len(self._pending) < needed:
                try:
                    self._pending.extend(self._output.get_nowait())
                except queue.Empty:
                    break
            chunk = self._pending[:needed]
            del self._pending[:len(chunk)]
            if len(chunk) < needed:
                chunk += b"\x00" * (needed - len(chunk))
            outdata[:] = chunk
            if not self._pending and self._output.empty() and self._speaking.is_set() and self._turn_complete:
                self._speaking.clear()
                if self._loop:
                    self._loop.call_soon_threadsafe(self._finish_playback)
                    self._loop.call_soon_threadsafe(self.emit, {"type": "voice_state", "state": "listening" if self._ptt_held.is_set() else "idle"})

        self._mic_callback = mic_callback
        self._speaker_stream = sd.RawOutputStream(samplerate=OUTPUT_RATE, blocksize=BLOCK, channels=1,
                                                  dtype="int16", callback=speaker_callback)
        self._speaker_stream.start()

    def _start_microphone(self):
        if self._mic_stream is not None:
            return
        self._mic_stream = sd.RawInputStream(
            samplerate=INPUT_RATE, blocksize=BLOCK, channels=1,
            dtype="int16", callback=self._mic_callback
        )
        try:
            self._mic_stream.start()
        except Exception:
            try:
                self._mic_stream.close()
            finally:
                self._mic_stream = None
            raise

    def _stop_microphone(self):
        if self._mic_stream is not None:
            try:
                self._mic_stream.stop()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

    def _queue_mic(self, pcm: bytes):
        if self._mic_queue is None:
            return
        if self._mic_queue.full():
            try:
                self._mic_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        self._mic_queue.put_nowait(pcm)

    def _barge_in(self, captured: list[bytes]):
        # Called on the asyncio loop after sustained, echo-filtered speech.
        self._interrupted = True
        self._stop_audio()
        self._echo.reset()
        self._barge.reset()
        self._auto_silence_blocks = 0
        self._auto_capture.set()
        self._barge_pending.clear()
        self.emit({"type": "voice_state", "state": "listening"})
        for block in captured:
            self._queue_mic(block)

    def _end_auto_capture(self):
        if not self._auto_capture.is_set():
            return
        self._auto_capture.clear()
        self._auto_silence_blocks = 0
        self._queue_end_marker()
        if not self._speaking.is_set() and not self._ptt_held.is_set():
            self._stop_microphone()
        self.emit({"type": "voice_state", "state": "thinking"})

    def _finish_playback(self):
        # The output device has drained the completed turn. Keep the mic open
        # only for a held PTT session or an utterance already captured by barge-in.
        if not self._ptt_held.is_set() and not self._auto_capture.is_set():
            self._stop_microphone()
            self._echo.reset()
            self._barge.reset()
            self._barge_pending.clear()

    def _stop_audio(self):
        self._speaking.clear()
        self._pending.clear()
        while True:
            try:
                self._output.get_nowait()
            except queue.Empty:
                break

    def _close_audio(self):
        self._stop_microphone()
        if self._speaker_stream is not None:
            try:
                self._speaker_stream.stop()
                self._speaker_stream.close()
            except Exception:
                pass
        self._speaker_stream = None

    async def _send_audio(self, session):
        while not self._stop.is_set():
            pcm = await self._mic_queue.get()
            try:
                if pcm is None:
                    await session.send_realtime_input(audio_stream_end=True)
                else:
                    await session.send_realtime_input(
                        audio=types.Blob(data=pcm, mime_type=f"audio/pcm;rate={INPUT_RATE}")
                    )
            finally:
                self._mic_queue.task_done()

    async def _receive(self, session):
        async for response in session.receive():
            if self._stop.is_set():
                return
            if response.data and not self._interrupted:
                self._turn_complete = False
                self._speaking.set()
                # Open the mic for local-only barge-in detection while Yon speaks.
                if not self._ptt_held.is_set() and not self._auto_capture.is_set():
                    try:
                        self._start_microphone()
                    except Exception as exc:
                        self.emit({"type": "voice_error", "text": f"Detecção de interrupção por voz indisponível: {exc}"})
                self.emit({"type": "voice_state", "state": "speaking"})
                for offset in range(0, len(response.data), 2400):
                    chunk = response.data[offset:offset + 2400]
                    samples = np.frombuffer(chunk, dtype="<i2").astype(np.float32)
                    level = float(np.sqrt(np.mean(samples * samples))) / 32768.0 if samples.size else 0.0
                    self._echo.note_output(chunk, OUTPUT_RATE, level)
                    try:
                        self._output.put_nowait(chunk)
                    except queue.Full:
                        break
            content = response.server_content
            if content:
                inp = getattr(content, "input_transcription", None)
                out = getattr(content, "output_transcription", None)
                if inp and inp.text:
                    self.emit({"type": "transcript", "speaker": "user", "text": inp.text})
                if out and out.text and not self._interrupted:
                    self.emit({"type": "transcript", "speaker": "yon", "text": out.text})
                if content.turn_complete:
                    self._turn_complete = True
                    if self._interrupted:
                        self._interrupted = False
                        self._echo.reset()
                        self._barge.reset()
                    self.emit({"type": "turn_complete"})
