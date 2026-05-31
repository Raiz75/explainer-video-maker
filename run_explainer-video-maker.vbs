Set WshShell = CreateObject("WScript.Shell")
WshShell.Run "pythonw.exe """ & WScript.ScriptFullName & """\..\explainer-video-maker.py""", 0, False
