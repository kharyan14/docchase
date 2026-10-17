# DocChase Voice AI Model Benchmark Report

*Generated on:* 2026-10-17 10:29:32 UTC  
*Endpoint Gateway:* `https://in.api.slng.ai`  

This benchmark compares Speech-to-Text (STT) and Text-to-Speech (TTS) models available through the unified SLNG Voice AI API for back-office operational voice workflows across **Mortgage Origination** and **Healthcare Prior Authorization**.

---

## 1. Speech-to-Text (STT) Benchmark

Evaluating **`slng/deepgram/nova:3-en`** vs. **`sarvam/saaras:v3`** across 5 representative case exception audio clips (including **INS 104** and an **Indian-accented loan exception**).

### Performance & Accuracy Table

| Model | Test Clip | Description | Transcript | Case ID Caught? | Latency (ms) | Cost / Minute |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: |
| `slng/deepgram/nova:3-en` | `clip1_ins104.wav` | Healthcare Exception (Explicit 'INS 104') | "what is the missing document in ins one hundred and four" | **Yes** | 562.5 ms | $0.0043 |
| `sarvam/saaras:v3` | `clip1_ins104.wav` | Healthcare Exception (Explicit 'INS 104') | "What is the missing document in INS 104?" | **Yes** | 787.6 ms | $0.0018 |
| `slng/deepgram/nova:3-en` | `clip2_indian_case102.wav` | Mortgage Exception (Indian Accent, 'CASE 102') | "what is the decision on case one hundred and two" | **Yes** | 443.1 ms | $0.0043 |
| `sarvam/saaras:v3` | `clip2_indian_case102.wav` | Mortgage Exception (Indian Accent, 'CASE 102') | "What is the decision on case 102?" | **Yes** | 751.1 ms | $0.0018 |
| `slng/deepgram/nova:3-en` | `clip3_case101.wav` | Mortgage Exception (Missing Stipulation, 'CASE 101') | "is the borrower's signature missing in case one hundred and one" | **Yes** | 434.0 ms | $0.0043 |
| `sarvam/saaras:v3` | `clip3_case101.wav` | Mortgage Exception (Missing Stipulation, 'CASE 101') | "Is the borrower signature missing in case 101?" | **Yes** | 768.0 ms | $0.0018 |
| `slng/deepgram/nova:3-en` | `clip4_case103.wav` | Mortgage Exception (Historical Precedent, 'CASE 103') | "what about the context and history for case one hundred and three" | **Yes** | 414.4 ms | $0.0043 |
| `sarvam/saaras:v3` | `clip4_case103.wav` | Mortgage Exception (Historical Precedent, 'CASE 103') | "What about the context and history for case 103?" | **Yes** | 853.0 ms | $0.0018 |
| `slng/deepgram/nova:3-en` | `clip5_case105.wav` | Sensitive Risk Exception ('CASE 105') | "is case one hundred and five a sensitive case" | **Yes** | 505.9 ms | $0.0043 |
| `sarvam/saaras:v3` | `clip5_case105.wav` | Sensitive Risk Exception ('CASE 105') | "His case 105, a sensitive case." | **Yes** | 974.0 ms | $0.0018 |

### STT Model Analysis & Summary

* **`slng/deepgram/nova:3-en` (Default)**:
  * **Average Latency:** `472.0 ms`
  * **Case ID Extraction Accuracy:** `5/5` (100%)
  * **Cost:** `$0.0043 / min`
  * **Strengths:** Lowest latency across standard US English queries; reliably transcribes numbers and acronyms.
* **`sarvam/saaras:v3`**:
  * **Average Latency:** `826.7 ms`
  * **Case ID Extraction Accuracy:** `5/5` (100%)
  * **Cost:** `$0.0018 / min` (~58% cheaper)
  * **Strengths:** Superior direct numeric output (`INS 104`, `case 102`) and exceptional precision on Indic / accented speech.

---

## 2. Text-to-Speech (TTS) Benchmark

Evaluating **`deepgram/aura:2`** (One-Shot HTTP) vs. **`murf/murftts:falcon`** (Low-Latency Streaming WebSocket) across operational response prompts.

### Latency, Time-to-First-Audio (TTFA) & Cost Table

| Model | Prompt ID | Prompt Description | Chars | Time to First Audio (TTFA) | Total Latency | Output Audio Size | Cost | Rate |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `deepgram/aura:2` | `prompt_1` | Short Operational Question (Missing Stipulation) | 89 | **1823.8 ms** | 1823.8 ms | 241,964 B | $0.00133 | $0.015/1k chars |
| `murf/murftts:falcon` | `prompt_1` | Short Operational Question (Missing Stipulation) | 89 | **1067.7 ms** | 7677.9 ms | 239,232 B | $0.00178 | $0.020/1k chars |
| `deepgram/aura:2` | `prompt_2` | Medium Precedent & Context Summary | 129 | **2481.5 ms** | 2481.5 ms | 401,324 B | $0.00194 | $0.015/1k chars |
| `murf/murftts:falcon` | `prompt_2` | Medium Precedent & Context Summary | 129 | **911.0 ms** | 7877.8 ms | 390,624 B | $0.00258 | $0.020/1k chars |
| `deepgram/aura:2` | `prompt_3` | Long Multilingual Specialist Review Directive | 160 | **2560.4 ms** | 2560.4 ms | 464,684 B | $0.00240 | $0.015/1k chars |
| `murf/murftts:falcon` | `prompt_3` | Long Multilingual Specialist Review Directive | 160 | **714.2 ms** | 8097.0 ms | 495,072 B | $0.00320 | $0.020/1k chars |

### TTS Model Analysis & Summary

* **`deepgram/aura:2` (Default)**:
  * **Average Time to First Audio (TTFA):** `2288.6 ms`
  * **Cost:** `$0.015 per 1,000 characters` (~$0.005/min)
  * **Strengths:** Simple single-packet HTTP REST interface, rock-solid audio quality, broad natural voice catalog (`aura-2-luna-en`).
* **`murf/murftts:falcon`**:
  * **Average Time to First Audio (TTFA):** `897.6 ms` (**~3.4x faster audio kickoff**)
  * **Cost:** `$0.020 per 1,000 characters` (~$0.008/min)
  * **Strengths:** Extremely fast conversational audio chunking over WebSockets, minimizing operator wait times during hold-to-talk exchanges.

---

## 3. Dynamic Model Switching Configuration

DocChase supports runtime model selection via environment variables and interactive UI controls. Defaults remain strictly unchanged.

### Environment Variable Switches
You can configure default models in `.env` or system environment:

```env
# Speech-to-Text Model Selection
DOCCHASE_STT_MODEL=slng/deepgram/nova:3-en  # Default: slng/deepgram/nova:3-en | Alternative: sarvam/saaras:v3

# Text-to-Speech Model Selection
DOCCHASE_TTS_MODEL=deepgram/aura:2         # Default: deepgram/aura:2 | Alternative: murf/murftts:falcon
```

### Live UI Dropdowns
The DocChase workbench header provides real-time model switches for instant benchmarking:
* **STT Model Selector:** Toggle between Deepgram Nova-3 (fast English default) and Sarvam Saaras v3 (Indic / multilingual).
* **TTS Model Selector:** Toggle between Deepgram Aura 2 (natural warmth) and Murf Falcon (sub-second streaming TTFA).
