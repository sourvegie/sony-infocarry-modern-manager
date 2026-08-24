// InfoCarry experiment timestamp helper for Windows Script Host/JScript 5.x.
// Double-click this file once per requested event.  It performs no USB, network,
// Manager, or SnoopyPro access.

var TOOL_VERSION = "1.0.0";
var FORMAT = "infocarry-experiment-timestamp-v1";
var fso = null;
var shell = null;
var openFile = null;
var outputPath = "";

function pad(value, width) {
    var text = String(value);
    while (text.length < width) {
        text = "0" + text;
    }
    return text;
}

function localOffsetMinutes(date) {
    return -date.getTimezoneOffset();
}

function offsetText(minutes) {
    var sign = minutes < 0 ? "-" : "+";
    var absolute = Math.abs(minutes);
    return sign + pad(Math.floor(absolute / 60), 2) + ":" + pad(absolute % 60, 2);
}

function localTimestamp(date, offsetMinutes) {
    return date.getFullYear() + "-" +
        pad(date.getMonth() + 1, 2) + "-" +
        pad(date.getDate(), 2) + "T" +
        pad(date.getHours(), 2) + ":" +
        pad(date.getMinutes(), 2) + ":" +
        pad(date.getSeconds(), 2) + "." +
        pad(date.getMilliseconds(), 3) + offsetText(offsetMinutes);
}

function utcTimestamp(date) {
    return date.getUTCFullYear() + "-" +
        pad(date.getUTCMonth() + 1, 2) + "-" +
        pad(date.getUTCDate(), 2) + "T" +
        pad(date.getUTCHours(), 2) + ":" +
        pad(date.getUTCMinutes(), 2) + ":" +
        pad(date.getUTCSeconds(), 2) + "." +
        pad(date.getUTCMilliseconds(), 3) + "Z";
}

function nextUnusedSequence(folder) {
    var used = {};
    var pattern = /^stamp-(\d{4,})\.txt$/i;
    var files = new Enumerator(folder.Files);
    for (; !files.atEnd(); files.moveNext()) {
        var file = files.item();
        var match = pattern.exec(file.Name);
        if (match !== null) {
            used[parseInt(match[1], 10)] = true;
        }
    }

    var sequence = 1;
    while (used[sequence]) {
        sequence += 1;
    }
    return sequence;
}

function safeComputerName() {
    var value = "";
    try {
        value = shell.ExpandEnvironmentStrings("%COMPUTERNAME%");
        if (value === "%COMPUTERNAME%") {
            value = "";
        }
    } catch (ignored) {
        value = "";
    }
    if (!/^[A-Za-z0-9_.-]+$/.test(value)) {
        return "";
    }
    return value;
}

function fail(message) {
    try {
        if (openFile !== null) {
            openFile.Close();
            openFile = null;
        }
    } catch (ignored) {
    }
    try {
        shell.Popup("Timestamp was not saved.\r\n\r\n" + message,
            0, "InfoCarry timestamp error", 16);
    } catch (ignoredPopup) {
        WScript.Echo("Timestamp was not saved: " + message);
    }
}

try {
    fso = new ActiveXObject("Scripting.FileSystemObject");
    shell = new ActiveXObject("WScript.Shell");

    var scriptDirectory = fso.GetParentFolderName(WScript.ScriptFullName);
    var logsDirectory = fso.BuildPath(scriptDirectory, "logs");
    if (!fso.FolderExists(logsDirectory)) {
        fso.CreateFolder(logsDirectory);
    }

    var logsFolder = fso.GetFolder(logsDirectory);
    var sequence = nextUnusedSequence(logsFolder);
    var sequenceText = pad(sequence, 4);
    outputPath = fso.BuildPath(logsDirectory, "stamp-" + sequenceText + ".txt");

    // Capture one Date object so every representation describes one instant.
    var instant = new Date();
    var offsetMinutes = localOffsetMinutes(instant);
    var epochMilliseconds = instant.getTime();
    var lines = [
        "format=" + FORMAT,
        "sequence=" + sequenceText,
        "local_timestamp=" + localTimestamp(instant, offsetMinutes),
        "utc_timestamp=" + utcTimestamp(instant),
        "epoch_ms=" + epochMilliseconds,
        "timezone_offset_minutes=" + offsetMinutes,
        "computer_name=" + safeComputerName(),
        "tool_version=" + TOOL_VERSION
    ];

    // overwrite=false is the WSH exclusive-create behavior.  A collision is
    // an error; this tool never replaces an existing numbered file.
    openFile = fso.CreateTextFile(outputPath, false, false);
    openFile.Write(lines.join("\r\n") + "\r\n");
    openFile.Close();
    openFile = null;

    shell.Popup("Timestamp " + sequenceText + " saved\r\n\r\n" + outputPath,
        0, "InfoCarry timestamp", 64);
} catch (error) {
    fail(error.description ? error.description : String(error));
}
