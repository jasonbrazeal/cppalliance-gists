# Runvil Linux installer test

Tested on Oct 28, 2026 with `Runvil_0.3.0_aarch64-setup.run` from the `installers-linux-arm` artifact (run 39986248214, attempt 1). The zip's SHA-256 matched the artifact digest.

**Machine:** Debian 13 (trixie), ARM64, Xfce, X11 (UTM VM on MacOS)

| Check | Result | What the agent saw |
|---|---|---|
| A. The components page | Fail | The install folder defaults to `~/Runvil`. All three components start checked, and the label reads "Speech to Text (downloads about 0.6 GB)". After Runvil Gateway is unchecked, Speech to Text stays checked, and checking Speech to Text does not re-check Gateway. The summary page still lists Runvil Gateway (22.37 MB), so it gets installed anyway, but the page allows Speech to Text to be checked while Gateway is unchecked. |
| B. Fresh install with the defaults | Fail | The install succeeded, and Show Details streamed the speech download's progress live, line by line (ggml-base.en 17%, 50%, ... done). The applications menu has Runvil and Runvil Gateway Settings under Development, both with icons, and the Gateway tray icon shows in the Xfce panel. With the network off (`gateway.log` confirms DNS failures at startup), dictation does not work: Ctrl+Shift+Space only shows "The agent isn't asking for input; the mic opens when it does." and the chat box cannot be clicked. Ctrl+Shift+L appears to do nothing because it reuses the existing empty chat. After the network came back, the tray menu still showed "Update failed: cannot fetch the release manifest https://github.com/cppalliance/runvil/releases/download/workshop-latest/latest.json". |
| C. The Gateway Settings entry | Pass | Firefox opened the Runvil Gateway Config page at `http://127.0.0.1:36707/config/#/local`, served from the local machine. It lands on the Local tab, not Settings. |
| D. A second install into the same folder | Pass | The installer showed "The directory you selected already exists and contains an installation. Choose a different target for installation." Cancelling left the existing install untouched. |
| E. Install a model and chat (optional) | Partial | Qwen3-0.6B (Q4_K_M, from the local Unsloth cache) was added through Gateway Settings: Add Local, Save, Apply, then added to the default profile. After a gateway restart the profile load failed (`switch profile failed at download-models`; the gateway downloaded `llama-b10082-bin-ubuntu-vulkan-arm64.tar.gz` but never unpacked a `llama-server`). A remote model, DeepSeek V4.1 Flash on the self-hosted RunPod vLLM pod, was configured instead. It shows in Runvil's model menu (Ctrl+/) and answered a message. |
| F. Uninstall | Pass | The maintenance tool's Remove all components finished with "Runvil has now been uninstalled from your computer." Both menu entries are gone, `~/Runvil` is gone, and `~/.runvil` remains with the Gateway's config, logs, and speech models. In the maintenance tool, Add or remove components and Update components are greyed out. |

## Notes on the failures

**A.** The installer pulls Runvil Gateway in silently as a dependency at install time, but the components page never shows it as checked. The "Space required" figure does include Gateway's size whenever Speech to Text is checked (135.97 MB without, 158.34 MB with).

**B.** In `crates/workshop/ui/src/parts/agent/agent-session-view.ts` (line 212), dictation is gated on `pendingInputToken`, which is set only while the agent is waiting for input. With no chat model installed (the default), the agent never waits, so the mic never opens and the chat box stays locked. The test expects dictation to work right after a default install, before any model is added. Ctrl+Shift+L doing nothing visible matches `newChat()` in `agent-commands.ts`, which reuses an empty active chat.

**B, retested with a chat model selected.** With DeepSeek V4.1 Flash selected, the chat box is clickable and Ctrl+Shift+Space gets past the input gate, but it fails with "No microphone is available." (`realtime-stt.ts`, failure kind `device-unavailable`). The VM's mic works through PipeWire. The AppImage bundles the GStreamer core libraries but no GStreamer plugins, and its AppRun sets `GST_PLUGIN_SYSTEM_PATH_1_0` to the AppImage's own empty `usr/lib/gstreamer-1.0`. The system's `libgstpulseaudio.so`, `libgstalsa.so`, and `libgstautodetect.so` are hidden from WebKitGTK, so it finds no audio source. Dictation therefore cannot work from this AppImage on Linux, online or offline.

## Environment notes

- The VM's virtio sound card did not deliver mic audio through PulseAudio (capture stalled, which PulseAudio's log blames on the `virtio_snd` driver). Replacing PulseAudio with PipeWire fixed capture, and a recorded test picked up speech before check B.
- The installer printed only `Warning: QProcess::readAllStandardError: Called with MergedChannels` to the terminal.
