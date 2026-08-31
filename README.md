# AI-Termux-Use-Local-LiteRtLM-model-for-web-search
<br><br>
<img width="677" height="369" alt="1000078704" src="https://github.com/user-attachments/assets/05e1d10c-53c1-4e46-a61a-90d86c86d2cc" />
<br><br>
Local AI Web Search
Empower your local AI model with real-time web search capabilities in Termux (Android) and Linux environments. The script is compatible with "LiteRtLm" models and "gguf" models. To choose either modify "default.txt":
 * 1 = "LiteRtLm"
 * 2 = "gguf" <br>
Prerequisites
Before installing, ensure you have the following packages installed on your system:
 * python3
 * litertlm
 * ollama

# Installation & Setup
 * Configure the Model Path:
   Open the ask.py file in a text editor and modify at the top of the file the paths that point to your locally stored litertlm model and/or ollama model name.
 * Update Script Reference:
   Update the internal path pointing to ask.py inside the ask file.
 * Move Files to Bin:
   Place both the ask and ask.py files into your system's bin directory:
   * Android (Termux): /data/data/com.termux/files/usr/bin/
   * Linux: /usr/bin/

# Grant Permissions:
   Make the files executable by running the appropriate command for your environment:

# Android / Termux
chmod +x /data/data/com.termux/files/usr/bin/ask<br>
chmod +x /data/data/com.termux/files/usr/bin/ask.py

# Linux
chmod +x /usr/bin/ask<br>
chmod +x /usr/bin/ask.py

# Usage
To ask your local AI a question with web search enabled, use the following command structure:
ask your question, search the web

> Note: Quotation marks are not required around your question. You must include the exact suffix <i>, search the web</i> at the end of your input to trigger the feature.
> 

<img width="720" height="1604" alt="1000078692" src="https://github.com/user-attachments/assets/9c361c60-3d0e-4507-baad-ac8b76f4a7d4" />
<img width="720" height="1604" alt="1000078693" src="https://github.com/user-attachments/assets/e5f9bb5a-f0e5-40cb-b3f2-3aad24d83ff6" />
