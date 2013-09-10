#include <ScreenCapture.au3>

;Get url from commandline and output filename
;Execute shell command Assumes that firefox with Fireshot is installed and configured as default web browser.
;Ctrl-Shift-Alt-Z is the screenshot command and that the default action is to take the entire webpage
$url = $CmdLine[1]
$outname = $CmdLine[2]

ShellExecute($url)

AutoItSetOption("WinTitleMatchMode",2)

;WinActivate($browser)
Sleep(10000) ;loading image
$browser = WinGetHandle("[CLASS:MozillaWindowClass]")
WinActivate($browser)
WinActivate($browser)

Send("{ALTDOWN}{CTRLDOWN}+z") ;Save screenshot command
Send("{ALTUP}{CTRLUP}")
Sleep(15000)  ;Wait to render

;Change dialog box save location
$savebox = WinGetHandle("Save Screenshot...")
WinActivate($savebox)
Sleep(1000) ;Wait for savebox to appear
Send("!n")
Send($outname)
Send("!s")

Sleep(2000) ;Wait for save as box

if WinExists("Confirm Save As") Then
	$saveprompt = WinGetHandle("Confirm Save As")
	WinActivate($saveprompt)
	Send("!y")
EndIf

;Sleep(10000) ;Wait for save to complete

;Sleep(1000)
;WinClose($browser)
