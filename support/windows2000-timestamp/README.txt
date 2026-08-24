InfoCarry experiment timestamp tool
====================================

1. Copy this complete folder to Windows 2000.
2. Confirm the Windows date, time, and timezone manually before the session.
3. Double-click CaptureTimestamp.js only when the guiding agent requests it.
4. Wait for the success popup.
5. Report the saved sequence number.
6. Never edit or rename files under the logs folder.
7. Preserve the complete logs folder after the session.

Each successful double-click creates one new file under logs named
stamp-0001.txt, stamp-0002.txt, and so on. Existing files are never replaced.
The files contain local/UTC timestamps, epoch milliseconds, timezone offset,
computer name when available, and the tool version. Their sequence numbers
are raw identities; event meanings belong in a separate session mapping.

This tool requires only Windows Script Host/JScript. It does not require
installation, Python, PowerShell, a network connection, USB access, InfoCarry
Manager, or SnoopyPro. Do not run it while changing USB ownership or while
any device application is active; it is intended for harmless clock
observations only.
