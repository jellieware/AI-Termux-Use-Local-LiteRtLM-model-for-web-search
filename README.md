# AI-Termux-Use-Local-LiteRtLM-model-for-web-search
<br><br>
Open "ask.py" file with text editor and simply replace the line where you store your litertlm model locally (line 928).
Change "ask.py" file location inside "ask" file
<br><br>
After editing, place "ask" and "ask.py" files in "bin" directory:
<br><br>
Android: /data/data/com.termux/files/usr/bin/
Linux: /usr/bin/
<br><br>
chmod +x /data/data/com.termux/files/usr/bin/ask
<br>
chmod +x /data/data/com.termux/files/usr/bin/ask.py
<br><br>
To ask a question simply type:
<br><br>
ask "question goes here"
<br><br>
You need to have litertlm and python3 installed in termux first! This script also works in Linux
<br><br>
<img width="720" height="1604" alt="1000078679" src="https://github.com/user-attachments/assets/4f9200ef-63a0-484c-94bd-80a002527fe0" />
