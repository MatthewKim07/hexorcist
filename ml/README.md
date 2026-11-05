# Guard classifier

A trained classifier behind `screen_request` in [`backend/app/guard.py`](../backend/app/guard.py). It adds to the regex rules and never replaces them. The sandbox does not rely on either: an upload the guard misses still only runs in a locked-down container.

**Shipped: TF-IDF + logistic regression.** It catches about 4 times as many attacks in new styles as regex alone, adds 2.2 ms, and is a 398 KiB JSON file with no new dependencies.

## Results

Test set: 1092 documents, 652 attacks and 440 benign. The threshold is set on validation for a 1% false positive rate, and is not tuned on test.

| Model | Precision | Recall | F1 | FPR | Recall, new styles | TP | FP | FN | TN |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Regex rules only | 0.904 | 0.130 | 0.228 | 2.0% | 10.0% | 85 | 9 | 567 | 431 |
| TF-IDF + logistic regression | 0.980 | 0.449 | 0.616 | 1.4% | 34.6% | 293 | 6 | 359 | 434 |
| **Regex + TF-IDF (shipped)** | **0.955** | **0.489** | **0.647** | **3.4%** | **39.4%** | **319** | **15** | **333** | **425** |
| MiniLM-L6 fine-tuned | 0.937 | 0.709 | 0.807 | 7.0% | 65.0% | 462 | 31 | 190 | 409 |
| Regex + MiniLM | 0.929 | 0.727 | 0.816 | 8.2% | 67.2% | 474 | 36 | 178 | 404 |

"New styles" leaves out `public_injection`, which is unseen text in a style the model trained on.

| | TF-IDF + logistic regression | MiniLM-L6 |
| --- | --- | --- |
| Recall at 1% FPR, read from test's own curve | 37.4% | 46.0% |
| Recall at 0.1% FPR, same | 33.0% | 33.9% |
| Latency per upload, p50, one core | 2.2 ms | 214 ms |
| Latency per upload, p95 | 3.3 ms | 385 ms |
| Latency, largest allowed upload (937 chunks) | 51 ms | 3477 ms |
| Model size | 0.39 MB | 88 MB |
| Runtime added to the backend | None | torch and transformers, 358 MB here on macOS |
| Training on CPU | 178 s, including choosing C | 360 s |

Latencies were measured on an idle Apple Silicon Mac, so a VM core may differ.

### Recall per attack style, at the shipped threshold

| Style | n | Regex | TF-IDF | Regex + TF-IDF | MiniLM |
| --- | --- | --- | --- | --- | --- |
| `public_injection`: unseen samples of a seen style | 112 | 0.28 | 0.95 | 0.95 | 0.99 |
| `llm_takeover`: written by another author | 30 | 0.17 | 0.80 | 0.80 | 0.93 |
| `llm_exfiltrate` | 30 | 0.13 | 0.60 | 0.60 | 0.87 |
| `indirect_include`: macros and unseen host paths | 70 | 0.56 | 0.24 | 0.56 | 0.66 |
| `obfuscated`: leetspeak, base64, homoglyphs and others | 70 | 0.00 | 0.44 | 0.44 | 0.67 |
| `disguised`: no trigger words | 70 | 0.00 | 0.39 | 0.39 | 0.67 |
| `foreign`: seven other languages | 70 | 0.00 | 0.37 | 0.37 | 0.77 |
| `fake_markup`: spoofed chat roles and tool output | 70 | 0.07 | 0.26 | 0.30 | 0.56 |
| `patch_exfil`: asks the patch to carry secrets | 70 | 0.00 | 0.29 | 0.29 | 0.67 |
| `llm_verdict`: asks for a passing report | 30 | 0.03 | 0.17 | 0.20 | 0.37 |
| `llm_poison`: asks for a hidden backdoor | 30 | 0.00 | 0.03 | 0.03 | 0.20 |

### False positives by kind of benign text

| Text | n | Regex | TF-IDF | Regex + TF-IDF | MiniLM share flagged |
| --- | --- | --- | --- | --- | --- |
| Real Arduino library examples | 86 | 0 | 0 | 0 | 17% |
| Whole projects written by the LLM | 70 | 0 | 1 | 1 | 1% |
| Harmless uses of attack words, LLM-written | 249 | 2 | 5 | 7 | 2% |
| Harmless uses of attack words, handwritten to be hard | 35 | 7 | 0 | 7 | 26% |

Seven of the shipped false positives are the regex rules on sentences written to trip them, such as "You are now in setup mode when D4 is held at boot".

## Why the baseline ships

MiniLM ranks attacks better. It could also run on the VM, so size is not the reason. The reasons are:

1. **A blocking gate needs its threshold to hold on code it has not seen.** A flagged upload goes to the containment demo and never gets tested, so false positives are costly. At its validation threshold, MiniLM flagged 7.0% of benign test documents, and 17% of real library sketches, against a 1% target. The baseline came in at 1.4%, with no real library sketch flagged.
2. **Near the operating point the gap is small.** At 0.1% FPR the two models are level. At 1% FPR MiniLM leads by 9 points.
3. **Latency and attack surface.** It is 100 times slower per upload and takes 3.5 s of CPU on the largest upload. It would also add a deep learning runtime to the one process holding the Docker socket and the LLM key. The baseline is read from plain JSON with no pickle, using only the standard library.

If the threshold could be made to hold, MiniLM would be the better model. It catches far more of the disguised, foreign and obfuscated styles, so it is the obvious next step, perhaps in its own process.

## How much to trust these numbers

- **The test set was looked at twice.** The first look showed the baseline at 10.0% FPR, flagging 37% of real library sketches, because training had too little real human code. Regex + TF-IDF scored P 0.884, R 0.618, FPR 12.0% then. I added real sketches from other repositories to train and validation, and retrained both models. A checksum confirms test did not change, and no held-out attack was used to make that fix. Still, these are not pristine first-look numbers.
- **Precision depends on the attack share.** 60% of this test set is attacks. If 1 upload in 100 were hostile, the shipped guard's 3.4% FPR and 48.9% recall would give a precision of about 13%. FPR is the number to watch.
- **Most attacks are synthetic.** I wrote the training styles and the held-out styles, so they share an author's habits. The `llm_*` styles were written by DeepSeek as a partial check on that, but from prompts I wrote.
- **The threshold is sensitive.** Small data changes moved it between 0.90 and 0.98, because a few validation documents decide it. Each model's FPR also moved a lot between the two looks: MiniLM went from 2.0% to 7.0%. One test run does not prove the baseline's 1.4% is stable.
- **It misses a lot.** The guard catches under half of the attacks, and almost no request for a hidden backdoor, which reads like an ordinary requirement. This is why it is defense in depth and the sandbox is the real boundary.

## How it works

Each upload is cut into overlapping chunks: 3 lines of code at a time, and pairs of spec sentences. The worst chunk decides, so one injected line cannot be diluted by a long sketch. Text is normalized first with NFKC, invisible characters removed, and Latin look-alike letters folded.

Features are words, word pairs and 3 to 5 character n-grams, with sublinear TF-IDF. The 15000 strongest features are kept and the model refit on only those. Training checks that the exported pure-Python inference matches scikit-learn: the worst difference was 0.000001.

The hard rules still run, and a low classifier score can never clear them. With no model file, the guard falls back to the rules alone.

## The data

| Split | Documents | Attacks | Benign |
| --- | --- | --- | --- |
| Train | 3236 | 1880 | 1356 |
| Validation | 729 | 291 | 438 |
| Test | 1092 | 652 | 440 |

Every attack sits inside a realistic benign sketch from the same split, so the model cannot pass by learning that Arduino code is benign.

| Source | Used for | License |
| --- | --- | --- |
| [deepset/prompt-injections](https://huggingface.co/datasets/deepset/prompt-injections) | Train | Apache-2.0 |
| [Lakera/gandalf_ignore_instructions](https://huggingface.co/datasets/Lakera/gandalf_ignore_instructions) | Train, validation, test as `public_injection` | MIT |
| [arduino/arduino-examples](https://github.com/arduino/arduino-examples) | Train, validation | CC0-1.0 |
| ArduinoJson, FastLED, Adafruit MQTT, WiFiManager | Train | MIT |
| PubSubClient, Adafruit DHT, Bounce2, MFRC522 | Validation | MIT, Unlicense |
| ArduinoCore-avr and arduino-libraries examples | Test only, never redistributed | LGPL or similar |
| `corpus/`: projects and harmless attack-word lines written by DeepSeek, real runs | All splits, real runs in validation only | This repo |
| Templates in `families.py` | Attack styles and hard negatives | This repo |

Test uses devices, carrier sketches and attack styles that training never saw, apart from `public_injection`.

## Retrain

Downloads and models stay out of git, in `ml/.cache`, `ml/dataset`, `ml/artifacts` and `ml/.venv`. The committed model is `backend/app/guard_model.json`.

```bash
cd ml
uv venv --python 3.12 .venv && uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python fetch_sources.py     # about 240 MB of public data
.venv/bin/python build_dataset.py     # reproducible from the seed
.venv/bin/python train_baseline.py    # about 3 minutes, rewrites backend/app/guard_model.json

# Optional comparison: about 360 MB more, plus an 88 MB model
uv pip install --python .venv/bin/python -r requirements-transformer.txt
.venv/bin/python train_transformer.py # about 10 minutes on CPU
.venv/bin/python evaluate.py          # prints the tables above, writes results.json

cd ../backend && .venv/bin/python -m pytest tests -q   # the presets must stay on the right side
```

`generate_corpus.py` and `export_real_runs.py` rebuild `corpus/`, but that needs an LLM key or a running stack, so the results are committed. Delete `.venv`, `.cache`, `dataset` and `artifacts` when you are done.
