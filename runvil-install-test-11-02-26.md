# Runvil Linux installer test, round 2

Tested on Nov 2, 2026 with `Runvil_0.3.0_aarch64-setup.run` from the `installers-linux-arm` artifact (run 41074186054, artifact 12987291067). The zip's SHA-256 matched the artifact digest. The test started clean, with no `~/Runvil` and no `~/.runvil`.

**Machine:** Debian 13 (trixie), ARM64, Xfce, X11 (UTM VM)

| Check | Result | What the agent saw |
|---|---|---|
| A. The components page | Pass | The install folder defaults to `~/Runvil`. All three components start checked, and the label reads "Speech to Text (downloads about 0.6 GB)". After Runvil Gateway was unchecked, Speech to Text stayed checked, and the summary page listed Runvil Gateway (22.37 MB) alongside Runvil Workshop and Speech to Text. |
| B. Fresh install with the defaults | Pass | Show Details streamed the speech download's progress live, line by line (ggml-base.en 29%, 73%, done; ggml-small.en 12%, 26%, ... 92%, done). The applications menu has Runvil and Runvil Gateway Settings under Development, both with icons. Runvil opened from the menu with an empty chat, and the Gateway's tray icon shows in the Xfce panel. |
| C. The Gateway Settings entry | Pass | Firefox opened the Runvil Gateway Config page at `http://127.0.0.1:40663/config/#/local`, served from the local machine, on the Local tab. |
| D. A second install into the same folder | Pass | The installer showed "The directory you selected already exists and contains an installation. Choose a different target for installation." Cancelling left the existing install untouched. |
| E. Install a model, chat, and dictate offline | Fail | The model installs and dictation works, but the model cannot chat with the settings Discover gives it. Discover, Qwen/Qwen3-1.7B-GGUF, Download on Q8_0 showed "Qwen3-1.7B-Q8_0 added to default - Apply and restart to download", and Apply showed "Restart the gateway to apply these changes." After quitting Runvil and the Gateway and starting Runvil from the menu, the model downloaded (1.7 GiB in about 45 seconds), `llama-server` was provisioned, and the log shows "local llama-server ready model=Qwen3-1.7B-Q8_0". The model shows in Runvil's model menu (Ctrl+/), but sending a message fails with "Connection Error: the environment cannot satisfy this prompt: - role 'chat': requires a context of at least 32768 tokens; the current model provides 4096". With the model's Context raised to 32768 in Gateway Settings (Local, Qwen3-1.7B-Q8_0, Save, Apply, then the same restart), the model answered the message. With the network off, dictation through Ctrl+Shift+Space put the spoken sentence in the chat box: "Hello there, what is your name?" |
| F. Uninstall | Pass | The maintenance tool's Remove all components finished with "Runvil has now been uninstalled from your computer." Both menu entries are gone, `~/Runvil` is gone, and `~/.runvil` remains with the Gateway's configuration, logs, and models. |

## Round 1 failures

Both failures this build set out to fix are fixed on ARM64:

- **Installing a model.** In round 1 the profile load failed at `download-models` and `~/.runvil/llama.cpp` stayed empty. In this round the model downloaded after the restart and `llama-server` started (`~/.runvil/llama.cpp/b10082-linux-aarch64-vulkan`).
- **Dictation.** In round 1 the AppImage reported "No microphone is available." In this round dictation transcribed a spoken sentence offline.

## Notes on the failure

**E.** A model downloaded through Discover is written to `gateway.toml` with `context = 4096`, while Runvil's built-in chat agent requires a context of at least 32768 tokens. A user following the test's steps cannot chat with the model, and therefore cannot reach the dictation step, since the microphone opens only after a chat model has answered. Raising the context by hand worked on this machine, with Qwen3-1.7B at Q8_0 and the default quantized KV cache (q8_0 for K, q4_0 for V).

## Environment notes

- The VM uses PipeWire for audio. Round 1 replaced PulseAudio with PipeWire because the virtio sound card's capture stalled under PulseAudio.
- The installer printed only `Warning: QProcess::readAllStandardError: Called with MergedChannels` to the terminal.
- The tray menu showed "Update failed" with a 404 for the release manifest, which the test instructions say to ignore.
- A Settings tab left open across a gateway restart keeps the old port, because the gateway binds a new port on each start. Reopening Runvil Gateway Settings from the menu loads the new one.
